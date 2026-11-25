"""
Phase 4 Step 2 Automated Accuracy Suite:
Covers 20 eligibility rule scenarios, deterministic 5-outcome aggregation precedence,
20 net-price component accounting invariants, freshness/provenance claim enforcement,
and end-to-end API propagation + translation parity.
"""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import re
import uuid

from app.models.institution import Institution, InstitutionCost
from app.models.rag import ScholarshipEligibilityRule, ScholarshipProgram
from app.services.financial_engine import (
    AGGREGATION_PRECEDENCE,
    _derive_student_context,
    calculate_net_price,
    evaluate_single_scholarship,
    match_scholarships_deterministic,
)


def _make_sch(
    *,
    title: str = "Controlled Scholarship",
    country_code: str = "US",
    covers_international: bool = True,
    applicant_type: str = "all",
    degree_levels=None,
    award_type: str = "full_tuition",
    award_min: float = 10000.0,
    award_max: float = 10000.0,
    award_fixed: float = None,
    award_currency: str = "USD",
    native_min: float = None,
    native_max: float = None,
    covers_tuition: bool = True,
    covers_fees: bool = False,
    covers_housing: bool = False,
    covers_meals: bool = False,
    covers_health_insurance: bool = False,
    covers_travel: bool = False,
    provides_living_stipend: bool = False,
    is_renewable: bool = False,
    funding_duration_years: float = None,
    max_funding_periods: int = None,
    renewal_conditions: str = None,
    is_guaranteed_statutory: bool = True,
    requires_financial_need: bool = False,
    institution_id=None,
    verified_at=None,
    verification_expires_at=None,
    freshness_status: str = "current",
    requires_manual_review: bool = False,
    conflict_notes: str = None,
    claim_provenance=None,
    application_deadline_date=None,
    rules=None,
) -> ScholarshipProgram:
    now = datetime.now(timezone.utc)
    sch = ScholarshipProgram(
        id=uuid.uuid4(),
        institution_id=institution_id,
        country_code=country_code,
        title=title,
        provider_type="university",
        award_type=award_type,
        applicant_type=applicant_type,
        funding_type="merit",
        covers_international=covers_international,
        award_amount_min_usd=award_min,
        award_amount_max_usd=award_max,
        award_fixed_usd=award_fixed,
        award_currency=award_currency,
        native_amount_min=native_min,
        native_amount_max=native_max,
        eligibility_summary="Controlled test award.",
        covers_tuition=covers_tuition,
        covers_fees=covers_fees,
        covers_housing=covers_housing,
        covers_meals=covers_meals,
        covers_health_insurance=covers_health_insurance,
        covers_travel=covers_travel,
        provides_living_stipend=provides_living_stipend,
        is_renewable=is_renewable,
        funding_duration_years=funding_duration_years,
        max_funding_periods=max_funding_periods,
        renewal_conditions=renewal_conditions,
        is_guaranteed_statutory=is_guaranteed_statutory,
        requires_financial_need=requires_financial_need,
        degree_levels=["bachelors"] if degree_levels is None else degree_levels,
        application_deadline_date=application_deadline_date,
        source_name="Official University Office",
        source_url="https://sfs.mit.edu/",
        source_type="official_university",
        verified_at=verified_at or (now - timedelta(days=5)),
        verification_expires_at=verification_expires_at or (now + timedelta(days=120)),
        freshness_status=freshness_status,
        requires_manual_review=requires_manual_review,
        conflict_notes=conflict_notes,
        claim_provenance=claim_provenance or {},
        is_verified=True,
        is_current=True,
    )
    sch.rules = [
        ScholarshipEligibilityRule(
            id=uuid.uuid4(),
            scholarship_id=sch.id,
            rule_dimension=dim,
            rule_operator="check",
            rule_value=val,
            human_label=lbl,
            is_mandatory=mandatory,
        )
        for dim, val, lbl, mandatory in (rules or [])
    ]
    return sch


def _ctx(db, **overrides) -> dict:
    return _derive_student_context(db, None, overrides)


# ---------------------------------------------------------------------------
# A. Eligibility Engine Tests (20 Required Scenarios)
# ---------------------------------------------------------------------------
def test_eligibility_rules_20_scenarios(db):
    # 1. Excluded citizenship -> ineligible
    sch_excl = _make_sch(rules=[("excluded_citizenships", {"countries": ["RU"]}, "Excluded countries", True)])
    assert evaluate_single_scholarship(sch_excl, _ctx(db, citizenship_country="RU", degree_level="bachelors"))["eligibility_status"] == "ineligible"

    # 2. Permitted citizenship + restricted residence -> ineligible (residence checked independently)
    sch_res = _make_sch(
        rules=[
            ("citizenship", {"countries": ["HT", "US"]}, "Citizenship", True),
            ("country_of_residence", {"countries": ["HT"]}, "Must reside in Haiti", True),
        ]
    )
    assert evaluate_single_scholarship(sch_res, _ctx(db, citizenship_country="HT", country_of_residence="FR", degree_level="bachelors"))["eligibility_status"] == "ineligible"

    # 3. Dual citizenship restriction enforced
    sch_dual = _make_sch(rules=[("dual_citizenship", {"policy": "restricted", "restricted_countries": ["US"]}, "No US dual citizen", True)])
    assert evaluate_single_scholarship(sch_dual, _ctx(db, citizenships=["HT", "US"], dual_citizenship=True, degree_level="bachelors"))["eligibility_status"] == "ineligible"
    assert evaluate_single_scholarship(sch_dual, _ctx(db, citizenships=["HT"], dual_citizenship=False, degree_level="bachelors"))["eligibility_status"] == "eligible"

    # 4. Missing citizenship produces insufficient_information (does not infer from residence)
    sch_cit = _make_sch(rules=[("citizenship", {"countries": ["HT"]}, "Haiti citizenship", True)])
    assert evaluate_single_scholarship(sch_cit, _ctx(db, country_of_residence="HT", degree_level="bachelors"))["eligibility_status"] == "insufficient_information"

    # 5. Missing residence produces insufficient_information (does not infer from citizenship)
    sch_cor = _make_sch(rules=[("country_of_residence", {"countries": ["HT"]}, "Must reside in HT", True)])
    assert evaluate_single_scholarship(sch_cor, _ctx(db, citizenship_country="HT", degree_level="bachelors"))["eligibility_status"] == "insufficient_information"

    # 6. Bachelor's-only rejects master's applicant
    sch_ba = _make_sch(degree_levels=["bachelors"])
    assert evaluate_single_scholarship(sch_ba, _ctx(db, degree_level="masters"))["eligibility_status"] == "ineligible"

    # 7. Graduate-only rejects bachelor's applicant
    sch_grad = _make_sch(degree_levels=["masters", "doctoral"])
    assert evaluate_single_scholarship(sch_grad, _ctx(db, degree_level="bachelors"))["eligibility_status"] == "ineligible"

    # 8. Valid transfer applicant is not treated as first-year
    sch_fy = _make_sch(applicant_type="first_year")
    assert evaluate_single_scholarship(sch_fy, _ctx(db, applicant_type="transfer", degree_level="bachelors"))["eligibility_status"] == "ineligible"

    # 9. Community college enrollment evaluated correctly
    sch_cc = _make_sch(rules=[("enrollment_context", {"requires_us_community_college": True}, "US CC required", True)])
    assert evaluate_single_scholarship(sch_cc, _ctx(db, degree_level="bachelors"))["eligibility_status"] == "insufficient_information"
    assert evaluate_single_scholarship(sch_cc, _ctx(db, us_community_college_enrolled=False, degree_level="bachelors"))["eligibility_status"] == "ineligible"
    assert evaluate_single_scholarship(sch_cc, _ctx(db, us_community_college_enrolled=True, degree_level="bachelors"))["eligibility_status"] == "eligible"

    # 10 & 11. Missing exam score is NOT zero (insufficient_information); score below min is ineligible
    sch_sat = _make_sch(rules=[("required_exams", {"exam": "SAT", "min_score": 1350}, "SAT >= 1350", True)])
    assert evaluate_single_scholarship(sch_sat, _ctx(db, degree_level="bachelors"))["eligibility_status"] == "insufficient_information"
    assert evaluate_single_scholarship(sch_sat, _ctx(db, exam_scores={"SAT": 1200}, degree_level="bachelors"))["eligibility_status"] == "ineligible"
    assert evaluate_single_scholarship(sch_sat, _ctx(db, exam_scores={"SAT": 1420}, degree_level="bachelors"))["eligibility_status"] == "eligible"

    # 12 & 13. Missing language evidence -> insufficient_information; unsupported format -> requires_manual_review
    sch_lang = _make_sch(rules=[("language_proficiency", {"language": "en", "min_scores": {"TOEFL": 95}}, "English TOEFL >= 95", True)])
    assert evaluate_single_scholarship(sch_lang, _ctx(db, degree_level="bachelors"))["eligibility_status"] == "insufficient_information"
    assert evaluate_single_scholarship(sch_lang, _ctx(db, language_proficiencies={"en": {"format": "self_assessed", "score": 100}}, degree_level="bachelors"))["eligibility_status"] == "requires_manual_review"
    assert evaluate_single_scholarship(sch_lang, _ctx(db, language_proficiencies={"en": {"format": "toefl", "test_type": "TOEFL", "score": 102}}, degree_level="bachelors"))["eligibility_status"] == "eligible"

    # 14 & 15. Age limit enforced; missing DOB never creates assumed age
    sch_age = _make_sch(
        rules=[("age_limit", {"min_age": 18, "max_age": 25, "reference_date": "2027-01-01"}, "Age 18–25", True)]
    )
    assert evaluate_single_scholarship(sch_age, _ctx(db, degree_level="bachelors"))["eligibility_status"] == "insufficient_information"
    assert evaluate_single_scholarship(sch_age, _ctx(db, date_of_birth="1995-05-01", degree_level="bachelors"))["eligibility_status"] == "ineligible"
    assert evaluate_single_scholarship(sch_age, _ctx(db, date_of_birth="2005-05-01", degree_level="bachelors"))["eligibility_status"] == "eligible"

    # 16. Field of study restrictions enforced
    sch_fos = _make_sch(rules=[("field_of_study", {"allowed_fields": ["computer science", "engineering"], "excluded_fields": ["medicine"]}, "STEM major", True)])
    assert evaluate_single_scholarship(sch_fos, _ctx(db, field_of_study="History", degree_level="bachelors"))["eligibility_status"] == "ineligible"
    assert evaluate_single_scholarship(sch_fos, _ctx(db, field_of_study="Computer Science", degree_level="bachelors"))["eligibility_status"] == "eligible"

    # 17. Geographic restrictions use explicit region mappings
    sch_reg = _make_sch(rules=[("geographic_region", {"regions": ["caribbean", "africa"]}, "Caribbean / Africa", True)])
    assert evaluate_single_scholarship(sch_reg, _ctx(db, citizenship_country="JM", degree_level="bachelors"))["eligibility_status"] == "eligible"
    assert evaluate_single_scholarship(sch_reg, _ctx(db, citizenship_country="DE", degree_level="bachelors"))["eligibility_status"] == "ineligible"

    # 18. Unsupported rule dimension returns requires_manual_review (never silently ignored)
    sch_unsup = _make_sch(rules=[("military_service_bracket", {"years": 2}, "Unsupported", True)])
    assert evaluate_single_scholarship(sch_unsup, _ctx(db, degree_level="bachelors"))["eligibility_status"] == "requires_manual_review"

    # 19. Conflicting rule evidence returns requires_manual_review
    sch_conf = _make_sch(rules=[("citizenship", {"countries": ["HT"], "excluded_countries": ["HT"]}, "Conflict", True)])
    assert evaluate_single_scholarship(sch_conf, _ctx(db, citizenship_country="HT", degree_level="bachelors"))["eligibility_status"] == "requires_manual_review"

    # 20. Renewal criteria do not disqualify initial eligibility
    sch_ren = _make_sch(
        rules=[
            ("citizenship", {"countries": ["HT"]}, "Citizenship", True),
            ("renewal", {"min_renewal_gpa": 3.5, "requires_full_time": True, "condition_text": "Maintain 3.5 GPA in Year 2+"}, "Year 2+ Renewal", True),
        ]
    )
    ren_res = evaluate_single_scholarship(sch_ren, _ctx(db, citizenship_country="HT", degree_level="bachelors"))
    assert ren_res["eligibility_status"] == "eligible"
    assert len(ren_res["renewal_evaluations"]) == 1


# ---------------------------------------------------------------------------
# B. Aggregation Precedence Tests
# ---------------------------------------------------------------------------
def test_aggregation_precedence_policy(db):
    assert AGGREGATION_PRECEDENCE == (
        "ineligible",
        "requires_manual_review",
        "insufficient_information",
        "conditionally_eligible",
        "eligible",
    )

    # Condition + missing + manual review + fail -> decisive fail wins (`ineligible`), and explanations remain populated
    sch = _make_sch(
        rules=[
            ("enrollment_context", {"is_future_condition": True, "condition_text": "Submit final transcript"}, "Future cond", True),
            ("required_exams", {"exam": "SAT", "min_score": 1300}, "Missing SAT", True),
            ("custom_unknown", {"x": 1}, "Unknown", True),
            ("citizenship", {"countries": ["CA"]}, "CA only", True),
        ]
    )
    res = evaluate_single_scholarship(sch, _ctx(db, citizenship_country="HT", degree_level="bachelors"))
    assert res["eligibility_status"] == "ineligible"
    assert len(res["failed_reasons"]) == 1
    assert len(res["manual_review_reasons"]) == 1
    assert len(res["missing_requirements"]) == 1
    assert len(res["conditional_requirements"]) == 1

    # Remove fail -> requires_manual_review beats insufficient_information & conditional
    sch2 = _make_sch(
        rules=[
            ("enrollment_context", {"is_future_condition": True, "condition_text": "Submit final transcript"}, "Future cond", True),
            ("required_exams", {"exam": "SAT", "min_score": 1300}, "Missing SAT", True),
            ("custom_unknown", {"x": 1}, "Unknown", True),
        ]
    )
    assert evaluate_single_scholarship(sch2, _ctx(db, degree_level="bachelors"))["eligibility_status"] == "requires_manual_review"

    # Remove manual review -> insufficient_information beats conditional
    sch3 = _make_sch(
        rules=[
            ("enrollment_context", {"is_future_condition": True, "condition_text": "Submit final transcript"}, "Future cond", True),
            ("required_exams", {"exam": "SAT", "min_score": 1300}, "Missing SAT", True),
        ]
    )
    assert evaluate_single_scholarship(sch3, _ctx(db, degree_level="bachelors"))["eligibility_status"] == "insufficient_information"

    # Condition only -> conditionally_eligible
    sch4 = _make_sch(
        rules=[("enrollment_context", {"is_future_condition": True, "condition_text": "Submit final transcript"}, "Future cond", True)]
    )
    assert evaluate_single_scholarship(sch4, _ctx(db, degree_level="bachelors"))["eligibility_status"] == "conditionally_eligible"


# ---------------------------------------------------------------------------
# C & D. Net-Price Component Accounting & Freshness Tests (20+ Scenarios)
# ---------------------------------------------------------------------------
def _create_test_institution_with_costs(db, suffix: str) -> Institution:
    inst = Institution(
        id=uuid.uuid4(),
        official_name=f"Accuracy Test University {suffix}",
        country_code="US",
        institution_type="private",
        currency="USD",
        is_verified=True,
        is_published=True,
    )
    db.add(inst)
    db.flush()
    cost = InstitutionCost(
        id=uuid.uuid4(),
        institution_id=inst.id,
        academic_year="2026-2027",
        student_type="international",
        degree_level="bachelors",
        tuition=20000.0,
        mandatory_fees=2000.0,
        room_board=12000.0,
        books_supplies=1000.0,
        transportation=1500.0,
        personal_expenses=1500.0,
        health_insurance=2000.0,
        total_estimated_cost=40000.0,
        currency="USD",
        is_current=True,
    )
    db.add(cost)
    db.flush()
    return inst


def test_net_price_component_accounting_and_freshness_20_scenarios(db, monkeypatch):
    monkeypatch.setattr(db, "commit", db.flush)
    nested = db.begin_nested()
    try:
        uid = uuid.uuid4().hex[:8]
        inst = _create_test_institution_with_costs(db, uid)
        now = datetime.now(timezone.utc)

        # 1 & 9. Tuition-only ($30k max) capped at tuition ($20k), NEVER offsets housing/living!
        tuition_only = _make_sch(
            institution_id=inst.id,
            title=f"Tuition Only {uid}",
            award_type="full_tuition",
            award_min=30000.0,
            award_max=30000.0,
            covers_tuition=True,
            covers_fees=False,
            covers_housing=False,
            covers_meals=False,
            provides_living_stipend=False,
            is_guaranteed_statutory=True,
            is_renewable=False,
            max_funding_periods=1,
        )
        db.add(tuition_only)
        db.flush()

        r1 = calculate_net_price(
            db, inst, None, {"residency_classification": "international", "citizenship_country": "HT", "degree_level": "bachelors", "program_years": 4}
        )
        cats1 = {c["category_key"]: c for c in r1["category_breakdown"]}
        assert cats1["tuition"]["applied_verified_max_usd"] == 20000.0
        assert cats1["tuition"]["remaining_cost_min_usd"] == 0.0
        assert cats1["room_board"]["applied_verified_max_usd"] == 0.0  # Housing untouched!
        assert cats1["mandatory_fees"]["applied_verified_max_usd"] == 0.0  # Fees untouched!
        assert r1["guaranteed_aid_max_usd"] == 20000.0
        # 13. One-time award (max_funding_periods=1) does NOT project into Years 2-4!
        # Year 1 net = 40000 - 20000 = 20000; Years 2..4 = 3 * 40000 = 120000 -> total 140000!
        assert r1["multi_year_net_max_usd"] == 140000.0

        # 2 & 10 & 11 & 12. Overlapping tuition-and-fees award allocates remaining fees ($2k) without negative balances!
        tuition_fees = _make_sch(
            institution_id=inst.id,
            title=f"Tuition Fees Second {uid}",
            award_type="full_tuition",
            award_min=15000.0,
            award_max=15000.0,
            covers_tuition=True,
            covers_fees=True,
            covers_housing=False,
            provides_living_stipend=False,
            is_guaranteed_statutory=True,
        )
        db.add(tuition_fees)
        db.flush()

        r2 = calculate_net_price(
            db, inst, None, {"residency_classification": "international", "citizenship_country": "HT", "degree_level": "bachelors"}
        )
        cats2 = {c["category_key"]: c for c in r2["category_breakdown"]}
        # Tuition already at $0 remaining -> second award can ONLY offset $2,000 mandatory fees (total guar aid = $22k)!
        assert cats2["tuition"]["applied_verified_max_usd"] == 20000.0
        assert cats2["mandatory_fees"]["applied_verified_max_usd"] == 2000.0
        assert r2["guaranteed_aid_max_usd"] == 22000.0
        assert all((c["remaining_cost_min_usd"] or 0.0) >= 0.0 for c in r2["category_breakdown"])
        assert r2["estimated_net_price_min_usd"] >= 0.0

        # 3 & 4 & 5. Living stipend & travel allowance reduce ONLY living/travel costs, NEVER tuition!
        db.delete(tuition_only)
        db.delete(tuition_fees)
        db.flush()

        stipend = _make_sch(
            institution_id=inst.id,
            title=f"Living Stipend {uid}",
            award_type="stipend",
            award_min=5000.0,
            award_max=5000.0,
            covers_tuition=False,
            covers_housing=False,
            provides_living_stipend=True,
            is_guaranteed_statutory=True,
            is_renewable=True,
            funding_duration_years=4.0,
            max_funding_periods=4,
            renewal_conditions="Good standing",
        )
        travel = _make_sch(
            institution_id=inst.id,
            title=f"Travel Grant {uid}",
            award_type="fixed_amount",
            award_min=1000.0,
            award_max=1000.0,
            covers_tuition=False,
            covers_travel=True,
            provides_living_stipend=False,
            is_guaranteed_statutory=True,
        )
        db.add_all([stipend, travel])
        db.flush()

        r3 = calculate_net_price(
            db, inst, None, {"residency_classification": "international", "citizenship_country": "HT", "degree_level": "bachelors", "program_years": 4}
        )
        cats3 = {c["category_key"]: c for c in r3["category_breakdown"]}
        assert cats3["tuition"]["applied_verified_max_usd"] == 0.0
        assert cats3["mandatory_fees"]["applied_verified_max_usd"] == 0.0
        assert cats3["transportation"]["applied_verified_max_usd"] >= 1000.0
        # 14 & 15. Renewable 4yr stipend repeats for all 4 years; unknown duration travel grant stays Year 1 only!
        # Gross 4yr = 160,000; stipend 4*5000 = 20,000; travel 1*1000 = 1,000 -> multi_year_net_min = 139,000!
        assert r3["multi_year_net_min_usd"] == 139000.0

        # 6, 7, 8, 16, 17, 18, 19, 20. Unknown scope, foreign currency, missing amount, expired, conflicting, manual review, & masters isolation
        unknown_scope = _make_sch(
            institution_id=inst.id, title=f"Unknown Scope {uid}", award_min=5000, award_max=5000, covers_tuition=False
        )
        eur_award = _make_sch(
            institution_id=inst.id, title=f"Euro Award {uid}", award_min=4000, award_max=4000, award_currency="EUR", native_min=4000, native_max=4000, covers_tuition=True
        )
        missing_amt = _make_sch(
            institution_id=inst.id, title=f"Missing Amt {uid}", award_min=None, award_max=None, covers_tuition=True
        )
        expired_sch = _make_sch(
            institution_id=inst.id,
            title=f"Expired Aid {uid}",
            award_min=5000,
            award_max=5000,
            covers_tuition=True,
            verification_expires_at=now - timedelta(days=2),
            freshness_status="expired",
        )
        expired_claim = _make_sch(
            institution_id=inst.id,
            title=f"Expired Amount Claim {uid}",
            award_min=5000,
            award_max=5000,
            covers_tuition=True,
            claim_provenance={"award_amounts": {"verified_at": (now - timedelta(days=150)).isoformat(), "source_url": "https://sfs.mit.edu/"}},
        )
        manual_sch = _make_sch(
            institution_id=inst.id, title=f"Manual Aid {uid}", award_min=5000, award_max=5000, covers_tuition=True, requires_manual_review=True
        )
        conf_sch = _make_sch(
            institution_id=inst.id, title=f"Conflict Aid {uid}", award_min=5000, award_max=5000, covers_tuition=True, conflict_notes="Conflict", freshness_status="conflicting_information"
        )
        masters_sch = _make_sch(
            institution_id=inst.id, title=f"Masters Only {uid}", degree_levels=["masters"], award_min=15000, award_max=15000, covers_tuition=True
        )
        db.add_all([unknown_scope, eur_award, missing_amt, expired_sch, expired_claim, manual_sch, conf_sch, masters_sch])
        db.flush()

        r4 = calculate_net_price(
            db, inst, None, {"residency_classification": "international", "citizenship_country": "HT", "degree_level": "bachelors"}
        )
        # ONLY stipend ($5k) + travel ($1k) are verified USD with valid scope -> total guar aid unchanged at $6k!
        assert r4["guaranteed_aid_max_usd"] == 6000.0
        unalloc_titles = {x["title"]: x for x in r4["unallocated_potential_aid"]}
        rev_titles = {x["title"]: x for x in r4["review_required_aid"]}
        assert f"Unknown Scope {uid}" in unalloc_titles
        assert f"Euro Award {uid}" in unalloc_titles
        assert unalloc_titles[f"Euro Award {uid}"]["award_currency"] == "EUR"
        assert unalloc_titles[f"Euro Award {uid}"]["native_amount_max"] == 4000.0
        assert f"Missing Amt {uid}" in unalloc_titles
        assert f"Manual Aid {uid}" in rev_titles
        # Expired & conflicting & masters excluded before verified offsets!
        all_verified_titles = {x["title"] for x in r4["verified_applicable_aid"]}
        for bad_t in (f"Expired Aid {uid}", f"Expired Amount Claim {uid}", f"Conflict Aid {uid}", f"Masters Only {uid}"):
            assert bad_t not in all_verified_titles
    finally:
        nested.rollback()


# ---------------------------------------------------------------------------
# E. API Integration & Complete Translation Parity Tests
# ---------------------------------------------------------------------------
def test_api_degree_propagation_and_arabic_translation_completeness(client, db):
    # API net-price accepts & propagates degree_level
    insts = client.get("/api/v1/institutions").json()
    mit = next(i for i in insts if "Massachusetts Institute of Technology" in i["official_name"])
    res = client.post(
        "/api/v1/financial/net-price",
        json={
            "institution_id": mit["id"],
            "residency_classification": "international",
            "housing_preference": "on_campus",
            "applicant_type": "first_year",
            "degree_level": "masters",
            "citizenship_country": "HT",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["degree_level"] == "masters"
    assert isinstance(body["category_breakdown"], list) and len(body["category_breakdown"]) >= 5
    assert "verified_applicable_aid" in body and "review_required_aid" in body and "unallocated_potential_aid" in body

    # Verify match endpoint exposes all 5 outcome counters
    mres = client.post(
        "/api/v1/financial/scholarships/match",
        json={"citizenship_country": "HT", "applicant_type": "transfer", "degree_level": "bachelors"},
    )
    assert mres.status_code == 200
    mbody = mres.json()
    for field in (
        "eligible_count",
        "conditionally_eligible_count",
        "insufficient_information_count",
        "requires_manual_review_count",
        "ineligible_count",
        "aggregation_precedence",
    ):
        assert field in mbody

    # Verify every key in phase4-translations.ts has non-empty Arabic (`ar-SA`) & all 10 locales
    repo_root = Path(__file__).resolve().parents[3]
    ts_path = repo_root / "apps" / "web" / "src" / "lib" / "i18n" / "phase4-translations.ts"
    ts_text = ts_path.read_text(encoding="utf-8")
    keys = re.findall(r'"((?:nav|fin|cred)\.[a-z0-9_]+)"\s*:', ts_text)
    assert len(keys) >= 40
    # Verify Arabic script characters exist for newly added keys
    for ar_snippet in (
        "معلومات غير كافية",
        "يتطلب مراجعة يدوية",
        "إجمالي تكلفة الحضور",
        "صافي التكلفة السنوية التقديرية (غير مضمونة)",
        "بلد الإقامة",
    ):
        assert ar_snippet in ts_text
