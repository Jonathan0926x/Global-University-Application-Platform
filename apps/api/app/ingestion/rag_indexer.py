"""
RAG Knowledge Indexing & Verified Official Scholarship Seeder (Milestone 6).

Populates `scholarship_programs` and indexes verified public UniGlobe database records into
`rag_knowledge_chunks` with 384-dim pgvector cosine embeddings + PostgreSQL `tsvector`
full-text search vectors.

STRICT INVARIANTS:
- NEVER indexes student-private profiles, transcripts, or document vault records into shared tables.
- Preserves official vs historical epistemic provenance, source URLs, verification dates, and conflict flags.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.articulation import ArticulationAgreement, CourseEquivalency
from app.models.institution import AcademicProgram, Institution, InstitutionCost
from app.models.provenance import DataQualityFlag
from app.models.rag import RagKnowledgeChunk, ScholarshipProgram
from app.models.requirements import CountryQualification, Deadline, InstitutionRequirement
from app.services.embeddings import embed_text


VERIFIED_SCHOLARSHIPS: List[Dict[str, Any]] = [
    {
        "institution_ipeds": "110635",
        "country_code": "US",
        "title": "UC Blue and Gold Opportunity Plan (UC Berkeley)",
        "applicant_type": "all",
        "funding_type": "need_based",
        "covers_international": False,
        "max_award_info": "Covers systemwide UC tuition & fees for CA residents with family income under $80,000",
        "eligibility_summary": "California residents enrolled in at least half-time undergraduate degree programs demonstrating financial need via FAFSA/CADAA. Does NOT cover non-resident supplemental tuition or international students.",
        "source_name": "University of California Admissions",
        "source_url": "https://admission.universityofcalifornia.edu/tuition-financial-aid/types-of-aid/blue-and-gold-opportunity-plan/",
    },
    {
        "institution_ipeds": "110662",
        "country_code": "US",
        "title": "UCLA Blue and Gold & Regents Scholarship Framework",
        "applicant_type": "all",
        "funding_type": "need_based",
        "covers_international": False,
        "max_award_info": "Full UC systemwide tuition for eligible CA residents; Regents merit stipends vary",
        "eligibility_summary": "Need-based UC aid applies strictly to California residents and eligible AB 540 students. International applicants are ineligible for federal, state, or UC need-based aid and must document full self-funding.",
        "source_name": "UCLA Financial Aid & Scholarships",
        "source_url": "https://financialaid.ucla.edu/",
    },
    {
        "institution_ipeds": "170976",
        "country_code": "US",
        "title": "UMich Go Blue Guarantee",
        "applicant_type": "all",
        "funding_type": "need_based",
        "covers_international": False,
        "max_award_info": "Full in-state undergraduate tuition for up to 4 years (transfers: up to 2 years)",
        "eligibility_summary": "Available to in-state Michigan residents meeting household income and asset thresholds. International and out-of-state transfer applicants are ineligible for Go Blue Guarantee funding.",
        "source_name": "University of Michigan Office of Financial Aid",
        "source_url": "https://goblueguarantee.umich.edu/",
    },
    {
        "institution_ipeds": "166683",
        "country_code": "US",
        "title": "MIT Need-Blind Admissions & Full-Need Institutional Aid",
        "applicant_type": "all",
        "funding_type": "need_based",
        "covers_international": True,
        "max_award_info": "Meets 100% of demonstrated financial need for domestic and international students",
        "eligibility_summary": "MIT practices need-blind admissions for all applicants regardless of citizenship and provides need-based MIT Scholarships covering tuition, housing, and dining according to family financial documentation.",
        "source_name": "MIT Student Financial Services",
        "source_url": "https://sfs.mit.edu/undergraduate-students/apply-for-aid/international/",
    },
    {
        "institution_name": "University of Toronto",
        "country_code": "CA",
        "title": "Lester B. Pearson International Scholarship",
        "applicant_type": "first_year",
        "funding_type": "merit",
        "covers_international": True,
        "max_award_info": "Full tuition, books, incidental fees, and residence support for 4 years",
        "eligibility_summary": "Recognizes outstanding international secondary school students nominated by their school. Requires separate nomination and application deadlines distinct from standard OUAC review.",
        "source_name": "University of Toronto Future Students",
        "source_url": "https://future.utoronto.ca/pearson/about/",
    },
    {
        "institution_name": "University of Oxford",
        "country_code": "GB",
        "title": "Reach Oxford & Palgrave Brown Undergraduate Scholarships",
        "applicant_type": "first_year",
        "funding_type": "need_based",
        "covers_international": True,
        "max_award_info": "Covers course fees and living grant for students from eligible low-income countries",
        "eligibility_summary": "Competitive funding for international undergraduate offer-holders from eligible countries (including Haiti and developing nations) who cannot study a degree in their home country for financial or political reasons.",
        "source_name": "University of Oxford Fees & Funding",
        "source_url": "https://www.ox.ac.uk/admissions/undergraduate/fees-and-funding/oxford-support",
    },
    {
        "institution_name": "Technical University of Munich",
        "country_code": "DE",
        "title": "TUM Deutschlandstipendium & Bavarian Public Fee Waiver Policy",
        "applicant_type": "all",
        "funding_type": "merit",
        "covers_international": True,
        "max_award_info": "EUR 300/month merit stipend; tuition fee waivers available for qualifying international hardship cases",
        "eligibility_summary": "EU/EEA and Bildungsinaender pay semester student union fees only; non-EU international bachelor/master students may face Bavarian tuition fees unless granted an approved TUM tuition waiver or DAAD/Deutschlandstipendium fellowship.",
        "source_name": "Technical University of Munich Fees & Aid",
        "source_url": "https://www.tum.de/en/studies/fees-and-financial-aid",
    },
    {
        "institution_name": "Sorbonne Université",
        "country_code": "FR",
        "title": "France Excellence Eiffel & Campus France Government Aid",
        "applicant_type": "all",
        "funding_type": "statutory_aid",
        "covers_international": True,
        "max_award_info": "French public university differentiated fee exemptions & monthly allowance on competitive award",
        "eligibility_summary": "French national differentiated registration fees apply by default to non-EU entrants unless exempted by institution/ambassy merit programs (Bourses d'Excellence / Campus France).",
        "source_name": "Campus France / Sorbonne Université",
        "source_url": "https://www.campusfrance.org/en/eiffel-scholarship-program-of-excellence",
    },
]


def _make_hash(*parts: Any) -> str:
    joined = "|".join(str(p or "") for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def seed_verified_scholarships(db: Session) -> int:
    created = 0
    for item in VERIFIED_SCHOLARSHIPS:
        inst = None
        if item.get("institution_ipeds"):
            inst = db.query(Institution).filter(Institution.ipeds_unit_id == item["institution_ipeds"]).first()
        elif item.get("institution_name"):
            inst = db.query(Institution).filter(Institution.official_name == item["institution_name"]).first()
        if not inst:
            continue

        exists = (
            db.query(ScholarshipProgram)
            .filter(
                ScholarshipProgram.institution_id == inst.id,
                ScholarshipProgram.title == item["title"],
            )
            .first()
        )
        if not exists:
            db.add(
                ScholarshipProgram(
                    institution_id=inst.id,
                    country_code=item["country_code"],
                    title=item["title"],
                    applicant_type=item["applicant_type"],
                    funding_type=item["funding_type"],
                    covers_international=item["covers_international"],
                    max_award_info=item["max_award_info"],
                    eligibility_summary=item["eligibility_summary"],
                    source_name=item["source_name"],
                    source_url=item["source_url"],
                    verified_at=datetime.now(timezone.utc),
                    is_verified=True,
                    is_current=True,
                )
            )
            created += 1
    db.flush()
    return created


def _upsert_chunk(
    db: Session,
    existing_hashes: set,
    *,
    institution_id,
    country_code: Optional[str],
    chunk_type: str,
    epistemic_tier: str,
    source_type: str,
    applicant_type: str,
    title: str,
    content_text: str,
    source_name: str,
    source_url: Optional[str],
    verified_at: Optional[datetime],
    is_outdated: bool = False,
    has_conflict: bool = False,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> bool:
    chash = _make_hash(
        institution_id,
        country_code,
        chunk_type,
        epistemic_tier,
        source_type,
        applicant_type,
        title,
        content_text,
        is_outdated,
        has_conflict,
    )
    if chash in existing_hashes:
        return False

    vec = embed_text(f"{title}. {content_text}")
    tsv_text = f"{title} {content_text}"
    chunk = RagKnowledgeChunk(
        institution_id=institution_id,
        country_code=country_code,
        chunk_type=chunk_type,
        epistemic_tier=epistemic_tier,
        source_type=source_type,
        applicant_type=applicant_type or "all",
        title=title[:300],
        content_text=content_text,
        source_name=source_name[:255],
        source_url=source_url,
        verified_at=verified_at or datetime.now(timezone.utc),
        is_outdated=is_outdated,
        has_conflict=has_conflict,
        metadata_json=metadata_json or {},
        content_hash=chash,
        embedding=vec,
        search_tsv=func.to_tsvector("simple", tsv_text),
    )
    db.add(chunk)
    existing_hashes.add(chash)
    return True


def index_single_institution_chunks(db: Session, inst: Institution, existing_hashes: Optional[set] = None) -> int:
    """Indexes an institution's overview, costs, and programs on-demand if not yet indexed."""
    if existing_hashes is None:
        existing_hashes = {h[0] for h in db.query(RagKnowledgeChunk.content_hash).filter(RagKnowledgeChunk.institution_id == inst.id).all()}

    added = 0
    conflict_count = (
        db.query(DataQualityFlag)
        .filter(
            DataQualityFlag.entity_id == inst.id,
            DataQualityFlag.entity_type == "institution",
            DataQualityFlag.resolved == False,
        )
        .count()
    )
    has_conflict = conflict_count > 0

    programs = [p.program_name for p in db.query(AcademicProgram).filter(AcademicProgram.institution_id == inst.id).limit(15).all() if p.program_name]
    prog_snippet = f" Academic programs indexed: {', '.join(programs[:8])}." if programs else ""
    overview_text = (
        f"{inst.official_name} is a {inst.control_type or ''} {inst.institution_type} in "
        f"{', '.join([x for x in (inst.city, inst.state_province, inst.country_code) if x])}. "
        f"First-year accepted: {inst.accepts_first_year}; Transfer accepted: {inst.accepts_transfer}. "
        f"Acceptance rate: {f'{float(inst.acceptance_rate):.1f}%' if inst.acceptance_rate is not None else 'Not reported'}. "
        f"Total enrollment: {inst.total_enrollment or 'Not reported'}.{prog_snippet}"
    )
    if _upsert_chunk(
        db,
        existing_hashes,
        institution_id=inst.id,
        country_code=inst.country_code,
        chunk_type="institutional_overview",
        epistemic_tier="official",
        source_type="federal_ipeds" if inst.ipeds_unit_id else "official_institutional",
        applicant_type="all",
        title=f"{inst.official_name} — Overview & Programs",
        content_text=overview_text,
        source_name=inst.primary_source or "UniGlobe Institutional Registry",
        source_url=inst.admissions_website or inst.official_website,
        verified_at=inst.last_verified_at,
        has_conflict=has_conflict,
        metadata_json={"programs": programs[:12], "acceptance_rate": float(inst.acceptance_rate) if inst.acceptance_rate is not None else None},
    ):
        added += 1

    if programs:
        if _upsert_chunk(
            db,
            existing_hashes,
            institution_id=inst.id,
            country_code=inst.country_code,
            chunk_type="program",
            epistemic_tier="official",
            source_type="federal_scorecard" if inst.country_code == "US" else "official_institutional",
            applicant_type="all",
            title=f"{inst.official_name} — Academic Majors & CIP Programs",
            content_text=f"{inst.official_name} offers indexed programs in: {', '.join(programs)}.",
            source_name="College Scorecard / IPEDS Programs" if inst.country_code == "US" else (inst.primary_source or "Institutional Catalog"),
            source_url=inst.official_website,
            verified_at=inst.last_verified_at,
            metadata_json={"programs": programs},
        ):
            added += 1

    # Itemized costs & historical net price
    costs = db.query(InstitutionCost).filter(InstitutionCost.institution_id == inst.id).order_by(InstitutionCost.academic_year.desc()).limit(3).all()
    if costs or inst.tuition_out_of_state is not None or inst.avg_net_price is not None:
        parts = []
        for c in costs:
            stu_lbl = (c.student_type or "general").replace("_", " ")
            parts.append(
                f"AY {c.academic_year} ({stu_lbl}): tuition ${float(c.tuition):,.0f}" if c.tuition is not None else f"AY {c.academic_year} ({stu_lbl})"
            )
            if c.total_estimated_cost is not None:
                parts[-1] += f", total COA ${float(c.total_estimated_cost):,.0f}"
        if not parts and inst.tuition_out_of_state is not None:
            parts.append(f"Published out-of-state tuition ${float(inst.tuition_out_of_state):,.0f}")
        cost_text = f"Published institutional cost schedule for {inst.official_name}: {'; '.join(parts)}."
        if _upsert_chunk(
            db,
            existing_hashes,
            institution_id=inst.id,
            country_code=inst.country_code,
            chunk_type="cost",
            epistemic_tier="official",
            source_type="federal_ipeds" if inst.ipeds_unit_id else "official_institutional",
            applicant_type="all",
            title=f"{inst.official_name} — Tuition & Cost of Attendance",
            content_text=cost_text,
            source_name="NCES IPEDS" if inst.ipeds_unit_id else (inst.primary_source or "Official Cost Schedule"),
            source_url=inst.net_price_calculator_url or inst.official_website,
            verified_at=inst.last_verified_at,
            metadata_json={
                "tuition_in_state": float(inst.tuition_in_state) if inst.tuition_in_state is not None else None,
                "tuition_out_of_state": float(inst.tuition_out_of_state) if inst.tuition_out_of_state is not None else None,
                "cost_of_attendance": float(inst.cost_of_attendance) if inst.cost_of_attendance is not None else None,
            },
        ):
            added += 1

        if inst.avg_net_price is not None or inst.median_earnings_10yr is not None:
            hist_text = (
                f"Historical College Scorecard federal cohort outcomes for {inst.official_name}: "
                f"average net price ${float(inst.avg_net_price):,.0f}" if inst.avg_net_price is not None else f"Historical outcomes for {inst.official_name}:"
            )
            if inst.median_earnings_10yr is not None:
                hist_text += f"; 10-year median earnings ${float(inst.median_earnings_10yr):,.0f}."
            if _upsert_chunk(
                db,
                existing_hashes,
                institution_id=inst.id,
                country_code=inst.country_code,
                chunk_type="cost",
                epistemic_tier="historical",
                source_type="federal_scorecard",
                applicant_type="all",
                title=f"{inst.official_name} — Historical Net Price & Outcomes",
                content_text=hist_text,
                source_name="U.S. Dept of Education College Scorecard",
                source_url=inst.net_price_calculator_url or inst.official_website,
                verified_at=inst.last_verified_at,
                metadata_json={"avg_net_price": float(inst.avg_net_price) if inst.avg_net_price is not None else None},
            ):
                added += 1

    return added


def sync_rag_knowledge_base(db: Session, institution_limit: int = 350) -> Dict[str, int]:
    """
    Idempotently syncs verified requirements, deadlines, scholarships, country qualifications,
    articulation agreements, transfer equivalencies, and prioritized institutional overviews/costs
    into `rag_knowledge_chunks` for hybrid pgvector + FTS retrieval.
    """
    seed_verified_scholarships(db)
    existing_hashes = {h[0] for h in db.query(RagKnowledgeChunk.content_hash).all()}
    counts = {"requirements": 0, "deadlines": 0, "scholarships": 0, "qualifications": 0, "articulation": 0, "institutions": 0}
    now = datetime.now(timezone.utc)

    # 1. Verified Admissions Requirements
    reqs = (
        db.query(InstitutionRequirement)
        .options(joinedload(InstitutionRequirement.institution), joinedload(InstitutionRequirement.template))
        .filter(InstitutionRequirement.is_current == True)
        .all()
    )
    for r in reqs:
        inst = r.institution
        if not inst:
            continue
        r_title = r.title_override or (r.template.display_name if r.template else "Requirement")
        r_desc = (r.template.description if r.template else "") or ""
        text = (
            f"{inst.official_name} ({r.applicant_type}) requirement — {r_title}: "
            f"{r_desc} "
            f"{f'Minimum threshold: {r.minimum_value}. ' if r.minimum_value else ''}"
            f"Importance: {r.importance}. {r.institution_specific_notes or ''}"
        ).strip()
        if _upsert_chunk(
            db,
            existing_hashes,
            institution_id=inst.id,
            country_code=inst.country_code,
            chunk_type="requirement",
            epistemic_tier="official",
            source_type="official_institutional",
            applicant_type=r.applicant_type or "all",
            title=f"{inst.official_name} — {r_title} ({r.applicant_type})",
            content_text=text,
            source_name=r.source_name,
            source_url=r.source_url or inst.admissions_website,
            verified_at=r.verified_at,
            metadata_json={"minimum_value": r.minimum_value, "importance": r.importance, "category": r.template.category if r.template else None},
        ):
            counts["requirements"] += 1

    # 2. Deadlines (detecting outdated / passed deadlines transparently)
    deadlines = db.query(Deadline).options(joinedload(Deadline.institution)).filter(Deadline.is_current == True).all()
    today = now.date()
    for d in deadlines:
        inst = d.institution
        if not inst:
            continue
        is_passed = bool(d.deadline_date and d.deadline_date < today)
        text = (
            f"{inst.official_name} ({d.applicant_type}) deadline for {d.intake_term} "
            f"({d.deadline_type}): {d.deadline_date.isoformat() if d.deadline_date else 'Rolling / Unspecified'}. "
            f"{'NOTE: This deadline date has passed relative to current date; verify next intake cycle.' if is_passed else 'Upcoming official cycle deadline.'} "
            f"{d.notes or ''}"
        ).strip()
        if _upsert_chunk(
            db,
            existing_hashes,
            institution_id=inst.id,
            country_code=inst.country_code,
            chunk_type="deadline",
            epistemic_tier="official",
            source_type="official_institutional",
            applicant_type=d.applicant_type or "all",
            title=f"{inst.official_name} — {d.intake_term} {d.deadline_type} Deadline",
            content_text=text,
            source_name=d.source_name,
            source_url=d.source_url or inst.admissions_website,
            verified_at=d.verified_at,
            is_outdated=is_passed,
            metadata_json={"deadline_date": d.deadline_date.isoformat() if d.deadline_date else None, "intake_term": d.intake_term},
        ):
            counts["deadlines"] += 1

    # 3. Verified Scholarships & Financial Aid Programs
    scholarships = db.query(ScholarshipProgram).options(joinedload(ScholarshipProgram.institution)).filter(ScholarshipProgram.is_current == True).all()
    for s in scholarships:
        inst = s.institution
        inst_name = inst.official_name if inst else s.country_code
        intl_note = "Covers international applicants." if s.covers_international else "Does NOT cover international applicants (domestic/in-state only)."
        text = f"{inst_name} scholarship/aid program — {s.title} ({s.funding_type}): {s.max_award_info or ''}. {intl_note} {s.eligibility_summary}"
        if _upsert_chunk(
            db,
            existing_hashes,
            institution_id=s.institution_id,
            country_code=s.country_code,
            chunk_type="scholarship",
            epistemic_tier="official",
            source_type="official_aid_program",
            applicant_type=s.applicant_type,
            title=f"{inst_name} — {s.title}",
            content_text=text,
            source_name=s.source_name,
            source_url=s.source_url,
            verified_at=s.verified_at,
            metadata_json={"covers_international": s.covers_international, "funding_type": s.funding_type},
        ):
            counts["scholarships"] += 1

    # 4. International Country Qualifications
    quals = db.query(CountryQualification).all()
    for q in quals:
        text = (
            f"National Qualification Framework ({q.country_code}): {q.qualification_name} ({q.qualification_type}). "
            f"Grading scale: {q.grading_scale or 'Country-specific'}; Passing threshold: {q.passing_threshold or 'Check official guideline'}. "
            f"US GPA & admission comparability: {q.equivalency_notes or 'Contextual review'}. "
            f"Recognition rules: {q.recognition_rules or {}}"
        )
        if _upsert_chunk(
            db,
            existing_hashes,
            institution_id=None,
            country_code=q.country_code,
            chunk_type="qualification",
            epistemic_tier="official",
            source_type="country_qualification",
            applicant_type="all",
            title=f"{q.country_code} Qualification — {q.qualification_name}",
            content_text=text,
            source_name=q.source_name,
            source_url=q.source_url,
            verified_at=q.verified_at,
            metadata_json={"grading_scale": q.grading_scale, "country_code": q.country_code},
        ):
            counts["qualifications"] += 1

    # 5. Articulation Agreements & Tier 1/2 Course Equivalencies
    agreements = db.query(ArticulationAgreement).options(joinedload(ArticulationAgreement.source_institution), joinedload(ArticulationAgreement.target_institution)).all()
    for ag in agreements:
        src = ag.source_institution.official_name if ag.source_institution else "Source Institution"
        tgt = ag.target_institution.official_name if ag.target_institution else "Target Institution"
        tier = "historical" if ag.agreement_type == "historical_pattern" else "official"
        src_type = "historical_transfer" if tier == "historical" else "articulation_agreement"
        eqs = (
            db.query(CourseEquivalency)
            .filter(
                CourseEquivalency.source_institution_id == ag.source_institution_id,
                CourseEquivalency.target_institution_id == ag.target_institution_id,
            )
            .limit(12)
            .all()
        )
        eq_list = "; ".join(
            f"{e.source_course_code} -> {e.target_course_code} ({'Major req' if e.satisfies_major_requirement else 'GE/Elective'}, Tier {e.equivalency_tier})"
            for e in eqs
        )
        text = (
            f"Transfer articulation agreement from {src} to {tgt} for program {ag.program_name or 'General'} ({ag.academic_year}): "
            f"{ag.notes or ''} Sample articulated equivalencies: {eq_list}."
        )
        if _upsert_chunk(
            db,
            existing_hashes,
            institution_id=ag.target_institution_id,
            country_code=ag.target_institution.country_code if ag.target_institution else "US",
            chunk_type="articulation",
            epistemic_tier=tier,
            source_type=src_type,
            applicant_type="transfer",
            title=f"Transfer Articulation: {src} -> {tgt} ({ag.program_name or 'General'})",
            content_text=text,
            source_name=ag.source_name,
            source_url=ag.source_url,
            verified_at=ag.verified_at,
            metadata_json={"source_institution_id": str(ag.source_institution_id) if ag.source_institution_id else None},
        ):
            counts["articulation"] += 1

    # 6. Prioritize curated + international + top enrollment institutions for overview/cost/program chunks
    curated_ids = {r.institution_id for r in reqs if r.institution_id} | {ag.target_institution_id for ag in agreements if ag.target_institution_id}
    prioritized_insts = (
        db.query(Institution)
        .filter(
            (Institution.id.in_(curated_ids))
            | (Institution.country_code != "US")
            | (Institution.is_published == True)
        )
        .order_by(Institution.id.in_(curated_ids).desc(), Institution.total_enrollment.desc().nullslast())
        .limit(institution_limit)
        .all()
    )
    for inst in prioritized_insts:
        counts["institutions"] += index_single_institution_chunks(db, inst, existing_hashes)

    db.commit()
    return counts
