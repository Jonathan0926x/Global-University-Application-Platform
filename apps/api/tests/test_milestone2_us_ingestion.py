import uuid
import pytest
from app.ingestion.base import (
    BaseInstitutionConnector,
    IngestionPipeline,
    NormalizedInstitution,
)
from app.ingestion.ipeds import IPEDSConnector
from app.ingestion.scorecard import CollegeScorecardConnector
from app.ingestion.dedup import deduplicate_us_non_ipeds
from app.models.institution import Institution
from app.models.provenance import DataQualityFlag


class _FixtureConnector(BaseInstitutionConnector):
    source_name = "Test Fixture"
    source_type = "college_scorecard"
    license_type = "Public Domain"

    def __init__(self, items, source_type="college_scorecard"):
        self._items = items
        self.source_type = source_type

    def fetch_institutions(self, **kwargs):
        return self._items


def test_ipeds_and_scorecard_real_values_verified_in_db(db):
    """Verify UC Berkeley and De Anza College match official IPEDS 2023 + Scorecard records."""
    ipeds_rows = IPEDSConnector().fetch_institutions(states=["CA"])
    ipeds_by_id = {r.ipeds_unit_id: r for r in ipeds_rows}

    assert "110635" in ipeds_by_id  # UC Berkeley
    assert "113333" in ipeds_by_id  # De Anza College

    ucb_src = ipeds_by_id["110635"]
    ucb_db = db.query(Institution).filter(Institution.ipeds_unit_id == "110635").first()
    assert ucb_db is not None
    assert ucb_db.official_name == ucb_src.official_name
    assert float(ucb_db.tuition_in_state) == pytest.approx(ucb_src.tuition_in_state, abs=0.01)
    assert float(ucb_db.tuition_out_of_state) == pytest.approx(ucb_src.tuition_out_of_state, abs=0.01)
    assert ucb_db.total_enrollment == ucb_src.total_enrollment
    assert float(ucb_db.acceptance_rate) == pytest.approx(ucb_src.acceptance_rate, abs=0.01)
    assert ucb_db.accrediting_body is not None
    assert ucb_db.completion_rate_4yr is not None

    deanza_src = ipeds_by_id["113333"]
    deanza_db = db.query(Institution).filter(Institution.ipeds_unit_id == "113333").first()
    assert deanza_db is not None
    assert deanza_db.institution_type == "community_college"
    assert float(deanza_db.tuition_in_state) == pytest.approx(deanza_src.tuition_in_state, abs=0.01)
    assert deanza_db.total_enrollment == deanza_src.total_enrollment
    # Open-admissions community college has no acceptance_rate -> stored as None, never 0
    assert deanza_db.acceptance_rate is None


def test_scorecard_parser_privacy_suppressed_and_branch_mapping():
    raw_row = {
        "UNITID": "999001",
        "OPEID": "00123401",
        "OPEID6": "001234",
        "INSTNM": "Test State University - Branch",
        "CITY": "Fresno",
        "STABBR": "CA",
        "MAIN": "0",
        "CONTROL": "1",
        "PREDDEG": "3",
        "ADM_RATE": "PrivacySuppressed",
        "TUITIONFEE_IN": "NULL",
        "TUITIONFEE_OUT": "18500",
        "C150_4": "0.625",
        "UGDS": "2400",
        "PCIP11": "0.18",
        "PCIP52": "0.01",  # below 0.03 threshold
    }
    parsed = CollegeScorecardConnector._parse_row(raw_row, "https://collegescorecard.ed.gov/data/")
    assert parsed is not None
    assert parsed.is_main_campus is False
    assert parsed.parent_ope6_id == "001234"
    assert parsed.acceptance_rate is None
    assert parsed.tuition_in_state is None
    assert parsed.tuition_out_of_state == 18500.0
    assert parsed.completion_rate_4yr == 62.5
    assert len(parsed.programs) == 1
    assert parsed.programs[0].cip_code == "11"


def test_authority_and_freshness_guards_never_overwrite_newer_verified(db):
    uid = f"TEST_{uuid.uuid4().hex[:6]}"
    pipeline = IngestionPipeline(db)

    # 1. Insert verified 2024-2025 IPEDS record (authority=90)
    newer_ipeds = NormalizedInstitution(
        official_name=f"Authority Test University {uid}",
        country_code="US",
        state_province="NY",
        city="Albany",
        institution_type="university",
        control_type="public",
        ipeds_unit_id=uid,
        tuition_in_state=10000.0,
        official_website="https://authtest.edu",
        source_type="ipeds",
        source_name="NCES IPEDS",
        academic_year="2024-2025",
        confidence_level="verified",
    )
    r1 = pipeline.run_connector(_FixtureConnector([newer_ipeds], source_type="ipeds"))
    assert r1.records_created == 1

    # 2. Attempt stale 2021-2022 Scorecard import -> skipped_stale=1, tuition untouched
    older_scorecard = newer_ipeds.model_copy(
        update={
            "tuition_in_state": 7500.0,
            "source_type": "college_scorecard",
            "academic_year": "2021-2022",
        }
    )
    r2 = pipeline.run_connector(_FixtureConnector([older_scorecard], source_type="college_scorecard"))
    vr2 = r2.metadata_json["validation_report"]
    assert vr2["skipped_stale"] == 1

    inst_db = db.query(Institution).filter(Institution.ipeds_unit_id == uid).first()
    assert float(inst_db.tuition_in_state) == 10000.0

    # 3. Same-year lower-authority source with >25% tuition divergence -> keep IPEDS, flag conflict
    conflict_sc = newer_ipeds.model_copy(
        update={
            "tuition_in_state": 15000.0,
            "source_type": "college_scorecard",
            "academic_year": "2024-2025",
        }
    )
    r3 = pipeline.run_connector(_FixtureConnector([conflict_sc], source_type="college_scorecard"))
    vr3 = r3.metadata_json["validation_report"]
    assert vr3["conflicts_detected"] == 1

    db.refresh(inst_db)
    assert float(inst_db.tuition_in_state) == 10000.0
    flag = db.query(DataQualityFlag).filter(
        DataQualityFlag.entity_id == inst_db.id,
        DataQualityFlag.flag_type == "conflicting_data",
    ).first()
    assert flag is not None


def test_idempotent_ipeds_reimport_no_duplicates(db):
    pipeline = IngestionPipeline(db)
    connector = IPEDSConnector()
    # Ingest a 10-institution subset twice; second run must create 0 and update 0
    pipeline.run_connector(connector, states=["DE"], limit=10)
    run_again = pipeline.run_connector(connector, states=["DE"], limit=10)
    assert run_again.records_created == 0
    assert run_again.records_updated == 0
    assert deduplicate_us_non_ipeds(db) == []


def test_directory_filters_pagination_and_detail_endpoints(client):
    # 1. Filters metadata endpoint
    f_res = client.get("/api/v1/institutions/filters")
    assert f_res.status_code == 200
    f_data = f_res.json()
    assert f_data["total_institutions"] >= 6000
    assert f_data["us_institutions"] >= 6000
    assert "CA" in f_data["us_states"]

    # 2. Pagination & state/type/control/tuition/enrollment filtering
    search_res = client.get(
        "/api/v1/institutions/search?country=US&state=CA&type=community_college&control=public&tuition_max=5000&enrollment_min=15000&sort=enrollment_desc&page=1&limit=10"
    )
    assert search_res.status_code == 200
    s_data = search_res.json()
    assert s_data["total"] >= 1
    assert len(s_data["items"]) <= 10
    for item in s_data["items"]:
        assert item["country_code"] == "US"
        assert item["state_province"] == "CA"
        assert item["institution_type"] == "community_college"
        assert item["control_type"] == "public"
        assert item["total_enrollment"] >= 15000
        assert item["tuition_in_state"] <= 5000

    # 3. Detail page endpoint for UC Berkeley
    ucb_search = client.get("/api/v1/institutions/search?q=110635")
    assert ucb_search.status_code == 200
    ucb_id = ucb_search.json()["items"][0]["id"]

    detail_res = client.get(f"/api/v1/institutions/{ucb_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["ipeds_unit_id"] == "110635"
    assert len(detail["costs"]) >= 1
    assert len(detail["programs"]) >= 1
    assert len(detail["provenance_summary"]) >= 1
    # Zero student PII
    assert "email" not in detail
    assert "profile_id" not in detail
