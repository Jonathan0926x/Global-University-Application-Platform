import io
import uuid
import pytest

from app.ingestion.assist_org import AssistOrgConnector


def _get_inst(client, query: str):
    res = client.get(f"/api/v1/institutions/search?q={query}&limit=5").json()
    assert res["total"] >= 1, f"Institution not found: {query}"
    return res["items"][0]


def test_assist_connector_enforces_eula_without_api_key():
    conn = AssistOrgConnector(api_key=None)
    conn.api_key = None
    assert conn.is_configured() is False
    with pytest.raises(RuntimeError, match="ASSIST_API_KEY"):
        conn.fetch_agreements(113, 79, 75)


def test_three_tier_equivalency_and_credit_systems(client):
    de_anza = _get_inst(client, "113333")
    ucb = _get_inst(client, "110635")
    ucla = _get_inst(client, "110662")
    umich = _get_inst(client, "170976")

    # 1. Tier 1 Officially Verified (De Anza ECON 2 -> UCLA ECON 1 & UCB ECON 1)
    t1_ucla = client.post(
        "/api/v1/transfer/equivalencies/evaluate",
        json={
            "source_institution_id": de_anza["id"],
            "source_course_code": "ECON 2",
            "source_course_name": "Principles of Microeconomics",
            "source_credits": 4.0,
            "source_credit_system": "us_quarter",
            "target_institution_id": ucla["id"],
            "intended_major": "Economics",
        },
    ).json()
    assert t1_ucla["equivalency_tier"] == 1
    assert t1_ucla["tier_label"] == "Officially Verified"
    assert t1_ucla["target_course_code"] == "ECON 1"
    assert t1_ucla["satisfies_major_requirement"] is True
    assert "assist.org" in (t1_ucla["source_url"] or "")

    # 2. Tier 2 Historically Observed (De Anza MATH 1A -> UMich MATH 115)
    t2_umich = client.post(
        "/api/v1/transfer/equivalencies/evaluate",
        json={
            "source_institution_id": de_anza["id"],
            "source_course_code": "MATH 1A",
            "source_course_name": "Calculus I",
            "source_credits": 5.0,
            "source_credit_system": "us_quarter",
            "target_institution_id": umich["id"],
            "intended_major": "Economics",
        },
    ).json()
    assert t2_umich["equivalency_tier"] == 2
    assert t2_umich["tier_label"] == "Historically Observed"
    assert t2_umich["target_course_code"] == "MATH 115"
    assert "not a binding guarantee" in t2_umich["disclaimer"].lower()

    # 3. Tier 3 AI-Predicted for International ECTS course w/ description & learning outcomes -> UCB
    t3_ects = client.post(
        "/api/v1/transfer/equivalencies/evaluate",
        json={
            "source_course_code": "IN0007",
            "source_course_name": "Fundamentals of Algorithms and Data Structures",
            "source_description": "Asymptotic Big-O complexity, linked lists, binary search trees, hash tables, graph traversal, sorting algorithms.",
            "source_learning_outcomes": ["Implement balanced trees, hash tables, and graph algorithms"],
            "source_credits": 8.0,
            "source_credit_system": "ects",
            "target_institution_id": ucb["id"],
            "intended_major": "Computer Science",
        },
    ).json()
    assert t3_ects["equivalency_tier"] == 3
    assert t3_ects["tier_label"] == "AI-Predicted (Unverified)"
    assert t3_ects["target_course_code"] == "COMPSCI 61B"
    assert t3_ects["original_credits"] == 8.0
    assert t3_ects["original_credit_system"] == "ects"
    assert t3_ects["normalized_semester_credits"] == 4.0
    assert "not an official university credit decision" in t3_ects["disclaimer"].lower()

    # 4. Unverified / Missing syllabus course (no agreement, no description)
    unv = client.post(
        "/api/v1/transfer/equivalencies/evaluate",
        json={
            "source_course_code": "MISC 99",
            "source_course_name": "Special Workshop",
            "source_credits": 3.0,
            "source_credit_system": "us_semester",
            "target_institution_id": ucb["id"],
        },
    ).json()
    assert unv["equivalency_tier"] is None
    assert unv["requires_syllabus"] is True
    assert unv["tier_label"] == "Unverified"


def test_student_transfer_dashboard_applicability_duplicates_and_syllabus(client):
    ucb = _get_inst(client, "110635")
    uid = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer mock_m4_{uid}@univ.edu"}
    other_headers = {"Authorization": f"Bearer mock_m4_other_{uid}@univ.edu"}

    client.post(
        "/api/v1/profile",
        json={"first_name": "Claire", "last_name": "Morel", "applicant_type": "transfer", "intended_major": "Economics"},
        headers=headers,
    )
    client.post(
        "/api/v1/profile",
        json={"first_name": "Other", "last_name": "User", "applicant_type": "transfer"},
        headers=other_headers,
    )

    # US Community College Enrollment (De Anza College, Quarter units)
    da_enr = client.post(
        "/api/v1/profile/enrollments",
        json={
            "institution_name_manual": "De Anza College",
            "institution_country": "US",
            "enrollment_type": "community_college",
            "cumulative_gpa": 3.7,
            "total_credits_earned": 27.0,
        },
        headers=headers,
    ).json()
    da_id = da_enr["id"]

    # Add Tier 1 Major+GE (ECON 1, ECON 2), GE-only (ART 1A), Elective-only (PE 1), Duplicate (ECON 2), and Unverified (CS 299)
    for code, name, hrs, sys in [
        ("ECON 1", "Principles of Macroeconomics", 4.0, "quarter_hour"),
        ("ECON 2", "Principles of Microeconomics", 4.0, "quarter_hour"),
        ("ECON 2", "Principles of Microeconomics", 4.0, "quarter_hour"),  # duplicate!
        ("ART 1A", "History of Art", 4.0, "quarter_hour"),              # GE only (not Econ major!)
        ("PE 1", "Lifetime Fitness & Conditioning", 1.0, "quarter_hour"), # Elective only (neither GE nor Major!)
    ]:
        client.post(
            f"/api/v1/profile/enrollments/{da_id}/courses",
            json={"course_code": code, "course_name": name, "credit_hours": hrs, "credit_type": sys, "status": "completed"},
            headers=headers,
        )

    # International ECTS enrollment (French/European coursework missing syllabus initially)
    fr_enr = client.post(
        "/api/v1/profile/enrollments",
        json={
            "institution_name_manual": "Université Étrangère",
            "institution_country": "FR",
            "enrollment_type": "undergraduate",
        },
        headers=headers,
    ).json()
    unv_course = client.post(
        f"/api/v1/profile/enrollments/{fr_enr['id']}/courses",
        json={"course_code": "INF-204", "course_name": "Cours Spécialisé", "credit_hours": 6.0, "credit_type": "ects", "status": "completed"},
        headers=headers,
    ).json()

    summary = client.get(
        f"/api/v1/transfer/profile-summary?target_institution_id={ucb['id']}&intended_major=Economics",
        headers=headers,
    ).json()

    # Verify duplicate exclusion, separate applicability accounting, international credit notice, and missing syllabus detection
    assert summary["duplicate_course_count"] == 1
    assert summary["officially_verified_count"] == 4
    assert summary["unverified_course_count"] == 1
    assert summary["missing_syllabus_count"] == 1
    assert "ects" in summary["total_original_credits_by_system"]
    assert "us_quarter" in summary["total_original_credits_by_system"]
    # Total official transferable > major_applicable (because ART 1A & PE 1 don't satisfy Economics major!)
    assert summary["officially_transferable_credits"] > summary["major_applicable_credits"]
    assert summary["elective_only_credits"] == 0.67
    assert "Calculus I" in summary["major_prerequisites_remaining"]
    assert any("Duplicate" in w for w in summary["warnings"])
    assert any("International" in w for w in summary["warnings"])

    # Upload syllabus for INF-204 & attach -> verifies extraction + Tier 3 upgrade + auth boundary
    syl_bytes = (
        b"CS-204 Data Structures and Algorithms Syllabus\n"
        b"- Implement binary search trees, hash tables, heaps, and graph traversal algorithms\n"
        b"- Analyze sorting complexity and Big-O runtime bounds\n"
    )
    doc_res = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": ("cs204_syllabus.txt", io.BytesIO(syl_bytes), "text/plain")},
        data={"document_category": "syllabus"},
    )
    assert doc_res.status_code == 201
    doc_data = doc_res.json()
    assert doc_data["extraction"]["extraction_confidence"] == "needs_review"
    assert len(doc_data["extraction"]["extracted_data_json"]["learning_outcomes"]) >= 2

    # Cross-user attach forbidden / 404
    assert (
        client.post(
            f"/api/v1/transfer/courses/{unv_course['id']}/attach-syllabus",
            headers=other_headers,
            json={"document_id": doc_data["id"]},
        ).status_code
        == 404
    )

    # Owner attaches syllabus -> INF-204 now evaluates via Tier 3 AI Content Matching!
    attach_res = client.post(
        f"/api/v1/transfer/courses/{unv_course['id']}/attach-syllabus",
        headers=headers,
        json={"document_id": doc_data["id"]},
    )
    assert attach_res.status_code == 200
    assert attach_res.json()["requires_human_verification"] is True

    summary_after = client.get(
        f"/api/v1/transfer/profile-summary?target_institution_id={ucb['id']}&intended_major=Economics",
        headers=headers,
    ).json()
    assert summary_after["ai_predicted_count"] >= 1
    assert summary_after["missing_syllabus_count"] == 0

    # Catalog & published agreements endpoints
    cat_res = client.get(f"/api/v1/transfer/catalog?institution_id={ucb['id']}")
    assert cat_res.status_code == 200 and len(cat_res.json()) >= 8
    ag_res = client.get(f"/api/v1/transfer/agreements?target_institution_id={ucb['id']}")
    assert ag_res.status_code == 200 and len(ag_res.json()) >= 1
