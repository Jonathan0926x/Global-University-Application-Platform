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

        # 8. Verifier/admin rejection requires valid rejection_reason_code and leaves status at `student_reported_submitted`
        missing_code = client.post(
            f"/api/v1/applications/evidence/{ev_id}/review",
            json={"decision": "rejected", "reviewer_notes": "Missing reason code check"},
            headers=admin_headers,
        )
        assert missing_code.status_code == 400

        rej_res = client.post(
            f"/api/v1/applications/evidence/{ev_id}/review",
            json={
                "decision": "rejected",
                "rejection_reason_code": "illegible_screenshot",
                "reviewer_notes": "Image cropped; include full timestamp.",
            },
            headers=admin_headers,
        )
        assert rej_res.status_code == 200
        assert rej_res.json()["review_status"] == "rejected"
        assert rej_res.json()["rejection_reason_code"] == "illegible_screenshot"
        assert "Illegible Screenshot" in (rej_res.json()["rejection_reason_label"] or "")
        assert len(rej_res.json()["audit_history"]) >= 2

        after_rej = client.get(f"/api/v1/applications/{app_id}", headers=student_headers).json()
        assert after_rej["status"] == "student_reported_submitted"
        assert after_rej["submission_confirmed_at"] is None
        # Student view scrubs reviewer email for privacy while preserving audit role + rejection reason
        ev_student_view = next(e for e in after_rej["submission_evidence"] if e["id"] == ev_id)
        assert ev_student_view["rejection_reason_code"] == "illegible_screenshot"
        assert all(a["actor_email"] is None for a in ev_student_view["audit_history"])

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


def test_data_verifier_rbac_evidence_queue_and_audit_trail(client):
    student_headers = _auth("student_ev_ops")
    verifier_headers = {"Authorization": "Bearer mock_verifier_ops_qa@uniglobe.edu"}
    _ensure_profile(client, student_headers, "first_year")

    # Student cannot access verification operations queues (403)
    assert client.get("/api/v1/admin/verification/taxonomies", headers=student_headers).status_code == 403
    assert client.get("/api/v1/admin/evidence/queue", headers=student_headers).status_code == 403
    assert client.get("/api/v1/admin/routing/queue", headers=student_headers).status_code == 403

    # Data Verifier CAN read taxonomies & inspect uploaded vault artifacts
    tax_res = client.get("/api/v1/admin/verification/taxonomies", headers=verifier_headers)
    assert tax_res.status_code == 200
    assert any(r["code"] == "missing_confirmation_id" for r in tax_res.json()["evidence_rejection_reasons"])

    insts = client.get("/api/v1/institutions").json()
    mit = next((i for i in insts if "Massachusetts Institute of Technology" in i["official_name"]), None)
    assert mit is not None

    app_id = client.post(
        "/api/v1/applications",
        json={"institution_id": mit["id"], "applicant_type": "first_year"},
        headers=student_headers,
    ).json()["id"]

    ev_res = client.post(
        f"/api/v1/applications/{app_id}/evidence",
        data={"evidence_type": "confirmation_email", "external_confirmation_number": "MIT-OP-552"},
        files={"file": ("ops_proof.txt", b"MIT Ops Proof Confirmation ID MIT-OP-552", "text/plain")},
        headers=student_headers,
    )
    assert ev_res.status_code == 201
    ev_id = ev_res.json()["id"]

    # Queue lists pending item with document SHA-256 + uploaded audit event
    q_res = client.get("/api/v1/admin/evidence/queue?review_status=pending", headers=verifier_headers)
    assert q_res.status_code == 200
    q_item = next((x for x in q_res.json() if x["id"] == ev_id), None)
    assert q_item is not None
    assert q_item["document_sha256"]
    assert q_item["audit_history"][0]["action"] == "uploaded"

    # Student blocked from verifier document inspection endpoint; verifier can inspect extracted text & SHA-256
    assert client.get(f"/api/v1/admin/evidence/{ev_id}/document", headers=student_headers).status_code == 403
    doc_meta = client.get(f"/api/v1/admin/evidence/{ev_id}/document", headers=verifier_headers)
    assert doc_meta.status_code == 200
    assert doc_meta.json()["reviewed_by_role"] == "data_verifier"
    assert doc_meta.json()["file_sha256"] == q_item["document_sha256"]

    # Data verifier accepts evidence -> immutable audit logs actor_role == data_verifier & promotes app
    acc = client.post(
        f"/api/v1/admin/evidence/{ev_id}/review",
        json={"decision": "accepted", "reviewer_notes": "Verified SHA-256 confirmation artifact."},
        headers=verifier_headers,
    )
    assert acc.status_code == 200
    acc_body = acc.json()
    assert acc_body["review_status"] == "accepted"
    assert acc_body["application_status"] == "submission_confirmed"
    assert [a["action"] for a in acc_body["audit_history"]] == ["uploaded", "accepted"]
    assert acc_body["audit_history"][1]["actor_role"] == "data_verifier"
    assert acc_body["audit_history"][1]["actor_email"] == "ops_qa@uniglobe.edu"


def test_routing_data_quality_batch_and_manual_verifier_audit(client):
    verifier_headers = {"Authorization": "Bearer mock_verifier_route_qa@uniglobe.edu"}
    student_headers = _auth("student_route_qa")

    summary_res = client.get("/api/v1/admin/routing/summary", headers=verifier_headers)
    assert summary_res.status_code == 200
    assert summary_res.json()["verified"] >= 400
    assert summary_res.json()["needs_verification"] <= 20

    # Seed one domain-matched IPEDS candidate and one CRM subdomain candidate cleanly
    db = SessionLocal()
    inst_dom_id = uuid.uuid4()
    inst_crm_id = uuid.uuid4()
    try:
        db.add_all(
            [
                Institution(
                    id=inst_dom_id,
                    official_name=f"Synthetic Verified Domain Univ {inst_dom_id.hex[:6]}",
                    ipeds_unit_id=f"99{inst_dom_id.hex[:4]}",
                    country_code="US",
                    institution_type="university",
                    official_website="https://www.verifieddomainqa.edu/",
                ),
                Institution(
                    id=inst_crm_id,
                    official_name=f"Synthetic CRM Tenant College {inst_crm_id.hex[:6]}",
                    ipeds_unit_id=f"98{inst_crm_id.hex[:4]}",
                    country_code="US",
                    institution_type="university",
                    official_website="https://www.crmtenantqa.edu/",
                ),
            ]
        )
        db.flush()
        rt_dom = ApplicationRoute(
            institution_id=inst_dom_id,
            platform_name="Verified Domain QA Portal",
            platform_type="direct_portal",
            country_code="US",
            applicant_type="all",
            official_url="https://apply.verifieddomainqa.edu/undergrad",
            source_name="NCES IPEDS HD2023",
            verification_status="needs_verification",
            confidence_level="medium",
            is_active=True,
        )
        rt_crm = ApplicationRoute(
            institution_id=inst_crm_id,
            platform_name="CRM Tenant QA Portal",
            platform_type="direct_portal",
            country_code="US",
            applicant_type="all",
            official_url="https://crmtenantqa.elluciancrmrecruit.com/Apply/Login",
            source_name="NCES IPEDS HD2023",
            verification_status="needs_verification",
            confidence_level="medium",
            is_active=True,
        )
        db.add_all([rt_dom, rt_crm])
        db.commit()
        dom_route_id = str(rt_dom.id)
        crm_route_id = str(rt_crm.id)
    finally:
        db.close()

    try:
        # Student forbidden from batch verify or route review
        assert client.post("/api/v1/admin/routing/verify-batch", headers=student_headers).status_code == 403
        assert client.post(
            f"/api/v1/admin/routing/{crm_route_id}/review",
            json={"decision": "verified"},
            headers=student_headers,
        ).status_code == 403

        # Batch verification promotes domain match -> `verified`, keeps CRM subdomain in `needs_verification`
        batch = client.post("/api/v1/admin/routing/verify-batch", headers=verifier_headers)
        assert batch.status_code == 200
        assert batch.json()["promoted_to_verified"] >= 1

        # Rejecting CRM link without rejection_reason_code -> 400
        bad_rej = client.post(
            f"/api/v1/admin/routing/{crm_route_id}/review",
            json={"decision": "unverified", "notes": "Missing code"},
            headers=verifier_headers,
        )
        assert bad_rej.status_code == 400

        # Manually verifying CRM link with corrected HTTPS domain or verified tenant decision logs audit trail
        ok_ver = client.post(
            f"/api/v1/admin/routing/{crm_route_id}/review",
            json={
                "decision": "verified",
                "notes": "Confirmed Ellucian CRM tenant matches crmtenantqa.edu.",
                "international_instructions": "International applicants select Global Applicant portal track.",
            },
            headers=verifier_headers,
        )
        assert ok_ver.status_code == 200
        assert ok_ver.json()["verification_status"] == "verified"
        assert ok_ver.json()["verification_method"] == "manual_verifier"
        assert ok_ver.json()["audits"][0]["actor_role"] == "data_verifier"

        # Verify domain route was promoted by batch run with audit entry
        q_dom = client.get(
            "/api/v1/admin/routing/queue?verification_status=verified&q=Verified%20Domain%20QA",
            headers=verifier_headers,
        )
        assert q_dom.status_code == 200
        matched = next((x for x in q_dom.json() if x["id"] == dom_route_id), None)
        assert matched is not None
        assert matched["verification_method"] == "ipeds_domain_match"
        assert matched["audits"][0]["action"] == "auto_verified"
    finally:
        db = SessionLocal()
        try:
            db.query(ApplicationRoute).filter(ApplicationRoute.institution_id.in_([inst_dom_id, inst_crm_id])).delete(
                synchronize_session=False
            )
            db.query(Institution).filter(Institution.id.in_([inst_dom_id, inst_crm_id])).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()


def test_route_health_expiration_pathway_redirect_and_reverification_triggers(client):
    from app.services.routing_health import (
        flag_routes_for_institution_website_change,
        perform_route_health_check,
        run_batch_health_checks,
    )

    verifier_headers = {"Authorization": "Bearer mock_verifier_health_qa@uniglobe.edu"}
    student_headers = _auth("student_health_qa")

    db = SessionLocal()
    inst_id = uuid.uuid4()
    try:
        db.add(
            Institution(
                id=inst_id,
                official_name=f"Synthetic Health Governance Univ {inst_id.hex[:6]}",
                ipeds_unit_id=f"97{inst_id.hex[:4]}",
                country_code="US",
                institution_type="university",
                official_website="https://www.healthgovqa.edu/",
            )
        )
        db.flush()
        rt_verified = ApplicationRoute(
            institution_id=inst_id,
            platform_name="Health Gov QA Portal",
            platform_type="direct_portal",
            country_code="US",
            applicant_type="all",
            official_url="https://apply.healthgovqa.edu/portal",
            source_name="NCES IPEDS HD2023",
            verification_status="verified",
            verification_method="ipeds_domain_match",
            confidence_level="high",
            verified_at=datetime.now(timezone.utc) - timedelta(days=200),
            verification_expires_at=datetime.now(timezone.utc) - timedelta(days=5),
            is_active=True,
        )
        rt_manual = ApplicationRoute(
            institution_id=inst_id,
            platform_name="Manual CRM QA Portal",
            platform_type="direct_portal",
            country_code="US",
            applicant_type="all",
            official_url="https://healthgovqa.elluciancrmrecruit.com/Apply",
            source_name="NCES IPEDS HD2023",
            verification_status="needs_verification",
            confidence_level="medium",
            is_active=True,
        )
        db.add_all([rt_verified, rt_manual])
        db.commit()
        verified_id = str(rt_verified.id)
        manual_id = str(rt_manual.id)
    finally:
        db.close()

    try:
        # 1. RBAC blocks students from health/expire/pathway endpoints
        assert client.post("/api/v1/admin/routing/expire-stale", headers=student_headers).status_code == 403
        assert client.post("/api/v1/admin/routing/health-check", headers=student_headers).status_code == 403
        assert client.post(f"/api/v1/admin/routing/{verified_id}/health-check", headers=student_headers).status_code == 403
        assert (
            client.post(
                f"/api/v1/admin/routing/{verified_id}/pathway",
                json={"pathway_verified": True, "applicant_type": "first_year"},
                headers=student_headers,
            ).status_code
            == 403
        )

        # 2. Pathway verification endpoint updates pathway_verified + applicant_type with audit log
        pw_res = client.post(
            f"/api/v1/admin/routing/{verified_id}/pathway",
            json={
                "pathway_verified": True,
                "applicant_type": "first_year",
                "notes": "Confirmed portal only accepts first-year applicants.",
            },
            headers=verifier_headers,
        )
        assert pw_res.status_code == 200
        pw_body = pw_res.json()
        assert pw_body["pathway_verified"] is True
        assert pw_body["applicant_type"] == "first_year"
        assert pw_body["audits"][0]["action"] == "pathway_verification_updated"

        # 3. Link-health check records HTTP status, redirect destination, and cross-domain warnings (mock probe)
        db = SessionLocal()
        try:
            rt_v = db.query(ApplicationRoute).filter(ApplicationRoute.id == uuid.UUID(verified_id)).first()
            hc_out = perform_route_health_check(
                db,
                rt_v,
                actor_role="data_verifier",
                probe_fn=lambda _u: {
                    "ok": True,
                    "http_code": 200,
                    "final_url": "https://apply.commonapp.org/healthgovqa",
                    "redirect_chain_length": 2,
                    "error": None,
                },
            )
            assert hc_out["status"] == "redirected"
            assert hc_out["http_code"] == 200
            assert hc_out["cross_domain_redirect"] is True
            assert rt_v.final_redirect_url == "https://apply.commonapp.org/healthgovqa"
            assert rt_v.redirect_chain_length == 2

            # Also verify 404 flags unreachable
            rt_m = db.query(ApplicationRoute).filter(ApplicationRoute.id == uuid.UUID(manual_id)).first()
            hc_m = perform_route_health_check(
                db,
                rt_m,
                actor_role="data_verifier",
                probe_fn=lambda _u: {
                    "ok": True,
                    "http_code": 404,
                    "final_url": _u,
                    "redirect_chain_length": 0,
                    "error": None,
                },
            )
            assert hc_m["status"] == "unreachable"
            assert rt_m.last_health_check_http_code == 404

            # Also exercise batch runner with mock probe
            batch_hc = run_batch_health_checks(
                db,
                limit=2,
                only_stale=False,
                probe_fn=lambda _u: {
                    "ok": True,
                    "http_code": 200,
                    "final_url": _u,
                    "redirect_chain_length": 0,
                    "error": None,
                },
            )
            assert batch_hc["checked"] == 2
        finally:
            db.close()

        # 4. Expired queue & expire-stale workflow flags expired verified route back to needs_verification
        exp_q = client.get("/api/v1/admin/routing/queue?verification_status=expired", headers=verifier_headers)
        assert exp_q.status_code == 200
        assert any(x["id"] == verified_id for x in exp_q.json())

        exp_res = client.post("/api/v1/admin/routing/expire-stale", headers=verifier_headers)
        assert exp_res.status_code == 200
        assert exp_res.json()["flagged_for_reverification"] >= 1

        # Promote verified route again via manual verifier (sets fresh 180-day expiration),
        # then simulate institutional website change -> automatically reverts to needs_verification
        re_ver = client.post(
            f"/api/v1/admin/routing/{verified_id}/review",
            json={"decision": "verified", "notes": "Reverified active portal URL."},
            headers=verifier_headers,
        )
        assert re_ver.status_code == 200
        assert re_ver.json()["verification_expires_at"] is not None
        assert re_ver.json()["verification_method"] == "manual_verifier"

        # 5. Manual review queue surfaces both pending needs_verification AND manually reviewed routes
        mq = client.get("/api/v1/admin/routing/queue?verification_status=manual_review&limit=500", headers=verifier_headers)
        assert mq.status_code == 200
        mq_ids = {x["id"] for x in mq.json()}
        assert verified_id in mq_ids  # manually verified stays visible!
        assert manual_id in mq_ids  # needs_verification stays visible!

        # 6. Institutional website change trigger flags verified route back to needs_verification
        db = SessionLocal()
        try:
            trig = flag_routes_for_institution_website_change(
                db=db,
                institution_id=inst_id,
                old_website="https://www.healthgovqa.edu/",
                new_website="https://www.newhealthgovqa.edu/",
                field_name="official_website",
            )
            assert trig["flagged"] == 1
            rt_after = db.query(ApplicationRoute).filter(ApplicationRoute.id == uuid.UUID(verified_id)).first()
            assert rt_after.verification_status == "needs_verification"
            assert rt_after.audits[0].action == "institution_website_changed"
        finally:
            db.close()

        # Verify summary health counters are populated cleanly
        sum_res = client.get("/api/v1/admin/routing/summary", headers=verifier_headers)
        assert sum_res.status_code == 200
        assert "health" in sum_res.json()
        assert sum_res.json()["health"]["pathway_verified"] >= 1
    finally:
        db = SessionLocal()
        try:
            db.query(ApplicationRoute).filter(ApplicationRoute.institution_id == inst_id).delete(
                synchronize_session=False
            )
            db.query(Institution).filter(Institution.id == inst_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
