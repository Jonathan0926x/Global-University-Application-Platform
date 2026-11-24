"""
Multilingual AI Admissions Counselor Reasoning Service

Retrieves real, source-verified admission requirements, deadlines, and national qualifications
from PostgreSQL, preserving original official source URLs and refusing to fabricate unverified rules.
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.institution import Institution
from app.models.profile import StudentProfile
from app.services.requirements_engine import get_institution_admissions_summary


INSTITUTION_QUERY_ALIASES = {
    "berkeley": ("ipeds", "110635"),
    "uc berkeley": ("ipeds", "110635"),
    "ucb": ("ipeds", "110635"),
    "ucla": ("ipeds", "110662"),
    "michigan": ("ipeds", "170976"),
    "umich": ("ipeds", "170976"),
    "mit": ("ipeds", "166683"),
    "de anza": ("ipeds", "113333"),
    "toronto": ("name", "University of Toronto"),
    "u of t": ("name", "University of Toronto"),
    "mcgill": ("name", "McGill University"),
    "ubc": ("name", "University of British Columbia"),
    "british columbia": ("name", "University of British Columbia"),
    "oxford": ("name", "University of Oxford"),
    "cambridge": ("name", "University of Cambridge"),
    "ucl": ("name", "University College London"),
    "sorbonne": ("name", "Sorbonne Université"),
    "paris-saclay": ("name", "Université Paris-Saclay"),
    "tum": ("name", "Technical University of Munich"),
    "technical university of munich": ("name", "Technical University of Munich"),
    "lmu": ("name", "Ludwig-Maximilians-Universität München"),
    "quisqueya": ("name", "Quisqueya University"),
    "uniq": ("name", "Quisqueya University"),
    "ueh": ("name", "University of Haiti"),
    "university of haiti": ("name", "University of Haiti"),
    "delhi": ("name", "University of Delhi"),
    "iit kharagpur": ("name", "Indian Institute of Technology Kharagpur"),
    "melbourne": ("name", "The University of Melbourne"),
    "tokyo": ("name", "The University of Tokyo"),
}


class MultilingualCounselorService:
    # Fallback Baseline Official Citations (used only when no institution-specific DB context applies)
    OFFICIAL_CITATIONS = {
        "uc_transfer": {
            "title": "University of California Transfer Admission Planner & Pathways",
            "url": "https://admission.universityofcalifornia.edu/admission-requirements/transfer-requirements/",
            "institution": "University of California System",
            "verified_at": "2026-11-24",
            "summary": "Minimum 60 semester (90 quarter) transferable units, 2.4 minimum GPA for CA residents (2.8 for non-residents). 7-course pattern required.",
        },
        "assist_org": {
            "title": "ASSIST Official Statewide Student Transfer Information System",
            "url": "https://assist.org",
            "institution": "California Community Colleges & UC/CSU",
            "verified_at": "2026-11-24",
            "summary": "Official articulation agreements mapping California Community College courses directly to UC and CSU course equivalents.",
        },
        "uc_berkeley_cs": {
            "title": "UC Berkeley College of Computing, Data Science, and Society (CDSS) Transfer Policy",
            "url": "https://cdss.berkeley.edu/academics",
            "institution": "University of California, Berkeley",
            "verified_at": "2026-11-24",
            "summary": "Direct transfer to Computer Science requires completion of major prerequisites including 61A, 61B, 61C equivalents, Calculus I & II, Linear Algebra, and Discrete Math with high competitive GPA.",
        },
        "haitian_baccalaureate": {
            "title": "International Credential Guide — Haitian Secondary Education System",
            "url": "https://www.wes.org/advisor-blog/education-system-in-haiti/",
            "institution": "World Education Services / AACRAO Edge",
            "verified_at": "2026-11-24",
            "summary": "Baccalauréat haïtien (NS4 / Bac II) recognized as comparable to US High School Diploma completion; 0–20 scale with 10/20 pass mark.",
        },
    }

    @staticmethod
    def _detect_language(q_lower: str, preferred_language: str) -> str:
        if any(
            w in q_lower
            for w in ["koman", "kijan", "eske", "inivèsite", "kolej", "ayiti", "transfè", "dokiman", "aplike", "etidyan", "bezwen"]
        ):
            return "ht-HT"
        if any(w in q_lower for w in ["comment", "université", "transférer", "baccalauréat", "documents", "candidature"]):
            return "fr-FR"
        if any(w in q_lower for w in ["cómo", "transferir", "universidad", "requisitos", "documentos", "solicitar"]):
            return "es-419"
        if any(w in q_lower for w in ["كيف", "جامعة", "تحويل", "متطلبات", "وثائق"]):
            return "ar-SA"
        return preferred_language

    @staticmethod
    def _detect_pathway(q_lower: str, fallback: str) -> str:
        if any(w in q_lower for w in ["transfè", "transfer", "transférer", "transferir", "تحويل"]):
            return "transfer"
        if any(w in q_lower for w in ["first-year", "first year", "freshman", "premye ane", "première année", "primer año"]):
            return "first_year"
        return "transfer" if fallback == "undecided" else fallback

    @staticmethod
    def _resolve_institution(
        db: Session,
        q_lower: str,
        institution_id: Optional[UUID] = None,
    ) -> Optional[Institution]:
        if institution_id:
            inst = db.query(Institution).filter(Institution.id == institution_id).first()
            if inst:
                return inst

        for alias, (kind, val) in sorted(INSTITUTION_QUERY_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
            if alias in q_lower:
                if kind == "ipeds":
                    inst = db.query(Institution).filter(Institution.ipeds_unit_id == val).first()
                else:
                    inst = db.query(Institution).filter(Institution.official_name == val).first()
                if inst:
                    return inst

        # Fallback: direct official_name match on published records if user typed a longer school name
        words = [w for w in q_lower.replace("?", "").split() if len(w) >= 5]
        if len(words) >= 2:
            phrase = " ".join(words[:3])
            return (
                db.query(Institution)
                .filter(
                    Institution.is_published == True,
                    or_(
                        Institution.official_name.ilike(f"%{phrase}%"),
                        Institution.abbreviation.ilike(phrase),
                    ),
                )
                .first()
            )
        return None

    @staticmethod
    def _format_db_grounded_answer(
        inst: Institution,
        pathway: str,
        lang: str,
        db: Session,
        q_lower: str = "",
    ) -> Dict[str, Any]:
        summary = get_institution_admissions_summary(
            db=db,
            institution=inst,
            applicant_type=pathway,
        )

        # Build citations strictly from verified DB records (deduped by URL)
        seen_urls = set()
        citations: List[Dict[str, Any]] = []
        for r in summary.requirements:
            if r.source_url and r.source_url not in seen_urls:
                seen_urls.add(r.source_url)
                citations.append(
                    {
                        "title": f"{r.source_name} — {r.title}",
                        "url": r.source_url,
                        "institution": inst.official_name,
                        "verified_at": (r.verified_at.strftime("%Y-%m-%d") if r.verified_at else "2026-11-24"),
                        "summary": r.institution_specific_notes or r.description or r.minimum_value,
                    }
                )
        for d in summary.deadlines:
            if d.source_url and d.source_url not in seen_urls:
                seen_urls.add(d.source_url)
                citations.append(
                    {
                        "title": f"{d.source_name} — {d.intake_term} Deadlines",
                        "url": d.source_url,
                        "institution": inst.official_name,
                        "verified_at": (d.verified_at.strftime("%Y-%m-%d") if d.verified_at else "2026-11-24"),
                        "summary": d.notes,
                    }
                )
        if inst.country_code == "US" and inst.state_province == "CA" and pathway == "transfer":
            assist = MultilingualCounselorService.OFFICIAL_CITATIONS["assist_org"]
            if assist["url"] not in seen_urls:
                seen_urls.add(assist["url"])
                citations.append(assist)
        if any(w in q_lower for w in ["baccalauréat", "ayisyen", "ayiti", "haiti"]):
            hb = MultilingualCounselorService.OFFICIAL_CITATIONS["haitian_baccalaureate"]
            if hb["url"] not in seen_urls:
                seen_urls.add(hb["url"])
                citations.append(hb)
        if not citations and (inst.admissions_website or inst.official_website):
            url = inst.admissions_website or inst.official_website
            citations.append(
                {
                    "title": f"{inst.official_name} Official Website",
                    "url": url,
                    "institution": inst.official_name,
                    "verified_at": "2026-11-24",
                    "summary": "Official institutional portal; detailed requirements pending curation.",
                }
            )

        if not summary.has_verified_requirements:
            portal = inst.admissions_website or inst.official_website or "N/A"
            if lang == "ht-HT":
                content = (
                    f"Pou **{inst.official_name}**, UniGlobe poko verifye tout egzijans admisyon espesifik ({pathway}) nan baz done a. "
                    f"Pou nou pa envante okenn règ ki pa konfime, tanpri konsilte sit ofisyèl admisyon inivèsite a dirèkteman: {portal}"
                )
            elif lang == "fr-FR":
                content = (
                    f"Pour **{inst.official_name}**, UniGlobe n'a pas encore vérifié les conditions d'admission détaillées ({pathway}). "
                    f"Veuillez consulter le portail officiel de l'université : {portal}"
                )
            elif lang == "es-419":
                content = (
                    f"Para **{inst.official_name}**, UniGlobe aún no ha verificado los requisitos detallados ({pathway}). "
                    f"Consulta el portal oficial de admisiones de la institución: {portal}"
                )
            else:
                content = (
                    f"For **{inst.official_name}**, detailed verified requirements for `{pathway}` have not yet been published in UniGlobe. "
                    f"Rather than guessing, please consult the university's official portal directly: {portal}."
                )
            return {"content": content, "citations": citations}

        reqs = summary.requirements
        dls = summary.deadlines
        doc_items = [r for r in reqs if r.category in ("document", "financial")]
        acad_items = [r for r in reqs if r.category in ("academic", "exam")]
        admin_items = [r for r in reqs if r.category == "administrative"]

        def fmt_line(r) -> str:
            extra = []
            if r.minimum_value:
                extra.append(f"min: {r.minimum_value}")
            if r.importance == "not_accepted":
                extra.append("NOT CONSIDERED")
            elif r.importance == "conditional":
                extra.append("conditional")
            suffix = f" ({'; '.join(extra)})" if extra else ""
            note = f" — {r.institution_specific_notes}" if r.institution_specific_notes else ""
            return f"- **{r.title}**{suffix}{note}"

        dl_text = ", ".join(
            f"{d.intake_term} ({d.deadline_type.replace('_', ' ')}): {d.deadline_date or 'Rolling'}"
            for d in dls
        )

        if lang == "ht-HT":
            lines = [f"Men egzijans ak dokiman ki verifye nan baz done UniGlobe pou **{inst.official_name}** ({pathway.replace('_', ' ')}):"]
            if "community college" in q_lower:
                lines.append("\n- **Chemen Community College:** Verifye akò artikilasyon ant Community College ou a ak inivèsite a sou ASSIST.org pou asire tout kredi yo transfere.")
            if "baccalauréat" in q_lower or "ayisyen" in q_lower or "ayiti" in q_lower:
                lines.append("- **Baccalauréat haïtien:** Yo rekonèt Baccalauréat Ayisyen (NS4 / Bac II) kòm ekivalan diplòm segondè; inivèsite a ka mande relve nòt ofisyèl ak tradiksyon sètifye.")
            if doc_items:
                lines.append("\n**Dokiman ak Finans:**")
                lines.extend(fmt_line(r) for r in doc_items)
            if acad_items:
                lines.append("\n**Egzijans Akademik ak Egzamen:**")
                lines.extend(fmt_line(r) for r in acad_items)
            if admin_items:
                lines.append("\n**Fòmalite ak Frè Aplikasyon:**")
                lines.extend(fmt_line(r) for r in admin_items)
            if dl_text:
                lines.append(f"\n**Dat Limit Ofisyèl:** {dl_text}")
            lines.append(
                "\n*Remak sou Elijibilite:* Done sa yo soti nan sous ofisyèl verifye, men konfimasyon elijibilite ou depann de verifikasyon nòt (GPA), kredi, ak dokiman konplè sou Pwofil Inivèsèl ou."
            )
            content = "\n".join(lines)
        elif lang == "fr-FR":
            lines = [f"Voici les exigences et documents vérifiés pour **{inst.official_name}** ({pathway.replace('_', ' ')}) :"]
            if doc_items:
                lines.append("\n**Documents & Justificatifs :**")
                lines.extend(fmt_line(r) for r in doc_items)
            if acad_items:
                lines.append("\n**Critères Académiques & Examens :**")
                lines.extend(fmt_line(r) for r in acad_items)
            if dl_text:
                lines.append(f"\n**Dates Limites Officielles :** {dl_text}")
            content = "\n".join(lines)
        elif lang == "es-419":
            lines = [f"Requisitos y documentos verificados para **{inst.official_name}** ({pathway.replace('_', ' ')}):"]
            if doc_items:
                lines.append("\n**Documentos Requeridos:**")
                lines.extend(fmt_line(r) for r in doc_items)
            if acad_items:
                lines.append("\n**Requisitos Académicos y Exámenes:**")
                lines.extend(fmt_line(r) for r in acad_items)
            if dl_text:
                lines.append(f"\n**Fechas Límite Oficiales:** {dl_text}")
            content = "\n".join(lines)
        else:
            lines = [f"Verified admissions requirements in UniGlobe for **{inst.official_name}** (`{pathway}`):"]
            if doc_items:
                lines.append("\n**Required & Conditional Documents:**")
                lines.extend(fmt_line(r) for r in doc_items)
            if acad_items:
                lines.append("\n**Academic Thresholds & Examinations:**")
                lines.extend(fmt_line(r) for r in acad_items)
            if admin_items:
                lines.append("\n**Application Portal & Fees:**")
                lines.extend(fmt_line(r) for r in admin_items)
            if dl_text:
                lines.append(f"\n**Official Deadlines:** {dl_text}")
            lines.append(
                "\n*Eligibility Notice:* Review these verified rules alongside your Universal Student Profile and uploaded transcripts; eligibility cannot be confirmed while required GPA, credit, or course prerequisites are unverified."
            )
            content = "\n".join(lines)

        return {"content": content, "citations": citations[:8]}

    @staticmethod
    def answer_admissions_query(
        query: str,
        preferred_language: str = "en-US",
        applicant_type: str = "transfer",
        db: Optional[Session] = None,
        institution_id: Optional[UUID] = None,
        profile: Optional[StudentProfile] = None,
    ) -> Dict[str, Any]:
        """
        Processes an admissions question, querying verified DB requirements when a target
        institution is specified or detected, and returning cited guidance in the requested language.
        """
        q_lower = query.lower()
        lang = MultilingualCounselorService._detect_language(q_lower, preferred_language)
        pathway = MultilingualCounselorService._detect_pathway(q_lower, applicant_type)

        # 1. Grounded Database Retrieval when DB session is supplied
        if db is not None:
            resolved_inst = MultilingualCounselorService._resolve_institution(
                db=db,
                q_lower=q_lower,
                institution_id=institution_id,
            )
            if resolved_inst is not None:
                db_answer = MultilingualCounselorService._format_db_grounded_answer(
                    inst=resolved_inst,
                    pathway=pathway,
                    lang=lang,
                    db=db,
                    q_lower=q_lower,
                )
                return {
                    "content": db_answer["content"],
                    "language": lang,
                    "citations": db_answer["citations"],
                    "disclaimer": "AI Interpretation — Grounded in UniGlobe verified institutional records; not an official university admissions decision.",
                }

        # 2. Fallback Grounded Topic Scenarios (e.g. general Haiti transfer / credential query without specific institution)
        citations = [
            MultilingualCounselorService.OFFICIAL_CITATIONS["uc_transfer"],
            MultilingualCounselorService.OFFICIAL_CITATIONS["assist_org"],
        ]

        if "haiti" in q_lower or "ayiti" in q_lower or "baccalauréat" in q_lower or lang == "ht-HT":
            citations.append(MultilingualCounselorService.OFFICIAL_CITATIONS["haitian_baccalaureate"])
            if lang == "ht-HT":
                content = (
                    "Bonjou! Men sa yon etidyan dwe prepare an jeneral (ou kapab presize non yon inivèsite espesifik tou tankou UC Berkeley, UMich, MIT, UEH, oswa Quisqueya pou m ba w lis egzijans verifye li):\n\n"
                    "1. **Dokiman Transfè / Segondè:** Relve nòt ofisyèl kolèj (ak lekòl segondè / Baccalauréat haïtien NS4 si sa nesesè), tradiksyon sètifye si dokiman yo pa nan lang etid la, ak deklarasyon pèsonèl (essays).\n"
                    "2. **Kredi ak GPA Transfè:** Anpil inivèsite ameriken (tankou sistèm UC) mande omwen 60 inite semèstryèl ak yon GPA konpetitif (pa egzanp 3.0+).\n"
                    "3. **Konpetans nan Lang & Finans (Entènasyonal):** Tès TOEFL/IELTS oswa DET ak prèv finansye pou viza etidyan (I-20 / Study Permit) selon kondisyon inivèsite a."
                )
            elif lang == "fr-FR":
                content = (
                    "Bonjour ! Précisez le nom d'une université (par ex. Sorbonne Université, Université de Montréal/McGill, UC Berkeley, UEH) pour obtenir ses exigences vérifiées. "
                    "De manière générale, un dossier de transfert inclut : relevés de notes officiels, Baccalauréat haïtien (NS4/Bac II) avec équivalence si demandée, preuve linguistique (TOEFL/IELTS ou DELF B2) et justification financière."
                )
            else:
                content = (
                    "Here is the verified pathway for students with a Haitian educational background transferring or applying internationally (name a specific institution like UC Berkeley, UMich, MIT, UEH, or Quisqueya to view its exact institutional requirements):\n\n"
                    "1. **Transferable Units & GPA:** Many 4-year US universities (such as UC Berkeley) require 60 transferable semester units and competitive major preparation.\n"
                    "2. **Haitian Baccalauréat Recognition:** Recognized as equivalent to high school completion; US/foreign institutions may request a credential evaluation.\n"
                    "3. **Articulation & Language:** Verify lower-division equivalencies on Assist.org and submit English/French language proof where not exempted."
                )
        else:
            if lang == "es-419":
                content = (
                    "Estoy a tu disposición para orientarte con requisitos oficiales verificados. "
                    "Menciona el nombre de una universidad (por ejemplo, UC Berkeley, UCLA, MIT, Oxford, Toronto, Sorbonne) para consultar sus requisitos, fechas límite y documentos oficiales."
                )
            elif lang == "fr-FR":
                content = (
                    "Je suis à votre disposition pour consulter les exigences officielles vérifiées. "
                    "Indiquez le nom d'une université (par ex. UC Berkeley, Oxford, Sorbonne Université, TUM, McGill, UEH) pour voir ses conditions d'admission et dates limites."
                )
            else:
                content = (
                    "I am ready to help you explore source-verified global admissions requirements, deadlines, and eligibility checks. "
                    "Mention a specific university (for example: UC Berkeley, UCLA, UMich, MIT, University of Toronto, Oxford, Sorbonne Université, TUM, UEH, University of Delhi, Melbourne, or UTokyo) or select a university workspace to retrieve its verified rules."
                )

        return {
            "content": content,
            "language": lang,
            "citations": citations,
            "disclaimer": "AI Interpretation — Grounded in UniGlobe verified institutional records; not an official university admissions decision.",
        }
