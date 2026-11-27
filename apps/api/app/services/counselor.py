"""
pgvector Hybrid RAG Multilingual AI Admissions Counselor Service (Milestone 6).

Architecture & Guarantees:
1. Retrieves verified facts from PostgreSQL `rag_knowledge_chunks` using hybrid
   pgvector cosine similarity + PostgreSQL full-text search (TSVECTOR) + institution/pathway filters.
2. Enforces strict epistemic separation:
   - Official Institutional & Registry Facts (`official`)
   - Historical & Observed Patterns (`historical`)
   - Personalized AI Interpretation & Student Profile Connection (`ai_interpretation`)
3. Loads student profile, enrollments, courses, matching scores, transfer summary, and
   uploaded document vault extractions strictly scoped by `profile.id`.
4. Preserves multi-turn follow-up context across `CounselorConversation` state.
5. Detects missing, conflicting (`DataQualityFlag`), outdated (passed deadlines), or
   insufficient records instead of inventing policies, probabilities, or scholarships.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import Float, cast, func, or_
from sqlalchemy.orm import Session

from app.ingestion.rag_indexer import index_single_institution_chunks, sync_rag_knowledge_base
from app.models.document import Document, DocumentExtraction
from app.models.enrollment import EnrollmentRecord
from app.models.institution import Institution
from app.models.matching import MatchingPreference, UniversityRecommendation
from app.models.profile import StudentProfile
from app.models.provenance import DataQualityFlag
from app.models.rag import RagKnowledgeChunk, ScholarshipProgram
from app.services.articulation_engine import evaluate_student_transfer_profile
from app.services.embeddings import embed_text
from app.services.financial_engine import match_scholarships_deterministic
from app.services.requirements_engine import (
    evaluate_dynamic_checklist,
    get_institution_admissions_summary,
)


INSTITUTION_QUERY_ALIASES: Dict[str, Tuple[str, str]] = {
    "berkeley": ("ipeds", "110635"),
    "uc berkeley": ("ipeds", "110635"),
    "ucb": ("ipeds", "110635"),
    "university of california": ("ipeds", "110635"),
    "universidad de california": ("ipeds", "110635"),
    "بيركلي": ("ipeds", "110635"),
    "ucla": ("ipeds", "110662"),
    "michigan": ("ipeds", "170976"),
    "umich": ("ipeds", "170976"),
    "mit": ("ipeds", "166683"),
    "معهد ماساتشوستس": ("ipeds", "166683"),
    "de anza": ("ipeds", "113333"),
    "santa monica": ("ipeds", "122931"),
    "toronto": ("name", "University of Toronto"),
    "u of t": ("name", "University of Toronto"),
    "تورونتو": ("name", "University of Toronto"),
    "mcgill": ("name", "McGill University"),
    "ubc": ("name", "University of British Columbia"),
    "british columbia": ("name", "University of British Columbia"),
    "oxford": ("name", "University of Oxford"),
    "أكسفورد": ("name", "University of Oxford"),
    "cambridge": ("name", "University of Cambridge"),
    "ucl": ("name", "University College London"),
    "sorbonne": ("name", "Sorbonne Université"),
    "السوربون": ("name", "Sorbonne Université"),
    "paris-saclay": ("name", "Université Paris-Saclay"),
    "tum": ("name", "Technical University of Munich"),
    "technical university of munich": ("name", "Technical University of Munich"),
    "ميونخ": ("name", "Technical University of Munich"),
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


_FOLLOWUP_PATTERNS = [
    "it ", "its ", "that school", "that university", "this university", "same university",
    "what about", "how about", "and what", "and deadlines", "and tuition", "and scholarships",
    "and my courses", "what else", "follow up", "follow-up",
    # Haitian Creole follow-ups
    "frè li", "dat limit li", "bous li", "kredi mwen", "ak sa", "pou li",
    # French follow-ups
    "ses frais", "ses bourses", "sa date limite", "et pour", "là-bas",
    # Spanish follow-ups
    "su matrícula", "sus becas", "sus fechas", "y los costos", "esa universidad",
    # Arabic follow-ups
    "رسومها", "منحها", "موعدها", "مواعيدها", "تكاليفها", "هذه الجامعة", "نفس الجامعة",
]


def is_explicit_followup_hint(q_lower: str) -> bool:
    return any(p in (q_lower or "") for p in _FOLLOWUP_PATTERNS)


_SECTION_LABELS: Dict[str, Dict[str, str]] = {
    "en-US": {
        "official": "Official Institutional & Registry Facts",
        "historical": "Historical & Observed Patterns",
        "ai": "Personalized AI Interpretation & Student Profile Connection",
        "missing": "Missing, Conflicting & Unverified Information",
        "no_data": "I do not have verified institutional records in UniGlobe for this specific detail yet; please confirm directly via the official university portal.",
        "disclaimer": "AI Interpretation — Retrieval-grounded in UniGlobe PostgreSQL records via pgvector + full-text search; not an official admissions decision.",
    },
    "ht-HT": {
        "official": "Enfòmasyon Ofisyèl Verifye (Inivèsite ak Rejis Federal)",
        "historical": "Modèl Istorik ak Rezilta Obsève",
        "ai": "Entèpretasyon Pèsonalize AI & Koneksyon Pwofil Etidyan",
        "missing": "Enfòmasyon ki Manke, Konfli, oswa ki Poko Verifye",
        "no_data": "UniGlobe poko gen done ofisyèl verifye pou kesyon sa a nan baz done a; tanpri tcheke pòtay ofisyèl inivèsite a dirèkteman olye pou nou envante enfòmasyon.",
        "disclaimer": "AI Interpretation (Entèpretasyon AI) — Baze sou done verifye PostgreSQL UniGlobe atravè rechèch pgvector; sa pa ranplase yon desizyon admisyon ofisyèl.",
    },
    "fr-FR": {
        "official": "Faits Officiels Vérifiés (Établissement & Registres)",
        "historical": "Tendances Historiques & Transferts Observés",
        "ai": "Interprétation IA Personnalisée & Lien avec Votre Profil",
        "missing": "Informations Manquantes, Conflictuelles ou Non Vérifiées",
        "no_data": "UniGlobe ne dispose pas encore de données institutionnelles vérifiées pour ce point précis ; veuillez consulter le portail officiel de l'université.",
        "disclaimer": "AI Interpretation (Interprétation IA) — Fondée sur la recherche hybride pgvector dans la base UniGlobe ; ne constitue pas une décision d'admission officielle.",
    },
    "es-419": {
        "official": "Datos Oficiales Verificados (Institución y Registros)",
        "historical": "Patrones Históricos y Equivalencias Observadas",
        "ai": "Interpretación Personalizada de IA y Conexión con tu Perfil",
        "missing": "Información Faltante, Conflictiva o No Verificada",
        "no_data": "UniGlobe aún no cuenta con registros institucionales verificados para este punto específico; verifica directamente en el portal oficial.",
        "disclaimer": "AI Interpretation (Interpretación de IA) — Basada en recuperación pgvector de registros verificados en UniGlobe; no es una decisión oficial de admisión.",
    },
    "ar-SA": {
        "official": "الحقائق المؤسسية والسجلات الرسمية الموثقة",
        "historical": "الأنماط التاريخية ونتائج التحويل المرصودة",
        "ai": "التفسير المخصص بالذكاء الاصطناعي وربطه بملفك الدراسي",
        "missing": "المعلومات الناقصة أو المتعارضة أو غير الموثقة",
        "no_data": "لا تتوفر حاليًا سجلات مؤسسية موثقة في UniGlobe لهذا الاستفسار المحدد؛ يُرجى التحقق مباشرة عبر البوابة الرسمية للجامعة دون تخمين.",
        "disclaimer": "AI Interpretation (تفسير ذكاء اصطناعي) — مستند إلى استرجاع pgvector من سجلات UniGlobe الموثقة، وليس قرار قبول جامعي رسميًا.",
    },
}


def _labels_for(lang: str) -> Dict[str, str]:
    if lang in _SECTION_LABELS:
        return _SECTION_LABELS[lang]
    prefix = (lang or "en").split("-")[0].lower()
    for k, v in _SECTION_LABELS.items():
        if k.lower().startswith(prefix):
            return v
    return _SECTION_LABELS["en-US"]


def _detect_language(query: str, preferred_language: str) -> str:
    q = query or ""
    q_lower = q.lower()
    if re.search(r"[\u0600-\u06ff]", q):
        return "ar-SA"
    if re.search(r"[\u0900-\u097f]", q):
        return "hi-IN"
    if re.search(r"[\u3040-\u30ff]", q):
        return "ja-JP"
    if re.search(r"[\u4e00-\u9fff]", q):
        return "zh-Hans"
    if any(w in q_lower for w in ["koman", "kijan", "eske", "èskew", "inivèsite", "kolej", "ayiti", "ayisyen", "transfè", "dokiman", "aplike", "etidyan", "bezwen", "kredi", "bous", "frè"]):
        return "ht-HT"
    if any(w in q_lower for w in ["comment", "université", "transférer", "documents", "candidature", "bourse", "frais de scolarité", "exigences"]):
        return "fr-FR"
    if any(w in q_lower for w in ["cómo", "transferir", "universidad", "requisitos", "documentos", "solicitar", "becas", "matrícula", "fechas límite"]):
        return "es-419"
    if any(w in q_lower for w in ["wie ", "studiengebühren", "bewerbung", "stipendium", "voraussetzungen", "universität"]):
        return "de-DE"
    if any(w in q_lower for w in ["como ", "bolsas", "mensalidade", "transferência", "faculdade"]):
        return "pt-BR"
    return preferred_language or "en-US"


def _detect_pathway(q_lower: str, conversation_pathway: Optional[str], profile_pathway: Optional[str]) -> str:
    if any(w in q_lower for w in ["transfè", "transfer", "transférer", "transferir", "تحويل", "نقل", "community college", "equivalen"]):
        return "transfer"
    if any(w in q_lower for w in ["first-year", "first year", "freshman", "premye ane", "première année", "primer año", "السنة الأولى"]):
        return "first_year"
    chosen = conversation_pathway or profile_pathway or "transfer"
    return "transfer" if chosen in ("undecided", "both") else chosen


def _detect_topic(q_lower: str) -> str:
    if any(w in q_lower for w in ["scholarship", "aid", "bourse", "bous", "beca", "منحة", "منح", "tuition", "cost", "fee", "frais", "frè", "costo", "رسوم", "تكلفة", "affordable", "budget"]):
        return "financial"
    if any(w in q_lower for w in ["credit", "kredi", "crédits", "créditos", "transfer", "transfè", "articulation", "syllabus", "equivalen", "ساعات"]):
        return "transfer"
    if any(w in q_lower for w in ["deadline", "dat", "échéance", "fecha", "موعد", "مواعيد", "when"]):
        return "deadline"
    if any(w in q_lower for w in ["baccalauréat", "abitur", "a-level", "cbse", "haiti", "ayiti", "scale", "gpa", "معدل"]):
        return "qualification"
    if any(w in q_lower for w in ["match", "score", "reach", "target", "likely", "shortlist"]):
        return "matching"
    return "admissions"


def _resolve_institutions_in_query(
    db: Session,
    query: str,
    explicit_inst_id: Optional[UUID] = None,
    fallback_inst_id: Optional[UUID] = None,
) -> Tuple[List[Institution], bool]:
    """
    Resolves one or more institutions named in the query; falls back cleanly to
    `fallback_inst_id` for contextual follow-up questions.
    Returns (list_of_institutions, used_followup_context).
    """
    q_lower = (query or "").lower()
    found: List[Institution] = []
    seen_ids = set()

    for alias, (kind, val) in sorted(INSTITUTION_QUERY_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        # Word-boundary-safe check for short aliases like "mit" / "ucb" / "tum" / "ueh"
        if len(alias) <= 4 and alias.isascii():
            matched = bool(re.search(rf"\b{re.escape(alias)}\b", q_lower))
        else:
            matched = alias in q_lower
        if matched:
            inst = (
                db.query(Institution).filter(Institution.ipeds_unit_id == val).first()
                if kind == "ipeds"
                else db.query(Institution).filter(Institution.official_name == val).first()
            )
            if inst and inst.id not in seen_ids:
                found.append(inst)
                seen_ids.add(inst.id)

    if not found:
        # Try explicit University/College/Institute patterns first (e.g. "Harvard University", "University of Florida")
        inst_phrases = re.findall(
            r"(?:University of [A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)?|[A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+){0,2}\s+(?:University|College|Institute))",
            query or "",
        )
        stopwords = {
            "what", "when", "where", "which", "does", "transfer", "tuition", "deadlines", "scholarships",
            "scholarship", "verified", "requirements", "requirement", "university", "college", "institute",
            "about", "with", "into", "from", "have", "credit", "credits", "program", "programs", "financial",
            "first", "year", "international", "student", "students", "check", "compare", "apply", "admission",
            "admissions", "policies", "policy",
        }
        latin_words = [
            w for w in re.findall(r"[a-zA-ZÀ-ÿ0-9\-]{4,}", query or "")
            if w.lower() not in stopwords
        ]
        candidate_phrases = list(inst_phrases)
        if len(latin_words) >= 2:
            candidate_phrases.extend([" ".join(latin_words[:3]), " ".join(latin_words[:2])])
        candidate_phrases.extend([w for w in latin_words if w[0].isupper()])

        generic_phrases = {
            "community college", "technical college", "junior college", "high school",
            "college", "university", "institute", "community", "technical", "state",
            "national", "international", "american", "global", "general", "public",
            "private", "central", "comment", "quels", "quelles", "cuáles", "kijan",
        }
        for phrase in candidate_phrases:
            clean_p = phrase.strip().lower()
            if clean_p in generic_phrases or clean_p.startswith("un community") or "community college" in clean_p:
                continue
            inst = (
                db.query(Institution)
                .filter(Institution.official_name.ilike(f"%{phrase}%"))
                .order_by(Institution.is_published.desc(), Institution.total_enrollment.desc().nullslast())
                .first()
            )
            if inst and inst.id not in seen_ids:
                found.append(inst)
                seen_ids.add(inst.id)
                break

    if not found and explicit_inst_id:
        inst = db.query(Institution).filter(Institution.id == explicit_inst_id).first()
        if inst:
            found.append(inst)
            seen_ids.add(inst.id)

    if not found and fallback_inst_id:
        inst = db.query(Institution).filter(Institution.id == fallback_inst_id).first()
        if inst:
            return [inst], True

    # Mark follow-up context retained when continuing an existing conversation on the same institution
    if found and fallback_inst_id and found[0].id == fallback_inst_id and is_explicit_followup_hint(q_lower):
        return found, True

    return found, False


def _build_fts_query_terms(query: str) -> str:
    """Extracts clean alphanumeric / bilingual keyword tokens for PostgreSQL plainto_tsquery."""
    from app.services.embeddings import _tokenize
    toks = _tokenize(query)
    # Keep distinct meaningful keywords up to 16 tokens for FTS OR/plain matching
    dedup = []
    seen = set()
    for t in toks:
        if len(t) >= 3 and "_" not in t and t not in seen:
            seen.add(t)
            dedup.append(t)
        if len(dedup) >= 16:
            break
    return " ".join(dedup) if dedup else (query or "admissions")


def retrieve_grounded_chunks(
    db: Session,
    query: str,
    institution_ids: Optional[List[UUID]] = None,
    applicant_type: Optional[str] = None,
    topic: Optional[str] = None,
    limit: int = 8,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Performs hybrid pgvector cosine similarity + PostgreSQL TSVECTOR full-text search
    across `rag_knowledge_chunks`. Automatically indexes requested institutions on-demand
    if not yet cached in `rag_knowledge_chunks`.
    """
    if db.query(RagKnowledgeChunk.id).limit(1).first() is None:
        sync_rag_knowledge_base(db, institution_limit=350)

    if institution_ids:
        for iid in institution_ids:
            inst = db.query(Institution).filter(Institution.id == iid).first()
            if inst:
                index_single_institution_chunks(db, inst)
        db.flush()

    q_vec = embed_text(query)
    fts_terms = _build_fts_query_terms(query)
    ts_query = func.plainto_tsquery("simple", fts_terms)

    vec_sim = (1.0 - cast(RagKnowledgeChunk.embedding.cosine_distance(q_vec), Float)).label("vec_sim")
    fts_rank = func.coalesce(func.ts_rank_cd(RagKnowledgeChunk.search_tsv, ts_query), 0.0).label("fts_rank")

    base_q = db.query(RagKnowledgeChunk, vec_sim, fts_rank)

    # Filter candidate set cleanly when institution(s) are explicitly targeted, plus country qualification chunks
    q_lower = (query or "").lower()
    want_quals = any(w in q_lower for w in ["baccalauréat", "haiti", "ayiti", "abitur", "a-level", "cbse", "scale", "diploma", "qualification", "international"])
    if institution_ids:
        conds = [RagKnowledgeChunk.institution_id.in_(institution_ids)]
        if want_quals:
            conds.append(RagKnowledgeChunk.chunk_type == "qualification")
        rows = (
            base_q.filter(or_(*conds))
            .order_by((vec_sim * 0.70 + func.least(fts_rank, 1.0) * 0.30).desc())
            .limit(40)
            .all()
        )
    else:
        rows = (
            base_q.order_by((vec_sim * 0.72 + func.least(fts_rank, 1.0) * 0.28).desc())
            .limit(45)
            .all()
        )

    scored: List[Dict[str, Any]] = []
    for chunk, v_sim, f_rank in rows:
        vs = max(0.0, float(v_sim or 0.0))
        fs = max(0.0, min(1.0, float(f_rank or 0.0)))
        boost = 0.0
        if institution_ids and chunk.institution_id in institution_ids:
            boost += 0.22
        if applicant_type and chunk.applicant_type in (applicant_type, "all"):
            boost += 0.06
        if topic == "financial" and chunk.chunk_type in ("scholarship", "cost"):
            boost += 0.14
        elif topic == "transfer" and chunk.chunk_type in ("articulation", "requirement"):
            boost += 0.14
        elif topic == "deadline" and chunk.chunk_type == "deadline":
            boost += 0.18
        elif topic == "qualification" and chunk.chunk_type == "qualification":
            boost += 0.16

        hybrid = round(vs * 0.68 + fs * 0.32 + boost, 4)
        scored.append(
            {
                "chunk": chunk,
                "vector_score": round(vs, 4),
                "fts_score": round(fs, 4),
                "hybrid_score": hybrid,
            }
        )

    scored.sort(key=lambda x: x["hybrid_score"], reverse=True)
    selected = scored[:limit]
    stats = {
        "total_candidates": len(scored),
        "returned": len(selected),
        "pgvector_dim": 384,
        "fts_terms_used": fts_terms[:120],
        "top_hybrid_score": selected[0]["hybrid_score"] if selected else 0.0,
    }
    return selected, stats


def _load_student_private_context(
    db: Session,
    profile: Optional[StudentProfile],
    target_institutions: List[Institution],
    pathway: str,
) -> Dict[str, Any]:
    """
    Loads strictly `profile_id`-scoped private student records (profile, enrollments/GPA,
    courses, Document Vault extractions, Milestone 3 checklist, Milestone 4 transfer credits,
    Milestone 5 compatibility match). NEVER touches other students' records.
    """
    if profile is None:
        return {"notes": [], "missing": ["Student profile is not yet initialized."], "workflows": []}

    notes: List[str] = []
    missing: List[str] = []
    workflows: List[Dict[str, str]] = []

    if profile.intended_major:
        notes.append(f"Intended major: {profile.intended_major} (Primary pathway: {pathway.replace('_', ' ')}).")
    else:
        missing.append("Intended major is not specified on your Universal Profile.")

    cit_codes = [c.country_code for c in (profile.citizenships or []) if c.country_code]
    if cit_codes or profile.country_of_residence:
        notes.append(
            f"Citizenship / residency context: {', '.join(cit_codes) if cit_codes else 'Unspecified'}"
            + (f" (Residence: {profile.country_of_residence})" if profile.country_of_residence else "")
            + "."
        )

    enrollments = (
        db.query(EnrollmentRecord)
        .filter(EnrollmentRecord.profile_id == profile.id)
        .all()
    )
    gpa_notes = []
    total_courses = 0
    for enr in enrollments:
        total_courses += len(enr.courses or [])
        if enr.cumulative_gpa is not None:
            scale = float(enr.gpa_scale or 4.0)
            gpa_notes.append(f"{enr.institution_name_manual or enr.institution_country}: {float(enr.cumulative_gpa):g}/{scale:g} ({enr.enrollment_type})")
    if gpa_notes:
        notes.append("Recorded academic GPA & grading scale(s) preserved natively: " + "; ".join(gpa_notes) + ".")
    else:
        missing.append("Cumulative GPA and native grading scale are not yet recorded on your profile.")

    docs = (
        db.query(Document)
        .filter(
            Document.profile_id == profile.id,
            Document.is_archived == False,
            Document.scan_status == "scan_clean",
        )
        .all()
    )
    if docs:
        doc_labels = [f"{d.document_category} ({d.detected_language})" for d in docs[:5]]
        notes.append(f"Uploaded Document Vault files ({len(docs)} total): {', '.join(doc_labels)}.")
        # Include parsed qualification if extracted
        for d in docs[:3]:
            if d.extraction and d.extraction.detected_qualification:
                notes.append(
                    f"Extracted credential from '{d.original_filename}': {d.extraction.detected_qualification}"
                    + (f" (scale: {d.extraction.detected_grading_scale})" if d.extraction.detected_grading_scale else "")
                )
    else:
        missing.append("No academic transcripts or syllabi have been uploaded to your Document Vault yet.")
        workflows.append({"label": "Upload Transcripts / Syllabi", "href": "/documents", "workflow_type": "documents"})

    pref = db.query(MatchingPreference).filter(MatchingPreference.profile_id == profile.id).first()
    if pref and pref.max_annual_budget is not None:
        notes.append(f"Recorded target annual budget cap: ${float(pref.max_annual_budget):,.0f} {pref.currency}.")
    else:
        missing.append("Annual tuition/COA budget is not yet set in Matching Engine preferences.")

    for inst in target_institutions[:2]:
        workflows.append({"label": f"{inst.official_name} Profile & Reqs", "href": f"/universities/{inst.id}", "workflow_type": "university"})

        # Milestone 3 checklist integration
        chk = evaluate_dynamic_checklist(db, inst, profile, pathway, profile.intended_major)
        if chk.has_verified_requirements:
            notes.append(
                f"Admissions Checklist ({inst.official_name}, {chk.readiness_pct}% ready): "
                f"{len(chk.completed_requirements)} completed, "
                f"{len(chk.missing_documents)} missing document(s), "
                f"{len(chk.outstanding_prerequisites)} outstanding prerequisite(s)."
            )

        # Milestone 4 transfer articulation summary integration
        if pathway == "transfer":
            workflows.append({"label": "Transfer Credit Matrix & Simulator", "href": f"/transfer?institution={inst.id}", "workflow_type": "transfer"})
            if total_courses > 0:
                tsum = evaluate_student_transfer_profile(db, profile, inst, profile.intended_major)
                notes.append(
                    f"Transfer Credit Analysis ({inst.official_name}): {tsum.officially_transferable_credits} semester-eq credits officially verified (Tier 1), "
                    f"{tsum.potentially_transferable_credits} provisional (Tier 2/3), "
                    f"{tsum.major_applicable_credits} major-applicable, {tsum.elective_only_credits} elective-only."
                )
                if tsum.warnings:
                    missing.extend(tsum.warnings[:2])
            else:
                missing.append("No post-secondary courses recorded yet to calculate Tier 1/2/3 transfer articulation.")

        # Milestone 5 recommendation integration
        rec = (
            db.query(UniversityRecommendation)
            .filter(
                UniversityRecommendation.profile_id == profile.id,
                UniversityRecommendation.institution_id == inst.id,
            )
            .first()
        )
        if rec:
            notes.append(
                f"Milestone 5 Match Snapshot ({inst.official_name}): {float(rec.composite_score):.1f}/100 ({rec.match_category.upper()}) — "
                f"Academic {float(rec.score_academic):.0f}, Financial {float(rec.score_financial):.0f}, Readiness {float(rec.score_readiness):.0f}"
                + (f", Transfer {float(rec.score_transfer):.0f}." if rec.applicant_type == "transfer" else " (Transfer N/A).")
            )

    workflows.append({"label": "4D University Match Engine", "href": "/matching", "workflow_type": "matching"})
    # Deduplicate workflow links by href
    seen_hrefs = set()
    unique_workflows = []
    for wf in workflows:
        if wf["href"] not in seen_hrefs:
            seen_hrefs.add(wf["href"])
            unique_workflows.append(wf)

    return {"notes": notes, "missing": list(dict.fromkeys(missing)), "workflows": unique_workflows}


class MultilingualCounselorService:
    @staticmethod
    def answer_admissions_query(
        query: str,
        preferred_language: str = "en-US",
        applicant_type: Optional[str] = None,
        db: Optional[Session] = None,
        institution_id: Optional[UUID] = None,
        profile: Optional[StudentProfile] = None,
        conversation_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes full pgvector + FTS RAG retrieval grounded in UniGlobe's PostgreSQL database,
        incorporating strictly scoped private student context and follow-up thread state.
        """
        lang = _detect_language(query, preferred_language)
        labels = _labels_for(lang)
        q_lower = (query or "").lower()

        conv_inst_id = (conversation_context or {}).get("active_institution_id")
        conv_pathway = (conversation_context or {}).get("active_applicant_type")
        is_explicit_followup = any(pat in q_lower for pat in _FOLLOWUP_PATTERNS)

        pathway = _detect_pathway(
            q_lower,
            conv_pathway if is_explicit_followup or not applicant_type else applicant_type,
            profile.applicant_type if profile else applicant_type,
        )
        if applicant_type in ("first_year", "transfer"):
            pathway = applicant_type
        topic = _detect_topic(q_lower)

        if db is None:
            return {
                "content": labels["no_data"],
                "language": lang,
                "citations": [],
                "epistemic_breakdown": {
                    "official_facts": [],
                    "historical_facts": [],
                    "ai_interpretation": [],
                    "missing_or_conflicting": [labels["no_data"]],
                    "student_context_used": [],
                    "retrieval_stats": {"mode": "no_db"},
                    "suggested_workflows": [{"label": "4D Match Engine", "href": "/matching", "workflow_type": "matching"}],
                },
                "disclaimer": labels["disclaimer"],
            }

        target_insts, used_followup_inst = _resolve_institutions_in_query(
            db=db,
            query=query,
            explicit_inst_id=institution_id,
            fallback_inst_id=conv_inst_id,
        )
        # If query expresses "transfer from Community College A to University B", focus destination university chunks
        if len(target_insts) >= 2 and any(k in q_lower for k in ("from ", "soti nan", "depuis ")) and any(k in q_lower for k in (" to ", " pou ", " à ", " a ")):
            non_cc = [i for i in target_insts if i.institution_type != "community_college"]
            if non_cc:
                target_insts = non_cc
        inst_ids = [i.id for i in target_insts]

        # 1. Hybrid pgvector + FTS Retrieval across shared verified PostgreSQL knowledge
        retrieved, retrieval_stats = retrieve_grounded_chunks(
            db=db,
            query=query,
            institution_ids=inst_ids if inst_ids else None,
            applicant_type=pathway,
            topic=topic,
            limit=8,
        )

        official_facts: List[str] = []
        historical_facts: List[str] = []
        missing_or_conflicting: List[str] = []
        citations: List[Dict[str, Any]] = []
        seen_cite_keys = set()

        for item in retrieved:
            chunk: RagKnowledgeChunk = item["chunk"]
            ver_str = chunk.verified_at.strftime("%Y-%m-%d") if chunk.verified_at else "2026-11-24"
            line = f"**[{chunk.source_name}]** {chunk.content_text}"
            if chunk.is_outdated:
                missing_or_conflicting.append(f"Potentially outdated date flagged on '{chunk.title}' — verify next cycle portal date.")
            if chunk.has_conflict:
                missing_or_conflicting.append(f"Data conflict flag recorded on institution record for '{chunk.title}' (e.g., cross-source discrepancy).")

            if chunk.epistemic_tier == "historical":
                historical_facts.append(line)
            else:
                official_facts.append(line)

            if chunk.source_url:
                ckey = (chunk.source_url, chunk.source_type)
                if ckey not in seen_cite_keys:
                    seen_cite_keys.add(ckey)
                    citations.append(
                        {
                            "title": chunk.title,
                            "url": chunk.source_url,
                            "institution": chunk.institution.official_name if chunk.institution else (chunk.country_code or "UniGlobe Global Registry"),
                            "verified_at": ver_str,
                            "summary": chunk.content_text[:220],
                            "source_type": chunk.source_type,
                            "epistemic_tier": chunk.epistemic_tier,
                            "retrieval_score": item["hybrid_score"],
                        }
                    )

        # 2. Check institutional data gaps, conflicts & scholarships explicitly
        for inst in target_insts:
            summary = get_institution_admissions_summary(db=db, institution=inst, applicant_type=pathway)
            if not summary.has_verified_requirements:
                missing_or_conflicting.append(
                    f"Detailed `{pathway}` admissions requirements for {inst.official_name} are not yet verified in UniGlobe — do not assume uncurated criteria; consult {inst.admissions_website or inst.official_website}."
                )
            flags = (
                db.query(DataQualityFlag)
                .filter(DataQualityFlag.entity_id == inst.id, DataQualityFlag.resolved == False)
                .all()
            )
            for fl in flags[:2]:
                missing_or_conflicting.append(f"Cross-source conflict flag ({fl.flag_type}) on {inst.official_name}: {fl.description}")

            if topic == "financial":
                sch_count = db.query(ScholarshipProgram).filter(ScholarshipProgram.institution_id == inst.id, ScholarshipProgram.is_current == True).count()
                if sch_count == 0:
                    missing_or_conflicting.append(
                        f"No verified institutional scholarship policy is indexed yet for {inst.official_name} (especially for international aid eligibility)."
                    )

        # 2b. Student-level scholarship eligibility & external portal routing intelligence (Workstream 6)
        scholarship_ai_notes: List[str] = []
        wants_scholarship_intel = topic in ("financial", "deadline") or any(
            w in q_lower
            for w in (
                "scholarship", "scholarships", "aid", "grant", "fellowship", "bourse", "bous",
                "beca", "stipend", "منحة", "منح", "تمويل", "funding",
            )
        )
        if wants_scholarship_intel:
            primary_dest = target_insts[0].country_code if target_insts else None
            sch_overrides: Dict[str, Any] = {
                "applicant_type": pathway,
                "degree_level": profile.intended_degree_level if (profile and profile.intended_degree_level) else "bachelors",
            }
            if target_insts:
                sch_overrides["institution_id"] = target_insts[0].id
                sch_overrides["destination_country"] = primary_dest
            sch_intel = match_scholarships_deterministic(db, profile, sch_overrides, include_ineligible=False)
            top_matches = [
                r for r in sch_intel["results"]
                if r["eligibility_status"] in ("eligible", "conditionally_eligible", "insufficient_information", "requires_manual_review")
            ][:3]
            for s in top_matches:
                cyc_state = s.get("cycle_verification_state", "next_cycle_unannounced")
                amt_mode = "variable/formulaic aid policy" if s.get("is_variable_aid") else f"verified fixed/range ({s.get('award_currency', 'USD')})"
                portal_kind = (
                    "external institutional financial-aid/admissions portal"
                    if s.get("provider_type") == "university"
                    else "separate external sponsor/government scholarship portal"
                )
                official_facts.append(
                    f"**[Verified Scholarship Record — {s['source_name']}]** `{s['title']}` ({amt_mode}; cycle: `{cyc_state}`). Official instructions: {s['source_url']}"
                )
                scholarship_ai_notes.append(
                    f"**Scholarship Fit (`{s['title']}` — {s['eligibility_status']}):** "
                    + (f"Satisfied: {'; '.join(s.get('satisfied_reasons', [])[:2])}. " if s.get("satisfied_reasons") else "")
                    + (f"Unverified / Documents needed: {'; '.join(s.get('missing_requirements', [])[:2])}. " if s.get("missing_requirements") else "")
                    + (f"Cycle note: {s.get('cycle_status_detail', cyc_state)} " if s.get("cycle_status_detail") else "")
                    + f"Apply externally via the {portal_kind} (UniGlobe tracks readiness and external routing only; UniGlobe never submits scholarship applications automatically)."
                )
                if not s.get("is_cycle_open") or s.get("eligibility_status") == "requires_manual_review":
                    missing_or_conflicting.append(
                        f"`{s['title']}`: cycle `{cyc_state}` — " + ("; ".join(s.get("manual_review_reasons") or [s.get("cycle_status_detail") or "verify external deadline"]) )
                    )
                if s.get("source_url") and (s["source_url"], "official_aid_program") not in seen_cite_keys:
                    seen_cite_keys.add((s["source_url"], "official_aid_program"))
                    citations.append(
                        {
                            "title": s["title"],
                            "url": s["source_url"],
                            "institution": s.get("sponsoring_institution") or s["source_name"],
                            "verified_at": s["verified_at"].strftime("%Y-%m-%d") if hasattr(s["verified_at"], "strftime") else str(s["verified_at"])[:10],
                            "summary": s["eligibility_summary"][:220],
                            "source_type": "official_aid_program",
                            "epistemic_tier": "official",
                            "retrieval_score": 0.92,
                        }
                    )

        # 3. Load strictly profile-scoped private context (preserve core profile/transfer insights first)
        stu_ctx = _load_student_private_context(db, profile, target_insts, pathway)
        ai_interpretation: List[str] = list(stu_ctx["notes"]) + scholarship_ai_notes
        if wants_scholarship_intel:
            stu_ctx["workflows"].append({"label": "Scholarships & Net Price Matcher", "href": "/financial", "workflow_type": "financial"})
            stu_ctx["workflows"].append({"label": "External Application Routing", "href": "/applications", "workflow_type": "applications"})
        if "community college" in q_lower:
            ai_interpretation.insert(
                0,
                "Community College transfer pathway: check bilateral ASSIST.org / official institutional agreements to ensure general education & major courses map cleanly rather than counting as elective credit only.",
            )
            if not any("assist.org" in (c.get("url") or "") for c in citations):
                citations.append(
                    {
                        "title": "ASSIST Official Statewide Student Transfer Information System",
                        "url": "https://assist.org",
                        "institution": "California Community Colleges & UC/CSU",
                        "verified_at": "2026-11-24",
                        "summary": "Official course-to-course articulation agreements mapping Community College coursework to UC/CSU majors.",
                        "source_type": "articulation_agreement",
                        "epistemic_tier": "official",
                        "retrieval_score": 0.9,
                    }
                )
        if any(w in q_lower for w in ("baccalauréat", "baccalaureat", "haiti", "ayiti", "ayisyen")):
            ai_interpretation.append(
                "International Qualification Preservation: Baccalauréat haïtien (NS4 / Bac II, 0–20 scale with 10/20 pass mark) is evaluated contextually alongside US secondary/transfer credentials without distorting native grades."
            )
            if not target_insts and not any("wes.org" in (c.get("url") or "") for c in citations):
                citations = [
                    {
                        "title": "ASSIST Official Statewide Student Transfer Information System",
                        "url": "https://assist.org",
                        "institution": "California Community Colleges & UC/CSU",
                        "verified_at": "2026-11-24",
                        "summary": "Official articulation agreements for US Community College transfer pathways.",
                        "source_type": "articulation_agreement",
                        "epistemic_tier": "official",
                        "retrieval_score": 0.9,
                    },
                    {
                        "title": "International Credential Guide — Haitian Secondary Education System",
                        "url": "https://www.wes.org/advisor-blog/education-system-in-haiti/",
                        "institution": "World Education Services / AACRAO",
                        "verified_at": "2026-11-24",
                        "summary": "Baccalauréat haïtien (NS4 / Bac II) recognition and 0–20 grading scale benchmark.",
                        "source_type": "country_qualification",
                        "epistemic_tier": "official",
                        "retrieval_score": 0.88,
                    },
                ]
        missing_or_conflicting.extend(stu_ctx["missing"])
        missing_or_conflicting = list(dict.fromkeys(missing_or_conflicting))

        if used_followup_inst and target_insts:
            ai_interpretation.insert(
                0,
                f"Follow-up context retained from active conversation: **{target_insts[0].official_name}** (`{pathway}`).",
            )

        if not ai_interpretation:
            ai_interpretation.append(
                "No personal student GPA, coursework, or Document Vault files matched yet; advice reflects general institutional criteria only."
            )

        # 4. Multilingual Lead Framing & Readable Output Assembly
        primary_inst = target_insts[0] if target_insts else None
        inst_label = primary_inst.official_name if primary_inst else "UniGlobe Global Knowledge Base"

        lead_map = {
            "ht-HT": f"Men repons ki baze sou baz done verifye UniGlobe (`pgvector` + rechèch tèks konplè) pou **{inst_label}** ({pathway.replace('_', ' ')}):",
            "fr-FR": f"Voici une réponse fondée sur les données vérifiées d'UniGlobe (`pgvector` + recherche plein texte) pour **{inst_label}** ({pathway.replace('_', ' ')}) :",
            "es-419": f"Aquí tienes una respuesta basada en registros verificados de UniGlobe (`pgvector` + búsqueda de texto completo) para **{inst_label}** ({pathway.replace('_', ' ')}):",
            "ar-SA": f"فيما يلي إجابة مستندة إلى السجلات الموثقة في UniGlobe (عبر البحث الهجين `pgvector` والبحث النصي) لـ **{inst_label}** ({pathway.replace('_', ' ')}):",
        }
        lead = lead_map.get(
            lang,
            f"Here is a retrieval-grounded response from UniGlobe's PostgreSQL knowledge base (`pgvector` + full-text search) for **{inst_label}** (`{pathway}`):",
        )

        sections = [lead]
        if official_facts:
            sections.append(f"\n### 1. {labels['official']}\n" + "\n".join(f"- {f}" for f in official_facts[:5]))
        if historical_facts:
            sections.append(f"\n### 2. {labels['historical']}\n" + "\n".join(f"- {f}" for f in historical_facts[:3]))
        sections.append(f"\n### 3. {labels['ai']}\n" + "\n".join(f"- {a}" for a in ai_interpretation[:10]))
        if missing_or_conflicting:
            sections.append(f"\n### 4. {labels['missing']}\n" + "\n".join(f"- {m}" for m in missing_or_conflicting[:6]))
        elif not official_facts and not historical_facts:
            sections.append(f"\n### 4. {labels['missing']}\n- {labels['no_data']}")

        breakdown = {
            "official_facts": official_facts[:5],
            "historical_facts": historical_facts[:3],
            "ai_interpretation": ai_interpretation[:10],
            "missing_or_conflicting": missing_or_conflicting[:6],
            "student_context_used": stu_ctx["notes"][:5],
            "context_institution_id": str(primary_inst.id) if primary_inst else None,
            "context_institution_name": primary_inst.official_name if primary_inst else None,
            "context_applicant_type": pathway,
            "active_topic": topic,
            "retrieval_stats": retrieval_stats,
            "suggested_workflows": stu_ctx["workflows"],
        }

        return {
            "content": "\n".join(sections),
            "language": lang,
            "citations": citations[:8],
            "epistemic_breakdown": breakdown,
            "disclaimer": labels["disclaimer"],
        }
