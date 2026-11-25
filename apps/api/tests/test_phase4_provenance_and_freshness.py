from datetime import datetime, timedelta, timezone
import uuid

from app.models.credentials import CredentialRecognitionRule, GradeConversionRule
from app.models.rag import ScholarshipEligibilityRule, ScholarshipProgram
from app.models.requirements import CountryQualification
from app.services.financial_engine import match_scholarships_deterministic
from app.services.freshness_governance import (
    FRESHNESS_STATES,
    VERIFICATION_POLICY_INTERVALS,
    classify_freshness,
    compute_verification_expiry,
    evaluate_scholarship_freshness,
    is_valid_official_url,
    sweep_phase4_freshness,
    validate_credential_catalog,
    validate_scholarship_catalog,
)


def test_freshness_classifications_and_differentiated_intervals():
    now = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)

    # Differentiated intervals strictly preserve volatility domains
    assert VERIFICATION_POLICY_INTERVALS["scholarship_deadlines"]["max_age_days"] == 90
    assert VERIFICATION_POLICY_INTERVALS["scholarship_amounts"]["max_age_days"] == 120
    assert VERIFICATION_POLICY_INTERVALS["scholarship_eligibility"]["max_age_days"] == 180
    assert VERIFICATION_POLICY_INTERVALS["qualification_frameworks"]["max_age_days"] == 365
    assert VERIFICATION_POLICY_INTERVALS["credential_recognition"]["max_age_days"] == 365
    assert VERIFICATION_POLICY_INTERVALS["grade_conversion_rules"]["max_age_days"] == 730

    assert compute_verification_expiry(now, "scholarship_deadlines") == now + timedelta(days=90)
    assert compute_verification_expiry(now, "grade_conversion_rules") == now + timedelta(days=730)
    assert compute_verification_expiry(None, "scholarship_amounts") is None

    # Verify all 6 canonical classifications
    states_seen = {
        classify_freshness(
            verified_at=now - timedelta(days=10),
            verification_expires_at=now + timedelta(days=80),
            policy_kind="scholarship_deadlines",
            source_url="https://finaid.mit.edu/",
            now=now,
        ),
        classify_freshness(
            verified_at=now - timedelta(days=85),
            verification_expires_at=now + timedelta(days=5),
            policy_kind="scholarship_deadlines",
            source_url="https://finaid.mit.edu/",
            now=now,
        ),
        classify_freshness(
            verified_at=now - timedelta(days=100),
            verification_expires_at=now - timedelta(days=10),
            policy_kind="scholarship_deadlines",
            source_url="https://finaid.mit.edu/",
            now=now,
        ),
        classify_freshness(
            verified_at=now - timedelta(days=10),
            verification_expires_at=now + timedelta(days=80),
            policy_kind="scholarship_deadlines",
            source_url="http://localhost/bad",
            now=now,
        ),
        classify_freshness(
            verified_at=now - timedelta(days=10),
            verification_expires_at=now + timedelta(days=80),
            policy_kind="scholarship_deadlines",
            source_url="https://finaid.mit.edu/",
            has_conflict=True,
            now=now,
        ),
        # Unestablished verification_expires_at never fabricates validity -> requires_manual_review
        classify_freshness(
            verified_at=now,
            verification_expires_at=None,
            policy_kind="scholarship_deadlines",
            source_url="https://finaid.mit.edu/",
            now=now,
        ),
    }
    assert states_seen == set(FRESHNESS_STATES)

    # Per-claim expiration overrides current parent status when deadline claim has aged >90d
    sch = ScholarshipProgram(
        country_code="US",
        title="Claim Level Expiry Check",
        eligibility_summary="Test claim governance.",
        source_name="MIT SFS",
        source_url="https://sfs.mit.edu/",
        verified_at=now - timedelta(days=95),
        verification_expires_at=now + timedelta(days=85),
        is_verified=True,
        is_current=True,
        claim_provenance={
            "deadlines": {
                "verified_at": (now - timedelta(days=95)).isoformat(),
                "source_url": "https://sfs.mit.edu/",
            },
            "eligibility_rules": {
                "verified_at": (now - timedelta(days=20)).isoformat(),
                "source_url": "https://sfs.mit.edu/",
            },
        },
    )
    assert evaluate_scholarship_freshness(sch, now=now) == "expired"


def test_historical_preservation_on_expiration_and_match_exclusion(db, monkeypatch):
    # Prevent transaction leak into shared session fixture / PostgreSQL tables
    monkeypatch.setattr(db, "commit", db.flush)
    nested = db.begin_nested()
    try:
        now = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
        uid = uuid.uuid4().hex[:8]
        expired_title = f"Expired Historical Award {uid}"

        expired_sch = ScholarshipProgram(
            country_code="US",
            title=expired_title,
            eligibility_summary="Historical award whose cycle verification expired.",
            covers_international=True,
            award_amount_min_usd=5000,
            award_amount_max_usd=10000,
            source_name="Official Aid Office",
            source_url="https://sfs.mit.edu/",
            verified_at=now - timedelta(days=200),
            verification_expires_at=now - timedelta(days=5),
            is_verified=True,
            is_current=True,
            source_type="official_university",
            academic_year="2025-2026",
            freshness_status="current",
        )
        db.add(expired_sch)

        expired_rec = CredentialRecognitionRule(
            source_country_code="HT",
            destination_country_code="DE",
            source_credential_name=f"Historical Rule {uid}",
            pathway_notes="Legacy guidance.",
            source_name="KMK anabin",
            source_url="https://anabin.kmk.org/",
            verified_at=now - timedelta(days=400),
            verification_expires_at=now - timedelta(days=10),
            verification_status="verified",
            freshness_status="current",
        )
        db.add(expired_rec)

        expired_qual = CountryQualification(
            country_code="HT",
            qualification_name=f"Historical Qual {uid}",
            qualification_type="national_exam",
            source_name="MENFP",
            source_url="https://menfp.gouv.ht/",
            verified_at=now - timedelta(days=400),
            verification_expires_at=now - timedelta(days=10),
            verification_status="verified",
            freshness_status="current",
        )
        db.add(expired_qual)
        db.flush()

        sweep_res = sweep_phase4_freshness(db, now=now)
        assert sweep_res["counts"]["expired"] >= 3

        # Expired records MUST remain in PostgreSQL (never deleted!) and flip cleanly
        kept_sch = db.query(ScholarshipProgram).filter(ScholarshipProgram.id == expired_sch.id).first()
        kept_rec = db.query(CredentialRecognitionRule).filter(CredentialRecognitionRule.id == expired_rec.id).first()
        kept_qual = db.query(CountryQualification).filter(CountryQualification.id == expired_qual.id).first()
        assert kept_sch is not None and kept_sch.freshness_status == "expired" and kept_sch.is_current is False
        assert kept_rec is not None and kept_rec.freshness_status == "expired"
        assert kept_qual is not None and kept_qual.freshness_status == "expired"

        # Expired awards must never surface in active deterministic scholarship matching
        match_res = match_scholarships_deterministic(
            db,
            None,
            {"citizenship_country": "HT", "applicant_type": "first_year", "degree_level": "bachelors"},
            include_ineligible=True,
        )
        matched_titles = {r["title"] for r in match_res["results"]}
        assert expired_title not in matched_titles
    finally:
        nested.rollback()


def test_independent_validation_detects_url_duplicate_provenance_expiry_and_conflicts(db):
    # Official seeded catalog passes strict structural integrity checks with zero errors
    base_sch_report = validate_scholarship_catalog(db)
    base_cred_report = validate_credential_catalog(db)
    assert base_sch_report["invalid_urls"] == []
    assert base_sch_report["duplicates"] == []
    assert base_sch_report["expired_records"] == []
    assert base_sch_report["conflicting_records"] == []
    assert base_cred_report["invalid_urls"] == []
    assert base_cred_report["expired_records"] == []
    assert base_cred_report["conflicting_records"] == []

    # Verify official URL validator rejects insecure, local, private-IP, and aggregator URLs
    assert is_valid_official_url("https://sfs.mit.edu/")[0] is True
    assert is_valid_official_url("http://sfs.mit.edu/")[0] is False
    assert is_valid_official_url("https://169.254.169.254/latest/meta-data/")[0] is False
    assert is_valid_official_url("https://www.scholarships.com/test")[0] is False
    assert is_valid_official_url("https://localhost/aid")[0] is False

    nested = db.begin_nested()
    try:
        # Inject synthetic bad rows inside savepoint
        uid = uuid.uuid4().hex[:8]
        now = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
        bad_url_title = f"Aggregator Bad Award {uid}"
        dup_title = f"Duplicate Audit Award {uid}"

        db.add(
            ScholarshipProgram(
                country_code="US",
                title=bad_url_title,
                eligibility_summary="Uses secondary aggregator URL.",
                award_amount_min_usd=9000,
                award_amount_max_usd=3000,  # Conflicting min > max!
                covers_international=False,
                source_name="Aggregator",
                source_url="https://www.scholarships.com/fake",
                verified_at=now - timedelta(days=200),
                verification_expires_at=now - timedelta(days=1),
                source_type="unknown",
            )
        )
        for _ in range(2):
            db.add(
                ScholarshipProgram(
                    country_code="US",
                    title=dup_title,
                    eligibility_summary="Duplicate test entry.",
                    source_name="Official Office",
                    source_url="https://studentaid.gov/",
                    verified_at=now,
                )
            )
        # Conflict between covers_international=False and rule allowing HT citizenship
        conflict_sch = ScholarshipProgram(
            country_code="US",
            title=f"Conflict Citizenship {uid}",
            eligibility_summary="Domestic vs international rule conflict.",
            covers_international=False,
            source_name="Official Office",
            source_url="https://studentaid.gov/",
            verified_at=now,
        )
        db.add(conflict_sch)
        db.flush()
        db.add(
            ScholarshipEligibilityRule(
                scholarship_id=conflict_sch.id,
                rule_dimension="citizenship",
                rule_operator="in",
                rule_value={"countries": ["HT"]},
                human_label="Conflicting international rule",
                is_mandatory=True,
            )
        )
        db.add(
            GradeConversionRule(
                source_country_code="ZZ",
                grading_system_key=f"bad_scale_{uid}",
                scale_name="Bad Broken Scale",
                band_order=1,
                min_numeric=15,
                max_numeric=10,
                classification_label="Broken",
                target_letter_equivalent="A",
                target_gpa_low=3.9,
                target_gpa_high=3.5,
                target_gpa_point=3.7,
                methodology="test",
                methodology_citation="test",
            )
        )
        db.flush()

        sch_report = validate_scholarship_catalog(db, now=now)
        cred_report = validate_credential_catalog(db, now=now)

        assert any(x["title"] == bad_url_title for x in sch_report["invalid_urls"])
        assert any(x["title"] == dup_title for x in sch_report["duplicates"])
        assert any(x["title"] == bad_url_title for x in sch_report["expired_records"])
        assert any(x["title"] == bad_url_title and "source_type" in x["missing_fields"] for x in sch_report["missing_provenance"])
        assert any(x["title"] == bad_url_title for x in sch_report["conflicting_records"])
        assert any(x["title"] == f"Conflict Citizenship {uid}" for x in sch_report["conflicting_records"])
        assert len(cred_report["conflicting_records"]) >= 2
    finally:
        nested.rollback()


def test_legacy_records_preserve_honest_unknown_metadata_and_backward_compatibility(client, db):
    # Remediated legacy records must NEVER carry fabricated reviewer names or invented source versions,
    # while CSS-Profile/need-dependent awards keep requires_manual_review on individualized amounts.
    mit = (
        db.query(ScholarshipProgram)
        .filter(ScholarshipProgram.title == "MIT Need-Blind Admissions & Full-Need Institutional Aid")
        .first()
    )
    assert mit is not None
    assert mit.verified_by is None
    assert mit.source_version is None
    assert mit.source_type == "official_institutional"
    assert mit.freshness_status == "requires_manual_review"
    assert mit.claim_provenance and "award_amounts" in mit.claim_provenance

    # Verify fallback honesty for un-audited unknown-source records still yields requires_manual_review
    unknown_fallback = ScholarshipProgram(
        country_code="US",
        title="Unverified Source Fallback Check",
        eligibility_summary="Fallback check",
        source_name="Unknown",
        source_url="https://example.edu/aid",
        source_type="unknown",
        freshness_status="requires_manual_review",
    )
    assert evaluate_scholarship_freshness(unknown_fallback) == "requires_manual_review"

    # Existing API contracts stay backward compatible and surface Step 1 governance fields
    res = client.post(
        "/api/v1/financial/scholarships/match",
        json={
            "citizenship_country": "HT",
            "applicant_type": "first_year",
            "degree_level": "bachelors",
            "financial_need_level": "high",
            "household_income_usd": 25000,
            "gpa_4": 3.85,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["total_scholarships"] >= 26
    mit_api = next(r for r in body["results"] if "MIT Need-Blind" in r["title"])
    assert mit_api["eligibility_status"] == "eligible"
    assert mit_api["freshness_status"] == "requires_manual_review"
    assert mit_api["verified_by"] is None
    assert mit_api["source_type"] == "official_institutional"

    cred_res = client.post(
        "/api/v1/credentials/evaluate",
        json={
            "source_country_code": "FR",
            "grading_system_key": "fr_20",
            "raw_grade": "14.5",
            "destination_country_code": "US",
        },
    )
    assert cred_res.status_code == 200
    cred_body = cred_res.json()
    assert cred_body["conversion"]["informational_equivalency"]["equivalency_classification"] == "reference_benchmark"
    assert cred_body["country_qualifications"][0]["freshness_status"] == "requires_manual_review"
