import io
import uuid
from datetime import date

from app.models.institution import Institution
from app.models.requirements import CountryQualification, InstitutionRequirement


def _get_inst_by_ipeds_or_name(client_or_db_session_func, q: str, country: str = None):
    pass


def test_global_requirements_and_qualifications_coverage(client):
    # Verify country qualifications across US + priority international countries
    q_res = client.get("/api/v1/qualifications")
    assert q_res.status_code == 200
    quals = q_res.json()
    countries = {q["country_code"] for q in quals}
    for code in ["US", "CA", "GB", "FR", "DE", "HT", "IN", "AU", "JP"]:
        assert code in countries, f"Missing CountryQualification coverage for {code}"

    # Inspect Haiti national qualifications
    ht_res = client.get("/api/v1/qualifications?country=HT")
    assert ht_res.status_code == 200
    assert any("Baccalauréat haïtien" in q["qualification_name"] for q in ht_res.json())

    # Verify UC Berkeley (US) first-year test-blind vs Transfer Economics major prep
    search_ucb = client.get("/api/v1/institutions/search?q=110635").json()
    ucb_id = search_ucb["items"][0]["id"]

    fy_sum = client.get(f"/api/v1/institutions/{ucb_id}/requirements?applicant_type=first_year").json()
    assert fy_sum["has_verified_requirements"] is True
    assert any(r["requirement_type"] == "standardized_test" and r["importance"] == "not_accepted" for r in fy_sum["requirements"])
    assert len(fy_sum["deadlines"]) >= 1
    assert all(r["source_url"].startswith("https://") for r in fy_sum["requirements"])

    econ_sum = client.get(f"/api/v1/institutions/{ucb_id}/requirements?applicant_type=transfer&major=Economics").json()
    econ_titles = [r["title"] for r in econ_sum["requirements"]]
    assert any("Economics Transfer Major Preparation" in t for t in econ_titles)
    assert not any("Computer Science Transfer Major Prep" in t for t in econ_titles)

    # Verify international institutions (Oxford GB, TUM DE, UEH HT, Delhi IN, Tokyo JP)
    for query, country, expected_keyword in [
        ("University of Oxford", "GB", "UCAS"),
        ("Technical University of Munich", "DE", "VPD"),
        ("University of Haiti", "HT", "Concours"),
        ("University of Delhi", "IN", "CUET"),
        ("The University of Tokyo", "JP", "JLPT N1"),
    ]:
        res = client.get(f"/api/v1/institutions/search?q={query}&country={country}").json()
        assert res["total"] >= 1, f"Missing seeded university {query} ({country})"
        inst_id = res["items"][0]["id"]
        req_sum = client.get(f"/api/v1/institutions/{inst_id}/requirements").json()
        assert req_sum["has_verified_requirements"] is True
        assert any(expected_keyword in r["title"] for r in req_sum["requirements"])


def test_uncurated_institution_never_fabricates_requirements(client):
    # Search for an uncurated US community college or regional school
    res = client.get("/api/v1/institutions/search?type=vocational&limit=5").json()
    uncurated_id = None
    for item in res["items"]:
        sum_res = client.get(f"/api/v1/institutions/{item['id']}/requirements").json()
        if not sum_res["has_verified_requirements"]:
            uncurated_id = item["id"]
            assert sum_res["requirements"] == []
            assert "not yet been verified" in (sum_res["coverage_notice"] or "").lower()
            break
    assert uncurated_id is not None

    # Authenticated checklist on uncurated institution must also refuse to mark eligible
    uid = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer mock_uncurated_{uid}@univ.edu"}
    client.post("/api/v1/profile", json={"first_name": "Alex", "last_name": "Rivera", "applicant_type": "first_year"}, headers=headers)
    chk = client.get(f"/api/v1/institutions/{uncurated_id}/checklist", headers=headers).json()
    assert chk["has_verified_requirements"] is False
    assert chk["eligibility_status"] == "requirements_unverified"
    assert chk["readiness_pct"] == 0


def test_dynamic_checklist_incomplete_missing_and_qualified_scenarios(client):
    search_ucb = client.get("/api/v1/institutions/search?q=110635").json()
    ucb_id = search_ucb["items"][0]["id"]

    # Invalid credentials rejected on checklist endpoint; public requirements never leak PII
    assert (
        client.get(
            f"/api/v1/institutions/{ucb_id}/checklist",
            headers={"Authorization": "Bearer invalid_bad_token"},
        ).status_code
        == 401
    )
    pub_req = client.get(f"/api/v1/institutions/{ucb_id}/requirements").json()
    assert "profile_id" not in pub_req and "email" not in pub_req

    # 1. Student with incomplete profile (missing GPA, credits, courses, citizenship) -> MUST NOT be marked eligible
    uid1 = uuid.uuid4().hex[:8]
    h1 = {"Authorization": f"Bearer mock_chk_inc_{uid1}@univ.edu"}
    client.post(
        "/api/v1/profile",
        json={"first_name": "Sam", "last_name": "Empty", "applicant_type": "transfer", "intended_major": "Economics"},
        headers=h1,
    )
    chk_empty = client.get(f"/api/v1/institutions/{ucb_id}/checklist?applicant_type=transfer&major=Economics", headers=h1).json()
    assert chk_empty["has_verified_requirements"] is True
    assert chk_empty["eligibility_status"] in ("needs_information", "concerns_identified")
    assert chk_empty["readiness_pct"] < 50
    assert len(chk_empty["eligibility_concerns"]) >= 1

    # 2. International Haitian Transfer Student with low GPA (2.6) & incomplete credits -> concerns_identified + English/I-20 triggered
    uid2 = uuid.uuid4().hex[:8]
    h2 = {"Authorization": f"Bearer mock_chk_ht_{uid2}@univ.edu"}
    client.post(
        "/api/v1/profile",
        json={
            "first_name": "Jean",
            "last_name": "Baptiste",
            "applicant_type": "transfer",
            "country_of_residence": "HT",
            "intended_major": "Economics",
        },
        headers=h2,
    )
    client.post(
        "/api/v1/profile/enrollments",
        json={
            "institution_name_manual": "Lycée de Port-au-Prince",
            "institution_country": "HT",
            "enrollment_type": "secondary",
            "degree_type": "Baccalauréat haïtien (NS4)",
            "cumulative_gpa": 15.0,
        },
        headers=h2,
    )
    client.post(
        "/api/v1/profile/enrollments",
        json={
            "institution_name_manual": "De Anza College",
            "institution_country": "US",
            "enrollment_type": "community_college",
            "cumulative_gpa": 2.60,
            "total_credits_earned": 32,
        },
        headers=h2,
    )
    chk_ht = client.get(f"/api/v1/institutions/{ucb_id}/checklist?applicant_type=transfer&major=Economics", headers=h2).json()
    assert chk_ht["is_international_for_target"] is True
    assert chk_ht["eligibility_status"] == "concerns_identified"
    assert any("below required 3.0" in c for c in chk_ht["eligibility_concerns"])
    assert any("English Language Proficiency" in r["title"] for r in chk_ht["other_requirements"] + chk_ht["completed_requirements"])
    assert any("Financial Certification" in r["title"] for r in chk_ht["missing_documents"])

    # Secondary transcript alone MUST NOT falsely satisfy post-secondary Official College Transcript(s)
    client.post(
        "/api/v1/documents/upload",
        headers=h2,
        files={"file": ("bulletin_baccalaureat_haitien.txt", io.BytesIO(b"Releve de notes Baccalaureat haitien NS4 15/20"), "text/plain")},
        data={"document_category": "transcript"},
    )
    chk_ht_sec = client.get(f"/api/v1/institutions/{ucb_id}/checklist?applicant_type=transfer&major=Economics", headers=h2).json()
    assert not any("Official College Transcript" in r["title"] for r in chk_ht_sec["completed_requirements"])
    assert any("Official College Transcript" in r["title"] and r["status"] == "missing" for r in chk_ht_sec["missing_documents"])

    # 3. Qualified Domestic Transfer Student w/ GPA 3.85, 64 units, Econ prereqs, 7-course pattern & documents
    uid3 = uuid.uuid4().hex[:8]
    h3 = {"Authorization": f"Bearer mock_chk_qual_{uid3}@univ.edu"}
    client.post(
        "/api/v1/profile",
        json={
            "first_name": "Elena",
            "last_name": "Vargas",
            "applicant_type": "transfer",
            "country_of_residence": "US",
            "residency_status": "US Citizen",
            "intended_major": "Economics",
        },
        headers=h3,
    )
    client.post(
        "/api/v1/profile/enrollments",
        json={
            "institution_name_manual": "US High School",
            "institution_country": "US",
            "enrollment_type": "secondary",
            "cumulative_gpa": 3.8,
        },
        headers=h3,
    )
    enr_res = client.post(
        "/api/v1/profile/enrollments",
        json={
            "institution_name_manual": "De Anza College",
            "institution_country": "US",
            "enrollment_type": "community_college",
            "cumulative_gpa": 3.85,
            "total_credits_earned": 64,
        },
        headers=h3,
    ).json()
    enr_id = enr_res["id"]

    for code, name in [
        ("ECON 1", "Principles of Microeconomics"),
        ("ECON 2", "Principles of Macroeconomics"),
        ("MATH 1A", "Calculus I"),
        ("MATH 1B", "Calculus II"),
        ("ENGL 1A", "English Composition I"),
        ("ENGL 1B", "English Composition II"),
        ("HIST 17A", "US History"),
        ("PSYC 1", "General Psychology"),
        ("BIOL 10", "Introductory Biology"),
        ("PHIL 1", "Introduction to Philosophy"),
    ]:
        client.post(
            f"/api/v1/profile/enrollments/{enr_id}/courses",
            json={"course_code": code, "course_name": name, "credit_hours": 4.0, "grade": "A", "status": "completed"},
            headers=h3,
        )

    # Upload transcript to Document Vault -> auto-matches official transcript requirement
    client.post(
        "/api/v1/documents/upload",
        headers=h3,
        files={"file": ("deanza_transcript.txt", io.BytesIO(b"De Anza College Official Transcript Grade A"), "text/plain")},
        data={"document_category": "transcript"},
    )

    chk_ok = client.get(f"/api/v1/institutions/{ucb_id}/checklist?applicant_type=transfer&major=Economics", headers=h3).json()
    assert chk_ok["is_international_for_target"] is False
    # English & I-20 waived/not_applicable for domestic US-educated citizen
    na_titles = [r["title"] for r in chk_ok["not_applicable_requirements"]]
    assert any("English Language Proficiency" in t for t in na_titles)
    comp_titles = [r["title"] for r in chk_ok["completed_requirements"]]
    assert any("Minimum Transferable College GPA" in t for t in comp_titles)
    assert any("Minimum Completed Transferable Credits" in t for t in comp_titles)
    assert any("Economics Transfer Major Preparation" in t for t in comp_titles)
    assert any("Official College Transcript" in t and r["satisfied_by_document_id"] for r in chk_ok["completed_requirements"] for t in [r["title"]])

    # Verify application workspace inherits real DB checklist & enforces owner authorization on refresh
    app_res = client.post(
        "/api/v1/applications",
        json={"institution_id": ucb_id, "applicant_type": "transfer", "intended_major": "Economics"},
        headers=h3,
    )
    assert app_res.status_code == 201
    app_id = app_res.json()["id"]
    assert any(r["verification_status"] == "verified" and r["source_url"] for r in app_res.json()["requirements_status"])
    assert client.post(f"/api/v1/applications/{app_id}/refresh-checklist", headers=h1).status_code == 404


def test_conditional_credit_threshold_umich_and_counselor_haitian_creole(client):
    # UMich transfer high school transcript condition (< 30 credits => required; >= 30 => optional)
    umich = client.get("/api/v1/institutions/search?q=170976").json()["items"][0]
    uid = uuid.uuid4().hex[:8]
    h = {"Authorization": f"Bearer mock_umich_{uid}@univ.edu"}
    client.post("/api/v1/profile", json={"first_name": "Marc", "last_name": "Noel", "applicant_type": "transfer"}, headers=h)
    client.post(
        "/api/v1/profile/enrollments",
        json={"institution_name_manual": "CC", "institution_country": "US", "enrollment_type": "community_college", "cumulative_gpa": 3.5, "total_credits_earned": 18},
        headers=h,
    )
    chk_low = client.get(f"/api/v1/institutions/{umich['id']}/checklist?applicant_type=transfer", headers=h).json()
    hs_items = [r for r in chk_low["missing_documents"] + chk_low["other_requirements"] if "High School Transcript" in r["title"]]
    assert len(hs_items) == 1
    assert hs_items[0]["effective_importance"] == "required"

    # Grounded Haitian Creole Counselor query scoped by institution_id (with exact prompt from spec)
    ucb_id = client.get("/api/v1/institutions/search?q=110635").json()["items"][0]["id"]
    chat_res = client.post(
        "/api/v1/counselor/chat",
        headers=h,
        json={
            "message": "Ki dokiman mwen bezwen pou m aplike kòm etidyan transfè nan inivèsite sa a?",
            "language": "ht-HT",
            "institution_id": ucb_id,
        },
    )
    assert chat_res.status_code == 200
    msg = chat_res.json()
    assert msg["language"] == "ht-HT"
    assert "University of California-Berkeley" in msg["content"]
    assert len(msg["citations"]) >= 2
    assert any("berkeley.edu" in c["url"] or "universityofcalifornia.edu" in c["url"] for c in msg["citations"])

    # Upcoming deadlines endpoint
    dl_res = client.get("/api/v1/deadlines/upcoming?days=365")
    assert dl_res.status_code == 200
    assert len(dl_res.json()) >= 1
