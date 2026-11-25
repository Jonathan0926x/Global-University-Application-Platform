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
from app.ingestion.phase4_batch2_seed import (
    BATCH2_LATIN_AMERICA_SCHOLARSHIPS,
    seed_phase4_batch2_latin_america,
)
from app.ingestion.phase4_batch3_seed import (
    BATCH3_ASIA_PACIFIC_SCHOLARSHIPS,
    seed_phase4_batch3_asia_pacific,
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

        # Verify catalog has at least the Batch 1 baseline (27 legacy + 11 Batch 1 = 38; subsequent batches add beyond 38)
        total = db.query(ScholarshipProgram).count()
        assert total >= 38, f"Expected at least 38 total programs (27 legacy + 11 Batch 1), got {total}"

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


# =====================================================================
# Phase 4, Step 3 — Batch 2: Latin America Expansion Tests
# =====================================================================


def test_14a_batch2_count_guard_and_provenance_completeness():
    # Hard gate: Batch 2 targets 6-10 programs and must never exceed 12
    assert 6 <= len(BATCH2_LATIN_AMERICA_SCHOLARSHIPS) <= 12
    assert len(BATCH2_LATIN_AMERICA_SCHOLARSHIPS) == 10

    db = SessionLocal()
    try:
        seed_phase4_batch2_latin_america(db)
        second = seed_phase4_batch2_latin_america(db)
        assert second["batch2_created"] == 0
        assert second["batch2_rules_created"] == 0

        for code in ("BR", "MX", "CO", "CL", "AR", "PE", "ES", "UY", "EC", "BO", "PY", "VE", "CR", "PA", "GT", "HN", "NI", "SV", "CU"):
            assert db.query(Country).filter(Country.code == code).first() is not None

        # Verify total catalog count: 27 legacy + 11 Batch 1 + 10 Batch 2 = 48
        total = db.query(ScholarshipProgram).count()
        assert total >= 48, f"Expected at least 48 total programs (27 legacy + 11 Batch 1 + 10 Batch 2), got {total}"

        titles = [item["title"] for item in BATCH2_LATIN_AMERICA_SCHOLARSHIPS]
        batch2_rows = db.query(ScholarshipProgram).filter(ScholarshipProgram.title.in_(titles)).all()
        assert len(batch2_rows) == 10

        for sch in batch2_rows:
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

        audit = validate_scholarship_catalog(db)
        assert audit["invalid_urls"] == []
        assert audit["duplicates"] == []
        assert audit["conflicting_records"] == []
        assert audit["expired_records"] == []
    finally:
        db.close()


def test_14b_batch2_exam_and_residency_eligibility():
    db = SessionLocal()
    try:
        seed_phase4_batch2_latin_america(db)

        # 1. ProUni (BR) requires ENEM >= 450 without fabricated GPA conversion
        prouni = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "ProUni — Programa Universidade para Todos (MEC Brasil)"
        ).one()
        prouni_pass = evaluate_single_scholarship(
            prouni,
            {
                "citizenships": ["BR"],
                "destination_country": "BR",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "financial_need_level": "high",
                "exam_scores": {"ENEM": 620},
            },
        )
        assert prouni_pass["eligibility_status"] == "conditionally_eligible"

        prouni_low = evaluate_single_scholarship(
            prouni,
            {
                "citizenships": ["BR"],
                "destination_country": "BR",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "financial_need_level": "high",
                "exam_scores": {"ENEM": 410},
            },
        )
        assert prouni_low["eligibility_status"] == "ineligible"

        prouni_missing_exam = evaluate_single_scholarship(
            prouni,
            {
                "citizenships": ["BR"],
                "destination_country": "BR",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "financial_need_level": "high",
            },
        )
        assert prouni_missing_exam["eligibility_status"] == "insufficient_information"

        # 2. PRONABEC Beca 18 (PE) enforces age < 22 on 2026-10-09 and ENP >= 84
        beca18 = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "PRONABEC Beca 18 y Becas Especiales — Convocatoria 2027 (Perú)"
        ).one()
        beca18_pass = evaluate_single_scholarship(
            beca18,
            {
                "citizenships": ["PE"],
                "destination_country": "PE",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "financial_need_level": "high",
                "date_of_birth": "2007-05-01",
                "exam_scores": {"ENP": 92},
            },
        )
        assert beca18_pass["eligibility_status"] == "conditionally_eligible"

        beca18_overage = evaluate_single_scholarship(
            beca18,
            {
                "citizenships": ["PE"],
                "destination_country": "PE",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "financial_need_level": "high",
                "date_of_birth": "2000-01-01",
                "exam_scores": {"ENP": 92},
            },
        )
        assert beca18_overage["eligibility_status"] == "ineligible"

        beca18_missing_enp = evaluate_single_scholarship(
            beca18,
            {
                "citizenships": ["PE"],
                "destination_country": "PE",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "financial_need_level": "high",
                "date_of_birth": "2007-05-01",
            },
        )
        assert beca18_missing_enp["eligibility_status"] == "insufficient_information"

        # 3. ICETEX Beca Colombia excludes CO nationals, CO residents, and out-of-range ages
        icetex = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "ICETEX Programa de Reciprocidad para Extranjeros en Colombia (Beca Colombia 2026-2)"
        ).one()
        icetex_br_ok = evaluate_single_scholarship(
            icetex,
            {
                "citizenships": ["BR"],
                "country_of_residence": "BR",
                "destination_country": "CO",
                "degree_level": "masters",
                "date_of_birth": "1999-03-10",
            },
        )
        assert icetex_br_ok["eligibility_status"] == "conditionally_eligible"

        icetex_co_nat = evaluate_single_scholarship(
            icetex,
            {
                "citizenships": ["CO"],
                "country_of_residence": "BR",
                "destination_country": "CO",
                "degree_level": "masters",
                "date_of_birth": "1999-03-10",
            },
        )
        assert icetex_co_nat["eligibility_status"] == "ineligible"

        icetex_co_res = evaluate_single_scholarship(
            icetex,
            {
                "citizenships": ["BR"],
                "country_of_residence": "CO",
                "destination_country": "CO",
                "degree_level": "masters",
                "date_of_birth": "1999-03-10",
            },
        )
        assert icetex_co_res["eligibility_status"] == "ineligible"

        icetex_missing_res = evaluate_single_scholarship(
            icetex,
            {
                "citizenships": ["BR"],
                "destination_country": "CO",
                "degree_level": "masters",
                "date_of_birth": "1999-03-10",
            },
        )
        assert icetex_missing_res["eligibility_status"] == "insufficient_information"

        icetex_overage = evaluate_single_scholarship(
            icetex,
            {
                "citizenships": ["BR"],
                "country_of_residence": "BR",
                "destination_country": "CO",
                "degree_level": "masters",
                "date_of_birth": "1974-01-01",
            },
        )
        assert icetex_overage["eligibility_status"] == "ineligible"
    finally:
        db.close()


def test_14c_batch2_regional_blocs_and_spanish_exclusion():
    db = SessionLocal()
    try:
        seed_phase4_batch2_latin_america(db)

        alianza = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "Alianza del Pacífico — Plataforma de Movilidad Estudiantil y Académica"
        ).one()
        assert evaluate_single_scholarship(
            alianza,
            {
                "citizenships": ["CL"],
                "destination_country": "MX",
                "degree_level": "bachelors",
                "applicant_type": "transfer",
                "field_of_study": "Engineering",
            },
        )["eligibility_status"] == "conditionally_eligible"
        assert evaluate_single_scholarship(
            alianza,
            {
                "citizenships": ["CO"],
                "destination_country": "PE",
                "degree_level": "bachelors",
                "applicant_type": "transfer",
                "field_of_study": "Computer Science",
            },
        )["eligibility_status"] == "conditionally_eligible"
        assert evaluate_single_scholarship(
            alianza,
            {
                "citizenships": ["BR"],
                "destination_country": "MX",
                "degree_level": "bachelors",
                "applicant_type": "transfer",
                "field_of_study": "Engineering",
            },
        )["eligibility_status"] == "ineligible"
        assert evaluate_single_scholarship(
            alianza,
            {
                "citizenships": ["AR"],
                "destination_country": "CL",
                "degree_level": "bachelors",
                "applicant_type": "transfer",
                "field_of_study": "Economics",
            },
        )["eligibility_status"] == "ineligible"
        assert evaluate_single_scholarship(
            alianza,
            {
                "citizenships": ["MX"],
                "destination_country": "CO",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "field_of_study": "Engineering",
            },
        )["eligibility_status"] == "ineligible"

        agcid = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "AGCID Programa de Becas República de Chile para Estudios de Magíster"
        ).one()
        assert evaluate_single_scholarship(
            agcid,
            {
                "citizenships": ["HT"],
                "destination_country": "CL",
                "degree_level": "masters",
            },
        )["eligibility_status"] == "conditionally_eligible"
        assert evaluate_single_scholarship(
            agcid,
            {
                "citizenships": ["CL"],
                "destination_country": "CL",
                "degree_level": "masters",
            },
        )["eligibility_status"] == "ineligible"

        carolina = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "Fundación Carolina — Becas de Postgrado (España / América Latina)"
        ).one()
        assert evaluate_single_scholarship(
            carolina,
            {
                "citizenships": ["PE"],
                "country_of_residence": "PE",
                "destination_country": "ES",
                "degree_level": "masters",
            },
        )["eligibility_status"] == "conditionally_eligible"
        assert evaluate_single_scholarship(
            carolina,
            {
                "citizenships": ["PE"],
                "country_of_residence": "ES",
                "destination_country": "ES",
                "degree_level": "masters",
            },
        )["eligibility_status"] == "ineligible"
    finally:
        db.close()


def test_14d_e_batch2_native_currencies_net_price_and_closed_cycles():
    db = SessionLocal()
    try:
        seed_phase4_batch2_latin_america(db)

        mx_match = match_scholarships_deterministic(
            db,
            None,
            {
                "citizenship_country": "MX",
                "country_of_residence": "MX",
                "destination_country": "MX",
                "degree_level": "masters",
                "applicant_type": "first_year",
            },
            include_ineligible=False,
        )
        mx_by_title = {r["title"]: r for r in mx_match["results"]}
        secihti_nat = mx_by_title["SECIHTI Becas Nacionales para Estudios de Posgrado (México)"]
        assert secihti_nat["award_currency"] == "MXN"
        assert secihti_nat["native_amount_min"] == 192575.88
        assert secihti_nat["native_amount_max"] == 256767.84
        assert secihti_nat["award_amount_min_usd"] is None
        assert secihti_nat["application_cycle_status"] == "closed"
        assert secihti_nat["claim_freshness"]["deadlines"] == "expired"
        assert secihti_nat["claim_freshness"]["award_amounts"] == "current"

        ar_match = match_scholarships_deterministic(
            db,
            None,
            {
                "citizenship_country": "AR",
                "country_of_residence": "AR",
                "destination_country": "AR",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "date_of_birth": "2006-05-01",
                "financial_need_level": "high",
            },
            include_ineligible=False,
        )
        progresar = {r["title"]: r for r in ar_match["results"]}[
            "Becas Progresar Nivel Superior (Educación Superior y Enfermería)"
        ]
        assert progresar["award_currency"] == "ARS"
        assert progresar["native_amount_min"] == 420000.0
        assert progresar["native_amount_max"] == 420000.0
        assert progresar["application_cycle_status"] == "closed"

        pe_es_match = match_scholarships_deterministic(
            db,
            None,
            {
                "citizenship_country": "PE",
                "country_of_residence": "PE",
                "destination_country": "ES",
                "degree_level": "masters",
                "applicant_type": "first_year",
            },
            include_ineligible=False,
        )
        carolina_out = {r["title"]: r for r in pe_es_match["results"]}[
            "Fundación Carolina — Becas de Postgrado (España / América Latina)"
        ]
        assert carolina_out["award_currency"] == "EUR"
        assert carolina_out["application_cycle_status"] == "closed"
        assert carolina_out["claim_freshness"]["deadlines"] == "expired"

        alianza = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "Alianza del Pacífico — Plataforma de Movilidad Estudiantil y Académica"
        ).one()
        assert alianza.award_currency == "UNK"
        assert alianza.native_amount_min is None
        assert alianza.native_amount_max is None

        us_inst = db.query(Institution).filter(Institution.country_code == "US").first()
        assert us_inst is not None
        np_res = calculate_net_price(
            db,
            us_inst,
            None,
            {
                "residency_classification": "international",
                "housing_preference": "on_campus",
                "applicant_type": "first_year",
                "degree_level": "masters",
                "citizenship_country": "MX",
                "country_of_residence": "MX",
                "destination_country": "MX",
                "include_competitive_aid": True,
            },
        )
        for applied in np_res["verified_applicable_aid"] + np_res["conditional_aid"]:
            assert applied["award_currency"] == "USD"
            assert applied["estimated_max_usd"] > 0
    finally:
        db.close()


def test_15a_batch3_count_guard_and_provenance_completeness():
    assert 6 <= len(BATCH3_ASIA_PACIFIC_SCHOLARSHIPS) <= 12

    db = SessionLocal()
    try:
        seed_phase4_batch3_asia_pacific(db)
        second = seed_phase4_batch3_asia_pacific(db)
        assert second["batch3_created"] == 0
        assert second["batch3_rules_created"] == 0

        for code in ("CN", "IN", "KR", "SG", "MY", "ID", "PK", "BD", "VN", "PH"):
            assert db.query(Country).filter(Country.code == code).first() is not None

        total = db.query(ScholarshipProgram).count()
        assert total == 59, f"Expected 59 total programs (48 prior + 11 Batch 3), got {total}"

        titles = [item["title"] for item in BATCH3_ASIA_PACIFIC_SCHOLARSHIPS]
        batch3_rows = db.query(ScholarshipProgram).filter(ScholarshipProgram.title.in_(titles)).all()
        assert len(batch3_rows) == 11

        currencies_seen = {sch.award_currency for sch in batch3_rows}
        assert currencies_seen == {"CNY", "INR", "KRW", "SGD", "MYR", "IDR", "PKR", "BDT", "VND", "PHP"}

        for sch in batch3_rows:
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

        audit = validate_scholarship_catalog(db)
        assert audit["invalid_urls"] == []
        assert audit["duplicates"] == []
        assert audit["conflicting_records"] == []
        assert audit["expired_records"] == []
    finally:
        db.close()


def test_15b_batch3_verified_funding_coverage_metric():
    db = SessionLocal()
    try:
        seed_phase4_batch3_asia_pacific(db)
        audit = validate_scholarship_catalog(db)
        assert audit["total_active_programs"] == 59
        assert 0 < audit["verified_funding_programs"] < 59
        assert 0.0 < audit["verified_funding_coverage"] < 1.0

        match_res = match_scholarships_deterministic(
            db,
            None,
            {
                "citizenships": ["VN"],
                "country_of_residence": "VN",
                "destination_country": "VN",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
            },
            include_ineligible=False,
        )
        assert match_res["total_active_programs"] == audit["total_active_programs"]
        assert match_res["verified_funding_programs"] == audit["verified_funding_programs"]
        assert match_res["verified_funding_coverage"] == audit["verified_funding_coverage"]

        # Temporarily flag an active funded Batch 3 program for manual review and confirm coverage drops cleanly
        cas = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "CAS-ANSO Scholarship (2027 Call — USTC / UCAS / CAS)"
        ).one()
        cas.requires_manual_review = True
        db.flush()
        lowered = validate_scholarship_catalog(db)
        assert lowered["verified_funding_programs"] == audit["verified_funding_programs"] - 1
    finally:
        db.rollback()
        db.close()


def test_15c_batch3_china_india_korea_singapore_rules():
    db = SessionLocal()
    try:
        seed_phase4_batch3_asia_pacific(db)

        # 1. CAS-ANSO (CN, CNY, open cycle)
        cas = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "CAS-ANSO Scholarship (2027 Call — USTC / UCAS / CAS)"
        ).one()
        cas_vn = evaluate_single_scholarship(
            cas,
            {
                "citizenships": ["VN"],
                "destination_country": "CN",
                "degree_level": "doctoral",
                "date_of_birth": "1998-06-15",
            },
        )
        assert cas_vn["eligibility_status"] == "conditionally_eligible"
        assert cas_vn["award_currency"] == "CNY"
        assert cas_vn["application_cycle_status"] == "open"
        assert evaluate_single_scholarship(
            cas,
            {
                "citizenships": ["CN"],
                "destination_country": "CN",
                "degree_level": "doctoral",
                "date_of_birth": "1998-06-15",
            },
        )["eligibility_status"] == "ineligible"

        # 2. USTC UG Fellowship requires CSCA + HSK 5 (not Gaokao) and age < 25
        ustc = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "USTC Fellowship for Undergraduate Programs (CSC / USTC Full & Partial)"
        ).one()
        ustc_ok = evaluate_single_scholarship(
            ustc,
            {
                "citizenships": ["PK"],
                "destination_country": "CN",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "date_of_birth": "2008-05-01",
                "exam_scores": {"CSCA": 88},
                "language_proficiencies": {"zh": {"format": "hsk", "test_type": "HSK", "score": 5}},
            },
        )
        assert ustc_ok["eligibility_status"] == "eligible"
        assert ustc_ok["award_currency"] == "CNY"
        assert ustc_ok["native_amount_min"] is None
        assert ustc_ok["application_cycle_status"] == "open"

        assert evaluate_single_scholarship(
            ustc,
            {
                "citizenships": ["PK"],
                "destination_country": "CN",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "date_of_birth": "2008-05-01",
                "language_proficiencies": {"zh": {"format": "hsk", "test_type": "HSK", "score": 5}},
            },
        )["eligibility_status"] == "insufficient_information"

        assert evaluate_single_scholarship(
            ustc,
            {
                "citizenships": ["PK"],
                "destination_country": "CN",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "date_of_birth": "2008-05-01",
                "exam_scores": {"CSCA": 88},
                "language_proficiencies": {"zh": {"format": "hsk", "test_type": "HSK", "score": 4}},
            },
        )["eligibility_status"] == "ineligible"

        # 3. DST INSPIRE-SHE (IN, INR, Basic Sciences vs Engineering/CS exclusion)
        inspire = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "DST INSPIRE Scholarship for Higher Education (SHE)"
        ).one()
        assert evaluate_single_scholarship(
            inspire,
            {
                "citizenships": ["IN"],
                "destination_country": "IN",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "date_of_birth": "2008-04-10",
                "field_of_study": "Physics",
            },
        )["eligibility_status"] == "conditionally_eligible"
        assert evaluate_single_scholarship(
            inspire,
            {
                "citizenships": ["IN"],
                "destination_country": "IN",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "date_of_birth": "2008-04-10",
                "field_of_study": "Computer Science",
            },
        )["eligibility_status"] == "ineligible"

        # 4. 2027 GKS-U (KR, KRW, closed cycle, dual-KR exclusion)
        gks = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "Global Korea Scholarship — Undergraduate Degrees (2027 GKS-U, NIIED)"
        ).one()
        gks_ok = evaluate_single_scholarship(
            gks,
            {
                "citizenships": ["ID"],
                "dual_citizenship": False,
                "destination_country": "KR",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "date_of_birth": "2008-02-01",
                "gpa_4": 3.5,
            },
        )
        assert gks_ok["eligibility_status"] == "conditionally_eligible"
        assert gks_ok["award_currency"] == "KRW"
        assert gks_ok["application_cycle_status"] == "closed"
        assert gks_ok["claim_freshness"]["deadlines"] == "expired"

        assert evaluate_single_scholarship(
            gks,
            {
                "citizenships": ["ID"],
                "destination_country": "KR",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "date_of_birth": "2008-02-01",
                "gpa_4": 3.5,
            },
        )["eligibility_status"] == "insufficient_information"

        assert evaluate_single_scholarship(
            gks,
            {
                "citizenships": ["ID", "KR"],
                "dual_citizenship": True,
                "destination_country": "KR",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "date_of_birth": "2008-02-01",
                "gpa_4": 3.5,
            },
        )["eligibility_status"] == "ineligible"

        # 5. A*STAR AGS (SG, SGD, open cycle, STEM vs Law)
        ags = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "A*STAR Graduate Scholarship (AGS — PhD)"
        ).one()
        ags_ok = evaluate_single_scholarship(
            ags,
            {
                "citizenships": ["IN"],
                "destination_country": "SG",
                "degree_level": "doctoral",
                "field_of_study": "Quantum Computing and Semiconductor Engineering",
            },
        )
        assert ags_ok["eligibility_status"] == "conditionally_eligible"
        assert ags_ok["award_currency"] == "SGD"
        assert ags_ok["application_cycle_status"] == "open"
        assert evaluate_single_scholarship(
            ags,
            {
                "citizenships": ["IN"],
                "destination_country": "SG",
                "degree_level": "doctoral",
                "field_of_study": "Law",
            },
        )["eligibility_status"] == "ineligible"
    finally:
        db.close()


def test_15d_batch3_southeast_and_south_asia_rules():
    db = SessionLocal()
    try:
        seed_phase4_batch3_asia_pacific(db)

        mis = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "Malaysia International Scholarship (MIS, MOHE)"
        ).one()
        mis_ph = evaluate_single_scholarship(
            mis,
            {
                "citizenships": ["PH"],
                "destination_country": "MY",
                "degree_level": "masters",
                "date_of_birth": "1999-01-10",
                "gpa_4": 3.5,
                "field_of_study": "Data Science",
                "language_proficiencies": {"en": {"format": "ielts", "test_type": "IELTS", "score": 6.5}},
            },
        )
        assert mis_ph["eligibility_status"] == "eligible"
        assert mis_ph["award_currency"] == "MYR"
        assert mis_ph["application_cycle_status"] == "closed"
        assert evaluate_single_scholarship(
            mis,
            {
                "citizenships": ["MY"],
                "destination_country": "MY",
                "degree_level": "masters",
                "date_of_birth": "1999-01-10",
                "gpa_4": 3.5,
                "field_of_study": "Data Science",
                "language_proficiencies": {"en": {"format": "ielts", "test_type": "IELTS", "score": 6.5}},
            },
        )["eligibility_status"] == "ineligible"
        assert evaluate_single_scholarship(
            mis,
            {
                "citizenships": ["PH"],
                "destination_country": "MY",
                "degree_level": "masters",
                "date_of_birth": "1999-01-10",
                "gpa_4": 3.5,
                "field_of_study": "Medicine",
                "language_proficiencies": {"en": {"format": "ielts", "test_type": "IELTS", "score": 6.5}},
            },
        )["eligibility_status"] == "ineligible"

        knb = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "Beasiswa Kemitraan Negara Berkembang (KNB Scholarship, Kemdiktisaintek RI)"
        ).one()
        knb_ok = evaluate_single_scholarship(
            knb,
            {
                "citizenships": ["PH"],
                "destination_country": "ID",
                "degree_level": "masters",
                "date_of_birth": "1998-03-01",
                "gpa_4": 3.3,
                "language_proficiencies": {"en": {"format": "ielts", "test_type": "IELTS", "score": 6.0}},
            },
        )
        assert knb_ok["eligibility_status"] == "conditionally_eligible"
        assert knb_ok["award_currency"] == "IDR"
        assert knb_ok["native_amount_min"] is None
        assert knb_ok["application_cycle_status"] == "closed"

        hec = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "HEC / BISP Undergraduate Scholarship (Ehsaas / Benazir Undergraduate Scholarship)"
        ).one()
        assert evaluate_single_scholarship(
            hec,
            {
                "citizenships": ["PK"],
                "destination_country": "PK",
                "degree_level": "bachelors",
                "applicant_type": "first_year",
                "financial_need_level": "high",
            },
        )["eligibility_status"] == "eligible"

        ugc = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "UGC PhD Scholarship (2026–2027, University Grants Commission of Bangladesh)"
        ).one()
        ugc_bd = evaluate_single_scholarship(
            ugc,
            {
                "citizenships": ["BD"],
                "destination_country": "BD",
                "degree_level": "doctoral",
            },
        )
        assert ugc_bd["eligibility_status"] == "conditionally_eligible"
        assert ugc_bd["award_currency"] == "BDT"
        assert ugc_bd["native_amount_min"] is None
        assert ugc_bd["application_cycle_status"] == "closed"

        vnu = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "VNU Hanoi Institutional & Partner Scholarships (Vingroup / KBSV / Nguyễn Trường Tộ — ĐHQGHN)"
        ).one()
        vnu_vn = evaluate_single_scholarship(
            vnu,
            {
                "citizenships": ["VN"],
                "destination_country": "VN",
                "degree_level": "bachelors",
            },
        )
        assert vnu_vn["eligibility_status"] == "conditionally_eligible"
        assert vnu_vn["award_currency"] == "VND"
        assert vnu_vn["native_amount_max"] == 25000000.0

        tes = db.query(ScholarshipProgram).filter(
            ScholarshipProgram.title == "CHED-UniFAST Tertiary Education Subsidy (TES — Republic Act 10931)"
        ).one()
        tes_ph = evaluate_single_scholarship(
            tes,
            {
                "citizenships": ["PH"],
                "destination_country": "PH",
                "degree_level": "bachelors",
                "financial_need_level": "high",
            },
        )
        assert tes_ph["eligibility_status"] == "conditionally_eligible"
        assert tes_ph["award_currency"] == "PHP"
        assert tes_ph["native_amount_min"] == 20000.0
        assert tes_ph["native_amount_max"] == 27000.0
    finally:
        db.close()


def test_15e_batch3_native_currencies_never_converted_to_usd_net_price():
    db = SessionLocal()
    try:
        seed_phase4_batch3_asia_pacific(db)
        us_inst = db.query(Institution).filter(Institution.country_code == "US").first()
        assert us_inst is not None
        for cit, dest in (("CN", "CN"), ("IN", "IN"), ("PH", "MY"), ("PK", "CN")):
            np_res = calculate_net_price(
                db,
                us_inst,
                None,
                {
                    "residency_classification": "international",
                    "housing_preference": "on_campus",
                    "applicant_type": "first_year",
                    "degree_level": "bachelors",
                    "citizenship_country": cit,
                    "country_of_residence": cit,
                    "destination_country": dest,
                    "include_competitive_aid": True,
                },
            )
            for applied in np_res["verified_applicable_aid"] + np_res["conditional_aid"]:
                assert applied["award_currency"] == "USD"
                assert applied["estimated_max_usd"] > 0
    finally:
        db.close()

