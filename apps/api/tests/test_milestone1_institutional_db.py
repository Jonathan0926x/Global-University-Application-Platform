import uuid
from app.ingestion.base import (
    BaseInstitutionConnector,
    IngestionPipeline,
    NormalizedInstitution,
)
from app.ingestion.countries_seed import seed_countries
from app.ingestion.openalex_ror import OpenAlexRorConnector
from app.models.institution import Institution
from app.models.provenance import DataProvenance, DataQualityFlag


class _FixtureConnector(BaseInstitutionConnector):
    source_name = "Test Fixture Source"
    source_type = "api"
    license_type = "CC0-1.0"

    def __init__(self, items):
        self._items = items

    def fetch_institutions(self, **kwargs):
        return self._items


def test_countries_catalog_and_endpoint(client, db):
    seed_countries(db)

    res = client.get("/api/v1/countries")
    assert res.status_code == 200
    countries = res.json()
    codes = {c["code"] for c in countries}
    assert {"US", "CA", "HT", "FR", "GB", "DE", "IN", "NG", "JP", "BR"}.issubset(codes)

    carib_res = client.get("/api/v1/countries?region=Caribbean")
    assert carib_res.status_code == 200
    carib_codes = {c["code"] for c in carib_res.json()}
    assert "HT" in carib_codes
    assert "JM" in carib_codes


def test_openalex_parser_multi_campus_and_international():
    sample_raw = {
        "id": "https://openalex.org/I999999999",
        "ror": "https://ror.org/0testror9",
        "display_name": "Université Test Campus Nord",
        "display_name_acronyms": ["UTCN"],
        "display_name_alternatives": ["UT Campus Nord"],
        "country_code": "HT",
        "geo": {
            "city": "Cap-Haïtien",
            "region": "Nord",
            "country": "Haiti",
            "latitude": 19.7578,
            "longitude": -72.2042,
        },
        "homepage_url": "https://example-ht.edu.ht",
        "associated_institutions": [
            {"relationship": "parent", "ror": "https://ror.org/0parent01"}
        ],
        "ids": {"wikidata": "https://www.wikidata.org/wiki/Q12345"},
    }
    parsed = OpenAlexRorConnector.parse_openalex_record(sample_raw)
    assert parsed is not None
    assert parsed.ror_id == "0testror9"
    assert parsed.openalex_id == "I999999999"
    assert parsed.country_code == "HT"
    assert parsed.abbreviation == "UTCN"
    assert parsed.parent_ror_id == "0parent01"
    assert parsed.is_main_campus is False
    assert parsed.institution_type == "branch_campus"
    assert parsed.external_ids.get("wikidata") == "https://www.wikidata.org/wiki/Q12345"


def test_ingestion_pipeline_idempotency_provenance_and_flags(db):
    unique_suffix = uuid.uuid4().hex[:6]
    parent_ror = f"ror_parent_{unique_suffix}"
    branch_ror = f"ror_branch_{unique_suffix}"

    parent_item = NormalizedInstitution(
        official_name=f"Test National University {unique_suffix}",
        country_code="CA",
        state_province="Ontario",
        city="Toronto",
        institution_type="university",
        control_type="public",
        ror_id=parent_ror,
        official_website=None,  # Intentionally missing to verify DataQualityFlag creation
        source_type="api",
        source_name="Test Fixture",
        source_url="https://example.org/test",
        academic_year="2026-2027",
    )
    branch_item = NormalizedInstitution(
        official_name=f"Test National University {unique_suffix} - Mississauga",
        campus_name="Mississauga Campus",
        is_main_campus=False,
        parent_ror_id=parent_ror,
        country_code="CA",
        state_province="Ontario",
        city="Mississauga",
        institution_type="branch_campus",
        ror_id=branch_ror,
        official_website="https://utm.example.ca",
        source_type="api",
        source_name="Test Fixture",
        source_url="https://example.org/test-branch",
        academic_year="2026-2027",
    )

    pipeline = IngestionPipeline(db)
    run1 = pipeline.run_connector(_FixtureConnector([parent_item, branch_item]))
    assert run1.status == "completed"
    assert run1.records_created == 2
    assert run1.records_updated == 0
    assert run1.records_flagged == 1  # Missing website on parent_item

    parent_db = db.query(Institution).filter(Institution.ror_id == parent_ror).first()
    branch_db = db.query(Institution).filter(Institution.ror_id == branch_ror).first()
    assert parent_db is not None
    assert branch_db is not None
    assert branch_db.parent_institution_id == parent_db.id

    # Verify DataQualityFlag created for parent_item missing official_website
    flag = db.query(DataQualityFlag).filter(
        DataQualityFlag.entity_id == parent_db.id,
        DataQualityFlag.flag_type == "missing_required_field",
        DataQualityFlag.resolved == False,
    ).first()
    assert flag is not None

    # Second run with identical payload must be 100% idempotent
    run2 = pipeline.run_connector(_FixtureConnector([parent_item, branch_item]))
    assert run2.records_created == 0
    assert run2.records_updated == 0

    # Third run updating parent website & tuition must preserve previous provenance version
    parent_updated = parent_item.model_copy(
        update={
            "official_website": "https://tnu.example.ca",
            "tuition_out_of_state": 32500.0,
            "academic_year": "2027-2028",
        }
    )
    run3 = pipeline.run_connector(_FixtureConnector([parent_updated]))
    assert run3.records_created == 0
    assert run3.records_updated == 1

    provs = (
        db.query(DataProvenance)
        .filter(DataProvenance.entity_id == parent_db.id)
        .order_by(DataProvenance.created_at.asc())
        .all()
    )
    assert len(provs) == 2
    assert provs[0].is_current is False
    assert provs[1].is_current is True
    assert provs[1].previous_value is not None
    assert "official_website" in provs[1].previous_value
    assert provs[1].previous_value["official_website"] is None


def test_institutional_search_detail_and_provenance_endpoints(client):
    # 1. Search by query (FTS)
    res = client.get("/api/v1/institutions/search?q=Berkeley")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    assert any("Berkeley" in item["official_name"] for item in body["items"])

    # Ensure zero student PII fields leak in public response
    first_item = body["items"][0]
    assert "email" not in first_item
    assert "profile_id" not in first_item

    # 2. Search global international records (ingested via OpenAlex CC0)
    ht_res = client.get("/api/v1/institutions/search?country=HT")
    assert ht_res.status_code == 200
    assert ht_res.json()["total"] >= 1

    # 3. Search by institution_type (paginated across 999+ community colleges)
    cc_res = client.get("/api/v1/institutions/search?type=community_college")
    assert cc_res.status_code == 200
    assert cc_res.json()["total"] >= 1
    assert all(i["institution_type"] == "community_college" for i in cc_res.json()["items"])
    deanza_res = client.get("/api/v1/institutions/search?q=De+Anza&type=community_college")
    assert deanza_res.status_code == 200
    assert any(i["official_name"] == "De Anza College" for i in deanza_res.json()["items"])

    # 4. Detail & provenance history endpoints
    inst_id = first_item["id"]
    detail_res = client.get(f"/api/v1/institutions/{inst_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == inst_id
    assert "provenance_summary" in detail
    assert "campuses" in detail

    prov_res = client.get(f"/api/v1/institutions/{inst_id}/provenance")
    assert prov_res.status_code == 200
    assert isinstance(prov_res.json(), list)


def test_admin_endpoints_enforce_rbac(client):
    student_headers = {"Authorization": "Bearer dev_token"}
    admin_headers = {"Authorization": "Bearer mock_admin_qa@uniglobe.edu"}

    # Students must receive 403 Forbidden
    assert client.get("/api/v1/admin/quality-flags", headers=student_headers).status_code == 403
    assert client.get("/api/v1/admin/ingestion-runs", headers=student_headers).status_code == 403

    # Admins receive 200 OK
    flags_res = client.get("/api/v1/admin/quality-flags", headers=admin_headers)
    assert flags_res.status_code == 200
    runs_res = client.get("/api/v1/admin/ingestion-runs", headers=admin_headers)
    assert runs_res.status_code == 200
    assert len(runs_res.json()) >= 1
