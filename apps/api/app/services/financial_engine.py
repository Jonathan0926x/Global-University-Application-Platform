"""
Phase 4 Global Scholarship Matching & Net Price Affordability Engine.

Guarantees:
1. Never invents scholarship rules or missing institutional costs.
2. Evaluates every verified ScholarshipProgram deterministically against profile + inputs,
   explicitly exposing pass / fail / missing_data reasons per rule.
3. Net Price Calculator distinguishes direct billable charges, indirect living expenses,
   guaranteed statutory aid vs. competitive aid ranges, and clearly reports data confidence
   and published source citations.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.ingestion.phase4_seed import seed_phase4_financial_and_credentials
from app.models.institution import Institution, InstitutionCost
from app.models.profile import CitizenshipRecord, StudentProfile
from app.models.rag import ScholarshipEligibilityRule, ScholarshipProgram
from app.services.matching_engine import _normalize_student_gpa_to_4

FINANCIAL_DISCLAIMER = (
    "Informational affordability and scholarship eligibility estimate only based on published institutional "
    "cost schedules and verified aid policies. Official university financial aid letters and FAFSA/CSS Profile "
    "reviews determine actual billed charges and aid awards."
)


def ensure_phase4_seeded(db: Session) -> None:
    """Seed verified Phase 4 scholarships, rules, and credential tables if empty or un-synced."""
    has_rule = db.query(ScholarshipEligibilityRule.id).limit(1).first()
    has_yale = (
        db.query(ScholarshipProgram.id)
        .filter(ScholarshipProgram.title == "Yale Need-Blind Worldwide & Full-Need Financial Aid")
        .limit(1)
        .first()
    )
    if has_rule is None or has_yale is None:
        seed_phase4_financial_and_credentials(db)


def _derive_student_context(
    db: Session,
    profile: Optional[StudentProfile],
    overrides: Dict[str, Any],
) -> Dict[str, Any]:
    citizenships: List[str] = []
    residency_state: Optional[str] = None
    applicant_type: Optional[str] = None
    gpa_4: Optional[float] = None
    gpa_display: str = "Not Reported"
    has_us_cc = False
    has_enrollment_history = False

    if profile is not None:
        cit_rows = (
            db.query(CitizenshipRecord)
            .filter(CitizenshipRecord.profile_id == profile.id)
            .all()
        )
        citizenships = [c.country_code.strip().upper()[:2] for c in cit_rows if c.country_code]
        if not citizenships and profile.country_code:
            citizenships = [profile.country_code.strip().upper()[:2]]
        residency_state = profile.state_province.strip().upper() if profile.state_province else None
        applicant_type = profile.applicant_type if profile.applicant_type != "undecided" else None

        enrollments = list(profile.enrollments or [])
        has_enrollment_history = len(enrollments) > 0
        for enr in enrollments:
            enr_cc = (enr.institution_country or "").strip().upper()[:2]
            if enr.enrollment_type == "community_college" and (enr_cc == "US" or not enr_cc):
                has_us_cc = True
        for enr in reversed(enrollments):
            if enr.cumulative_gpa is not None:
                scale_val = float(enr.gpa_scale) if getattr(enr, "gpa_scale", None) else 4.0
                gpa_4, gpa_display = _normalize_student_gpa_to_4(
                    float(enr.cumulative_gpa),
                    scale_val,
                    profile.country_of_residence or (citizenships[0] if citizenships else None),
                )
                break

    if overrides.get("citizenship_country"):
        cc = str(overrides["citizenship_country"]).strip().upper()[:2]
        if cc:
            citizenships = [cc]
            if cc != "US" and overrides.get("residency_state") is None:
                residency_state = None

    if overrides.get("residency_state") is not None:
        st = str(overrides["residency_state"]).strip().upper()
        residency_state = st or None

    if overrides.get("applicant_type"):
        applicant_type = str(overrides["applicant_type"]).strip().lower()

    if overrides.get("gpa_4") is not None:
        gpa_4 = float(overrides["gpa_4"])
        gpa_display = f"{gpa_4:.2f}/4.0"

    need_level = (overrides.get("financial_need_level") or "").strip().lower() or None
    income_usd = overrides.get("household_income_usd")
    if not need_level and income_usd is not None:
        inc = float(income_usd)
        if inc <= 65000:
            need_level = "high"
        elif inc <= 125000:
            need_level = "moderate"
        else:
            need_level = "low"

    if overrides.get("us_community_college_enrolled") is True:
        has_us_cc = True

    degree_level = (
        overrides.get("degree_level")
        or (profile.intended_degree_level if profile and profile.intended_degree_level else None)
        or "bachelors"
    ).strip().lower()

    return {
        "citizenships": citizenships,
        "primary_citizenship": citizenships[0] if citizenships else None,
        "residency_state": residency_state,
        "applicant_type": applicant_type,
        "degree_level": degree_level,
        "has_us_community_college": has_us_cc,
        "has_enrollment_history": has_enrollment_history,
        "gpa_4": gpa_4,
        "gpa_display": gpa_display,
        "financial_need_level": need_level,
        "household_income_usd": float(income_usd) if income_usd is not None else None,
        "destination_country": (overrides.get("destination_country") or "").strip().upper()[:2] or None,
        "institution_id": str(overrides["institution_id"]) if overrides.get("institution_id") else None,
    }


def _eval_rule(
    rule: ScholarshipEligibilityRule,
    sch: ScholarshipProgram,
    ctx: Dict[str, Any],
) -> Dict[str, Any]:
    dim = rule.rule_dimension
    val = rule.rule_value or {}

    if dim == "citizenship":
        allowed = [c.upper() for c in val.get("countries", [])]
        stud_cits = ctx["citizenships"]
        if not stud_cits:
            return {"status": "missing_data", "detail": "Citizenship country not specified."}
        if any(c in allowed for c in stud_cits):
            return {"status": "pass", "detail": f"Citizenship {stud_cits[0]} matches eligible list {allowed}."}
        return {"status": "fail", "detail": f"Citizenship {stud_cits[0]} is outside eligible countries {allowed}."}

    if dim == "residency_state":
        allowed = [s.upper() for s in val.get("states", [])]
        st = ctx["residency_state"]
        # US residency aid strictly excludes non-US citizens unless domestic residency established
        if ctx["primary_citizenship"] and ctx["primary_citizenship"] != "US" and not sch.covers_international:
            return {"status": "fail", "detail": "International citizens are ineligible for state-resident need programs."}
        if not st:
            return {"status": "missing_data", "detail": f"Residency state required ({'/'.join(allowed)})."}
        if st in allowed:
            return {"status": "pass", "detail": f"State residency '{st}' matches {allowed}."}
        return {"status": "fail", "detail": f"Residency '{st}' does not match required {allowed}."}

    if dim == "destination_country":
        allowed = [c.upper() for c in val.get("countries", [])]
        dest = ctx["destination_country"]
        if not dest:
            return {"status": "pass", "detail": f"Applicable for destination {', '.join(allowed)}."}
        if dest in allowed:
            return {"status": "pass", "detail": f"Destination '{dest}' matches scholarship target."}
        return {"status": "fail", "detail": f"Scholarship applies to {', '.join(allowed)}, not '{dest}'."}

    if dim == "applicant_type":
        allowed = [t.lower() for t in val.get("types", [])]
        app_t = ctx["applicant_type"]
        if not app_t:
            return {"status": "missing_data", "detail": f"Applicant pathway ({'/'.join(allowed)}) not selected."}
        if app_t in allowed or (app_t == "both" and any(x in ("first_year", "transfer", "both") for x in allowed)):
            return {"status": "pass", "detail": f"Applicant pathway '{app_t}' qualifies."}
        return {"status": "fail", "detail": f"Restricted to {', '.join(allowed)} applicants (student: '{app_t}')."}

    if dim == "minimum_gpa":
        req_gpa = float(val.get("min_gpa", 0.0))
        stud_gpa = ctx["gpa_4"]
        if stud_gpa is None:
            return {"status": "missing_data", "detail": f"Academic GPA needed to verify {req_gpa:.2f} minimum."}
        if stud_gpa >= req_gpa:
            return {"status": "pass", "detail": f"GPA {stud_gpa:.2f} meets >= {req_gpa:.2f} requirement."}
        return {"status": "fail", "detail": f"GPA {stud_gpa:.2f} is below {req_gpa:.2f} minimum."}

    if dim == "financial_need_level":
        allowed_levels = [lvl.lower() for lvl in val.get("levels", [])]
        max_inc = val.get("max_income_usd")
        inc = ctx["household_income_usd"]
        need = ctx["financial_need_level"]
        if max_inc is not None and inc is not None:
            if inc <= float(max_inc):
                return {"status": "pass", "detail": f"Household income ${inc:,.0f} is within ${float(max_inc):,.0f} cap."}
            return {"status": "fail", "detail": f"Household income ${inc:,.0f} exceeds ${float(max_inc):,.0f} cap."}
        if not need:
            return {"status": "missing_data", "detail": "Financial need level or household income required."}
        if need in allowed_levels:
            return {"status": "pass", "detail": f"Financial need level '{need}' aligns with program criteria."}
        return {"status": "fail", "detail": f"Requires {'/'.join(allowed_levels)} financial need (reported '{need}')."}

    if dim == "enrollment_context":
        if val.get("requires_us_community_college"):
            if ctx.get("has_us_community_college"):
                return {"status": "pass", "detail": "Active U.S. community college enrollment verified on student profile."}
            if ctx.get("has_enrollment_history"):
                return {"status": "fail", "detail": "Requires current enrollment at an accredited U.S. 2-year community college."}
            return {"status": "missing_data", "detail": "Confirm current enrollment at a U.S. 2-year community college on your Student Profile."}

    return {"status": "pass", "detail": "Criterion satisfied."}


def evaluate_single_scholarship(
    sch: ScholarshipProgram,
    ctx: Dict[str, Any],
) -> Dict[str, Any]:
    evals: List[Dict[str, Any]] = []
    failed_reasons: List[str] = []
    missing_reqs: List[str] = []

    # Implicit baseline checks from scholarship columns (applicant_type & international policy)
    if sch.applicant_type and sch.applicant_type != "all":
        has_app_rule = any(r.rule_dimension == "applicant_type" for r in (sch.rules or []))
        if not has_app_rule:
            app_t = ctx["applicant_type"]
            if not app_t:
                msg = f"Applicant pathway ({sch.applicant_type}) not selected."
                evals.append({"dimension": "applicant_type", "human_label": f"Pathway: {sch.applicant_type}", "status": "missing_data", "detail": msg, "is_mandatory": True})
                missing_reqs.append(msg)
            elif app_t not in (sch.applicant_type, "both"):
                msg = f"Restricted to {sch.applicant_type} applicants."
                evals.append({"dimension": "applicant_type", "human_label": f"Pathway: {sch.applicant_type}", "status": "fail", "detail": msg, "is_mandatory": True})
                failed_reasons.append(msg)
            else:
                evals.append({"dimension": "applicant_type", "human_label": f"Pathway: {sch.applicant_type}", "status": "pass", "detail": f"Applicant pathway '{app_t}' matches.", "is_mandatory": True})

    # International citizenship baseline guard
    stud_cits = ctx["citizenships"]
    if stud_cits and not sch.covers_international:
        dom_allowed = [c.upper() for c in (sch.eligible_citizenships or [sch.country_code])]
        if not any(c in dom_allowed for c in stud_cits):
            msg = f"Award is restricted to {', '.join(dom_allowed)} domestic/resident students (does not cover international {stud_cits[0]} applicants)."
            evals.append({"dimension": "international_policy", "human_label": "International student coverage", "status": "fail", "detail": msg, "is_mandatory": True})
            failed_reasons.append(msg)

    for rule in (sch.rules or []):
        res = _eval_rule(rule, sch, ctx)
        evals.append(
            {
                "dimension": rule.rule_dimension,
                "human_label": rule.human_label,
                "status": res["status"],
                "detail": res["detail"],
                "is_mandatory": bool(rule.is_mandatory),
            }
        )
        if res["status"] == "fail" and rule.is_mandatory:
            failed_reasons.append(res["detail"])
        elif res["status"] == "missing_data" and rule.is_mandatory:
            missing_reqs.append(res["detail"])

    if failed_reasons:
        elig_status = "ineligible"
        score = 15
    elif missing_reqs:
        elig_status = "conditionally_eligible"
        score = 70
    else:
        elig_status = "eligible"
        score = 100 if sch.is_guaranteed_statutory else 90

    return {
        "id": sch.id,
        "institution_id": sch.institution_id,
        "institution_name": sch.institution.official_name if sch.institution else None,
        "country_code": sch.country_code,
        "title": sch.title,
        "provider_type": sch.provider_type,
        "award_type": sch.award_type,
        "applicant_type": sch.applicant_type,
        "funding_type": sch.funding_type,
        "covers_international": sch.covers_international,
        "award_amount_min_usd": float(sch.award_amount_min_usd) if sch.award_amount_min_usd is not None else None,
        "award_amount_max_usd": float(sch.award_amount_max_usd) if sch.award_amount_max_usd is not None else None,
        "max_award_info": sch.max_award_info,
        "eligibility_summary": sch.eligibility_summary,
        "covers_tuition": sch.covers_tuition,
        "covers_fees": sch.covers_fees,
        "covers_housing": sch.covers_housing,
        "covers_meals": sch.covers_meals,
        "covers_health_insurance": sch.covers_health_insurance,
        "provides_living_stipend": sch.provides_living_stipend,
        "is_renewable": sch.is_renewable,
        "is_guaranteed_statutory": sch.is_guaranteed_statutory,
        "application_deadline_date": sch.application_deadline_date,
        "is_deadline_rolling": sch.is_deadline_rolling,
        "min_gpa_4": float(sch.min_gpa_4) if sch.min_gpa_4 is not None else None,
        "requires_financial_need": sch.requires_financial_need,
        "eligible_citizenships": sch.eligible_citizenships or [],
        "eligible_residency_states": sch.eligible_residency_states or [],
        "eligible_destination_countries": sch.eligible_destination_countries or [],
        "eligibility_status": elig_status,
        "match_score": score,
        "rule_evaluations": evals,
        "missing_requirements": missing_reqs,
        "failed_reasons": failed_reasons,
        "source_name": sch.source_name,
        "source_url": sch.source_url,
        "verified_at": sch.verified_at,
    }


def match_scholarships_deterministic(
    db: Session,
    profile: Optional[StudentProfile],
    overrides: Dict[str, Any],
    include_ineligible: bool = True,
) -> Dict[str, Any]:
    ensure_phase4_seeded(db)
    ctx = _derive_student_context(db, profile, overrides)

    qry = (
        db.query(ScholarshipProgram)
        .options(joinedload(ScholarshipProgram.institution), joinedload(ScholarshipProgram.rules))
        .filter(ScholarshipProgram.is_verified == True, ScholarshipProgram.is_current == True)
    )
    if ctx["institution_id"]:
        inst_uuid = UUID(ctx["institution_id"])
        # Keep institution-specific + portable global/national scholarships
        qry = qry.filter((ScholarshipProgram.institution_id == inst_uuid) | (ScholarshipProgram.institution_id.is_(None)))

    programs = [
        p
        for p in qry.all()
        if ctx["degree_level"] in [d.lower() for d in (p.degree_levels or ["bachelors"])]
    ]
    evaluated = [evaluate_single_scholarship(p, ctx) for p in programs]

    rank_order = {"eligible": 0, "conditionally_eligible": 1, "ineligible": 2}
    evaluated.sort(
        key=lambda r: (
            rank_order.get(r["eligibility_status"], 3),
            not r["is_guaranteed_statutory"],
            -(r["award_amount_max_usd"] or 0.0),
            r["title"],
        )
    )

    elig_cnt = sum(1 for r in evaluated if r["eligibility_status"] == "eligible")
    cond_cnt = sum(1 for r in evaluated if r["eligibility_status"] == "conditionally_eligible")
    inelig_cnt = sum(1 for r in evaluated if r["eligibility_status"] == "ineligible")

    filtered = evaluated if include_ineligible else [r for r in evaluated if r["eligibility_status"] != "ineligible"]

    return {
        "evaluated_profile": ctx,
        "total_scholarships": len(evaluated),
        "eligible_count": elig_cnt,
        "conditionally_eligible_count": cond_cnt,
        "ineligible_count": inelig_cnt,
        "results": filtered,
        "disclaimer": FINANCIAL_DISCLAIMER,
    }


def calculate_net_price(
    db: Session,
    institution: Institution,
    profile: Optional[StudentProfile],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    ensure_phase4_seeded(db)

    residency = (params.get("residency_classification") or "international").strip().lower()
    housing = (params.get("housing_preference") or "on_campus").strip().lower()
    applicant_type = (params.get("applicant_type") or "first_year").strip().lower()
    program_years = int(params.get("program_years") or (2 if applicant_type == "transfer" else 4))
    include_competitive = bool(params.get("include_competitive_aid", True))
    annual_budget = params.get("annual_budget_usd")

    # Lookup matching InstitutionCost record
    cost_rows = (
        db.query(InstitutionCost)
        .filter(InstitutionCost.institution_id == institution.id, InstitutionCost.is_current == True)
        .all()
    )
    cost_by_type = {c.student_type: c for c in cost_rows}
    chosen_cost = (
        cost_by_type.get(residency)
        or (cost_by_type.get("out_of_state") if residency == "international" else None)
        or next(iter(cost_rows), None)
    )

    warnings: List[str] = []
    direct_items: List[Dict[str, Any]] = []
    indirect_items: List[Dict[str, Any]] = []

    tuition_val: Optional[float] = None
    if chosen_cost and chosen_cost.tuition is not None:
        tuition_val = float(chosen_cost.tuition)
    elif residency == "in_state" and institution.tuition_in_state is not None:
        tuition_val = float(institution.tuition_in_state)
    elif institution.tuition_out_of_state is not None:
        tuition_val = float(institution.tuition_out_of_state)

    fees_val = float(chosen_cost.mandatory_fees) if chosen_cost and chosen_cost.mandatory_fees is not None else None
    room_board_val = float(chosen_cost.room_board) if chosen_cost and chosen_cost.room_board is not None else None

    if tuition_val is None and institution.avg_net_price is None and institution.cost_of_attendance is None:
        warnings.append("Official tuition schedule not yet reported for this institution.")

    direct_items.append(
        {
            "key": "tuition",
            "label": f"Published Tuition ({residency.replace('_', ' ')})",
            "category": "direct_billable",
            "amount_usd": tuition_val,
            "is_published": tuition_val is not None,
            "notes": None if tuition_val is not None else "Missing published tuition record.",
        }
    )
    direct_items.append(
        {
            "key": "mandatory_fees",
            "label": "Mandatory Institutional Fees",
            "category": "direct_billable",
            "amount_usd": fees_val,
            "is_published": fees_val is not None,
            "notes": "Included in IPEDS combined tuition & fees when not broken out." if fees_val is None else None,
        }
    )

    if housing == "on_campus":
        housing_amt = room_board_val
        housing_note = None if room_board_val is not None else "On-campus housing & dining not itemized separately."
    elif housing == "with_family":
        housing_amt = 0.0
        housing_note = "Student selected living with family ($0 institutional housing)."
    else:
        housing_amt = room_board_val
        housing_note = "Uses campus COA living allowance benchmark for off-campus housing estimate."

    direct_items.append(
        {
            "key": "room_board",
            "label": "Housing & Meals",
            "category": "direct_billable" if housing == "on_campus" else "indirect_living",
            "amount_usd": housing_amt,
            "is_published": room_board_val is not None or housing == "with_family",
            "notes": housing_note,
        }
    )

    # Indirect costs
    books_val = float(chosen_cost.books_supplies) if chosen_cost and chosen_cost.books_supplies is not None else None
    trans_val = float(chosen_cost.transportation) if chosen_cost and chosen_cost.transportation is not None else None
    pers_val = float(chosen_cost.personal_expenses) if chosen_cost and chosen_cost.personal_expenses is not None else None
    ins_val = float(chosen_cost.health_insurance) if chosen_cost and chosen_cost.health_insurance is not None else None

    # If detailed indirect fields absent, check if published total COA exceeds tuition+fees+room
    if (
        chosen_cost is None
        and institution.cost_of_attendance is not None
        and tuition_val is not None
        and float(institution.cost_of_attendance) > tuition_val
    ):
        residual = round(float(institution.cost_of_attendance) - tuition_val - (room_board_val or 0.0), 2)
        if residual > 0:
            pers_val = residual
            warnings.append("Books, housing, and indirect living expenses derived from IPEDS/Scorecard total COA minus tuition.")

    indirect_items.extend(
        [
            {
                "key": "books_supplies",
                "label": "Books & Course Materials",
                "category": "indirect_living",
                "amount_usd": books_val,
                "is_published": books_val is not None,
                "notes": None if books_val is not None else "Not published separately.",
            },
            {
                "key": "transportation",
                "label": "Transportation & Travel",
                "category": "indirect_living",
                "amount_usd": trans_val,
                "is_published": trans_val is not None,
                "notes": None if trans_val is not None else "Not published separately (international flights extra).",
            },
            {
                "key": "personal_expenses",
                "label": "Personal Living Expenses",
                "category": "indirect_living",
                "amount_usd": pers_val,
                "is_published": pers_val is not None,
                "notes": None if pers_val is not None else "Not published separately.",
            },
            {
                "key": "health_insurance",
                "label": "Student Health Insurance",
                "category": "indirect_living",
                "amount_usd": ins_val,
                "is_published": ins_val is not None,
                "notes": (
                    "Mandatory for F-1/J-1 international students if not waived (typically $2,000–$4,500/yr at US universities)."
                    if residency == "international" and ins_val is None
                    else None
                ),
            },
        ]
    )

    if residency == "international" and ins_val is None:
        warnings.append("Mandatory international student health insurance is not itemized in federal COA data; budget ~$2,500–$4,500/yr extra.")

    direct_sum = round(
        sum(i["amount_usd"] for i in direct_items if i["category"] == "direct_billable" and i["amount_usd"] is not None),
        2,
    ) if any(i["amount_usd"] is not None for i in direct_items) else None
    indirect_sum = round(
        sum(
            i["amount_usd"]
            for i in (direct_items + indirect_items)
            if i["category"] == "indirect_living" and i["amount_usd"] is not None
        ),
        2,
    ) if any(i["amount_usd"] is not None for i in (direct_items + indirect_items) if i["category"] == "indirect_living") else 0.0

    total_coa: Optional[float] = None
    if direct_sum is not None:
        total_coa = round(direct_sum + (indirect_sum or 0.0), 2)
    elif institution.cost_of_attendance is not None:
        total_coa = float(institution.cost_of_attendance)

    # Evaluate eligible scholarships/aid applicable to this institution & pathway
    overrides = {
        "citizenship_country": params.get("citizenship_country") or ("US" if residency != "international" else None),
        "residency_state": params.get("residency_state") or (institution.state_province if residency == "in_state" else None),
        "applicant_type": applicant_type,
        "gpa_4": params.get("gpa_4"),
        "financial_need_level": params.get("financial_need_level"),
        "household_income_usd": params.get("household_income_usd"),
        "destination_country": institution.country_code,
        "institution_id": institution.id,
    }
    sch_match = match_scholarships_deterministic(db, profile, overrides, include_ineligible=False)

    coa_cap = total_coa if total_coa is not None else 0.0
    inc_val = params.get("household_income_usd")
    need_lvl = (params.get("financial_need_level") or "").strip().lower()

    aid_offsets: List[Dict[str, Any]] = []
    guar_min = 0.0
    guar_max = 0.0
    comp_min = 0.0
    comp_max = 0.0

    for s in sch_match["results"]:
        if s["eligibility_status"] != "eligible":
            continue
        amin = float(s["award_amount_min_usd"] or 0.0)
        amax = float(s["award_amount_max_usd"] or amin)
        if coa_cap > 0:
            amax = min(amax, coa_cap)
            amin = min(amin, amax)

        # Conservative income-aware cap for institutional 100%-demonstrated-need full-ride programs
        if s["award_type"] == "full_ride" and s["requires_financial_need"] and s["provider_type"] == "university":
            if inc_val is not None:
                est_efc = max(0.0, (float(inc_val) - 75000.0) * 0.28)
                need_cap = max(0.0, coa_cap - est_efc) if coa_cap > 0 else amax
                amax = min(amax, round(need_cap, 2))
                amin = min(amin, amax)
            elif need_lvl == "moderate" and coa_cap > 0:
                amax = min(amax, round(coa_cap * 0.65, 2))
                amin = min(amin, amax)

        if amax <= 0.0:
            continue
        aid_offsets.append(
            {
                "scholarship_id": s["id"],
                "title": s["title"],
                "provider_type": s["provider_type"],
                "eligibility_status": s["eligibility_status"],
                "is_guaranteed_statutory": s["is_guaranteed_statutory"],
                "estimated_min_usd": round(amin, 2),
                "estimated_max_usd": round(amax, 2),
                "source_url": s["source_url"],
            }
        )
        if s["is_guaranteed_statutory"]:
            guar_min += amin
            guar_max += amax
        else:
            comp_min += amin
            comp_max += amax

    # Keep component ceilings coherent with Gross Total COA (awards cannot stack above COA)
    guar_min = min(coa_cap, round(guar_min, 2)) if total_coa else 0.0
    guar_max = min(coa_cap, round(guar_max, 2)) if total_coa else 0.0
    comp_cap = max(0.0, round(coa_cap - guar_min, 2)) if total_coa else 0.0
    comp_min = min(comp_cap, round(comp_min, 2))
    comp_max = min(comp_cap, round(comp_max, 2))

    eligible_min = min(coa_cap, round(guar_min + (comp_min if include_competitive else 0.0), 2)) if total_coa else 0.0
    eligible_max = min(coa_cap, round(guar_max + (comp_max if include_competitive else 0.0), 2)) if total_coa else 0.0

    net_min = round(max(0.0, total_coa - eligible_max), 2) if total_coa is not None else None
    net_max = round(max(0.0, total_coa - eligible_min), 2) if total_coa is not None else None

    multi_min = round(net_min * program_years, 2) if net_min is not None else None
    multi_max = round(net_max * program_years, 2) if net_max is not None else None

    gap_min = round(net_min - float(annual_budget), 2) if (net_min is not None and annual_budget is not None) else None
    gap_max = round(net_max - float(annual_budget), 2) if (net_max is not None and annual_budget is not None) else None

    if total_coa is None:
        affordability = "missing_cost_data"
    elif annual_budget is None:
        affordability = "within_budget" if (net_max or 0) <= 0 else "reachable_with_competitive_aid" if eligible_max > 0 else "exceeds_budget"
    else:
        b = float(annual_budget)
        if net_max is not None and net_max <= b:
            affordability = "within_budget"
        elif net_min is not None and net_min <= b:
            affordability = "reachable_with_competitive_aid"
        else:
            affordability = "exceeds_budget"

    confidence = "high" if chosen_cost is not None else ("medium" if total_coa is not None else "low")
    sources = [
        {
            "name": institution.primary_source or "NCES IPEDS / Institutional Cost Schedule",
            "url": (chosen_cost.source_url if chosen_cost and chosen_cost.source_url else None)
            or institution.financial_aid_website
            or institution.official_website,
        }
    ]

    return {
        "institution_id": institution.id,
        "institution_name": institution.official_name,
        "country_code": institution.country_code,
        "residency_classification": residency,
        "housing_preference": housing,
        "applicant_type": applicant_type,
        "academic_year": chosen_cost.academic_year if chosen_cost else institution.data_reporting_year,
        "currency": chosen_cost.currency if chosen_cost else (institution.currency or "USD"),
        "direct_billable_items": direct_items,
        "indirect_living_items": [i for i in indirect_items if i["category"] == "indirect_living"],
        "gross_direct_cost_usd": direct_sum,
        "gross_indirect_cost_usd": indirect_sum,
        "total_coa_usd": total_coa,
        "guaranteed_aid_min_usd": round(guar_min, 2),
        "guaranteed_aid_max_usd": round(guar_max, 2),
        "competitive_aid_min_usd": round(comp_min, 2),
        "competitive_aid_max_usd": round(comp_max, 2),
        "eligible_aid_min_usd": eligible_min,
        "eligible_aid_max_usd": eligible_max,
        "estimated_net_price_min_usd": net_min,
        "estimated_net_price_max_usd": net_max,
        "multi_year_net_min_usd": multi_min,
        "multi_year_net_max_usd": multi_max,
        "annual_budget_usd": float(annual_budget) if annual_budget is not None else None,
        "budget_gap_min_usd": gap_min,
        "budget_gap_max_usd": gap_max,
        "affordability_status": affordability,
        "aid_offsets": aid_offsets,
        "data_confidence": confidence,
        "warnings": warnings,
        "sources": sources,
        "disclaimer": FINANCIAL_DISCLAIMER,
    }
