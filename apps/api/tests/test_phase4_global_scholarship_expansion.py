"""
Phase 4, Step 3 — Global Scholarship Expansion (Batch 1: Africa & Caribbean) Tests.

Covers:
13A. Data integrity, official URLs, provenance completeness, non-duplicate check,
     no fabricated reviewer/amount metadata, and strictly <=12 new Batch 1 programs.
13B. Primary-source URL verification & aggregator domain rejection.
13C. Deterministic Africa, Caribbean, CARICOM vs non-CARICOM, Commonwealth vs
     LDC/non-Commonwealth, citizenship vs residency, and diaspora eligibility rules.
13D. Financial engine integration: GBP/EUR/CAD/ZAR/GHS/NGN/DOP native isolation
     (never converted with invented USD rates), expired deadline vs expired amount
     claims, and unpublished amounts never treated as $0 guaranteed awards.
13E. Expiration & freshness separation (program existence current while deadline
     closed vs expired award amount claim blocked from verified net price).
"""

from datetime import date, datetime, timedelta, timezone

from app.database import SessionLocal
from app.ingestion.phase4_batch1_seed import (
    BATCH1_AFRICA_CARIBBEAN_SCHOLARSHIPS,
    seed_phase4_batch1_africa_caribbean,
)
from app.models.country import Country
from app.models.institution import Institution
from app.models.rag import ScholarshipEligibilityRule, ScholarshipProgram
from app.services.financial_engine import (
    calculate_net_price,
    evaluate_single_scholarship,
    match_scholarships_deterministic,
)
from app.services.freshness_governance import (
    evaluate_scholarship_claim_breakdown,
    is_valid_official_url,
    validate_scholarship_catalog,
)


REQUIRED_15_CLAIM_KEYS = {
    "program_existence",
    "sponsor",
    "citizenship_eligibility",
    "residency_eligibility",
    "destination_country",
    "degree_level",
    "applicant_type",
    "award_amount",
    "currency",
    "funding_scope",
    "funding_duration",
    "renewal",
    "deadlines",
    "application_cycle",
    "academic_year",
}


def test_13a_batch1_count_guard_and_provenance_completeness():
    # Hard gate: Batch 1 must contain strictly <= 12 newly verified records and idempotently seed
    assert 6 <= len(BATCH1_AFRICA_CARIBBEAN_SCHOLARSHIPS) <= 12

    db = SessionLocal()
    try:
        seed_phase4_batch1_africa_caribbean(db)
        second = seed_phase4_batch1_africa_caribbean(db)
        assert second["batch1_created"] == 0
        assert second["batch1_rules_created"] == 0

        # Batch 1 countries seeded cleanly
        for code in ("NG", "GH", "KE", "ZA", "ET", "RW", "SN", "CI", "HT", "JM", "TT", "BB", "BS", "DO"):
            assert db.query(Country).filter(Country.code == code).first() is not None

        # Verify total catalog count: 27 legacy + 11 Batch 1 = 38
        total = db.query(ScholarshipProgram).count()
        assert total == 38, f"Expected 38 total programs (27 legacy + 11 Batch 1), got {total}"

        # Every Batch 1 record has non-empty 15-field provenance, non-fabricated reviewer/FX, and HTTPS official URL
        titles = [item["title"] for item in BATCH1_AFRICA_CARIBBEAN_SCHOLARSHIPS]
        batch1_rows = db.query(ScholarshipProgram).filter(ScholarshipProgram.title.in_(titles)).all()
        assert len(batch1_rows) == 11

        for sch in batch1_rows:
            assert sch.source_url.startswith("https://")
            assert sch.sponsoring_institution
            assert sch.source_type in ("government_portal", "official_institutional", "official_agency")
            assert sch.verification_method == "manual_primary_source_fetch"
            assert sch.verified_by is None, "Never fabricate reviewer identity"
            assert sch.academic_year
            assert sch.award_currency and len(sch.award_currency.strip()) == 3
            assert isinstance(sch.claim_provenance, dict)
            missing_keys = REQUIRED_15_CLAIM_KEYS - set(sch.claim_provenance.keys())
            assert not missing_keys, f"{sch.title} missing provenance keys: {missing_keys}"
            if sch.award_currency != "USD":
                assert sch.award_amount_min_usd is None
                assert sch.award_amount_max_usd is None

        # Governance catalog audit reports zero duplicates, zero invalid URLs, zero conflicting records
        audit = validate_scholarship_catalog(db)
        assert audit["invalid_urls"] == []
        assert audit["duplicates"] == []
        assert audit["conflicting_records"] == []
        assert audit["expired_records"] == []
    finally:
        db.close()


def test_13b_aggregator_url_rejected_and_official_domains_accepted():
    for bad_url in (
        "https://www.scholarships.com/african-awards",
        "https://www.fastweb.com/caribbean",
        "https://www.scholars4dev.com/123/chevening/",
        "http://www.chevening.org/scholarships/",
        "https://localhost/fake",
    ):
        ok, _ = is_valid_official_url(bad_url)
        assert not ok, f"Expected rejection for non-official/HTTP URL: {bad_url}"

    for item in BATCH1_AFRICA_CARIBBEAN_SCHOLARSHIPS:
        ok, reason = is_valid_official_url(item["source_url"])
        assert ok, f"Official primary URL rejected for {item['title']}: {reason}"


def test_13c_african_and_caribbean_deterministic_eligibility_scenarios():
    db = SessionLocal()
    try:
        seed_phase4_batch1_africa_caribbean(db)

        # Scenario 1: Nigerian Master's applicant -> Chevening + CSC Master's + DAAD EPOS qualify (conditional),
        # while Haitian Master's applicant -> Chevening & DAAD EPOS qualify, CSC Master's INELIGIBLE (non-Commonwealth)!
        ng_masters = match_scholarships_deterministic(
            db,
            None,
            {
                "citizenship_country": "NG",
                "country_of_residence": "NG",
                "degree_level": "masters",
                "applicant_type": "first_year",
                "gpa_4": 3.80,
                "financial_need_level": "high",
            },
            include_ineligible=True,
        )
        ng_by_title = {r["title"]: r for r in ng_masters["results"]}
        assert ng_by_title["Chevening Scholarships (UK FCDO)"]["eligibility_status"] == "conditionally_eligible"
        assert ng_by_title["Commonwealth Master's Scholarships (CSC UK / FCDO)"]["eligibility_status"] == "conditionally_eligible"
        assert ng_by_title["DAAD Development-Related Postgraduate Courses (EPOS)"]["eligibility_status"] == "conditionally_eligible"

        ht_masters = match_scholarships_deterministic(
            db,
            None,
            {
                "citizenship_country": "HT",
                "country_of_residence": "HT",
                "degree_level": "masters",
                "applicant_type": "first_year",
                "gpa_4": 3.80,
                "financial_need_level": "high",
            },
            include_ineligible=True,
        )
        ht_by_title = {r["title"]: r for r in ht_masters["results"]}
        assert ht_by_title["Chevening Scholarships (UK FCDO)"]["eligibility_status"] == "conditionally_eligible"
        assert ht_by_title["DAAD Development-Related Postgraduate Courses (EPOS)"]["eligibility_status"] == "conditionally_eligible"
        assert ht_by_title["Commonwealth Master's Scholarships (CSC UK / FCDO)"]["eligibility_status"] == "ineligible"
        assert ht_by_title["The Mandela Rhodes Scholarship"]["eligibility_status"] == "ineligible"

        # Scenario 2: Commonwealth PhD LDC vs middle-income Commonwealth distinction (RW eligible, ZA ineligible)
        rw_phd = match_scholarships_deterministic(
            db,
            None,
            {"citizenship_country": "RW", "degree_level": "doctoral", "applicant_type": "first_year", "gpa_4": 3.7, "financial_need_level": "high"},
            include_ineligible=True,
        )
        za_phd = match_scholarships_deterministic(
            db,
            None,
            {"citizenship_country": "ZA", "degree_level": "doctoral", "applicant_type": "first_year", "gpa_4": 3.7, "financial_need_level": "high"},
            include_ineligible=True,
        )
        csc_phd_title = "Commonwealth PhD Scholarships for Least Developed Countries & Vulnerable States (CSC UK)"
        assert {r["title"]: r for r in rw_phd["results"]}[csc_phd_title]["eligibility_status"] == "conditionally_eligible"
        assert {r["title"]: r for r in za_phd["results"]}[csc_phd_title]["eligibility_status"] == "ineligible"

        # Scenario 3: CARICOM vs Caribbean distinction on UWI awards
        # Dominican Republic (DO) transfer UG: eligible for P. J. Patterson (Caribbean) if Law/PolSci & GPA >=3.0,
        # but INELIGIBLE for UWI Toronto Gala / AFUWI (strictly CARICOM)! Meanwhile Jamaican (JM) transfer UG matches AFUWI & Toronto Gala!
        do_ug = match_scholarships_deterministic(
            db,
            None,
            {
                "citizenship_country": "DO",
                "degree_level": "bachelors",
                "applicant_type": "transfer",
                "gpa_4": 3.5,
                "financial_need_level": "high",
                "field_of_study": "Political Science",
            },
            include_ineligible=True,
        )
        do_by_title = {r["title"]: r for r in do_ug["results"]}
        assert do_by_title["P. J. Patterson Endowment Fund Scholarship (UWI Cave Hill)"]["eligibility_status"] == "conditionally_eligible"
        assert do_by_title["The UWI Toronto Gala Scholarship (UWI Cave Hill)"]["eligibility_status"] == "ineligible"
        assert do_by_title["The AFUWI Undergraduate Scholarship (UWI Cave Hill)"]["eligibility_status"] == "ineligible"
        assert do_by_title["MESCyT Becas Internacionales de Grado y Postgrado (Dominican Republic)"]["eligibility_status"] == "conditionally_eligible"

        jm_ug = match_scholarships_deterministic(
            db,
            None,
            {
                "citizenship_country": "JM",
                "degree_level": "bachelors",
                "applicant_type": "transfer",
                "gpa_4": 3.5,
                "financial_need_level": "high",
                "field_of_study": "Engineering",
            },
            include_ineligible=True,
        )
        jm_by_title = {r["title"]: r for r in jm_ug["results"]}
        assert jm_by_title["The AFUWI Undergraduate Scholarship (UWI Cave Hill)"]["eligibility_status"] == "eligible"
        assert jm_by_title["The UWI Toronto Gala Scholarship (UWI Cave Hill)"]["eligibility_status"] == "conditionally_eligible"
        assert jm_by_title["P. J. Patterson Endowment Fund Scholarship (UWI Cave Hill)"]["eligibility_status"] == "ineligible"

        # Scenario 4: Chevening excludes British / dual-British citizens (GB)
        gb_ng_masters = match_scholarships_deterministic(
            db,
            None,
            {"citizenship_country": "GB", "degree_level": "masters", "applicant_type": "first_year", "gpa_4": 3.8},
            include_ineligible=True,
        )
        assert {r["title"]: r for r in gb_ng_masters["results"]}["Chevening Scholarships (UK FCDO)"]["eligibility_status"] == "ineligible"

        # Scenario 5: Mandela Rhodes age gate (African aged 24 eligible vs aged 35 ineligible, missing DOB -> insufficient_info)
        mrf = db.query(ScholarshipProgram).filter(ScholarshipProgram.title == "The Mandela Rhodes Scholarship").one()
        ev_24 = evaluate_single_scholarship(
            mrf,
            {
                "citizenships": ["KE"],
                "country_of_residence": "KE",
                "degree_level": "masters",
                "applicant_type": "first_year",
                "gpa_4": 3.6,
                "date_of_birth": "2003-05-01",
                "destination_country": "ZA",
            },
        )
        assert ev_24["eligibility_status"] == "eligible"

        ev_35 = evaluate_single_scholarship(
            mrf,
            {
                "citizenships": ["KE"],
                "country_of_residence": "KE",
                "degree_level": "masters",
                "applicant_type": "first_year",
                "gpa_4": 3.6,
                "date_of_birth": "1992-05-01",
                "destination_country": "ZA",
            },
        )
        assert ev_35["eligibility_status"] == "ineligible"
    finally:
        db.close()


def test_13d_e_currency_isolation_and_claim_level_expiration_in_net_price():
    db = SessionLocal()
    try:
        seed_phase4_batch1_africa_caribbean(db)

        # Pick a US public/private institution to verify net price engine never applies non-USD or unpublished awards
        yale = db.query(Institution).filter(Institution.official_name.ilike("%Yale%")).first()
        if not yale:
            yale = db.query(Institution).filter(Institution.country_code == "US").first()
        assert yale is not None

        # Closed deadline claim on CSC Master's keeps existence current (`application_cycle_status == 'closed'`),
        # while CAD / GBP / EUR native amounts are isolated from USD net-price deductions.
        csc_m = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "Commonwealth Master's Scholarships (CSC UK / FCDO)"
        ).one()
        cb = evaluate_scholarship_claim_breakdown(csc_m)
        assert cb["existence_current"] is True
        assert cb["deadline_expired"] is True
        assert cb["amount_expired"] is False

        match_res = match_scholarships_deterministic(
            db,
            None,
            {"citizenship_country": "JM", "degree_level": "masters", "applicant_type": "first_year", "gpa_4": 3.7, "financial_need_level": "high"},
            include_ineligible=False,
        )
        csc_out = next(r for r in match_res["results"] if r["title"] == csc_m.title)
        assert csc_out["application_cycle_status"] == "closed"
        assert csc_out["claim_freshness"]["deadlines"] == "expired"
        assert csc_out["claim_freshness"]["award_amounts"] == "current"
        assert csc_out["award_currency"] == "GBP"
        assert csc_out["award_amount_min_usd"] is None

        # Verify net price against US institution never converts GBP/EUR/CAD or treats null USD amount as $0 discount
        np_res = calculate_net_price(
            db,
            yale,
            None,
            {
                "residency_classification": "international",
                "housing_preference": "on_campus",
                "applicant_type": "first_year",
                "degree_level": "masters",
                "citizenship_country": "JM",
                "gpa_4": 3.7,
                "financial_need_level": "high",
                "include_competitive_aid": True,
            },
        )
        for applied in np_res["verified_applicable_aid"] + np_res["conditional_aid"]:
            assert applied["award_currency"] == "USD"
            assert applied["estimated_max_usd"] > 0

        # Mutate in memory ONLY (rollback before exit): verify expired `award_amounts` claim blocks USD discount
        # even if `program_existence` and `verification_expires_at` are current!
        p_expired_amt = ScholarshipProgram(
            country_code="US",
            title="__TEST__ Current Program With Expired Amount Claim",
            applicant_type="first_year",
            funding_type="merit",
            covers_international=True,
            award_type="fixed_amount",
            award_amount_min_usd=5000.0,
            award_amount_max_usd=5000.0,
            award_currency="USD",
            covers_tuition=True,
            is_guaranteed_statutory=True,
            eligible_citizenships=["HT"],
            degree_levels=["bachelors"],
            eligibility_summary="Synthetic claim-level expiration test.",
            source_name="Official Synthetic Test",
            source_url="https://example.edu/test",
            verified_at=datetime.now(timezone.utc) - timedelta(days=10),
            verification_expires_at=datetime.now(timezone.utc) + timedelta(days=170),
            freshness_status="current",
            requires_manual_review=False,
            claim_provenance={
                "program_existence": {"verified_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()},
                "award_amounts": {
                    "verified_at": (datetime.now(timezone.utc) - timedelta(days=150)).isoformat(),
                    "expires_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
                },
            },
            is_verified=True,
            is_current=True,
        )
        db.add(p_expired_amt)
        db.flush()
        try:
            net_before = calculate_net_price(
                db,
                yale,
                None,
                {
                    "residency_classification": "international",
                    "applicant_type": "first_year",
                    "degree_level": "bachelors",
                    "citizenship_country": "HT",
                    "gpa_4": 3.8,
                    "financial_need_level": "low",
                    "include_competitive_aid": False,
                },
            )
            review_titles = {a["title"]: a for a in net_before["review_required_aid"]}
            assert "__TEST__ Current Program With Expired Amount Claim" in review_titles
            applied_titles = {a["title"] for a in net_before["verified_applicable_aid"]}
            assert "__TEST__ Current Program With Expired Amount Claim" not in applied_titles
        finally:
            db.rollback()
    finally:
        db.close()
