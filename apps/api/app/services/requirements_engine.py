"""
Dynamic Admissions Requirements & Personalized Checklist Engine (Milestone 3).

Strict integrity rules:
1. Never invent institutional requirements when none are verified in the database.
2. Never mark an applicant eligible when required academic/residency data is missing.
3. Preserve explicit distinction between first-year, transfer, domestic, and international pathways.
4. Keep full provenance (source_name, source_url, verified_at, verification_status) on every item.
"""

from datetime import date
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.document import Document
from app.models.enrollment import EnrollmentRecord
from app.models.institution import Institution
from app.models.profile import CitizenshipRecord, StudentProfile
from app.models.requirements import (
    CountryQualification,
    Deadline,
    InstitutionRequirement,
    RequirementCondition,
    RequirementTemplate,
)
from app.models.application import StandardizedTest
from app.schemas.requirements import (
    ChecklistItemEvaluationSchema,
    CountryQualificationSchema,
    DeadlineSchema,
    DynamicChecklistResponseSchema,
    InstitutionAdmissionsSummarySchema,
    InstitutionRequirementSchema,
    RequirementConditionSchema,
)


ENGLISH_MAJORITY_COUNTRIES = {"US", "GB", "CA", "AU", "NZ", "IE"}


def _serialize_requirement(req: InstitutionRequirement) -> InstitutionRequirementSchema:
    tpl: RequirementTemplate = req.template
    return InstitutionRequirementSchema(
        id=req.id,
        institution_id=req.institution_id,
        program_id=req.program_id,
        program_name_filter=req.program_name_filter,
        cip_code=req.cip_code,
        applicant_type=req.applicant_type,
        importance=req.importance,
        requirement_type=tpl.requirement_type,
        requirement_subtype=tpl.requirement_subtype,
        category=tpl.category,
        title=req.title_override or tpl.display_name,
        description=tpl.description,
        institution_specific_notes=req.institution_specific_notes,
        quantity=req.quantity,
        minimum_value=req.minimum_value,
        maximum_value=req.maximum_value,
        fee_amount=float(req.fee_amount) if req.fee_amount is not None else None,
        fee_currency=req.fee_currency.strip() if req.fee_currency else None,
        fee_waiver_available=req.fee_waiver_available,
        academic_year=req.academic_year,
        source_name=req.source_name,
        source_type=req.source_type,
        source_url=req.source_url,
        verified_at=req.verified_at,
        confidence_level=req.confidence_level,
        verification_status=req.verification_status,
        conditions=[RequirementConditionSchema.model_validate(c) for c in req.conditions],
    )


def _serialize_deadline(dl: Deadline, today: Optional[date] = None) -> DeadlineSchema:
    ref = today or date.today()
    days_remaining = (dl.deadline_date - ref).days if dl.deadline_date else None
    return DeadlineSchema(
        id=dl.id,
        institution_id=dl.institution_id,
        program_name_filter=dl.program_name_filter,
        applicant_type=dl.applicant_type,
        deadline_type=dl.deadline_type,
        intake_term=dl.intake_term,
        deadline_date=dl.deadline_date,
        deadline_time=dl.deadline_time,
        timezone=dl.timezone,
        is_firm=dl.is_firm,
        notification_date=dl.notification_date,
        academic_year=dl.academic_year,
        notes=dl.notes,
        days_remaining=days_remaining,
        is_past=(days_remaining < 0) if days_remaining is not None else None,
        source_name=dl.source_name,
        source_url=dl.source_url,
        verified_at=dl.verified_at,
        verification_status=dl.verification_status,
        confidence_level=dl.confidence_level,
    )


def get_institution_admissions_summary(
    db: Session,
    institution: Institution,
    applicant_type: Optional[str] = None,
    intended_major: Optional[str] = None,
    academic_year: str = "2026-2027",
) -> InstitutionAdmissionsSummarySchema:
    """
    Returns verified institutional requirements, deadlines, and relevant country qualifications.
    If no verified requirements exist for this institution, explicitly reports coverage_notice
    instead of fabricating rules.
    """
    req_query = (
        db.query(InstitutionRequirement)
        .filter(
            InstitutionRequirement.institution_id == institution.id,
            InstitutionRequirement.is_current == True,
            InstitutionRequirement.academic_year == academic_year,
        )
    )
    if applicant_type:
        req_query = req_query.filter(InstitutionRequirement.applicant_type.in_([applicant_type, "all"]))

    reqs = req_query.order_by(InstitutionRequirement.applicant_type.asc(), InstitutionRequirement.created_at.asc()).all()

    if intended_major:
        major_clean = intended_major.strip().lower()
        reqs = [
            r
            for r in reqs
            if not r.program_name_filter or r.program_name_filter.lower() in major_clean or major_clean in r.program_name_filter.lower()
        ]

    dl_query = (
        db.query(Deadline)
        .filter(
            Deadline.institution_id == institution.id,
            Deadline.is_current == True,
            Deadline.academic_year == academic_year,
        )
    )
    if applicant_type:
        dl_query = dl_query.filter(Deadline.applicant_type.in_([applicant_type, "all"]))
    deadlines = dl_query.order_by(Deadline.deadline_date.asc().nulls_last()).all()

    country_quals = (
        db.query(CountryQualification)
        .filter(CountryQualification.country_code == institution.country_code)
        .order_by(CountryQualification.qualification_type.asc())
        .all()
    )

    has_verified = len(reqs) > 0
    notice = None
    if not has_verified:
        notice = (
            f"Detailed course, essay, and deadline requirements have not yet been verified in UniGlobe for "
            f"{institution.official_name}. Showing verified federal/national baselines and official portal links where available."
        )

    return InstitutionAdmissionsSummarySchema(
        institution_id=institution.id,
        official_name=institution.official_name,
        country_code=institution.country_code,
        academic_year=academic_year,
        has_verified_requirements=has_verified,
        coverage_notice=notice,
        admissions_website=institution.admissions_website,
        application_portal_url=institution.application_portal_url,
        net_price_calculator_url=institution.net_price_calculator_url,
        open_admissions=institution.open_admissions,
        undergrad_application_fee=float(institution.undergrad_application_fee)
        if institution.undergrad_application_fee is not None
        else None,
        requirements=[_serialize_requirement(r) for r in reqs],
        deadlines=[_serialize_deadline(d) for d in deadlines],
        country_qualifications=[CountryQualificationSchema.model_validate(q) for q in country_quals],
    )


# ---------------------------------------------------------------------------
# Profile Context Extraction & Condition Evaluation
# ---------------------------------------------------------------------------
def _extract_profile_context(
    profile: Optional[StudentProfile],
    target_country: str,
    applicant_type: str,
) -> Dict[str, Any]:
    if not profile:
        return {
            "has_profile": False,
            "is_international_for_target": None,
            "requires_english_proficiency": None,
            "earned_college_credits": None,
            "completed_college_terms": None,
            "college_gpa": None,
            "secondary_gpa": None,
            "secondary_country": None,
            "courses": [],
            "tests": [],
            "documents": [],
            "enrollments": [],
        }

    enrollments: List[EnrollmentRecord] = list(profile.enrollments or [])
    citizenships: List[CitizenshipRecord] = list(profile.citizenships or [])
    tests: List[StandardizedTest] = list(profile.standardized_tests or [])
    documents: List[Document] = [
        d for d in (profile.documents or [])
        if not d.is_archived and getattr(d, "scan_status", "scan_clean") == "scan_clean"
    ]

    courses: List[Course] = []
    for enr in enrollments:
        courses.extend(enr.courses or [])

    citizen_codes = {c.country_code.strip().upper() for c in citizenships if c.country_code}
    pr_codes = {
        c.country_code.strip().upper()
        for c in citizenships
        if c.country_code and c.citizenship_type == "permanent_resident"
    }
    res_country = profile.country_of_residence.strip().upper() if profile.country_of_residence else None
    res_status = (profile.residency_status or "").lower()

    secondary_enrs = [e for e in enrollments if e.enrollment_type == "secondary"]
    college_enrs = [e for e in enrollments if e.enrollment_type in ("community_college", "undergraduate")]

    secondary_country = (
        secondary_enrs[0].institution_country.strip().upper()
        if secondary_enrs and secondary_enrs[0].institution_country
        else None
    )

    # Determine international status relative to target university country (never guess if completely absent)
    tgt = target_country.strip().upper()
    is_intl: Optional[bool] = None
    if tgt in citizen_codes or tgt in pr_codes:
        is_intl = False
    elif "international" in applicant_type or "international" in res_status or "visa" in res_status or "f1" in res_status:
        is_intl = True
    elif citizen_codes:
        is_intl = tgt not in citizen_codes
    elif res_country:
        if res_country != tgt:
            is_intl = True
        elif "citizen" in res_status or "permanent" in res_status or "domestic" in res_status:
            is_intl = False
    elif profile.country_code and profile.country_code.strip().upper() != tgt:
        is_intl = True

    # Determine English proficiency requirement trigger
    edu_countries = {
        e.institution_country.strip().upper()
        for e in enrollments
        if e.institution_country
    }
    req_english: Optional[bool] = None
    if edu_countries:
        if edu_countries.issubset(ENGLISH_MAJORITY_COUNTRIES) and (is_intl is False or secondary_country in ENGLISH_MAJORITY_COUNTRIES):
            req_english = False
        elif not edu_countries.intersection(ENGLISH_MAJORITY_COUNTRIES):
            req_english = True
        elif secondary_country and secondary_country not in ENGLISH_MAJORITY_COUNTRIES:
            req_english = True
        else:
            req_english = False
    elif is_intl is True and res_country and res_country not in ENGLISH_MAJORITY_COUNTRIES:
        req_english = True
    elif is_intl is False and res_country in ENGLISH_MAJORITY_COUNTRIES:
        req_english = False

    # College credits (convert quarter credits to semester credits at 2/3)
    earned_credits: Optional[float] = None
    if college_enrs:
        explicit_sum = 0.0
        has_explicit = False
        for enr in college_enrs:
            if enr.total_credits_earned is not None:
                has_explicit = True
                explicit_sum += float(enr.total_credits_earned)
        if has_explicit:
            earned_credits = round(explicit_sum, 2)
        else:
            completed_course_credits = 0.0
            has_course_credits = False
            for enr in college_enrs:
                for c in (enr.courses or []):
                    if c.credit_hours is not None and c.status in ("completed", "in_progress"):
                        has_course_credits = True
                        factor = (2.0 / 3.0) if c.credit_type == "quarter_hour" else 1.0
                        completed_course_credits += float(c.credit_hours) * factor
            if has_course_credits:
                earned_credits = round(completed_course_credits, 2)

    # Estimate completed terms from distinct academic_term values or earned credits
    distinct_terms = {
        (c.academic_term or "").strip().lower()
        for enr in college_enrs
        for c in (enr.courses or [])
        if c.academic_term and c.status == "completed"
    }
    completed_terms: Optional[int] = len(distinct_terms) if distinct_terms else (
        int(earned_credits // 15) if earned_credits is not None else None
    )

    college_gpas = [float(e.cumulative_gpa) for e in college_enrs if e.cumulative_gpa is not None]
    secondary_gpas = [float(e.cumulative_gpa) for e in secondary_enrs if e.cumulative_gpa is not None]

    return {
        "has_profile": True,
        "is_international_for_target": is_intl,
        "requires_english_proficiency": req_english,
        "earned_college_credits": earned_credits,
        "completed_college_terms": completed_terms,
        "college_gpa": max(college_gpas) if college_gpas else None,
        "secondary_gpa": max(secondary_gpas) if secondary_gpas else None,
        "secondary_country": secondary_country,
        "citizen_countries": list(citizen_codes),
        "courses": courses,
        "tests": tests,
        "documents": documents,
        "enrollments": enrollments,
    }


def _evaluate_condition(cond: RequirementCondition, ctx: Dict[str, Any]) -> Tuple[Optional[bool], Optional[str]]:
    field_val = ctx.get(cond.condition_field)
    if field_val is None:
        return None, f"Profile missing '{cond.condition_field}' to verify conditional applicability."

    op = cond.condition_operator
    target = cond.condition_value
    matched = False
    if op == "equals":
        matched = field_val == target
    elif op == "not_equals":
        matched = field_val != target
    elif op == "in":
        matched = field_val in (target or [])
    elif op == "not_in":
        matched = field_val not in (target or [])
    elif op == "greater_than":
        matched = float(field_val) > float(target)
    elif op == "less_than":
        matched = float(field_val) < float(target)
    elif op == "between" and isinstance(target, list) and len(target) == 2:
        matched = float(target[0]) <= float(field_val) <= float(target[1])

    return matched, cond.explanation if matched else None


def _parse_first_float(text: Optional[str]) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None


def _match_prerequisites(req: InstitutionRequirement, courses: List[Course], ctx: Dict[str, Any]) -> Tuple[str, List[str], List[str], str]:
    tpl = req.template
    subtype = tpl.requirement_subtype or ""
    major = (req.program_name_filter or "").lower()

    if not courses:
        return (
            "needs_verification",
            [],
            [req.minimum_value or tpl.display_name],
            "No college coursework recorded on Universal Profile to audit prerequisites.",
        )

    course_labels = [
        f"{(c.course_code or '').lower()} {(c.course_name or '').lower()} {(c.department or '').lower()}".strip()
        for c in courses
    ]

    def has_any(patterns: List[str]) -> Optional[str]:
        for idx, lbl in enumerate(course_labels):
            if any(p in lbl for p in patterns):
                c = courses[idx]
                return f"{c.course_code or ''} {c.course_name} ({c.status})".strip()
        return None

    matched: List[str] = []
    missing: List[str] = []

    if subtype == "uc_seven_course_pattern":
        eng_matches = [
            f"{c.course_code or ''} {c.course_name}".strip()
            for idx, c in enumerate(courses)
            if any(p in course_labels[idx] for p in ["engl", "english", "writing", "composition", "rhetoric"])
        ]
        math_matches = [
            f"{c.course_code or ''} {c.course_name}".strip()
            for idx, c in enumerate(courses)
            if any(p in course_labels[idx] for p in ["math", "calc", "stat", "quantitative", "algebra"])
        ]
        breadth_matches = [
            f"{c.course_code or ''} {c.course_name}".strip()
            for idx, c in enumerate(courses)
            if any(
                p in course_labels[idx]
                for p in ["econ", "psych", "soc", "hist", "bio", "chem", "phys", "art", "phil", "pol", "anth", "cs", "comp"]
            )
        ]
        matched.extend(eng_matches[:2] + math_matches[:1] + breadth_matches[:4])
        if len(eng_matches) < 2:
            missing.append(f"English Composition ({len(eng_matches)}/2 courses matched)")
        if len(math_matches) < 1:
            missing.append("Mathematical Concepts / Quantitative Reasoning (0/1 matched)")
        if len(breadth_matches) < 4:
            missing.append(f"Breadth Courses across Humanities/Social/Physical Sciences ({len(breadth_matches)}/4 matched)")

    elif "econ" in major or "econ" in (req.minimum_value or "").lower():
        checks = [
            ("Microeconomics (ECON 1 equiv)", ["microecon", "econ 1", "econ1", "principles of micro"]),
            ("Macroeconomics (ECON 2 equiv)", ["macroecon", "econ 2", "econ2", "principles of macro"]),
            ("Calculus I (MATH 1A/16A equiv)", ["calculus i", "calculus 1", "calc 1", "math 1a", "math 16a", "single variable calculus"]),
            ("Calculus II (MATH 1B/16B equiv)", ["calculus ii", "calculus 2", "calc 2", "math 1b", "math 16b"]),
        ]
        for label, pats in checks:
            hit = has_any(pats)
            if hit:
                matched.append(hit)
            else:
                missing.append(label)

    elif "computer" in major or "cs 61" in (req.minimum_value or "").lower():
        checks = [
            ("Intro Programming / SICP (CS 61A equiv)", ["cs 61a", "intro to programming", "python", "computer science i", "cis 22a"]),
            ("Data Structures (CS 61B equiv)", ["data structures", "cs 61b", "cis 22c", "algorithms"]),
            ("Computer Architecture / Assembly (CS 61C equiv)", ["architecture", "assembly", "cs 61c", "machine structures"]),
            ("Calculus I & II", ["calculus", "math 1a", "math 1b"]),
            ("Linear Algebra / Discrete Math", ["linear algebra", "discrete math", "math 54"]),
        ]
        for label, pats in checks:
            hit = has_any(pats)
            if hit:
                matched.append(hit)
            else:
                missing.append(label)
    else:
        # Generic stem/major check (e.g. MIT)
        checks = [
            ("Calculus", ["calculus", "math 1"]),
            ("Physics", ["physics"]),
            ("Chemistry or Biology", ["chem", "bio"]),
        ]
        for label, pats in checks:
            hit = has_any(pats)
            if hit:
                matched.append(hit)
            else:
                missing.append(label)

    if not missing:
        return "completed", matched, [], "All required prerequisite areas matched on student coursework."
    if matched:
        return (
            "in_progress",
            matched,
            missing,
            f"Matched {len(matched)} course(s), but {len(missing)} prerequisite(s) remain outstanding.",
        )
    return (
        "missing",
        [],
        missing,
        "None of the required major prerequisites matched recorded coursework.",
    )


def evaluate_dynamic_checklist(
    db: Session,
    institution: Institution,
    profile: Optional[StudentProfile],
    applicant_type: Optional[str] = None,
    intended_major: Optional[str] = None,
    academic_year: str = "2026-2027",
) -> DynamicChecklistResponseSchema:
    """
    Compares a StudentProfile against verified institutional/program requirements and generates a
    personalized, non-fabricating checklist with missing documents, prerequisites, concerns, and next actions.
    """
    pathway = (applicant_type or (profile.applicant_type if profile else None) or "first_year").lower()
    if pathway == "undecided":
        pathway = "first_year"
    major = intended_major or (profile.intended_major if profile else None)

    summary = get_institution_admissions_summary(
        db=db,
        institution=institution,
        applicant_type=pathway,
        intended_major=major,
        academic_year=academic_year,
    )
    ctx = _extract_profile_context(profile, institution.country_code, pathway)
    today = date.today()

    # Load ORM requirements matching pathway & major so we have template + condition ORM fields
    req_query = db.query(InstitutionRequirement).filter(
        InstitutionRequirement.institution_id == institution.id,
        InstitutionRequirement.is_current == True,
        InstitutionRequirement.academic_year == academic_year,
        InstitutionRequirement.applicant_type.in_([pathway, f"international_{pathway}", "all"]),
    )
    reqs = req_query.order_by(InstitutionRequirement.created_at.asc()).all()
    if major:
        m_low = major.strip().lower()
        reqs = [
            r
            for r in reqs
            if not r.program_name_filter or r.program_name_filter.lower() in m_low or m_low in r.program_name_filter.lower()
        ]
    else:
        # Without major filter, keep general requirements first (program_name_filter is None) + tag any major ones
        reqs = [r for r in reqs if not r.program_name_filter]

    if not reqs:
        next_actions = []
        if institution.admissions_website:
            next_actions.append(f"Consult official admissions portal: {institution.admissions_website}")
        next_actions.append("Complete your Universal Student Profile and upload official transcripts before applying.")
        return DynamicChecklistResponseSchema(
            institution_id=institution.id,
            official_name=institution.official_name,
            country_code=institution.country_code,
            applicant_type=pathway,
            is_international_for_target=ctx["is_international_for_target"],
            intended_major=major,
            academic_year=academic_year,
            has_verified_requirements=False,
            eligibility_status="requirements_unverified",
            readiness_pct=0,
            summary_notice=summary.coverage_notice,
            upcoming_deadlines=summary.deadlines,
            next_actions=next_actions,
            applicable_qualifications=summary.country_qualifications,
        )

    completed_list: List[ChecklistItemEvaluationSchema] = []
    missing_docs: List[ChecklistItemEvaluationSchema] = []
    outstanding_prereqs: List[ChecklistItemEvaluationSchema] = []
    other_reqs: List[ChecklistItemEvaluationSchema] = []
    not_applicable_list: List[ChecklistItemEvaluationSchema] = []
    concerns: List[str] = []
    next_actions: List[str] = []

    for req in reqs:
        tpl = req.template
        title = req.title_override or tpl.display_name
        eff_imp = req.importance
        cond_notes: List[str] = []
        missing_cond_data = False

        if req.conditions:
            if not ctx["has_profile"]:
                missing_cond_data = True
                cond_notes.append("Sign in / complete Universal Profile to determine conditional applicability.")
            else:
                for cond in req.conditions:
                    matched, note = _evaluate_condition(cond, ctx)
                    if matched is None:
                        missing_cond_data = True
                        if note:
                            cond_notes.append(note)
                    elif matched:
                        eff_imp = cond.result_importance
                        if note:
                            cond_notes.append(note)

        if eff_imp in ("not_applicable", "not_accepted", "waived"):
            status_val = "not_applicable" if eff_imp != "waived" else "waived"
            item = ChecklistItemEvaluationSchema(
                requirement_id=req.id,
                title=title,
                category=tpl.category,
                requirement_type=tpl.requirement_type,
                program_name_filter=req.program_name_filter,
                original_importance=req.importance,
                effective_importance=eff_imp,
                status=status_val,
                explanation=" | ".join(cond_notes) if cond_notes else req.institution_specific_notes,
                minimum_value=req.minimum_value,
                maximum_value=req.maximum_value,
                auto_matched=True,
                source_name=req.source_name,
                source_url=req.source_url,
                verified_at=req.verified_at,
                verification_status=req.verification_status,
            )
            not_applicable_list.append(item)
            continue

        # Default item state
        item_status = "pending"
        explanation = req.institution_specific_notes or tpl.description
        sat_doc_id = None
        sat_field = None
        evidence: List[str] = []
        missing_items: List[str] = []
        auto_matched = False

        if missing_cond_data:
            item_status = "needs_verification"
            explanation = " | ".join(cond_notes)
        elif not ctx["has_profile"]:
            item_status = "needs_verification"
            explanation = "Universal Student Profile required to evaluate readiness."
        else:
            rtype = tpl.requirement_type
            # A. Document requirements
            if tpl.category in ("document", "financial"):
                allowed_cats = (tpl.profile_source_filter or {}).get("document_category", [])
                matching_docs = [d for d in ctx["documents"] if not allowed_cats or d.document_category in allowed_cats]
                subtype = tpl.requirement_subtype or ""

                # Distinguish secondary-level vs post-secondary transcripts cleanly
                def _is_secondary_doc(doc: Document) -> bool:
                    qual = (doc.extraction.detected_qualification if doc.extraction else None) or ""
                    inst_txt = (doc.extraction.detected_institution if doc.extraction else None) or ""
                    text = f"{doc.original_filename} {qual} {inst_txt}".lower()
                    sec_markers = ["baccalaureat", "baccalauréat", "high school", "high_school", "lycée", "lycee", "ns4", "abitur", "a-level"]
                    col_markers = ["college", "university", "université", "de anza", "undergraduate", "associate"]
                    return any(m in text for m in sec_markers) and not any(c in text for c in col_markers)

                secondary_only_note = None
                if subtype == "college_all" and matching_docs:
                    filtered = [d for d in matching_docs if not _is_secondary_doc(d)]
                    if not filtered:
                        secondary_only_note = "Uploaded transcript(s) appear to be secondary-level; upload official post-secondary college transcript(s)."
                    matching_docs = filtered
                elif subtype in ("high_school", "high_school_conditional") and matching_docs:
                    # Keep transcripts that are secondary or unlabelled, excluding obvious college-only files
                    def _is_college_only(doc: Document) -> bool:
                        qual = (doc.extraction.detected_qualification if doc.extraction else None) or ""
                        inst_txt = (doc.extraction.detected_institution if doc.extraction else None) or ""
                        text = f"{doc.original_filename} {qual} {inst_txt}".lower()
                        return any(m in text for m in ["college", "university", "de anza", "associate"]) and not any(
                            s in text for s in ["high school", "high_school", "baccalauréat", "baccalaureat", "lycée"]
                        )
                    matching_docs = [d for d in matching_docs if not _is_college_only(d)]

                needed_qty = req.quantity or 1
                if len(matching_docs) >= needed_qty:
                    item_status = "completed"
                    sat_doc_id = matching_docs[0].id
                    evidence = [d.original_filename for d in matching_docs[:needed_qty]]
                    auto_matched = True
                    explanation = f"Verified {len(matching_docs)} matching document(s) in Document Vault."
                elif len(matching_docs) > 0:
                    item_status = "in_progress"
                    sat_doc_id = matching_docs[0].id
                    evidence = [d.original_filename for d in matching_docs]
                    missing_items = [f"Need {needed_qty - len(matching_docs)} additional file(s)"]
                    auto_matched = True
                else:
                    item_status = "missing"
                    missing_items = [title]
                    if secondary_only_note:
                        explanation = secondary_only_note
                    next_actions.append(f"Upload {title} to Document Vault.")

            # B. Minimum GPA
            elif rtype == "minimum_gpa":
                min_gpa = _parse_first_float(req.minimum_value)
                is_pct_rule = bool(req.minimum_value and "%" in req.minimum_value)
                student_gpa = ctx["college_gpa"] if pathway == "transfer" else ctx["secondary_gpa"]
                if student_gpa is None:
                    item_status = "needs_verification"
                    explanation = f"No {'college' if pathway == 'transfer' else 'secondary'} GPA recorded on profile (required: {req.minimum_value})."
                    concerns.append(f"GPA missing: unable to verify {req.minimum_value} minimum.")
                elif is_pct_rule and student_gpa <= 4.5:
                    item_status = "needs_verification"
                    explanation = f"Profile GPA {student_gpa} is on a 4.0-style scale; manual verification needed against {req.minimum_value} percentage rule."
                elif min_gpa is not None and student_gpa >= min_gpa:
                    item_status = "completed"
                    sat_field = "enrollments.cumulative_gpa"
                    evidence = [f"Recorded GPA: {student_gpa:.2f} (min {req.minimum_value})"]
                    auto_matched = True
                elif min_gpa is not None:
                    item_status = "missing"
                    missing_items = [f"GPA {student_gpa:.2f} below {req.minimum_value} minimum"]
                    concerns.append(f"GPA Concern: recorded GPA {student_gpa:.2f} is below required {req.minimum_value}.")
                    explanation = f"Recorded GPA {student_gpa:.2f} does not meet minimum {req.minimum_value}."

            # C. Minimum Transfer Credits / Terms
            elif rtype == "minimum_credits":
                is_terms = bool(req.minimum_value and "term" in req.minimum_value.lower())
                req_num = _parse_first_float(req.minimum_value)
                val = ctx["completed_college_terms"] if is_terms else ctx["earned_college_credits"]
                unit_lbl = "term(s)" if is_terms else "semester units"
                if val is None:
                    item_status = "needs_verification"
                    explanation = f"No college credits/terms recorded on profile (required: {req.minimum_value})."
                    concerns.append(f"Transfer credits missing: unable to verify {req.minimum_value} requirement.")
                elif req_num is not None and val >= req_num:
                    item_status = "completed"
                    sat_field = "enrollments.total_credits_earned"
                    evidence = [f"{val:g} {unit_lbl} verified (min {req.minimum_value})"]
                    auto_matched = True
                elif req_num is not None:
                    item_status = "in_progress"
                    evidence = [f"{val:g} {unit_lbl} currently recorded"]
                    missing_items = [f"Remaining: {req_num - val:.1f} {unit_lbl}"]
                    concerns.append(f"Transfer Credit Progress: {val:g} {unit_lbl} recorded vs. {req.minimum_value} required before entry.")
                    next_actions.append(f"Plan remaining {req_num - val:.1f} transferable {unit_lbl} prior to matriculation.")

            # D. Prerequisite Coursework & 7-Course Pattern
            elif rtype in ("prerequisite_courses", "specific_coursework"):
                item_status, evidence, missing_items, explanation = _match_prerequisites(req, ctx["courses"], ctx)
                if item_status == "completed":
                    sat_field = "courses"
                    auto_matched = True
                elif item_status in ("missing", "in_progress"):
                    concerns.append(f"Prerequisite Gap ({title}): {', '.join(missing_items)}")
                    next_actions.append(f"Complete missing prerequisites for {title}: {', '.join(missing_items)}")
                elif item_status == "needs_verification":
                    concerns.append(f"Coursework Missing: add college courses to audit {title}.")

            # E. Exams & Proficiency Tests
            elif tpl.category == "exam" or rtype in ("standardized_test", "english_proficiency", "language_proficiency", "national_exam"):
                allowed_tests = {t.upper() for t in (tpl.profile_source_filter or {}).get("test_type", [])}
                matched_tests = [t for t in ctx["tests"] if t.test_type.upper() in allowed_tests]
                if matched_tests:
                    item_status = "completed"
                    sat_field = "standardized_tests"
                    evidence = [f"{t.test_type}: {t.total_score or 'Recorded'}" for t in matched_tests]
                    auto_matched = True
                    explanation = "Matching examination record found on Universal Profile."
                else:
                    item_status = "missing"
                    missing_items = [title]
                    if rtype in ("standardized_test", "english_proficiency", "national_exam"):
                        next_actions.append(f"Add or upload score for {title} ({req.minimum_value or 'official score'}).")

            # F. Secondary Qualification / Associate / Academic Standing / Administrative
            elif rtype == "secondary_qualification":
                sec = [e for e in ctx["enrollments"] if e.enrollment_type == "secondary"]
                if sec:
                    item_status = "completed"
                    sat_field = "enrollments"
                    evidence = [sec[0].degree_type or sec[0].institution_name_manual or "Secondary enrollment recorded"]
                    auto_matched = True
                else:
                    item_status = "needs_verification"
                    missing_items = ["Secondary education record"]
                    next_actions.append("Add secondary/high school qualification details to Universal Profile.")

            elif rtype == "associate_degree":
                cc = [e for e in ctx["enrollments"] if e.enrollment_type == "community_college"]
                if cc:
                    item_status = "in_progress" if cc[0].enrollment_status == "current" else "completed"
                    sat_field = "enrollments"
                    evidence = [cc[0].degree_type or "Community College pathway recorded"]
                    auto_matched = True
                else:
                    item_status = "pending"

            elif rtype == "academic_standing":
                standings = [e.academic_standing for e in ctx["enrollments"] if e.academic_standing]
                if standings and all("good" in s.lower() for s in standings):
                    item_status = "completed"
                    sat_field = "enrollments.academic_standing"
                    evidence = standings
                    auto_matched = True
                else:
                    item_status = "needs_verification"
                    explanation = "Confirm good academic standing in Universal Profile enrollment records."
            else:
                # Administrative form / fee
                item_status = "pending"
                if req.fee_amount is not None:
                    explanation = f"Application fee: {req.fee_amount:g} {req.fee_currency or ''} ({'Waiver available' if req.fee_waiver_available else 'No waiver specified'}). {req.institution_specific_notes or ''}".strip()

        evaluated = ChecklistItemEvaluationSchema(
            requirement_id=req.id,
            title=title,
            category=tpl.category,
            requirement_type=tpl.requirement_type,
            program_name_filter=req.program_name_filter,
            original_importance=req.importance,
            effective_importance=eff_imp,
            status=item_status,
            explanation=" | ".join(cond_notes) if (cond_notes and item_status != "needs_verification") else explanation,
            minimum_value=req.minimum_value,
            maximum_value=req.maximum_value,
            satisfied_by_document_id=sat_doc_id,
            satisfied_by_profile_field=sat_field,
            matched_evidence=evidence,
            missing_items=missing_items,
            auto_matched=auto_matched,
            source_name=req.source_name,
            source_url=req.source_url,
            verified_at=req.verified_at,
            verification_status=req.verification_status,
        )

        if item_status == "completed":
            completed_list.append(evaluated)
        elif tpl.category in ("document", "financial") and item_status in ("missing", "in_progress", "needs_verification"):
            missing_docs.append(evaluated)
        elif tpl.requirement_type in ("prerequisite_courses", "specific_coursework", "minimum_credits", "minimum_gpa") and item_status != "completed":
            outstanding_prereqs.append(evaluated)
        else:
            other_reqs.append(evaluated)

    # Compute Readiness & Strict Eligibility Status (never mark eligible with missing/unverified required info!)
    all_active = completed_list + missing_docs + outstanding_prereqs + other_reqs
    required_active = [
        x for x in all_active if x.effective_importance in ("required", "strongly_recommended")
    ]
    completed_req_count = sum(1 for x in required_active if x.status == "completed")
    readiness_pct = int(round((completed_req_count / len(required_active)) * 100)) if required_active else 0

    has_needs_verif = any(x.status == "needs_verification" for x in required_active)
    has_missing = any(x.status == "missing" for x in required_active)
    has_in_prog = any(x.status in ("in_progress", "pending") for x in required_active)

    if concerns or has_missing:
        elig_status = "concerns_identified"
    elif has_needs_verif:
        elig_status = "needs_information"
    elif has_in_prog:
        elig_status = "in_progress"
    else:
        elig_status = "eligible_preliminary"

    # Sort deadlines & check upcoming urgencies
    upcoming_dls = sorted(
        summary.deadlines,
        key=lambda d: (d.deadline_date is None, d.deadline_date or date.max),
    )
    for d in upcoming_dls:
        if d.days_remaining is not None and 0 <= d.days_remaining <= 45:
            next_actions.insert(0, f"Upcoming deadline in {d.days_remaining} days: {d.intake_term} ({d.deadline_date}).")

    # Country qualifications relevant to BOTH student origin & target institution
    qual_countries = {institution.country_code}
    if ctx["secondary_country"]:
        qual_countries.add(ctx["secondary_country"])
    for cc in (ctx.get("citizen_countries") or []):
        qual_countries.add(cc)

    app_quals = (
        db.query(CountryQualification)
        .filter(CountryQualification.country_code.in_(list(qual_countries)))
        .order_by(CountryQualification.country_code.asc())
        .all()
    )

    return DynamicChecklistResponseSchema(
        institution_id=institution.id,
        official_name=institution.official_name,
        country_code=institution.country_code,
        applicant_type=pathway,
        is_international_for_target=ctx["is_international_for_target"],
        intended_major=major,
        academic_year=academic_year,
        has_verified_requirements=True,
        eligibility_status=elig_status,
        readiness_pct=readiness_pct,
        summary_notice=None,
        completed_requirements=completed_list,
        missing_documents=missing_docs,
        outstanding_prerequisites=outstanding_prereqs,
        other_requirements=other_reqs,
        not_applicable_requirements=not_applicable_list,
        eligibility_concerns=list(dict.fromkeys(concerns)),
        upcoming_deadlines=upcoming_dls,
        next_actions=list(dict.fromkeys(next_actions)),
        applicable_qualifications=[CountryQualificationSchema.model_validate(q) for q in app_quals],
    )
