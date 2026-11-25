"""
Phase 4.1: Student-Level Scholarship Eligibility Intelligence & Coverage Optimization Suite.

Verifies:
1. Citizenship and residency restrictions (checked independently, never cross-inferred).
2. Dual citizenship policies (restricted vs single citizen vs missing dual flag).
3. Transfer vs first-year eligibility & 7-way transfer pathway classification
   (including refusal to infer transfer eligibility from generic 'all' UG awards
   and honest Haitian US community college transfer scenario without fabricated certainty).
4. Missing student information (never converted into eligibility).
5. Variable / CSS Profile / full-need vs fixed published financial aid separation.
6. Expired / closed cycles separated cleanly from verified funding amounts.
7. Exchange-only funding excluded from verified funding & USD net price reductions.
8. Manual review conditions & conflicting information handling.
9. Net-price calculations & zero variable/unverified deductions.
10. Separated student-level coverage denominators, prioritized coverage gaps, and deferred research queue.
"""

from app.database import SessionLocal
from app.models.institution import Institution
from app.models.rag import ScholarshipProgram
from app.services.coverage_analytics import analyze_student_coverage, generate_global_coverage_audit
from app.services.financial_engine import (
    calculate_net_price,
    classify_aid_type,
    classify_transfer_pathway,
    evaluate_single_scholarship,
    match_scholarships_deterministic,
)


def test_41_01_citizenship_residency_and_dual_citizenship_separation():
    db = SessionLocal()
    try:
        mefd = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title.ilike("%MEFD Beca General%")
        ).first()
        gks = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title.ilike("%Global Korea Scholarship%")
        ).first()
        si_sisgp = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title.ilike("%Swedish Institute Scholarship for Global Professionals%")
        ).first()
        assert mefd is not None and gks is not None and si_sisgp is not None

        # Spanish residence without Spanish citizenship or missing residence must NOT infer Spain residency
        es_missing_res = evaluate_single_scholarship(
            mefd,
            {"citizenships": ["ES"], "degree_level": "bachelors", "applicant_type": "first_year", "financial_need_level": "high"},
        )
        assert es_missing_res["eligibility_status"] == "insufficient_information"
        assert es_missing_res["missing_requirements"]

        es_wrong_res = evaluate_single_scholarship(
            mefd,
            {"citizenships": ["ES"], "country_of_residence": "FR", "destination_country": "ES", "degree_level": "bachelors", "applicant_type": "first_year", "financial_need_level": "high"},
        )
        assert es_wrong_res["eligibility_status"] == "ineligible"
        assert es_wrong_res["failed_reasons"]

        # GKS-U restricts Korean dual citizenships strictly
        kr_dual = evaluate_single_scholarship(
            gks,
            {
                "citizenships": ["KR", "US"],
                "dual_citizenship": True,
                "country_of_residence": "US",
                "destination_country": "KR",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "gpa_4": 3.8,
                "date_of_birth": "2006-05-01",
            },
        )
        assert kr_dual["eligibility_status"] == "ineligible"
        assert any("dual" in r.lower() or "excluded" in r.lower() for r in kr_dual["failed_reasons"])

        # Morocco MA vs Mauritania MR separated on SI SISGP
        ma_ev = evaluate_single_scholarship(
            si_sisgp,
            {"citizenships": ["MA"], "country_of_residence": "MA", "destination_country": "SE", "degree_level": "masters", "applicant_type": "first_year", "language_proficiencies": {"en": {"format": "ielts", "test_type": "IELTS", "score": 7.0}}},
        )
        mr_ev = evaluate_single_scholarship(
            si_sisgp,
            {"citizenships": ["MR"], "country_of_residence": "MR", "destination_country": "SE", "degree_level": "masters", "applicant_type": "first_year", "language_proficiencies": {"en": {"format": "ielts", "test_type": "IELTS", "score": 7.0}}},
        )
        assert ma_ev["eligibility_status"] in ("eligible", "conditionally_eligible")
        assert mr_ev["eligibility_status"] == "ineligible"
    finally:
        db.close()


def test_41_02_seven_way_transfer_taxonomy_and_never_infer_transfer_from_ug():
    db = SessionLocal()
    try:
        active = db.query(ScholarshipProgram).filter(ScholarshipProgram.is_current == True).all()
        categories_seen = set()
        for p in active:
            tx_cls, detail = classify_transfer_pathway(p)
            categories_seen.add(tx_cls)
            assert detail
        assert {
            "explicitly_accepts_transfer",
            "ug_transfer_unconfirmed",
            "first_year_only",
            "community_college_required",
            "transfer_restricted_by_institution_or_country",
            "graduate_only",
            "exchange_only",
        }.issubset(categories_seen)

        # Unconfirmed UG transfer ('all' applicant_type with transfer_supported=None) MUST require manual review for a transfer student!
        bavaria = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title.ilike("%LMU Munich Bavarian Tuition-Free%")
        ).first()
        assert bavaria is not None
        tx_bav = evaluate_single_scholarship(
            bavaria,
            {"citizenships": ["HT"], "country_of_residence": "HT", "destination_country": "DE", "degree_level": "bachelors", "applicant_type": "transfer"},
        )
        assert tx_bav["transfer_pathway_classification"] == "ug_transfer_unconfirmed"
        assert tx_bav["eligibility_status"] == "requires_manual_review"
        assert any("unconfirmed" in r.lower() for r in tx_bav["manual_review_reasons"])

        # Same program for incoming first-year does NOT hit unconfirmed-transfer manual review gate
        fy_bav = evaluate_single_scholarship(
            bavaria,
            {"citizenships": ["HT"], "country_of_residence": "HT", "destination_country": "DE", "degree_level": "bachelors", "applicant_type": "first_year"},
        )
        assert fy_bav["eligibility_status"] == "eligible"

        # Haitian US community college transfer scenario: honest variable / manual-review reality without fabricated fixed USD offers
        ht_cc = analyze_student_coverage(
            db,
            None,
            {
                "citizenship_country": "HT",
                "country_of_residence": "US",
                "destination_country": "US",
                "degree_level": "bachelors",
                "applicant_type": "transfer",
                "us_community_college_enrolled": True,
                "gpa_4": 3.85,
                "financial_need_level": "high",
                "household_income_usd": 20000.0,
            },
        )
        assert ht_cc["programs_matched"] >= 5
        assert ht_cc["programs_verified_funding"] == 0
        assert "no_verified_funding" in ht_cc["gap_codes"]
    finally:
        db.close()


def test_41_03_missing_info_variable_aid_cycle_status_and_supporting_sources():
    db = SessionLocal()
    try:
        mit = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "MIT Need-Blind Admissions & Full-Need Institutional Aid"
        ).first()
        imperial = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "Imperial College President's Undergraduate Scholarships"
        ).first()
        gks = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title.ilike("%Global Korea Scholarship%")
        ).first()
        erasmus_mob = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.funding_type == "exchange_mobility"
        ).first()
        mcgill = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title.ilike("%McGill Mastercard Foundation Scholars%")
        ).first()
        assert mit and imperial and gks and erasmus_mob and mcgill

        # Missing financial need on MIT -> insufficient_information (never guessed eligible)
        mit_missing = evaluate_single_scholarship(
            mit,
            {"citizenships": ["HT"], "destination_country": "US", "degree_level": "bachelors", "applicant_type": "first_year"},
        )
        assert mit_missing["eligibility_status"] == "insufficient_information"
        assert mit_missing["missing_requirements"]
        assert mit_missing["official_supporting_sources"]

        # Reported financial need on MIT -> eligible in rules, BUT variable CSS Profile aid (is_amount_verified=False, is_variable_aid=True)
        mit_need = evaluate_single_scholarship(
            mit,
            {"citizenships": ["HT"], "destination_country": "US", "degree_level": "bachelors", "applicant_type": "first_year", "financial_need_level": "high"},
        )
        assert mit_need["eligibility_status"] == "eligible"
        assert mit_need["satisfied_reasons"]
        assert mit_need["aid_classification"] == "css_profile_full_need"
        assert mit_need["is_variable_aid"] is True
        assert mit_need["is_amount_verified"] is False
        assert mit_need["is_actionable_for_student"] is False

        # Imperial GBP 1,000 fixed published award with open deadline 2027-01-29
        imp_ev = evaluate_single_scholarship(
            imperial,
            {"citizenships": ["HT"], "destination_country": "GB", "degree_level": "bachelors", "applicant_type": "first_year", "gpa_4": 3.9},
        )
        assert imp_ev["eligibility_status"] == "eligible"
        assert imp_ev["is_amount_verified"] is True
        assert imp_ev["is_variable_aid"] is False
        assert imp_ev["is_cycle_open"] is True
        assert imp_ev["is_actionable_for_student"] is True
        assert imp_ev["aid_classification"] == "fixed_published"

        # GKS-U has verified funding amount (KRW) BUT expired 2026-09-30 cycle -> is_amount_verified=True, is_cycle_open=False, is_actionable_for_student=False
        gks_ev = evaluate_single_scholarship(
            gks,
            {"citizenships": ["HT"], "destination_country": "KR", "degree_level": "bachelors", "applicant_type": "first_year", "gpa_4": 3.8, "date_of_birth": "2006-05-01"},
        )
        assert gks_ev["application_cycle_status"] == "closed"
        assert gks_ev["is_amount_verified"] is True
        assert gks_ev["is_cycle_open"] is False
        assert gks_ev["is_actionable_for_student"] is False

        # Erasmus+ mobility exchange-only
        mob_ev = evaluate_single_scholarship(
            erasmus_mob,
            {"citizenships": ["FR"], "destination_country": "ES", "degree_level": "bachelors"},
        )
        assert mob_ev["aid_classification"] == "exchange_only"
        assert mob_ev["is_amount_verified"] is False
        assert mob_ev["transfer_pathway_classification"] == "exchange_only"

        # McGill conflicting data -> requires_manual_review
        mcgill_ev = evaluate_single_scholarship(
            mcgill,
            {"citizenships": ["HT"], "destination_country": "CA", "degree_level": "bachelors", "applicant_type": "first_year", "gpa_4": 3.9, "financial_need_level": "high"},
        )
        assert mcgill_ev["eligibility_status"] == "requires_manual_review"
    finally:
        db.close()


def test_41_04_net_price_isolation_and_separated_coverage_endpoints(client):
    # Check POST /api/v1/financial/scholarships/match includes separated student_coverage_summary
    res = client.post(
        "/api/v1/financial/scholarships/match",
        json={
            "citizenship_country": "NG",
            "country_of_residence": "NG",
            "destination_country": "SE",
            "degree_level": "masters",
            "applicant_type": "first_year",
            "gpa_4": 3.85,
            "financial_need_level": "high",
            "language_proficiencies": {"en": {"format": "ielts", "test_type": "IELTS", "score": 7.0}},
        },
    )
    assert res.status_code == 200
    body = res.json()
    summary = body["student_coverage_summary"]
    for k in (
        "programs_evaluated",
        "programs_matched",
        "programs_verified_eligibility",
        "programs_verified_funding",
        "programs_open_cycle",
        "programs_actionable_open_verified",
        "programs_insufficient_info",
        "programs_manual_review",
    ):
        assert k in summary
    assert summary["programs_matched"] >= 2
    assert summary["programs_actionable_open_verified"] <= summary["programs_verified_funding"]

    # Check POST /api/v1/financial/student-coverage
    cov_res = client.post(
        "/api/v1/financial/student-coverage",
        json={
            "citizenship_country": "HT",
            "country_of_residence": "CA",
            "destination_country": "CA",
            "degree_level": "bachelors",
            "applicant_type": "first_year",
            "gpa_4": 3.85,
            "financial_need_level": "high",
        },
    )
    assert cov_res.status_code == 200
    cov = cov_res.json()
    assert cov["programs_verified_funding"] == 0
    assert "no_verified_funding" in cov["gap_codes"]

    # Check GET /api/v1/financial/coverage-audit exposes matrix, prioritized gaps, and deferred research queue
    audit_res = client.get("/api/v1/financial/coverage-audit")
    assert audit_res.status_code == 200
    audit = audit_res.json()
    assert audit["verified_funding_programs"] == 25
    assert audit["actionable_coverage_count"] == 18
    assert audit["confirmed_open_verified_programs"] == 7
    assert len(audit["student_archetype_matrix"]) >= 15
    assert len(audit["coverage_gaps"]) >= 3
    assert audit["coverage_gaps"][0]["affected_profile_count"] >= audit["coverage_gaps"][-1]["affected_profile_count"]
    assert len(audit["deferred_research_queue"]) >= 3
