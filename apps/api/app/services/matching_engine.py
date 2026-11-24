"""
Four-Dimensional Explainable University Matching Engine (Milestone 5).

Evaluates institutions independently across:
  A. Academic Fit
  B. Financial Compatibility
  C. Admissions Readiness
  D. Transfer & Credit Compatibility

Core Principles:
1. Compatibility alignment (0–100), NEVER deceptive admission probability predictions.
2. Every recommendation exposes exact per-dimension scores, calculation formula, positive factors,
   missing info, unsatisfied requirements, financial concerns, transfer uncertainties, and sources.
3. Missing data NEVER silently counts as a negative failure; every sub-factor tags:
   verified_match | partial_match | potential_concern | insufficient_information | not_applicable.
4. First-year applicants are NEVER penalized on the Transfer & Credit Compatibility dimension.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.models.country import Country
from app.models.institution import AcademicProgram, Institution, InstitutionCost
from app.models.matching import MatchingPreference, UniversityRecommendation
from app.models.profile import StudentProfile
from app.models.requirements import InstitutionRequirement
from app.schemas.matching import (
    DimensionEvaluationSchema,
    InstitutionMatchSummaryInfo,
    MatchFactorSchema,
    MatchingRunResponse,
    UniversityMatchRecommendationSchema,
)
from app.services.articulation_engine import evaluate_student_transfer_profile
from app.services.requirements_engine import (
    _extract_profile_context,
    evaluate_dynamic_checklist,
)


MATCH_DISCLAIMER = (
    "UniGlobe compatibility scores reflect alignment with published academic, financial, readiness, and "
    "transfer-credit criteria based on available verified records. Compatibility scores are NOT admission "
    "probabilities and do not guarantee admission or credit transfer."
)


def _normalize_weights(
    w_acad: float,
    w_fin: float,
    w_ready: float,
    w_trans: float,
    transfer_applicable: bool,
) -> Dict[str, float]:
    effective_trans = w_trans if transfer_applicable else 0.0
    total = w_acad + w_fin + w_ready + effective_trans
    if total <= 0.0:
        if transfer_applicable:
            return {"academic": 0.30, "financial": 0.25, "readiness": 0.25, "transfer": 0.20}
        return {"academic": 0.38, "financial": 0.31, "readiness": 0.31, "transfer": 0.00}
    return {
        "academic": round(w_acad / total, 4),
        "financial": round(w_fin / total, 4),
        "readiness": round(w_ready / total, 4),
        "transfer": round(effective_trans / total, 4),
    }


def _normalize_student_gpa_to_4(gpa: Optional[float], scale: Optional[float], country: Optional[str]) -> Tuple[Optional[float], str]:
    """Converts reported numeric GPA onto a 4.0 comparison scale while preserving original notation."""
    if gpa is None:
        return None, "Not Reported"
    sc = float(scale) if scale else 4.0
    if sc == 20.0 or (gpa > 4.5 and (country in ("FR", "HT") or gpa <= 20.0)):
        # French/Haitian 20-point scale (10/20 = pass ~ 2.0, 16/20 ~ 3.8, 14/20 ~ 3.3)
        conv = max(0.0, min(4.0, round((gpa / 20.0) * 4.2, 2)))
        return conv, f"{gpa:.1f}/20 (~{conv:.2f} US 4.0 equiv)"
    if sc == 100.0 or gpa > 20.0:
        conv = max(0.0, min(4.0, round((gpa - 55.0) / 10.0, 2)))
        return conv, f"{gpa:.1f}% (~{conv:.2f} US 4.0 equiv)"
    if sc == 6.0 or (country == "DE" and 1.0 <= gpa <= 5.0 and scale == 6.0):
        # German Abitur Bavarian inverse scale (1.0 best -> 4.0, 4.0 pass -> 1.0)
        conv = max(0.0, min(4.0, round(5.0 - gpa, 2)))
        return conv, f"{gpa:.2f}/6.0 German (~{conv:.2f} US 4.0 equiv)"
    return min(4.0, float(gpa)), f"{gpa:.2f}/{sc:g}"


def _parse_gpa_percentile_piecewise(val: float, p25: float, p75: float, p_min: float = 2.0, p_max: float = 4.0) -> float:
    if p75 <= p25:
        return 85.0 if val >= p25 else 55.0
    if val < p25:
        denom = max(0.2, p25 - p_min)
        return round(50.0 * max(0.0, min(1.0, (val - p_min) / denom)), 2)
    if val <= p75:
        return round(50.0 + 35.0 * ((val - p25) / (p75 - p25)), 2)
    denom = max(0.1, p_max - p75)
    return round(85.0 + 15.0 * min(1.0, (val - p75) / denom), 2)


def _evaluate_academic_fit(
    db: Session,
    inst: Institution,
    profile: Optional[StudentProfile],
    ctx: Dict[str, Any],
    pathway: str,
    intended_major: Optional[str],
    pref_countries: List[str],
    pref_types: List[str],
) -> Tuple[DimensionEvaluationSchema, List[str], List[str], float]:
    """Dimension A: Academic Fit (returns DimensionEvaluation, positive_factors, missing_info, confidence_contrib)."""
    factors: List[MatchFactorSchema] = []
    positives: List[str] = []
    missing: List[str] = []
    sub_scores: List[Tuple[float, float]] = []  # (score, weight)
    data_signals = 0
    total_signals = 3

    # 1. Program & Major Availability
    programs: List[AcademicProgram] = list(inst.programs or [])
    req_majors = (
        db.query(InstitutionRequirement.program_name_filter)
        .filter(
            InstitutionRequirement.institution_id == inst.id,
            InstitutionRequirement.is_current == True,
            InstitutionRequirement.program_name_filter.isnot(None),
        )
        .distinct()
        .all()
    )
    req_major_names = [r[0] for r in req_majors if r[0]]

    if not intended_major or intended_major.lower() == "undecided":
        factors.append(
            MatchFactorSchema(
                name="Intended Major Alignment",
                status="insufficient_information",
                score_impact=65.0,
                detail="No specific intended major declared on profile; neutral baseline applied.",
            )
        )
        sub_scores.append((65.0, 0.35))
        missing.append("Intended major not specified on profile.")
    else:
        m_low = intended_major.strip().lower()
        matching_progs = [
            p.program_name
            for p in programs
            if any(tok in p.program_name.lower() for tok in m_low.split() if len(tok) >= 4)
            or any(tok in m_low for tok in p.program_name.lower().split() if len(tok) >= 4)
        ]
        matching_reqs = [rm for rm in req_major_names if rm.lower() in m_low or m_low in rm.lower()]
        if matching_progs or matching_reqs:
            data_signals += 1
            hit_label = ", ".join((matching_reqs + matching_progs)[:2])
            factors.append(
                MatchFactorSchema(
                    name="Intended Major Alignment",
                    status="verified_match",
                    score_impact=95.0,
                    detail=f"Institution offers verified programs/tracks matching '{intended_major}': {hit_label}.",
                    source_name=inst.primary_source or "Institutional Program Catalog",
                    source_url=inst.official_website,
                )
            )
            positives.append(f"Offers academic program alignment for {intended_major} ({hit_label}).")
            sub_scores.append((95.0, 0.35))
        elif len(programs) == 0:
            factors.append(
                MatchFactorSchema(
                    name="Intended Major Alignment",
                    status="insufficient_information",
                    score_impact=60.0,
                    detail=f"Program-level CIP directory is not yet reported for {inst.official_name}; verify '{intended_major}' availability directly.",
                    source_url=inst.official_website,
                )
            )
            missing.append(f"Program catalog coverage missing for {inst.official_name}.")
            sub_scores.append((60.0, 0.35))
        else:
            data_signals += 1
            factors.append(
                MatchFactorSchema(
                    name="Intended Major Alignment",
                    status="potential_concern",
                    score_impact=35.0,
                    detail=f"No direct CIP program match found for '{intended_major}' among {len(programs)} indexed program areas.",
                    source_name=inst.primary_source,
                    source_url=inst.official_website,
                )
            )
            sub_scores.append((35.0, 0.35))

    # 2. GPA & International Grading Scale Alignment
    enrollments = ctx.get("enrollments") or []
    target_enrs = [
        e for e in enrollments if (e.enrollment_type != "secondary" if pathway == "transfer" else e.enrollment_type == "secondary")
    ]
    if not target_enrs and enrollments:
        target_enrs = enrollments
    best_enr = next((e for e in target_enrs if e.cumulative_gpa is not None), None)
    raw_gpa = float(best_enr.cumulative_gpa) if best_enr and best_enr.cumulative_gpa is not None else None
    raw_scale = float(best_enr.gpa_scale) if best_enr and best_enr.gpa_scale is not None else None
    enr_country = best_enr.institution_country if best_enr else None

    conv_gpa, gpa_label = _normalize_student_gpa_to_4(raw_gpa, raw_scale, enr_country)

    if conv_gpa is None:
        factors.append(
            MatchFactorSchema(
                name="Academic GPA / Grading Alignment",
                status="insufficient_information",
                score_impact=55.0,
                detail="No GPA recorded on Universal Student Profile; neutral baseline assigned instead of penalizing.",
            )
        )
        missing.append("Cumulative GPA not recorded on Universal Profile.")
        sub_scores.append((55.0, 0.45))
    elif inst.open_admissions:
        data_signals += 1
        factors.append(
            MatchFactorSchema(
                name="Academic GPA / Grading Alignment",
                status="verified_match",
                score_impact=95.0,
                detail=f"Open-admissions institution aligns cleanly with recorded academic standing ({gpa_label}).",
                source_name="NCES IPEDS",
            )
        )
        positives.append(f"Open-admissions policy matches your recorded academic record ({gpa_label}).")
        sub_scores.append((95.0, 0.45))
    elif inst.gpa_25 is not None and inst.gpa_75 is not None:
        data_signals += 1
        p25, p75 = float(inst.gpa_25), float(inst.gpa_75)
        sc = _parse_gpa_percentile_piecewise(conv_gpa, p25, p75)
        st = "verified_match" if conv_gpa >= p25 else "potential_concern"
        factors.append(
            MatchFactorSchema(
                name="Academic GPA / Grading Alignment",
                status=st,
                score_impact=sc,
                detail=f"Recorded GPA {gpa_label} compared to published 25th–75th cohort range ({p25:.2f}–{p75:.2f}).",
                source_name=inst.primary_source,
            )
        )
        if conv_gpa >= p25:
            positives.append(f"Academic GPA ({gpa_label}) meets or exceeds published 25th percentile ({p25:.2f}).")
        sub_scores.append((sc, 0.45))
    else:
        # Compare against verified min GPA requirement if published, or acceptance selectivity heuristic
        min_gpa_req = (
            db.query(InstitutionRequirement)
            .filter(
                InstitutionRequirement.institution_id == inst.id,
                InstitutionRequirement.is_current == True,
                InstitutionRequirement.applicant_type.in_([pathway, "all"]),
                InstitutionRequirement.minimum_value.isnot(None),
            )
            .join(InstitutionRequirement.template)
            .filter_by(requirement_type="minimum_gpa")
            .first()
        )
        if min_gpa_req:
            import re as _re
            m = _re.search(r"(\d+(?:\.\d+)?)", min_gpa_req.minimum_value or "")
            floor = float(m.group(1)) if m and float(m.group(1)) <= 4.5 else None
            if floor is not None:
                data_signals += 1
                if conv_gpa >= floor:
                    sc = min(94.0, 72.0 + (conv_gpa - floor) * 22.0)
                    factors.append(
                        MatchFactorSchema(
                            name="Academic GPA / Grading Alignment",
                            status="verified_match",
                            score_impact=round(sc, 2),
                            detail=f"Recorded GPA ({gpa_label}) satisfies verified minimum floor ({floor:.2f}).",
                            source_name=min_gpa_req.source_name,
                            source_url=min_gpa_req.source_url,
                        )
                    )
                    positives.append(f"GPA ({gpa_label}) exceeds verified minimum ({floor:.2f}).")
                else:
                    sc = max(20.0, round(50.0 * (conv_gpa / max(floor, 0.5)), 2))
                    factors.append(
                        MatchFactorSchema(
                            name="Academic GPA / Grading Alignment",
                            status="potential_concern",
                            score_impact=sc,
                            detail=f"Recorded GPA ({gpa_label}) is below verified minimum ({floor:.2f}).",
                            source_name=min_gpa_req.source_name,
                            source_url=min_gpa_req.source_url,
                        )
                    )
                sub_scores.append((sc, 0.45))
            else:
                factors.append(
                    MatchFactorSchema(
                        name="Academic GPA / Grading Alignment",
                        status="partial_match",
                        score_impact=65.0,
                        detail=f"Recorded GPA ({gpa_label}); institution specifies national-scale threshold '{min_gpa_req.minimum_value}'.",
                        source_name=min_gpa_req.source_name,
                        source_url=min_gpa_req.source_url,
                    )
                )
                sub_scores.append((65.0, 0.45))
        elif inst.acceptance_rate is not None:
            data_signals += 1
            acc = float(inst.acceptance_rate)
            # Infer benchmark band conservatively without claiming exact cohort quartiles
            bench = 3.65 if acc < 20 else 3.25 if acc < 50 else 2.75
            sc = _parse_gpa_percentile_piecewise(conv_gpa, bench - 0.25, bench + 0.20)
            st = "verified_match" if sc >= 70 else "partial_match" if sc >= 50 else "potential_concern"
            factors.append(
                MatchFactorSchema(
                    name="Academic GPA / Grading Alignment",
                    status=st,
                    score_impact=sc,
                    detail=f"Recorded GPA ({gpa_label}) evaluated alongside institutional selectivity ({acc:.1f}% acceptance rate; exact GPA quartiles not reported).",
                    source_name="NCES IPEDS",
                )
            )
            if sc >= 75:
                positives.append(f"Strong GPA profile ({gpa_label}) relative to selectivity ({acc:.1f}% acceptance).")
            sub_scores.append((sc, 0.45))
        else:
            factors.append(
                MatchFactorSchema(
                    name="Academic GPA / Grading Alignment",
                    status="insufficient_information",
                    score_impact=60.0,
                    detail=f"Recorded GPA ({gpa_label}); institution has not published numeric GPA quartiles or acceptance rate.",
                )
            )
            missing.append(f"Cohort GPA benchmarks not reported for {inst.official_name}.")
            sub_scores.append((60.0, 0.45))

    # 3. Standardized Testing / Outcomes & Environment Preferences
    sat_req = (
        db.query(InstitutionRequirement)
        .filter(InstitutionRequirement.institution_id == inst.id, InstitutionRequirement.is_current == True)
        .join(InstitutionRequirement.template)
        .filter_by(requirement_type="standardized_test")
        .first()
    )
    if sat_req and sat_req.importance == "not_accepted":
        data_signals += 1
        factors.append(
            MatchFactorSchema(
                name="Standardized Testing (SAT/ACT)",
                status="not_applicable",
                score_impact=85.0,
                detail="Test-Blind admissions policy: SAT/ACT scores are not considered.",
                source_name=sat_req.source_name,
                source_url=sat_req.source_url,
            )
        )
        sub_scores.append((85.0, 0.20))
    else:
        tests = ctx.get("tests") or []
        sat_test = next((t for t in tests if t.test_type.upper() == "SAT" and t.total_score), None)
        if inst.sat_math_25 and inst.sat_ebrw_25 and sat_test:
            try:
                tot = float(sat_test.total_score)
                s25 = float(inst.sat_math_25) + float(inst.sat_ebrw_25)
                s75 = float(inst.sat_math_75 or inst.sat_math_25) + float(inst.sat_ebrw_75 or inst.sat_ebrw_25)
                sc = _parse_gpa_percentile_piecewise(tot, s25, s75, p_min=800.0, p_max=1600.0)
                st = "verified_match" if tot >= s25 else "potential_concern"
                data_signals += 1
                factors.append(
                    MatchFactorSchema(
                        name="Standardized Testing (SAT)",
                        status=st,
                        score_impact=sc,
                        detail=f"SAT {int(tot)} vs. published 25th–75th composite range ({int(s25)}–{int(s75)}).",
                        source_name="NCES IPEDS",
                    )
                )
                sub_scores.append((sc, 0.20))
            except ValueError:
                sub_scores.append((65.0, 0.20))
        else:
            # Preference / Institutional quality fit factor when tests aren't applicable or reported
            country_match = (not pref_countries) or (inst.country_code.strip().upper() in [c.upper() for c in pref_countries])
            type_match = (not pref_types) or (inst.institution_type in pref_types)
            pref_score = 88.0 if (country_match and type_match) else 65.0 if (country_match or type_match) else 45.0
            factors.append(
                MatchFactorSchema(
                    name="Program Country & Institution Preference",
                    status="verified_match" if pref_score >= 80 else "partial_match",
                    score_impact=pref_score,
                    detail=f"Country ({inst.country_code}) & type ({inst.institution_type.replace('_', ' ')}) alignment with matching preferences.",
                )
            )
            sub_scores.append((pref_score, 0.20))

    total_w = sum(w for _, w in sub_scores) or 1.0
    dim_score = round(sum(s * w for s, w in sub_scores) / total_w, 2)
    dim_status = (
        "verified_match"
        if dim_score >= 78 and data_signals >= 2
        else "potential_concern"
        if dim_score < 50
        else "insufficient_information"
        if data_signals == 0
        else "partial_match"
    )
    return (
        DimensionEvaluationSchema(
            key="academic",
            label="Academic Fit",
            score=dim_score,
            weight_configured=0.30,
            weight_applied=0.30,
            status=dim_status,
            summary=f"Academic Fit {dim_score:.0f}/100 across program availability, normalized GPA alignment ({gpa_label}), and academic benchmarks.",
            factors=factors,
        ),
        positives,
        missing,
        data_signals / total_signals,
    )


def _evaluate_financial_compatibility(
    db: Session,
    inst: Institution,
    profile: Optional[StudentProfile],
    ctx: Dict[str, Any],
    max_budget: Optional[float],
    requires_full_aid: bool,
    requires_merit: bool,
) -> Tuple[DimensionEvaluationSchema, Optional[float], Optional[float], Optional[float], str, bool, List[str], List[str], List[str], float]:
    """
    Dimension B: Financial Compatibility.
    Distinguishes published costs from estimates and evaluates student budget & intl aid rules.
    """
    factors: List[MatchFactorSchema] = []
    positives: List[str] = []
    fin_concerns: List[str] = []
    missing: List[str] = []

    is_intl = ctx.get("is_international_for_target")
    student_state = (profile.state_province or "").strip().upper() if profile and profile.state_province else ""
    inst_state = (inst.state_province or "").strip().upper() if inst.state_province else ""
    is_in_state = (is_intl is False) and bool(student_state and inst_state and student_state == inst_state)

    # Query published itemized InstitutionCost rows first
    student_type_pref = "in_state" if is_in_state else "out_of_state"
    costs: List[InstitutionCost] = list(inst.costs or [])
    cost_row = next((c for c in costs if c.is_current and c.student_type == student_type_pref), None)
    if not cost_row and costs:
        cost_row = next((c for c in costs if c.is_current), costs[0])

    published_tuition: Optional[float] = None
    est_living: Optional[float] = None
    est_net_cost: Optional[float] = None
    cost_basis = "Institutional Tuition/Cost Not Reported"
    cost_is_estimated = True
    confidence = 0.0

    if cost_row and cost_row.total_estimated_cost is not None:
        t_val = float(cost_row.tuition or 0.0) + float(cost_row.mandatory_fees or 0.0)
        published_tuition = round(t_val, 2) if t_val > 0 else None
        living = float(cost_row.room_board or 0.0) + float(cost_row.books_supplies or 0.0) + float(cost_row.personal_expenses or 0.0)
        est_living = round(living, 2) if living > 0 else None
        est_net_cost = round(float(cost_row.total_estimated_cost), 2)
        # Check if domestic in-state federal avg_net_price provides an additional benchmark
        cost_basis = f"Published Itemized COA ({cost_row.student_type.replace('_', ' ').title()}, AY {cost_row.academic_year})"
        cost_is_estimated = False if (not is_intl and inst.control_type == "public" and is_in_state) else True
        confidence = 0.90
        factors.append(
            MatchFactorSchema(
                name="Published Tuition & Living Expenses",
                status="verified_match",
                detail=f"Published tuition+fees ${published_tuition or 0:,.0f} + room/board/books ${est_living or 0:,.0f} = ${est_net_cost:,.0f}/yr ({cost_row.student_type.replace('_', ' ')}).",
                source_name="NCES IPEDS (IC2023_AY)",
                source_url=cost_row.source_url,
            )
        )
    elif (inst.tuition_in_state is not None) or (inst.tuition_out_of_state is not None):
        published_tuition = float(inst.tuition_in_state if is_in_state and inst.tuition_in_state is not None else (inst.tuition_out_of_state or inst.tuition_in_state))
        if inst.cost_of_attendance is not None and (is_in_state or inst.control_type != "public"):
            est_net_cost = float(inst.cost_of_attendance)
            est_living = round(max(0.0, est_net_cost - published_tuition), 2)
            cost_basis = "Published Tuition + Estimated Living (Federal COA)"
        else:
            est_net_cost = published_tuition
            cost_basis = "Published Tuition Only (Living Expenses Not Reported)"
        cost_is_estimated = True
        confidence = 0.70
        factors.append(
            MatchFactorSchema(
                name="Tuition Benchmark",
                status="partial_match",
                detail=f"Published tuition ${published_tuition:,.0f}/yr ({cost_basis}).",
                source_name=inst.primary_source or "College Scorecard / IPEDS",
            )
        )
    else:
        factors.append(
            MatchFactorSchema(
                name="Published Tuition & Cost Data",
                status="insufficient_information",
                detail=f"Annual tuition and living costs are not reported in UniGlobe for {inst.official_name}; verify current international/domestic fees directly.",
                source_url=inst.official_website,
            )
        )
        missing.append(f"Official tuition & cost of attendance not reported for {inst.official_name}.")

    if is_in_state and inst.avg_net_price is not None and not is_intl:
        factors.append(
            MatchFactorSchema(
                name="Federal Average Net Price Reference",
                status="verified_match",
                detail=f"Historical Title IV average net price benchmark is ${float(inst.avg_net_price):,.0f}/yr (depends on household aid eligibility).",
                source_name="U.S. Dept. of Education College Scorecard",
            )
        )

    # Budget Evaluation
    if est_net_cost is None:
        fin_score = 55.0
        factors.append(
            MatchFactorSchema(
                name="Budget Affordability Check",
                status="insufficient_information",
                score_impact=55.0,
                detail="Cannot compare against student budget without published tuition/COA figures.",
            )
        )
    elif max_budget is None:
        fin_score = 65.0
        factors.append(
            MatchFactorSchema(
                name="Budget Affordability Check",
                status="insufficient_information",
                score_impact=65.0,
                detail=f"Estimated cost is ${est_net_cost:,.0f}/yr; enter a maximum annual budget to score personal affordability.",
            )
        )
        missing.append("Maximum annual budget not set in Matching Preferences.")
    else:
        b = max(1.0, float(max_budget))
        if est_net_cost <= b:
            fin_score = round(82.0 + 18.0 * (1.0 - (est_net_cost / b)), 2)
            factors.append(
                MatchFactorSchema(
                    name="Budget Affordability Check",
                    status="verified_match",
                    score_impact=fin_score,
                    detail=f"Estimated cost (${est_net_cost:,.0f}/yr) fits within your ${b:,.0f}/yr annual budget.",
                )
            )
            positives.append(f"Fits within your ${b:,.0f}/yr budget (est. ${est_net_cost:,.0f}/yr, {cost_basis}).")
        elif est_net_cost <= b * 1.25:
            ratio = (est_net_cost - b) / (0.25 * b)
            fin_score = round(78.0 - 28.0 * ratio, 2)
            factors.append(
                MatchFactorSchema(
                    name="Budget Affordability Check",
                    status="partial_match",
                    score_impact=fin_score,
                    detail=f"Estimated cost (${est_net_cost:,.0f}/yr) exceeds your ${b:,.0f}/yr budget by ${est_net_cost - b:,.0f}/yr; scholarships or aid required.",
                )
            )
            fin_concerns.append(f"Estimated cost (${est_net_cost:,.0f}) exceeds budget (${b:,.0f}) by ${est_net_cost - b:,.0f}/yr.")
        else:
            fin_score = round(max(12.0, 48.0 - 25.0 * min(1.5, (est_net_cost - b * 1.25) / b)), 2)
            factors.append(
                MatchFactorSchema(
                    name="Budget Affordability Check",
                    status="potential_concern",
                    score_impact=fin_score,
                    detail=f"Significant affordability gap: ${est_net_cost:,.0f}/yr vs. ${b:,.0f}/yr budget (${est_net_cost - b:,.0f}/yr gap).",
                )
            )
            fin_concerns.append(f"Significant affordability gap of ${est_net_cost - b:,.0f}/yr above stated budget.")

    # International Aid Policy Guard
    if is_intl is True and (requires_full_aid or requires_merit) and inst.country_code == "US" and inst.control_type == "public":
        fin_score = round(max(15.0, fin_score - 15.0), 2)
        msg = "US public institutions rarely award need-based institutional aid to non-US citizens/non-permanent residents."
        factors.append(
            MatchFactorSchema(
                name="International Aid Policy",
                status="potential_concern",
                detail=msg,
                source_url=inst.financial_aid_website or inst.admissions_website,
            )
        )
        fin_concerns.append(msg)

    dim_status = (
        "insufficient_information"
        if est_net_cost is None or max_budget is None
        else "verified_match"
        if fin_score >= 78
        else "partial_match"
        if fin_score >= 50
        else "potential_concern"
    )
    return (
        DimensionEvaluationSchema(
            key="financial",
            label="Financial Compatibility",
            score=fin_score,
            weight_configured=0.25,
            weight_applied=0.25,
            status=dim_status,
            summary=f"Financial Compatibility {fin_score:.0f}/100 ({cost_basis}).",
            factors=factors,
        ),
        est_net_cost,
        published_tuition,
        est_living,
        cost_basis,
        cost_is_estimated,
        positives,
        fin_concerns,
        missing,
        confidence,
    )


def _evaluate_admissions_readiness(
    db: Session,
    inst: Institution,
    profile: Optional[StudentProfile],
    pathway: str,
    intended_major: Optional[str],
) -> Tuple[DimensionEvaluationSchema, List[str], List[str], List[str], List[Dict[str, Any]], List[Dict[str, Any]], float]:
    """Dimension C: Admissions Readiness (reusing Milestone 3 checklist engine)."""
    chk = evaluate_dynamic_checklist(
        db=db,
        institution=inst,
        profile=profile,
        applicant_type=pathway,
        intended_major=intended_major,
    )

    factors: List[MatchFactorSchema] = []
    positives: List[str] = []
    unsatisfied: List[str] = []
    missing_docs_out: List[str] = []
    sources: List[Dict[str, Any]] = []
    seen_urls = set()

    for grp in (chk.completed_requirements, chk.missing_documents, chk.outstanding_prerequisites, chk.other_requirements):
        for item in grp:
            if item.source_url and item.source_url not in seen_urls:
                seen_urls.add(item.source_url)
                sources.append({"name": item.source_name, "url": item.source_url, "verified_at": str(item.verified_at.date()) if item.verified_at else None})

    if not chk.has_verified_requirements:
        # Uncurated institution: do not fabricate rules or penalize unfairly
        base = 70.0 if inst.open_admissions else 55.0
        factors.append(
            MatchFactorSchema(
                name="Verified Institutional Checklist",
                status="insufficient_information",
                score_impact=base,
                detail=chk.summary_notice or "Detailed institutional requirements not yet verified in UniGlobe.",
                source_url=inst.admissions_website or inst.official_website,
            )
        )
        return (
            DimensionEvaluationSchema(
                key="readiness",
                label="Admissions Readiness",
                score=base,
                weight_configured=0.25,
                weight_applied=0.25,
                status="insufficient_information",
                summary=f"Detailed admissions checklist unverified for {inst.official_name}; verify requirements on official portal.",
                factors=factors,
            ),
            positives,
            [],
            [],
            [],
            sources,
            0.35,
        )

    readiness_score = float(chk.readiness_pct)
    # Adjust slightly so having partial progress without firm failures isn't zeroed
    if readiness_score < 50.0 and not chk.eligibility_concerns:
        readiness_score = max(45.0, readiness_score + 20.0)

    for item in chk.missing_documents:
        missing_docs_out.append(item.title)
        unsatisfied.append(f"Missing Document: {item.title}")
    for item in chk.outstanding_prerequisites:
        unsatisfied.append(f"Academic/Prereq: {item.title} ({item.status.replace('_', ' ')})")
    for item in chk.other_requirements:
        if item.status in ("missing", "needs_verification"):
            unsatisfied.append(f"{item.title} ({item.status.replace('_', ' ')})")

    factors.append(
        MatchFactorSchema(
            name="Checklist Completion Ratio",
            status="verified_match" if chk.readiness_pct >= 75 else "partial_match" if chk.readiness_pct >= 40 else "insufficient_information" if chk.eligibility_status == "needs_information" else "potential_concern",
            score_impact=round(readiness_score, 2),
            detail=f"{len(chk.completed_requirements)} completed, {len(chk.missing_documents)} missing docs, {len(chk.outstanding_prerequisites)} outstanding prereq/academic checks ({chk.readiness_pct}% required items verified).",
        )
    )
    if chk.completed_requirements:
        positives.append(
            f"Completed {len(chk.completed_requirements)} verified requirement(s) including {chk.completed_requirements[0].title}."
        )

    for c in chk.eligibility_concerns:
        factors.append(
            MatchFactorSchema(
                name="Eligibility Threshold Check",
                status="potential_concern",
                detail=c,
            )
        )

    deadlines_out = [
        {
            "intake_term": d.intake_term,
            "deadline_type": d.deadline_type,
            "deadline_date": str(d.deadline_date) if d.deadline_date else None,
            "days_remaining": d.days_remaining,
            "is_past": d.is_past,
            "source_url": d.source_url,
        }
        for d in chk.upcoming_deadlines
    ]
    if deadlines_out:
        open_dls = [d for d in deadlines_out if not d.get("is_past")]
        factors.append(
            MatchFactorSchema(
                name="Application Deadlines",
                status="verified_match" if open_dls else "potential_concern",
                detail=(
                    f"Next open deadline: {open_dls[0]['intake_term']} ({open_dls[0]['deadline_date']}, {open_dls[0]['days_remaining']}d remaining)."
                    if open_dls
                    else "Published deadline(s) for current cycle have passed."
                ),
                source_url=deadlines_out[0]["source_url"],
            )
        )

    dim_status = (
        "potential_concern"
        if chk.eligibility_concerns
        else "verified_match"
        if chk.readiness_pct >= 75
        else "insufficient_information"
        if chk.eligibility_status == "needs_information"
        else "partial_match"
    )
    return (
        DimensionEvaluationSchema(
            key="readiness",
            label="Admissions Readiness",
            score=round(readiness_score, 2),
            weight_configured=0.25,
            weight_applied=0.25,
            status=dim_status,
            summary=f"Admissions Readiness {readiness_score:.0f}/100 ({chk.eligibility_status.replace('_', ' ')}).",
            factors=factors,
        ),
        positives,
        unsatisfied,
        missing_docs_out,
        deadlines_out,
        sources,
        0.95,
    )


def _evaluate_transfer_compatibility(
    db: Session,
    inst: Institution,
    profile: Optional[StudentProfile],
    ctx: Dict[str, Any],
    pathway: str,
    intended_major: Optional[str],
) -> Tuple[DimensionEvaluationSchema, bool, List[str], List[str], List[str], float]:
    """
    Dimension D: Transfer & Credit Compatibility (reusing Milestone 4 articulation engine).
    Adapts cleanly for First-Year students so they are NEVER penalized for lacking college coursework.
    """
    factors: List[MatchFactorSchema] = []
    positives: List[str] = []
    uncertainties: List[str] = []
    missing: List[str] = []

    if pathway == "first_year":
        tests = ctx.get("tests") or []
        ap_ib = [t for t in tests if t.test_type.upper() in ("AP", "IB")]
        ap_ib_courses = [c for c in (ctx.get("courses") or []) if c.is_ap_ib_dual]
        detail = (
            f"Not applicable for First-Year admission (zero penalty applied). Found {len(ap_ib) + len(ap_ib_courses)} AP/IB/dual-enrollment credit item(s) potentially eligible for advanced standing."
            if (ap_ib or ap_ib_courses)
            else "Not applicable for First-Year applicant without post-secondary transfer credits (no score penalty applied)."
        )
        factors.append(
            MatchFactorSchema(
                name="First-Year Credit Adaptation",
                status="not_applicable",
                score_impact=100.0,
                detail=detail,
            )
        )
        return (
            DimensionEvaluationSchema(
                key="transfer",
                label="Transfer & Credit Compatibility",
                score=100.0,
                weight_configured=0.20,
                weight_applied=0.0,
                status="not_applicable",
                summary="Adapted for First-Year applicant (re-weighted across Academic, Financial & Readiness).",
                factors=factors,
            ),
            False,
            positives,
            uncertainties,
            missing,
            0.90,
        )

    # Transfer Applicant Evaluation
    t_sum = evaluate_student_transfer_profile(db=db, profile=profile, target_inst=inst, intended_major=intended_major)
    if t_sum.total_courses_evaluated == 0:
        factors.append(
            MatchFactorSchema(
                name="Completed Transferable Coursework",
                status="insufficient_information",
                score_impact=55.0,
                detail="No post-secondary courses recorded on Universal Profile to evaluate articulation against this university.",
            )
        )
        missing.append("No college coursework recorded on Universal Profile for transfer evaluation.")
        uncertainties.append("Add completed/in-progress college courses to measure Tier 1/2/3 credit transferability.")
        return (
            DimensionEvaluationSchema(
                key="transfer",
                label="Transfer & Credit Compatibility",
                score=55.0,
                weight_configured=0.20,
                weight_applied=0.20,
                status="insufficient_information",
                summary="Transfer Compatibility 55/100 (neutral baseline — add college courses to analyze degree applicability).",
                factors=factors,
            ),
            True,
            positives,
            uncertainties,
            missing,
            0.35,
        )

    total_attempted = max(1.0, t_sum.normalized_semester_credits_attempted)
    t1_ratio = t_sum.officially_transferable_credits / total_attempted
    pot_ratio = t_sum.potentially_transferable_credits / total_attempted
    degree_applicable = t_sum.major_applicable_credits + t_sum.ge_applicable_credits
    app_ratio = min(1.0, degree_applicable / total_attempted)

    # Explicit distinction: Tier 1 gets full credit certainty; Tier 2/3 get discounted certainty; degree applicability adds weight!
    raw_score = 70.0 * min(1.0, t1_ratio + 0.65 * pot_ratio) + 30.0 * app_ratio
    if t_sum.officially_verified_count == 0 and t_sum.potentially_transferable_credits == 0:
        raw_score = 48.0  # unverified baseline rather than 0 when university simply lacks published catalog/agreements
    score = round(min(100.0, max(30.0, raw_score)), 2)

    if t_sum.officially_verified_count > 0:
        factors.append(
            MatchFactorSchema(
                name="Tier 1 Official Articulation",
                status="verified_match",
                detail=f"{t_sum.officially_verified_count} course(s) ({t_sum.officially_transferable_credits} sem eq) verified via published agreements.",
                source_name="ASSIST.org / Official Articulation",
            )
        )
        positives.append(
            f"{t_sum.officially_verified_count} completed course(s) ({t_sum.officially_transferable_credits} sem eq) have Tier 1 official transfer articulation."
        )
    if t_sum.historically_observed_count + t_sum.ai_predicted_count > 0:
        factors.append(
            MatchFactorSchema(
                name="Tier 2/3 Provisional Equivalencies",
                status="partial_match",
                detail=f"{t_sum.historically_observed_count} Tier 2 historical + {t_sum.ai_predicted_count} Tier 3 AI-predicted ({t_sum.potentially_transferable_credits} sem eq; subject to official review).",
            )
        )
        if t_sum.ai_predicted_count > 0:
            uncertainties.append(
                f"{t_sum.ai_predicted_count} course(s) rely on Tier 3 AI similarity matching and are NOT official transfer guarantees."
            )
    if t_sum.unverified_course_count > 0:
        factors.append(
            MatchFactorSchema(
                name="Unverified Courses / Missing Syllabi",
                status="insufficient_information",
                detail=f"{t_sum.unverified_course_count} course(s) ({t_sum.unverified_credits} sem eq) unverified; {t_sum.missing_syllabus_count} missing syllabi.",
            )
        )
        uncertainties.append(
            f"{t_sum.unverified_course_count} unverified course(s) lack published agreements ({t_sum.missing_syllabus_count} need syllabi)."
        )

    factors.append(
        MatchFactorSchema(
            name="Degree Applicability (Major & GE vs. Electives)",
            status="verified_match" if app_ratio >= 0.6 else "partial_match" if app_ratio > 0.2 else "potential_concern",
            detail=(
                f"Major: {t_sum.major_applicable_credits} sem eq • GE: {t_sum.ge_applicable_credits} sem eq • "
                f"Elective-only: {t_sum.elective_only_credits} sem eq (accepted units ≠ degree progress)."
            ),
        )
    )
    if t_sum.major_prerequisites_remaining:
        uncertainties.append(f"Remaining major prerequisites: {', '.join(t_sum.major_prerequisites_remaining)}.")

    dim_status = (
        "verified_match"
        if t_sum.officially_verified_count > 0 and app_ratio >= 0.5
        else "insufficient_information"
        if t_sum.officially_verified_count == 0 and t_sum.ai_predicted_count == 0
        else "partial_match"
    )
    conf = 0.90 if t_sum.officially_verified_count > 0 else 0.60 if t_sum.ai_predicted_count > 0 else 0.35
    return (
        DimensionEvaluationSchema(
            key="transfer",
            label="Transfer & Credit Compatibility",
            score=score,
            weight_configured=0.20,
            weight_applied=0.20,
            status=dim_status,
            summary=(
                f"Transfer Fit {score:.0f}/100 ({t_sum.officially_transferable_credits} Tier 1 sem eq, "
                f"{t_sum.major_applicable_credits} major-applicable, {t_sum.elective_only_credits} elective-only)."
            ),
            factors=factors,
        ),
        True,
        positives,
        uncertainties,
        missing,
        conf,
    )


def evaluate_single_institution_match(
    db: Session,
    inst: Institution,
    profile: Optional[StudentProfile],
    pref: Optional[MatchingPreference],
    pathway: str,
    intended_major: Optional[str],
    weights_override: Optional[Dict[str, float]] = None,
    budget_override: Optional[float] = None,
    persist: bool = False,
) -> UniversityMatchRecommendationSchema:
    ctx = _extract_profile_context(profile, inst.country_code, pathway)
    pref_countries = list(pref.preferred_countries or []) if pref else []
    pref_types = list(pref.preferred_institution_types or []) if pref else []
    max_budget = budget_override if budget_override is not None else (float(pref.max_annual_budget) if pref and pref.max_annual_budget is not None else None)
    req_full_aid = bool(pref.requires_full_aid) if pref else False
    req_merit = bool(pref.requires_merit_scholarships) if pref else False

    w_acad_cfg = (weights_override or {}).get("academic", float(pref.weight_academic) if pref else 0.30)
    w_fin_cfg = (weights_override or {}).get("financial", float(pref.weight_financial) if pref else 0.25)
    w_ready_cfg = (weights_override or {}).get("readiness", float(pref.weight_readiness) if pref else 0.25)
    w_trans_cfg = (weights_override or {}).get("transfer", float(pref.weight_transfer) if pref else 0.20)

    dim_acad, pos_a, miss_a, conf_a = _evaluate_academic_fit(
        db, inst, profile, ctx, pathway, intended_major, pref_countries, pref_types
    )
    dim_fin, est_net, pub_tui, est_liv, cost_basis, cost_est, pos_b, fin_concerns, miss_b, conf_b = (
        _evaluate_financial_compatibility(db, inst, profile, ctx, max_budget, req_full_aid, req_merit)
    )
    dim_ready, pos_c, unsat_c, miss_docs_c, deadlines_c, sources_c, conf_c = (
        _evaluate_admissions_readiness(db, inst, profile, pathway, intended_major)
    )
    dim_trans, transfer_applicable, pos_d, trans_uncert, miss_d, conf_d = (
        _evaluate_transfer_compatibility(db, inst, profile, ctx, pathway, intended_major)
    )

    weights = _normalize_weights(w_acad_cfg, w_fin_cfg, w_ready_cfg, w_trans_cfg, transfer_applicable)
    dim_acad.weight_configured, dim_acad.weight_applied = w_acad_cfg, weights["academic"]
    dim_fin.weight_configured, dim_fin.weight_applied = w_fin_cfg, weights["financial"]
    dim_ready.weight_configured, dim_ready.weight_applied = w_ready_cfg, weights["readiness"]
    dim_trans.weight_configured, dim_trans.weight_applied = w_trans_cfg, weights["transfer"]

    composite = round(
        dim_acad.score * weights["academic"]
        + dim_fin.score * weights["financial"]
        + dim_ready.score * weights["readiness"]
        + dim_trans.score * weights["transfer"],
        2,
    )
    calc_str = (
        f"({dim_acad.score:.1f}×{weights['academic']:.2f}) + "
        f"({dim_fin.score:.1f}×{weights['financial']:.2f}) + "
        f"({dim_ready.score:.1f}×{weights['readiness']:.2f}) + "
        f"({dim_trans.score:.1f}×{weights['transfer']:.2f}) = {composite:.2f}"
    )

    all_missing = list(dict.fromkeys(miss_a + miss_b + miss_d))
    raw_conf = conf_a * 0.30 + conf_b * 0.30 + conf_c * 0.25 + conf_d * 0.15
    data_conf = round(min(1.0, max(0.15, raw_conf - 0.08 * len(all_missing))), 2)
    all_positives = list(dict.fromkeys(pos_a + pos_b + pos_c + pos_d))
    all_sources = list(sources_c)
    if inst.primary_source:
        all_sources.insert(
            0,
            {
                "name": inst.primary_source.upper(),
                "url": inst.admissions_website or inst.official_website,
                "verified_at": str(inst.last_verified_at.date()) if inst.last_verified_at else None,
            },
        )

    # Categorization (Respects missing-data threshold + Reach/Target/Likely rules)
    acc_rate = float(inst.acceptance_rate) if inst.acceptance_rate is not None else None
    has_gpa_concern = any(f.status == "potential_concern" and "GPA" in f.name for f in dim_acad.factors)
    missing_core_profile = any("Cumulative GPA" in m for m in all_missing) and any("budget" in m.lower() for m in all_missing)
    if (data_conf < 0.45 and len(all_missing) >= 2) or (len(all_missing) >= 3 and missing_core_profile):
        category = "insufficient_data"
    elif (acc_rate is not None and acc_rate < 15.0) or has_gpa_concern or dim_acad.score < 52.0 or dim_fin.score < 45.0:
        category = "reach"
    elif (
        dim_acad.score >= 76.0
        and dim_fin.score >= 65.0
        and (acc_rate is None or acc_rate >= 30.0 or bool(inst.open_admissions))
        and not fin_concerns
    ):
        category = "likely"
    else:
        category = "target"

    is_saved = False
    is_dismissed = False
    rec_id = inst.id
    computed_at = datetime.now(timezone.utc)

    if persist and profile is not None:
        existing = (
            db.query(UniversityRecommendation)
            .filter(
                UniversityRecommendation.profile_id == profile.id,
                UniversityRecommendation.institution_id == inst.id,
            )
            .first()
        )
        payload_breakdown = {
            "calculation_formula": calc_str,
            "dimensions": [d.model_dump() for d in (dim_acad, dim_fin, dim_ready, dim_trans)],
            "positive_factors": all_positives,
            "missing_information": all_missing,
            "sources": all_sources,
            "published_tuition": pub_tui,
            "estimated_living_expenses": est_liv,
            "cost_basis": cost_basis,
        }
        if existing:
            existing.applicant_type = pathway
            existing.intended_major = intended_major
            existing.match_category = category
            existing.composite_score = composite
            existing.score_academic = dim_acad.score
            existing.score_financial = dim_fin.score
            existing.score_readiness = dim_ready.score
            existing.score_transfer = dim_trans.score
            existing.data_confidence_score = data_conf
            existing.explanation_breakdown = payload_breakdown
            existing.outstanding_prerequisites = unsat_c
            existing.missing_documents = miss_docs_c
            existing.financial_concerns = fin_concerns
            existing.transfer_uncertainties = trans_uncert
            existing.upcoming_deadlines = deadlines_c
            existing.estimated_net_cost = est_net
            existing.cost_is_estimated = cost_est
            existing.computed_at = computed_at
            db.flush()
            rec_id = existing.id
            is_saved = existing.is_saved_by_student
            is_dismissed = existing.is_dismissed
        else:
            rec = UniversityRecommendation(
                profile_id=profile.id,
                institution_id=inst.id,
                applicant_type=pathway,
                intended_major=intended_major,
                match_category=category,
                composite_score=composite,
                score_academic=dim_acad.score,
                score_financial=dim_fin.score,
                score_readiness=dim_ready.score,
                score_transfer=dim_trans.score,
                data_confidence_score=data_conf,
                explanation_breakdown=payload_breakdown,
                outstanding_prerequisites=unsat_c,
                missing_documents=miss_docs_c,
                financial_concerns=fin_concerns,
                transfer_uncertainties=trans_uncert,
                upcoming_deadlines=deadlines_c,
                estimated_net_cost=est_net,
                cost_is_estimated=cost_est,
                computed_at=computed_at,
            )
            db.add(rec)
            db.flush()
            rec_id = rec.id

    return UniversityMatchRecommendationSchema(
        id=rec_id,
        institution_id=inst.id,
        institution=InstitutionMatchSummaryInfo(
            id=inst.id,
            official_name=inst.official_name,
            country_code=inst.country_code,
            state_province=inst.state_province,
            city=inst.city,
            institution_type=inst.institution_type,
            control_type=inst.control_type,
            acceptance_rate=float(inst.acceptance_rate) if inst.acceptance_rate is not None else None,
            tuition_in_state=float(inst.tuition_in_state) if inst.tuition_in_state is not None else None,
            tuition_out_of_state=float(inst.tuition_out_of_state) if inst.tuition_out_of_state is not None else None,
            avg_net_price=float(inst.avg_net_price) if inst.avg_net_price is not None else None,
            cost_of_attendance=float(inst.cost_of_attendance) if inst.cost_of_attendance is not None else None,
            currency=inst.currency,
            total_enrollment=inst.total_enrollment,
            official_website=inst.official_website,
            admissions_website=inst.admissions_website,
            application_portal_url=inst.application_portal_url,
            primary_source=inst.primary_source,
            last_verified_at=inst.last_verified_at,
        ),
        applicant_type=pathway,
        intended_major=intended_major,
        match_category=category,
        composite_score=composite,
        score_academic=dim_acad.score,
        score_financial=dim_fin.score,
        score_readiness=dim_ready.score,
        score_transfer=dim_trans.score,
        data_confidence_score=data_conf,
        calculation_formula=calc_str,
        dimensions=[dim_acad, dim_fin, dim_ready, dim_trans],
        positive_factors=all_positives,
        missing_information=all_missing,
        unsatisfied_requirements=unsat_c,
        financial_concerns=fin_concerns,
        transfer_uncertainties=trans_uncert,
        upcoming_deadlines=deadlines_c,
        sources=all_sources,
        estimated_net_cost=est_net,
        published_tuition=pub_tui,
        estimated_living_expenses=est_liv,
        cost_basis=cost_basis,
        cost_is_estimated=cost_est,
        is_saved_by_student=is_saved,
        is_dismissed=is_dismissed,
        computed_at=computed_at,
        disclaimer=MATCH_DISCLAIMER,
    )


def run_matching_discovery(
    db: Session,
    profile: Optional[StudentProfile],
    pref: Optional[MatchingPreference],
    applicant_type: Optional[str] = None,
    intended_major: Optional[str] = None,
    countries: Optional[List[str]] = None,
    states: Optional[List[str]] = None,
    institution_types: Optional[List[str]] = None,
    budget_override: Optional[float] = None,
    weights_override: Optional[Dict[str, float]] = None,
    limit: int = 24,
    persist: bool = True,
) -> MatchingRunResponse:
    pathway = (applicant_type or (profile.applicant_type if profile else None) or "first_year").lower()
    if pathway in ("undecided", "both"):
        pathway = "first_year"
    major = intended_major or (profile.intended_major if profile else None)

    query = db.query(Institution).filter(Institution.is_published == True)
    if pathway == "transfer":
        query = query.filter(Institution.accepts_transfer == True)
    else:
        query = query.filter(Institution.accepts_first_year == True)

    country_list = [c.strip().upper()[:2] for c in (countries if countries is not None else (pref.preferred_countries if pref and pref.preferred_countries else [])) if c and c.strip()]
    if country_list:
        query = query.filter(Institution.country_code.in_(country_list))

    state_list = [s.strip().upper() for s in (states if states is not None else (pref.preferred_states_provinces if pref and pref.preferred_states_provinces else [])) if s and s.strip()]
    if state_list:
        query = query.filter(func.upper(Institution.state_province).in_(state_list))

    type_list = [t.strip() for t in (institution_types if institution_types is not None else (pref.preferred_institution_types if pref and pref.preferred_institution_types else [])) if t and t.strip()]
    if type_list:
        query = query.filter(Institution.institution_type.in_(type_list))

    # Prioritize curated verified universities (M3/M4) + high-data institutions so rich profiles surface cleanly
    verified_req_subq = db.query(InstitutionRequirement.institution_id).distinct().subquery()
    priority = case(
        (Institution.id.in_(db.query(verified_req_subq.c.institution_id)), 0),
        (Institution.ipeds_unit_id.in_(["110635", "110662", "122597", "170976", "166683", "113333", "122977"]), 1),
        else_=2,
    )
    candidates = (
        query.order_by(priority.asc(), Institution.data_completeness_score.desc(), Institution.total_enrollment.desc().nulls_last())
        .limit(limit)
        .all()
    )

    recs: List[UniversityMatchRecommendationSchema] = []
    for inst in candidates:
        recs.append(
            evaluate_single_institution_match(
                db=db,
                inst=inst,
                profile=profile,
                pref=pref,
                pathway=pathway,
                intended_major=major,
                weights_override=weights_override,
                budget_override=budget_override,
                persist=persist,
            )
        )

    if persist and profile is not None:
        db.commit()

    recs.sort(key=lambda r: r.composite_score, reverse=True)
    counts = {"reach": 0, "target": 0, "likely": 0, "insufficient_data": 0}
    for r in recs:
        counts[r.match_category] = counts.get(r.match_category, 0) + 1

    transfer_active = pathway == "transfer"
    w_used = _normalize_weights(
        (weights_override or {}).get("academic", float(pref.weight_academic) if pref else 0.30),
        (weights_override or {}).get("financial", float(pref.weight_financial) if pref else 0.25),
        (weights_override or {}).get("readiness", float(pref.weight_readiness) if pref else 0.25),
        (weights_override or {}).get("transfer", float(pref.weight_transfer) if pref else 0.20),
        transfer_active,
    )

    return MatchingRunResponse(
        applicant_type=pathway,
        intended_major=major,
        total_evaluated=len(recs),
        counts_by_category=counts,
        weights_used=w_used,
        recommendations=recs,
        disclaimer=MATCH_DISCLAIMER,
    )
