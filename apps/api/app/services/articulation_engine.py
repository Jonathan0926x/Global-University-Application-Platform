"""
3-Tier Transfer Articulation & Degree Applicability Intelligence Engine (Milestone 4).

Strict Non-Fabrication & Academic Honesty Rules:
1. Tier 1 (Officially Verified) strictly requires an official DB CourseEquivalency row.
2. Tier 2 (Historically Observed) strictly requires a historical DB CourseEquivalency row.
3. Tier 3 (AI-Predicted) compares course description, learning outcomes, subject, academic level,
   and normalized credits using pgvector / local cosine embeddings — always labeled as AI-Predicted
   and NEVER represented as an official institutional decision.
4. Never equates total accepted transfer credits with credits counting toward graduation.
5. Preserves original international/domestic credit systems alongside informational semester conversions.
6. Detects duplicate coursework and flags unverified courses missing syllabi/descriptions.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

from app.ingestion.articulation_seed import normalize_course_code
from app.models.articulation import CourseCatalog, CourseEquivalency
from app.models.course import Course
from app.models.document import Document
from app.models.enrollment import EnrollmentRecord
from app.models.institution import Institution
from app.models.profile import StudentProfile
from app.schemas.articulation import (
    AdHocCourseEquivalencyRequest,
    DegreeApplicabilitySummary,
    EvaluatedCourseResult,
)
from app.services.embeddings import cosine_similarity, embed_text


CREDIT_TO_SEMESTER_FACTOR: Dict[str, float] = {
    "us_semester": 1.0,
    "semester_hour": 1.0,
    "us_quarter": 2.0 / 3.0,
    "quarter_hour": 2.0 / 3.0,
    "ects": 0.5,        # Informational heuristic: 60 ECTS ≈ 30 US semester credits
    "uk_cat": 0.25,     # Informational heuristic: 120 CATS ≈ 30 US semester credits
    "ca_credit": 6.0,   # Informational UofT FCE heuristic: 1.0 FCE ≈ 6 US semester credits
    "unit": 1.0,
    "other": 1.0,
}

CREDIT_SYSTEM_LABELS: Dict[str, str] = {
    "us_semester": "US Semester Hours",
    "semester_hour": "US Semester Hours",
    "us_quarter": "US Quarter Units",
    "quarter_hour": "US Quarter Units",
    "ects": "European ECTS",
    "uk_cat": "UK CATS Credits",
    "ca_credit": "Canadian FCE Credits",
    "unit": "Institutional Units",
    "other": "National/Other Credits",
}

TIER_LABELS = {
    1: "Officially Verified",
    2: "Historically Observed",
    3: "AI-Predicted (Unverified)",
}

DISCLAIMER_OFFICIAL = (
    "Officially articulated per published institutional / ASSIST agreement; confirm catalog year and grade minimums with receiving registrar."
)
DISCLAIMER_HISTORICAL = (
    "Historically observed transfer outcome — NOT a binding guarantee; subject to receiving university confirmation."
)
DISCLAIMER_AI = (
    "AI-predicted content similarity match — NOT an official university credit decision. Official transfer evaluation is made solely by the receiving institution."
)
DISCLAIMER_UNVERIFIED = (
    "Insufficient official/historical agreement or syllabus detail; upload an official course syllabus or description for Tier 3 content comparison."
)


def normalize_to_semester_credits(value: Optional[float], system: str) -> Optional[float]:
    if value is None:
        return None
    factor = CREDIT_TO_SEMESTER_FACTOR.get((system or "us_semester").lower(), 1.0)
    return round(float(value) * factor, 2)


def _canonical_credit_system(system: Optional[str], inst: Optional[Institution] = None) -> str:
    s = (system or "").lower()
    if s in ("semester_hour", "us_semester"):
        return "us_semester"
    if s in ("quarter_hour", "us_quarter"):
        return "us_quarter"
    if s in ("ects", "uk_cat", "ca_credit", "unit"):
        return s
    if inst:
        if inst.calendar_system == "quarter":
            return "us_quarter"
        if inst.country_code in ("DE", "FR"):
            return "ects"
        if inst.country_code == "GB":
            return "uk_cat"
        if inst.country_code == "CA":
            return "ca_credit"
    return "us_semester"


def _infer_level(code: str, level_hint: Optional[str]) -> str:
    if level_hint:
        hl = level_hint.lower()
        if any(x in hl for x in ["300", "400", "upper"]):
            return "upper"
        if any(x in hl for x in ["100", "200", "lower", "ap", "ib", "bac"]):
            return "lower"
    m = re.search(r"(\d{2,3})", code or "")
    if m:
        num = int(m.group(1))
        if num >= 300:
            return "upper"
    return "lower"


def _infer_subject(text: str) -> Optional[str]:
    low = (text or "").lower()
    if any(k in low for k in ["calc", "math", "linear algebra", "discrete", "stat"]):
        return "mathematics"
    if any(k in low for k in ["computer", "cis ", "csc ", "cs ", "data structures", "programming", "algorithm", "software", "informatik", "programmation"]):
        return "computer_science"
    if any(k in low for k in ["econ", "macro", "micro", "économie"]):
        return "economics"
    if any(k in low for k in ["ewrt", "engl", "writing", "composition", "rhetoric"]):
        return "english_composition"
    if any(k in low for k in ["phys", "mechanics", "electromagnetism", "physique"]):
        return "physics"
    if any(k in low for k in ["biol", "biology", "genetics"]):
        return "biology"
    if any(k in low for k in ["art ", "histart", "history", "psych", "phil", "sociol"]):
        return "humanities"
    return None


def _resolve_enrollment_institution(db: Session, enr: EnrollmentRecord) -> Optional[Institution]:
    if enr.institution_id:
        return db.query(Institution).filter(Institution.id == enr.institution_id).first()
    name = (enr.institution_name_manual or "").strip()
    if not name:
        return None
    clean = name.split(",")[0].strip()
    inst = db.query(Institution).filter(Institution.official_name.ilike(clean)).first()
    if inst:
        return inst
    return db.query(Institution).filter(Institution.official_name.ilike(f"%{clean}%")).first()


def _determine_applicability(
    eq_major_req: bool,
    eq_ge_req: bool,
    eq_elective_only: bool,
    eq_type: str,
    programs: List[str],
    intended_major: Optional[str],
) -> Tuple[str, bool]:
    """
    Distinguishes major-applicable, GE-applicable, elective-only, and non-applicable credits.
    Returns (applicability_bucket, satisfies_intended_major).
    """
    if eq_type == "no_equivalent":
        return "non_applicable", False

    major_matches = False
    if eq_major_req:
        if not intended_major or not programs or "All" in programs:
            major_matches = True
        else:
            m_low = intended_major.strip().lower()
            major_matches = any(p.lower() in m_low or m_low in p.lower() for p in programs)

    if major_matches and eq_ge_req:
        return "major_and_ge", True
    if major_matches:
        return "major", True
    if eq_ge_req:
        return "ge", False
    if eq_elective_only or eq_type == "elective_only":
        return "elective_only", False
    return "elective_only", False


def _score_tier3_candidate(
    src_text: str,
    src_sem_credits: Optional[float],
    src_level: str,
    src_subject: Optional[str],
    candidate: CourseCatalog,
) -> Tuple[float, str]:
    cand_text = " ".join(
        [
            candidate.course_code,
            candidate.course_name,
            candidate.department or "",
            candidate.description or "",
            " ".join(candidate.learning_outcomes or []),
        ]
    )
    src_vec = embed_text(src_text)
    cand_vec = list(candidate.description_embedding) if candidate.description_embedding is not None else embed_text(cand_text)
    sem_sim = cosine_similarity(src_vec, cand_vec)

    cand_sem = normalize_to_semester_credits(
        float(candidate.credit_hours) if candidate.credit_hours is not None else None,
        candidate.credit_system,
    )
    credit_score = 0.0
    if src_sem_credits is not None and cand_sem is not None:
        diff = abs(src_sem_credits - cand_sem)
        if diff <= 0.8:
            credit_score = 1.0
        elif diff <= 1.5:
            credit_score = 0.6
        else:
            credit_score = 0.2
    else:
        credit_score = 0.5  # neutral when target/source credits unspecified

    cand_level = _infer_level(candidate.course_code, candidate.course_level)
    level_score = 1.0 if src_level == cand_level else 0.3

    subj_score = 0.0
    if src_subject and candidate.subject_area:
        subj_score = 1.0 if src_subject == candidate.subject_area else 0.0
    elif src_subject and candidate.department:
        subj_score = 0.8 if src_subject.split("_")[0] in candidate.department.lower() else 0.0

    # Strict subject guard: never cross-match math to humanities, etc.
    if src_subject and candidate.subject_area and src_subject != candidate.subject_area:
        subj_penalty = 0.5
    else:
        subj_penalty = 1.0

    weighted = (sem_sim * 0.50 + credit_score * 0.20 + level_score * 0.15 + subj_score * 0.15) * subj_penalty
    final_score = round(min(0.95, weighted), 3)
    evidence = (
        f"Content/outcome cosine similarity={sem_sim:.2f}, normalized credits={src_sem_credits} vs {cand_sem}, "
        f"subject={src_subject or 'general'}->{candidate.subject_area or 'general'}, level={src_level}->{cand_level}."
    )
    return final_score, evidence


def evaluate_course_against_target(
    db: Session,
    target_inst: Institution,
    source_inst: Optional[Institution],
    source_inst_name: Optional[str],
    course_code: str,
    course_name: str,
    description: Optional[str],
    learning_outcomes: List[str],
    original_credits: Optional[float],
    original_credit_system: str,
    course_level: Optional[str],
    department: Optional[str],
    intended_major: Optional[str] = None,
    syllabus_document_id: Optional[UUID] = None,
    student_course_id: Optional[UUID] = None,
) -> EvaluatedCourseResult:
    norm_code = normalize_course_code(course_code)
    canon_sys = _canonical_credit_system(original_credit_system, source_inst)
    norm_sem = normalize_to_semester_credits(original_credits, canon_sys)

    # 1. Check Tier 1 (Officially Verified) and Tier 2 (Historically Observed) when sending institution is known
    if source_inst is not None and norm_code:
        eq_candidates = (
            db.query(CourseEquivalency)
            .filter(
                CourseEquivalency.source_institution_id == source_inst.id,
                CourseEquivalency.target_institution_id == target_inst.id,
                CourseEquivalency.is_current == True,
                CourseEquivalency.equivalency_tier.in_([1, 2]),
            )
            .order_by(CourseEquivalency.equivalency_tier.asc())
            .all()
        )
        matched_eq = next(
            (e for e in eq_candidates if normalize_course_code(e.source_course_code) == norm_code),
            None,
        )
        if matched_eq:
            tier = matched_eq.equivalency_tier
            bucket, sat_major = _determine_applicability(
                matched_eq.satisfies_major_requirement,
                matched_eq.satisfies_ge_requirement,
                matched_eq.elective_only,
                matched_eq.equivalency_type,
                list(matched_eq.applies_to_degree_programs or []),
                intended_major,
            )
            # If credits_transferable specified on DB equivalency, respect it; else use norm_sem
            trans_cred = (
                float(matched_eq.credits_transferable)
                if matched_eq.credits_transferable is not None
                else (norm_sem or 0.0)
            )
            return EvaluatedCourseResult(
                student_course_id=student_course_id,
                source_institution_name=source_inst.official_name,
                source_course_code=course_code,
                source_course_name=course_name,
                original_credits=original_credits,
                original_credit_system=canon_sys,
                normalized_semester_credits=norm_sem,
                credits_transferable=trans_cred,
                equivalency_tier=tier,
                tier_label=TIER_LABELS[tier],
                equivalency_type=matched_eq.equivalency_type,
                confidence_score=float(matched_eq.confidence_score or (1.0 if tier == 1 else 0.85)),
                target_course_code=matched_eq.target_course_code,
                target_course_name=matched_eq.target_course_name,
                applicability_bucket=bucket,
                satisfies_major_requirement=sat_major,
                satisfies_ge_requirement=matched_eq.satisfies_ge_requirement,
                ge_category=matched_eq.ge_category,
                satisfies_prerequisite=matched_eq.satisfies_prerequisite and (sat_major or matched_eq.satisfies_ge_requirement or not intended_major),
                elective_only=matched_eq.elective_only,
                syllabus_document_id=syllabus_document_id,
                supporting_evidence=matched_eq.supporting_evidence or f"Published {TIER_LABELS[tier]} mapping ({matched_eq.source_name}).",
                disclaimer=DISCLAIMER_OFFICIAL if tier == 1 else DISCLAIMER_HISTORICAL,
                source_name=matched_eq.source_name,
                source_url=matched_eq.source_url,
                verified_at=matched_eq.verified_at,
            )

    # 2. Check if course has enough content / syllabus for Tier 3 AI Content Matching
    # Look up official catalog course description if student didn't enter one
    catalog_desc = description
    catalog_outcomes = list(learning_outcomes or [])
    if source_inst is not None and not catalog_desc and norm_code:
        src_cat = (
            db.query(CourseCatalog)
            .filter(
                CourseCatalog.institution_id == source_inst.id,
                CourseCatalog.normalized_code == norm_code,
            )
            .first()
        )
        if src_cat:
            catalog_desc = src_cat.description
            catalog_outcomes = catalog_outcomes or list(src_cat.learning_outcomes or [])

    has_syllabus_content = bool(
        (catalog_desc and len(catalog_desc.strip()) >= 15)
        or len(catalog_outcomes) > 0
        or syllabus_document_id is not None
    )

    if not has_syllabus_content:
        return EvaluatedCourseResult(
            student_course_id=student_course_id,
            source_institution_name=source_inst.official_name if source_inst else source_inst_name,
            source_course_code=course_code,
            source_course_name=course_name,
            original_credits=original_credits,
            original_credit_system=canon_sys,
            normalized_semester_credits=norm_sem,
            credits_transferable=0.0,
            equivalency_tier=None,
            tier_label="Unverified",
            equivalency_type="unverified",
            confidence_score=0.0,
            applicability_bucket="unverified",
            requires_syllabus=True,
            syllabus_document_id=syllabus_document_id,
            supporting_evidence=(
                "No published Tier 1/2 agreement found and no course syllabus or description was provided. "
                "Upload a syllabus or add course description/learning outcomes to enable Tier 3 content comparison."
            ),
            disclaimer=DISCLAIMER_UNVERIFIED,
        )

    # 3. Tier 3 AI-Predicted Content, Learning Outcomes & Credit-Level Matching
    target_catalog = (
        db.query(CourseCatalog)
        .filter(CourseCatalog.institution_id == target_inst.id)
        .all()
    )
    src_text = " ".join(
        [
            course_code,
            course_name,
            department or "",
            catalog_desc or "",
            " ".join(catalog_outcomes),
        ]
    )
    src_level = _infer_level(course_code, course_level)
    src_subject = _infer_subject(src_text)

    best_cand: Optional[CourseCatalog] = None
    best_score = 0.0
    best_evidence = ""

    for cand in target_catalog:
        score, evidence = _score_tier3_candidate(src_text, norm_sem, src_level, src_subject, cand)
        if score > best_score:
            best_score = score
            best_cand = cand
            best_evidence = evidence

    if best_cand and best_score >= 0.45:
        subj = best_cand.subject_area
        sat_ge = subj in ("english_composition", "mathematics", "physics", "biology", "economics", "humanities")
        sat_major = bool(
            intended_major
            and (
                ("econ" in intended_major.lower() and subj in ("economics", "mathematics"))
                or ("computer" in intended_major.lower() and subj in ("computer_science", "mathematics"))
            )
        )
        bucket = (
            "major_and_ge"
            if (sat_major and sat_ge)
            else "major"
            if sat_major
            else "ge"
            if sat_ge
            else "elective_only"
        )
        est_credits = norm_sem if norm_sem is not None else (float(best_cand.credit_hours) if best_cand.credit_hours else 0.0)
        return EvaluatedCourseResult(
            student_course_id=student_course_id,
            source_institution_name=source_inst.official_name if source_inst else source_inst_name,
            source_course_code=course_code,
            source_course_name=course_name,
            original_credits=original_credits,
            original_credit_system=canon_sys,
            normalized_semester_credits=norm_sem,
            credits_transferable=round(est_credits, 2),
            equivalency_tier=3,
            tier_label=TIER_LABELS[3],
            equivalency_type="partial" if best_score < 0.72 else "direct",
            confidence_score=best_score,
            target_course_code=best_cand.course_code,
            target_course_name=best_cand.course_name,
            applicability_bucket=bucket,
            satisfies_major_requirement=sat_major,
            satisfies_ge_requirement=sat_ge,
            ge_category=f"Predicted {subj.replace('_', ' ').title()}" if sat_ge and subj else None,
            satisfies_prerequisite=sat_major,
            elective_only=(bucket == "elective_only"),
            requires_syllabus=False,
            syllabus_document_id=syllabus_document_id,
            supporting_evidence=f"AI Tier 3 match ({best_score:.2f}): {best_evidence}",
            disclaimer=DISCLAIMER_AI,
            source_name=f"UniGlobe Tier 3 Content Engine vs. {best_cand.source_name}",
            source_url=best_cand.source_url,
        )

    return EvaluatedCourseResult(
        student_course_id=student_course_id,
        source_institution_name=source_inst.official_name if source_inst else source_inst_name,
        source_course_code=course_code,
        source_course_name=course_name,
        original_credits=original_credits,
        original_credit_system=canon_sys,
        normalized_semester_credits=norm_sem,
        credits_transferable=0.0,
        equivalency_tier=None,
        tier_label="Unverified",
        equivalency_type="no_equivalent",
        confidence_score=best_score,
        applicability_bucket="unverified",
        requires_syllabus=False,
        syllabus_document_id=syllabus_document_id,
        supporting_evidence=(
            f"Evaluated against {target_inst.official_name} catalog; best content similarity ({best_score:.2f}) fell below threshold "
            "or target course catalog is not yet indexed."
        ),
        disclaimer=DISCLAIMER_UNVERIFIED,
    )


def evaluate_student_transfer_profile(
    db: Session,
    profile: Optional[StudentProfile],
    target_inst: Institution,
    intended_major: Optional[str] = None,
) -> DegreeApplicabilitySummary:
    """
    Evaluates all post-secondary coursework in a student's Universal Profile against a receiving
    institution, computing separate totals for accepted units vs. major/GE graduation applicability.
    """
    major = intended_major or (profile.intended_major if profile else None)
    summary = DegreeApplicabilitySummary(
        target_institution_id=target_inst.id,
        target_institution_name=target_inst.official_name,
        intended_major=major,
        disclaimer=(
            "Informational 3-Tier Transfer Intelligence Assessment. Official credit acceptance and degree "
            "applicability are determined solely by the receiving institution's registrar and academic department."
        ),
    )

    if not profile or not profile.enrollments:
        summary.warnings.append("No college enrollment or coursework records found on Universal Profile.")
        return summary

    college_enrs = [
        e for e in profile.enrollments if e.enrollment_type in ("community_college", "undergraduate")
    ]
    if not college_enrs:
        summary.warnings.append("No post-secondary college enrollments recorded; add college coursework to evaluate transfer credits.")
        return summary

    seen_courses = set()
    credits_by_sys: Dict[str, float] = {}
    ge_set: List[str] = []
    major_sat: List[str] = []
    intl_systems_used: List[str] = []

    for enr in college_enrs:
        src_inst = _resolve_enrollment_institution(db, enr)
        src_name = src_inst.official_name if src_inst else enr.institution_name_manual

        for c in (enr.courses or []):
            if c.status not in ("completed", "in_progress"):
                continue

            canon_sys = _canonical_credit_system(c.credit_type, src_inst)
            orig_cred = float(c.credit_hours) if c.credit_hours is not None else None
            norm_sem = normalize_to_semester_credits(orig_cred, canon_sys)

            if canon_sys not in ("us_semester", "us_quarter") and canon_sys not in intl_systems_used:
                intl_systems_used.append(CREDIT_SYSTEM_LABELS.get(canon_sys, canon_sys))

            dedup_key = (
                str(src_inst.id) if src_inst else (src_name or "").lower(),
                normalize_course_code(c.course_code or c.course_name),
            )
            is_dup = dedup_key in seen_courses
            seen_courses.add(dedup_key)

            # Pull extracted text/outcomes from attached syllabus document if course description is empty
            desc_txt = c.description
            outcomes_list = list(c.learning_outcomes or [])
            if c.syllabus_document_id and (not desc_txt or not outcomes_list):
                doc = db.query(Document).filter(Document.id == c.syllabus_document_id).first()
                if doc and doc.extraction:
                    if not desc_txt:
                        desc_txt = doc.extraction.extracted_text[:1200]
                    ext_json = doc.extraction.extracted_data_json or {}
                    if not outcomes_list and isinstance(ext_json.get("learning_outcomes"), list):
                        outcomes_list = ext_json["learning_outcomes"]

            ev = evaluate_course_against_target(
                db=db,
                target_inst=target_inst,
                source_inst=src_inst,
                source_inst_name=src_name,
                course_code=c.course_code or "UNLISTED",
                course_name=c.course_name,
                description=desc_txt,
                learning_outcomes=outcomes_list,
                original_credits=orig_cred,
                original_credit_system=canon_sys,
                course_level=c.course_level,
                department=c.department,
                intended_major=major,
                syllabus_document_id=c.syllabus_document_id,
                student_course_id=c.id,
            )

            if is_dup:
                ev.is_duplicate = True
                ev.credits_transferable = 0.0
                ev.applicability_bucket = "non_applicable"
                ev.satisfies_major_requirement = False
                ev.satisfies_ge_requirement = False
                ev.supporting_evidence = f"Duplicate coursework detected ({c.course_code or c.course_name}); excluded from transferable credit totals."
                summary.duplicate_course_count += 1
                summary.non_applicable_or_duplicate_credits = round(
                    summary.non_applicable_or_duplicate_credits + (norm_sem or 0.0), 2
                )
                summary.warnings.append(f"Duplicate course '{c.course_code or c.course_name}' excluded from double-counting.")
            else:
                if orig_cred is not None:
                    credits_by_sys[canon_sys] = round(credits_by_sys.get(canon_sys, 0.0) + orig_cred, 2)
                if norm_sem is not None:
                    summary.normalized_semester_credits_attempted = round(
                        summary.normalized_semester_credits_attempted + norm_sem, 2
                    )

                if ev.equivalency_tier == 1:
                    summary.officially_verified_count += 1
                    summary.officially_transferable_credits = round(
                        summary.officially_transferable_credits + ev.credits_transferable, 2
                    )
                elif ev.equivalency_tier == 2:
                    summary.historically_observed_count += 1
                    summary.potentially_transferable_credits = round(
                        summary.potentially_transferable_credits + ev.credits_transferable, 2
                    )
                elif ev.equivalency_tier == 3:
                    summary.ai_predicted_count += 1
                    summary.potentially_transferable_credits = round(
                        summary.potentially_transferable_credits + ev.credits_transferable, 2
                    )
                else:
                    summary.unverified_course_count += 1
                    if norm_sem:
                        summary.unverified_credits = round(summary.unverified_credits + norm_sem, 2)
                    if ev.requires_syllabus:
                        summary.missing_syllabus_count += 1

                # Separate Degree Applicability accounting
                if ev.satisfies_major_requirement:
                    summary.major_applicable_credits = round(
                        summary.major_applicable_credits + ev.credits_transferable, 2
                    )
                    lbl = f"{ev.target_course_code or ev.source_course_code}: {ev.target_course_name or ev.source_course_name}"
                    if lbl not in major_sat:
                        major_sat.append(lbl)
                if ev.satisfies_ge_requirement:
                    summary.ge_applicable_credits = round(
                        summary.ge_applicable_credits + ev.credits_transferable, 2
                    )
                    if ev.ge_category and ev.ge_category not in ge_set:
                        ge_set.append(ev.ge_category)
                if ev.applicability_bucket == "elective_only":
                    summary.elective_only_credits = round(
                        summary.elective_only_credits + ev.credits_transferable, 2
                    )
                elif ev.applicability_bucket == "non_applicable":
                    summary.non_applicable_or_duplicate_credits = round(
                        summary.non_applicable_or_duplicate_credits + (norm_sem or 0.0), 2
                    )

            summary.total_courses_evaluated += 1
            summary.evaluated_courses.append(ev)

    if intl_systems_used:
        summary.warnings.append(
            f"International/non-US credit system(s) detected ({', '.join(intl_systems_used)}). "
            "Normalized US semester conversions shown alongside original credits are informational approximations; "
            "formal academic equivalency requires receiving-institution or NACES/WES evaluation."
        )
    if summary.missing_syllabus_count > 0:
        summary.warnings.append(
            f"{summary.missing_syllabus_count} course(s) lack official articulation and syllabi/descriptions; "
            "upload course syllabi in Document Vault to enable Tier 3 content comparison."
        )

    # Identify Remaining Major Prerequisites for intended major
    if major:
        m_low = major.lower()
        ev_targets = " ".join(
            f"{e.target_course_code or ''} {e.target_course_name or ''} {e.source_course_name}".lower()
            for e in summary.evaluated_courses
            if not e.is_duplicate and e.equivalency_tier in (1, 2, 3)
        )
        expected_prereqs: List[Tuple[str, List[str]]] = []
        if "econ" in m_low:
            expected_prereqs = [
                ("Calculus I", ["math 1a", "math 31a", "math 226", "calculus i", "calc 1", "calculus"]),
                ("Calculus II", ["math 1b", "math 31b", "math 227", "calculus ii", "calc 2"]),
                ("Microeconomics", ["microecon", "econ 1", "econ 101"]),
                ("Macroeconomics", ["macroecon", "econ 2", "econ 102"]),
            ]
        elif "computer" in m_low:
            expected_prereqs = [
                ("Intro Programming / CS 61A equiv", ["61a", "31", "csc 210", "beginning programming", "cs 1"]),
                ("Data Structures / CS 61B equiv", ["61b", "32", "csc 220", "data structures", "abstraction"]),
                ("Calculus I & II", ["calculus", "math 1a", "math 1b", "math 31a"]),
                ("Linear Algebra / Discrete Math", ["linear algebra", "discrete", "math 54"]),
            ]
        for label, keys in expected_prereqs:
            if not any(k in ev_targets for k in keys):
                summary.major_prerequisites_remaining.append(label)

    summary.total_original_credits_by_system = credits_by_sys
    summary.ge_areas_satisfied = ge_set
    summary.major_prerequisites_satisfied = major_sat
    return summary
