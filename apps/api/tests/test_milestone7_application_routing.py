from datetime import datetime, timedelta, timezone
import uuid

from app.database import SessionLocal
from app.ingestion.routing_seed import seed_verified_application_routes, validate_routing_url
from app.models.requirements import Deadline
from app.models.institution import Institution
from app.models.routing import ApplicationRoute


def _auth(prefix: str) -> dict[str, str]:
    uid = uuid.uuid4().hex[:8]
    return {"Authorization": f"Bearer mock_{prefix}_{uid}@uniglobe.edu"}


def _ensure_profile(client, headers: dict[str, str], applicant_type: str = "first_year") -> None:
    res = client.post(
        "/api/v1/profile",
        json={
            "first_name": "Claire",
            "last_name": "Laurent",
            "applicant_type": applicant_type,
            "intended_major": "Computer Science",
            "gpa": "3.9",
            "gpa_scale": "4.0",
            "citizenship_country": "HT",
        },
        headers=headers,
    )
    assert res.status_code in (200, 201)


def test_routing_directory_seeding_idempotent_and_filters(client):
    db = SessionLocal()
    try:
        first_stats = seed_verified_application_routes(db)
        second_stats = seed_verified_application_routes(db)
        assert second_stats == {
            "centralized_created": 0,
            "institution_created": 0,
            "ipeds_needs_verification": 0,
        }
        assert first_stats["centralized_created"] >= 0
    finally:
        db.close()

    # Directory returns verified centralized + institutional portals
    res_verified = client.get("/api/v1/routing/directory?verified_only=true&limit=250")
    assert res_verified.status_code == 200
    rows = res_verified.json()
    assert len(rows) >= 20
    assert all(r["verification_status"] == "verified" for r in rows)

    platform_names = {r["platform_name"] for r in rows}
    assert any("Common App" in p for p in platform_names)
    assert any("UCAS" in p for p in platform_names)
    assert any("UC Application" in p for p in platform_names)
    assert any("Études en France" in p for p in platform_names)

    # Country and pathway filters
    uk_res = client.get("/api/v1/routing/directory?country=GB&verified_only=true")
    assert uk_res.status_code == 200
    uk_rows = uk_res.json()
    assert any("UCAS" in r["platform_name"] and r["international_instructions"] for r in uk_rows)

    transfer_res = client.get("/api/v1/routing/directory?applicant_type=transfer&verified_only=true")
    assert transfer_res.status_code == 200
    assert any("UC Application" in r["platform_name"] or "Common App for Transfer" in r["platform_name"] for r in transfer_res.json())


def test_routing_url_safety_validation_endpoint(client):
    good = client.post("/api/v1/routing/validate-url", json={"url": "https://apply.mit.edu/apply/"})
    assert good.status_code == 200
    assert good.json()["valid"] is True
    assert good.json()["normalized_url"] == "https://apply.mit.edu/apply/"
    assert good.json()["scheme_secure"] is True

    bad_urls = [
        "",
        "apply.mit.edu/apply/",
        "javascript:alert(1)",
        "http://localhost:8000/portal",
        "https://127.0.0.1/admin",
        "https://example.com/bad space",
        "ftp://ftp.university.edu/apply",
    ]
    for raw in bad_urls:
        resp = client.post("/api/v1/routing/validate-url", json={"url": raw})
        assert resp.status_code == 200
        assert resp.json()["valid"] is False, f"Expected invalid URL rejection for {raw}"

    assert validate_routing_url("https://www.commonapp.org/")["valid"] is True


def test_institution_routing_excludes_unverified_and_blocks_blind_redirect(client):
    headers = _auth("unverif")
    _ensure_profile(client, headers, "first_year")

    # Create a synthetic institution with NO verified route and one unsafe/unverified IPEDS-like portal
    db = SessionLocal()
    inst_id = uuid.uuid4()
    try:
        inst = Institution(
            id=inst_id,
            official_name=f"Synthetic Unverified Institute {inst_id.hex[:6]}",
            country_code="US",
            institution_type="university",
            control_type="private_nonprofit",
            application_portal_url="https://apply.synthetic-unverified-example.edu/portal",
        )
        db.add(inst)
        db.flush()
        db.add(
            ApplicationRoute(
                institution_id=inst_id,
                platform_name="Unverified Registry Link",
                platform_type="institution_portal",
                country_code="US",
                applicant_type="all",
                official_url="https://apply.synthetic-unverified-example.edu/portal",
                source_name="Synthetic Registry",
                verification_status="needs_verification",
                confidence_level="low",
                is_active=True,
            )
        )
        db.add(
            ApplicationRoute(
                institution_id=inst_id,
                platform_name="Broken Unverified Link",
                platform_type="institution_portal",
                country_code="US",
                applicant_type="all",
                official_url="https://apply.broken-unverified-example.edu/",
                source_name="Legacy Scrape",
                verification_status="unverified",
                confidence_level="low",
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        res_route = client.get(f"/api/v1/routing/institutions/{inst_id}?applicant_type=first_year")
        assert res_route.status_code == 200
        body = res_route.json()
        assert body["routing_status"] == "needs_verification_only"
        assert body["has_verified_destination"] is False
        assert body["verified_routes"] == []
        assert len(body["needs_verification_routes"]) == 1
        assert len(body["excluded_unverified"]) >= 1

        app_res = client.post(
            "/api/v1/applications",
            json={"institution_id": str(inst_id), "applicant_type": "first_year"},
            headers=headers,
        )
        assert app_res.status_code == 201
        app_id = app_res.json()["id"]

        # Redirect without acknowledge_unverified is blocked
        blocked = client.post(
            f"/api/v1/applications/{app_id}/redirect",
            json={"acknowledge_unverified": False},
            headers=headers,
        )
        assert blocked.status_code == 400

        # Redirect with explicit acknowledge_unverified=True records redirect honestly (never submitted)
        allowed = client.post(
            f"/api/v1/applications/{app_id}/redirect",
            json={"acknowledge_unverified": True},
            headers=headers,
        )
        assert allowed.status_code == 200
        assert allowed.json()["verified_route"] is False
        assert allowed.json()["application"]["status"] == "redirected_to_external_portal"
    finally:
        from app.models.application import Application

        db = SessionLocal()
        try:
            db.query(Application).filter(Application.institution_id == inst_id).delete()
            db.query(ApplicationRoute).filter(ApplicationRoute.institution_id == inst_id).delete()
            db.query(Institution).filter(Institution.id == inst_id).delete()
            db.commit()
        finally:
            db.close()


def test_full_six_state_lifecycle_evidence_vault_and_rbac_guardrails(client):
    student_headers = _auth("student_m7")
    other_headers = _auth("other_m7")
    admin_headers = {"Authorization": "Bearer mock_admin_m7@uniglobe.edu"}

    _ensure_profile(client, student_headers, "both")
    _ensure_profile(client, other_headers, "first_year")

    # Lookup MIT & UC Berkeley seeded institutions
    insts = client.get("/api/v1/institutions").json()
    mit = next((i for i in insts if "Massachusetts Institute of Technology" in i["official_name"]), None)
    assert mit is not None

    # Ensure MIT has an upcoming verified deadline to verify countdown calculation
    db = SessionLocal()
    dl_id = uuid.uuid4()
    future_date = datetime.now(timezone.utc).date() + timedelta(days=10)
    try:
        db.add(
            Deadline(
                id=dl_id,
                institution_id=uuid.UUID(mit["id"]),
                applicant_type="first_year",
                intake_term="Fall 2027 QA",
                deadline_type="regular_decision",
                deadline_date=future_date,
                academic_year="2026-2027",
                source_name="MIT Admissions",
                source_url="https://mitadmissions.org/apply/",
                verification_status="verified",
            )
        )
        db.commit()
    finally:
        db.close()

    try:
        # 1. Start application workspace -> initial state is `not_started`
        create_res = client.post(
            "/api/v1/applications",
            json={
                "institution_id": mit["id"],
                "applicant_type": "first_year",
                "intended_major": "Electrical Engineering & Computer Science",
                "intended_term": "Fall 2027",
            },
            headers=student_headers,
        )
        assert create_res.status_code == 201
        app_data = create_res.json()
        app_id = app_data["id"]
        assert app_data["status"] == "not_started"
        assert len(app_data["verified_routes"]) >= 1
        assert any(dl["intake_term"] == "Fall 2027 QA" and dl["days_remaining"] == 10 and dl["is_urgent"] for dl in app_data["deadlines"])

        # 2. Update a requirement item -> moves cleanly to `preparing`
        first_req_id = app_data["requirements_status"][0]["id"]
        prep_res = client.post(
            f"/api/v1/applications/{app_id}/requirements/{first_req_id}?item_status=completed",
            headers=student_headers,
        )
        assert prep_res.status_code == 200
        assert prep_res.json()["status"] == "preparing"
        assert prep_res.json()["readiness_pct"] > 0

        # 3. Student manually marks `ready_to_apply`, but CANNOT self-confirm `submission_confirmed`
        forbid_self_confirm = client.post(
            f"/api/v1/applications/{app_id}/status",
            json={"status": "submission_confirmed"},
            headers=student_headers,
        )
        assert forbid_self_confirm.status_code == 403

        ready_res = client.post(
            f"/api/v1/applications/{app_id}/status",
            json={"status": "ready_to_apply", "reason": "Checklist finalized before portal launch."},
            headers=student_headers,
        )
        assert ready_res.status_code == 200
        assert ready_res.json()["status"] == "ready_to_apply"

        # 4. Click external official link -> moves strictly to `redirected_to_external_portal`, never submitted
        route_id = app_data["verified_routes"][0]["id"]
        redir_res = client.post(
            f"/api/v1/applications/{app_id}/redirect",
            json={"route_id": route_id},
            headers=student_headers,
        )
        assert redir_res.status_code == 200
        redir_body = redir_res.json()
        assert redir_body["verified_route"] is True
        assert "my.mit.edu" in redir_body["redirect_url"]
        assert redir_body["application"]["status"] == "redirected_to_external_portal"
        assert redir_body["application"]["redirected_at"] is not None
        assert redir_body["application"]["submission_confirmed_at"] is None

        # 5. Student self-reports external submission -> moves strictly to `student_reported_submitted`
        rep_res = client.post(
            f"/api/v1/applications/{app_id}/report-submission",
            json={
                "external_confirmation_number": "MIT-2027-99412",
                "submitted_via": "MyMIT Portal",
                "note": "Submitted essay and payment receipt on MyMIT.",
            },
            headers=student_headers,
        )
        assert rep_res.status_code == 200
        rep_body = rep_res.json()
        assert rep_body["status"] == "student_reported_submitted"
        assert rep_body["external_confirmation_number"] == "MIT-2027-99412"
        assert rep_body["submission_confirmed_at"] is None

        # 6. Upload private confirmation proof to Document Vault
        ev_res = client.post(
            f"/api/v1/applications/{app_id}/evidence",
            data={
                "evidence_type": "confirmation_email",
                "external_confirmation_number": "MIT-2027-99412",
                "submitted_note": "Official confirmation email receipt",
            },
            files={
                "file": (
                    "mit_confirmation.txt",
                    b"Thank you for submitting your MIT First-Year Application. Confirmation ID: MIT-2027-99412",
                    "text/plain",
                )
            },
            headers=student_headers,
        )
        assert ev_res.status_code == 201
        ev_body = ev_res.json()
        ev_id = ev_body["id"]
        doc_id = ev_body["document_id"]
        assert ev_body["review_status"] == "pending"
        assert ev_body["original_filename"] == "mit_confirmation.txt"
        assert doc_id is not None

        # Cross-user isolation checks on applications AND vault documents
        assert client.get(f"/api/v1/applications/{app_id}", headers=other_headers).status_code == 404
        assert client.post(f"/api/v1/applications/{app_id}/redirect", json={}, headers=other_headers).status_code == 404
        assert client.delete(f"/api/v1/applications/{app_id}", headers=other_headers).status_code == 404
        assert client.get(f"/api/v1/documents/{doc_id}", headers=other_headers).status_code == 404
        assert client.get(f"/api/v1/documents/{doc_id}", headers=student_headers).status_code == 200

        # 7. RBAC: student CANNOT approve confirmation evidence
        forbid_review = client.post(
            f"/api/v1/applications/evidence/{ev_id}/review",
            json={"decision": "accepted"},
            headers=student_headers,
        )
        assert forbid_review.status_code == 403

        # 8. Verifier/admin rejection leaves status at `student_reported_submitted`
        rej_res = client.post(
            f"/api/v1/applications/evidence/{ev_id}/review",
            json={"decision": "rejected", "reviewer_notes": "Image cropped; include full timestamp."},
            headers=admin_headers,
        )
        assert rej_res.status_code == 200
        assert rej_res.json()["review_status"] == "rejected"
        after_rej = client.get(f"/api/v1/applications/{app_id}", headers=student_headers).json()
        assert after_rej["status"] == "student_reported_submitted"
        assert after_rej["submission_confirmed_at"] is None

        # 9. Student uploads clear confirmation & verifier accepts -> `submission_confirmed`
        ev2_res = client.post(
            f"/api/v1/applications/{app_id}/evidence",
            data={"evidence_type": "portal_screenshot", "external_confirmation_number": "MIT-2027-99412"},
            files={"file": ("mit_receipt_full.txt", b"MIT Confirmation MIT-2027-99412 Timestamp Verified", "text/plain")},
            headers=student_headers,
        )
        assert ev2_res.status_code == 201
        ev2_id = ev2_res.json()["id"]

        acc_res = client.post(
            f"/api/v1/applications/evidence/{ev2_id}/review",
            json={"decision": "accepted", "reviewer_notes": "Verified against confirmation ID and institutional email domain."},
            headers=admin_headers,
        )
        assert acc_res.status_code == 200
        assert acc_res.json()["review_status"] == "accepted"

        final_app = client.get(f"/api/v1/applications/{app_id}", headers=student_headers).json()
        assert final_app["status"] == "submission_confirmed"
        assert final_app["submission_confirmed_at"] is not None

        # Verify immutable audit trail order contains all lifecycle transitions
        history_states = [h["to_status"] for h in final_app["status_history"]]
        for expected_state in [
            "not_started",
            "preparing",
            "ready_to_apply",
            "redirected_to_external_portal",
            "student_reported_submitted",
            "submission_confirmed",
        ]:
            assert expected_state in history_states
    finally:
        db = SessionLocal()
        try:
            db.query(Deadline).filter(Deadline.id == dl_id).delete()
            db.commit()
        finally:
            db.close()
