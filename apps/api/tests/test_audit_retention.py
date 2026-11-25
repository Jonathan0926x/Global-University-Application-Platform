from datetime import datetime, timedelta, timezone
import uuid

import httpcore
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.database import SessionLocal
from app.models.institution import Institution
from app.models.routing import (
    ApplicationRoute,
    ApplicationRouteAudit,
    ApplicationStatusHistory,
    ApplicationSubmissionEvidence,
    EvidenceReviewAudit,
)


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


def test_database_enforces_append_only_audit_retention_and_safe_parent_deletion(client):
    student_headers = _auth("audit_ret_student")
    verifier_headers = {"Authorization": "Bearer mock_verifier_audit_ret@uniglobe.edu"}
    _ensure_profile(client, student_headers, "first_year")

    # Lookup MIT
    insts = client.get("/api/v1/institutions").json()
    mit = next((i for i in insts if "Massachusetts Institute of Technology" in i["official_name"]), None)
    assert mit is not None

    # Create disposable route + manual review audit
    db = SessionLocal()
    inst_id = uuid.uuid4()
    try:
        db.add(
            Institution(
                id=inst_id,
                official_name=f"Audit Retention Test Univ {inst_id.hex[:6]}",
                ipeds_unit_id=f"95{inst_id.hex[:4]}",
                country_code="US",
                institution_type="university",
                official_website="https://www.auditretentionqa.edu/",
            )
        )
        db.flush()
        route = ApplicationRoute(
            institution_id=inst_id,
            platform_name="Audit Retention Portal",
            platform_type="direct_portal",
            country_code="US",
            applicant_type="first_year",
            official_url="https://apply.auditretentionqa.edu/",
            source_name="Audit Test",
            verification_status="needs_verification",
            confidence_level="medium",
            is_active=True,
        )
        db.add(route)
        db.commit()
        route_id = route.id
    finally:
        db.close()

    rev_res = client.post(
        f"/api/v1/admin/routing/{route_id}/review",
        json={"decision": "verified", "notes": "Verified for append-only retention check."},
        headers=verifier_headers,
    )
    assert rev_res.status_code == 200
    route_audit_id = uuid.UUID(rev_res.json()["audits"][0]["id"])

    # Create application, transition, upload evidence, review -> creates status history + evidence audit
    app_res = client.post(
        "/api/v1/applications",
        json={"institution_id": mit["id"], "applicant_type": "first_year"},
        headers=student_headers,
    )
    assert app_res.status_code == 201
    app_id = uuid.UUID(app_res.json()["id"])

    ev_res = client.post(
        f"/api/v1/applications/{app_id}/evidence",
        data={"evidence_type": "confirmation_email", "external_confirmation_number": "RET-2027-01"},
        files={"file": ("ret_proof.txt", b"MIT Confirmation RET-2027-01", "text/plain")},
        headers=student_headers,
    )
    assert ev_res.status_code == 201
    ev_id = uuid.UUID(ev_res.json()["id"])

    acc_res = client.post(
        f"/api/v1/admin/evidence/{ev_id}/review",
        json={"decision": "accepted", "reviewer_notes": "Confirmed retention test receipt."},
        headers=verifier_headers,
    )
    assert acc_res.status_code == 200
    ev_audit_id = uuid.UUID(acc_res.json()["audit_history"][0]["id"])

    db = SessionLocal()
    try:
        status_hist = (
            db.query(ApplicationStatusHistory)
            .filter(ApplicationStatusHistory.application_id == app_id)
            .first()
        )
        assert status_hist is not None
        status_hist_id = status_hist.id

        # 1. Direct UPDATE and DELETE on all 3 audit tables MUST be blocked by PostgreSQL trigger
        for tbl, col, row_id, val in [
            ("application_route_audits", "notes", route_audit_id, "tampered"),
            ("application_status_history", "reason", status_hist_id, "tampered"),
            ("evidence_review_audits", "notes", ev_audit_id, "tampered"),
        ]:
            with pytest.raises(DBAPIError):
                db.execute(
                    text(f"UPDATE {tbl} SET {col} = :val WHERE id = :rid"),
                    {"val": val, "rid": row_id},
                )
            db.rollback()

            with pytest.raises(DBAPIError):
                db.execute(text(f"DELETE FROM {tbl} WHERE id = :rid"), {"rid": row_id})
            db.rollback()
    finally:
        db.close()

    # 2. Safe parent deletion: deleting ApplicationRoute retains ApplicationRouteAudit with retained_route_id + parent_deleted_at
    db = SessionLocal()
    try:
        r_obj = db.query(ApplicationRoute).filter(ApplicationRoute.id == route_id).first()
        db.delete(r_obj)
        inst_obj = db.query(Institution).filter(Institution.id == inst_id).first()
        db.delete(inst_obj)
        db.commit()

        retained_route_audit = (
            db.query(ApplicationRouteAudit).filter(ApplicationRouteAudit.id == route_audit_id).first()
        )
        assert retained_route_audit is not None
        assert retained_route_audit.route_id is None
        assert retained_route_audit.retained_route_id == route_id
        assert retained_route_audit.parent_deleted_at is not None
        assert retained_route_audit.notes == "Verified for append-only retention check."
    finally:
        db.close()

    # 3. Safe parent deletion via DELETE /applications/{app_id}:
    #    Application + ApplicationSubmissionEvidence deleted, while status_history + evidence_review_audits RETAINED!
    del_app = client.delete(f"/api/v1/applications/{app_id}", headers=student_headers)
    assert del_app.status_code == 200
    assert del_app.json()["deleted"] is True

    db = SessionLocal()
    try:
        ev_gone = (
            db.query(ApplicationSubmissionEvidence)
            .filter(ApplicationSubmissionEvidence.id == ev_id)
            .first()
        )
        assert ev_gone is None

        retained_hist = (
            db.query(ApplicationStatusHistory)
            .filter(ApplicationStatusHistory.id == status_hist_id)
            .first()
        )
        assert retained_hist is not None
        assert retained_hist.application_id is None
        assert retained_hist.retained_application_id == app_id
        assert retained_hist.parent_deleted_at is not None

        retained_ev_audits = (
            db.query(EvidenceReviewAudit)
            .filter(EvidenceReviewAudit.retained_evidence_id == ev_id)
            .order_by(EvidenceReviewAudit.created_at.asc())
            .all()
        )
        assert [a.action for a in retained_ev_audits] == ["uploaded", "accepted"]
        for a in retained_ev_audits:
            assert a.evidence_id is None
            assert a.application_id is None
            assert a.retained_evidence_id == ev_id
            assert a.retained_application_id == app_id
            assert a.parent_deleted_at is not None
    finally:
        db.close()


def test_cross_profile_evidence_isolation_and_controlled_upload_reject_accept_e2e(client):
    student_a = _auth("cross_a")
    student_b = _auth("cross_b")
    verifier = {"Authorization": "Bearer mock_verifier_e2e_qa@uniglobe.edu"}

    _ensure_profile(client, student_a, "first_year")
    _ensure_profile(client, student_b, "first_year")

    insts = client.get("/api/v1/institutions").json()
    mit = next((i for i in insts if "Massachusetts Institute of Technology" in i["official_name"]), None)
    assert mit is not None

    # Student A creates application and uploads confirmation proof
    app_a = client.post(
        "/api/v1/applications",
        json={"institution_id": mit["id"], "applicant_type": "first_year"},
        headers=student_a,
    )
    assert app_a.status_code == 201
    app_id = app_a.json()["id"]

    ev_upload = client.post(
        f"/api/v1/applications/{app_id}/evidence",
        data={
            "evidence_type": "portal_screenshot",
            "external_confirmation_number": "E2E-111",
            "submitted_note": "Initial cropped receipt",
        },
        files={"file": ("e2e_first.txt", b"Cropped submission page E2E-111", "text/plain")},
        headers=student_a,
    )
    assert ev_upload.status_code == 201
    ev1_id = ev_upload.json()["id"]
    doc1_id = ev_upload.json()["document_id"]

    # Cross-profile Student B checks: every Student A application, evidence, and document endpoint MUST deny access
    assert client.get(f"/api/v1/applications/{app_id}", headers=student_b).status_code == 404
    assert client.get(f"/api/v1/applications/{app_id}/evidence", headers=student_b).status_code == 404
    assert (
        client.post(
            f"/api/v1/applications/{app_id}/evidence",
            data={"evidence_type": "portal_screenshot"},
            files={"file": ("hijack.txt", b"bad", "text/plain")},
            headers=student_b,
        ).status_code
        == 404
    )
    assert client.get(f"/api/v1/documents/{doc1_id}", headers=student_b).status_code == 404
    assert client.get(f"/api/v1/documents/{doc1_id}/download", headers=student_b).status_code == 404
    assert (
        client.post(
            f"/api/v1/applications/evidence/{ev1_id}/review",
            json={"decision": "accepted"},
            headers=student_b,
        ).status_code
        == 403
    )
    assert client.get(f"/api/v1/admin/evidence/{ev1_id}/document", headers=student_b).status_code == 403
    assert (
        client.post(
            f"/api/v1/admin/evidence/{ev1_id}/review",
            json={"decision": "accepted"},
            headers=student_b,
        ).status_code
        == 403
    )

    # Controlled E2E Journey Step 1: Data Verifier inspects Vault artifact, rejects with taxonomy + notes
    doc_preview = client.get(f"/api/v1/admin/evidence/{ev1_id}/document", headers=verifier)
    assert doc_preview.status_code == 200
    assert "E2E-111" in (doc_preview.json()["extracted_text"] or "")

    rej = client.post(
        f"/api/v1/admin/evidence/{ev1_id}/review",
        json={
            "decision": "rejected",
            "rejection_reason_code": "illegible_screenshot",
            "reviewer_notes": "Timestamp and university header missing; re-upload full receipt.",
        },
        headers=verifier,
    )
    assert rej.status_code == 200
    assert rej.json()["review_status"] == "rejected"
    assert rej.json()["application_status"] == "student_reported_submitted"

    # Student A sees rejection reason + notes, but verifier email is scrubbed
    app_after_rej = client.get(f"/api/v1/applications/{app_id}", headers=student_a).json()
    assert app_after_rej["status"] == "student_reported_submitted"
    assert app_after_rej["submission_confirmed_at"] is None
    assert all(a["actor_email"] is None for a in app_after_rej["submission_evidence"][0]["audit_history"])

    # Controlled E2E Journey Step 2: Student A re-uploads complete proof -> Verifier accepts -> submission_confirmed
    ev2 = client.post(
        f"/api/v1/applications/{app_id}/evidence",
        data={
            "evidence_type": "confirmation_email",
            "external_confirmation_number": "E2E-111-FULL",
            "submitted_note": "Full official MIT email receipt",
        },
        files={"file": ("e2e_second.txt", b"MIT Official Confirmation E2E-111-FULL 2026-11-25", "text/plain")},
        headers=student_a,
    )
    assert ev2.status_code == 201
    ev2_id = ev2.json()["id"]

    acc = client.post(
        f"/api/v1/admin/evidence/{ev2_id}/review",
        json={"decision": "accepted", "reviewer_notes": "Full confirmation ID and header verified."},
        headers=verifier,
    )
    assert acc.status_code == 200
    assert acc.json()["review_status"] == "accepted"
    assert acc.json()["application_status"] == "submission_confirmed"

    final_app = client.get(f"/api/v1/applications/{app_id}", headers=student_a).json()
    assert final_app["status"] == "submission_confirmed"
    assert final_app["submission_confirmed_at"] is not None

    # Disposable cleanup (retains immutable audits safely)
    assert client.delete(f"/api/v1/applications/{app_id}", headers=student_a).status_code == 200


def test_pinned_dns_backend_prevents_rebinding_and_automated_sweep_expires_stale(monkeypatch):
    from app.services import routing_health

    # 1. Verify connection-time DNS rebinding is blocked even if pre-check passed earlier
    backend = routing_health._PinnedPublicIPBackend("portal.example.edu", ["93.184.216.34"])

    # Simulate DNS rebinding to loopback/link-local between initial check and TCP connect
    monkeypatch.setattr(
        routing_health.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("169.254.169.254", 443))],
    )
    with pytest.raises(httpcore.ConnectError):
        backend.connect_tcp("portal.example.edu", 443)

    # Also block IPv4-mapped IPv6 loopback rebinding
    monkeypatch.setattr(
        routing_health.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("::ffff:127.0.0.1", 443))],
    )
    with pytest.raises(httpcore.ConnectError):
        backend.connect_tcp("portal.example.edu", 443)

    # When connection-time DNS matches valid public IP, connect_tcp passes ONLY pinned IP string to socket connect
    connected_hosts: list[str] = []
    monkeypatch.setattr(
        routing_health.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )
    monkeypatch.setattr(
        httpcore.SyncBackend,
        "connect_tcp",
        lambda self, host, port, **kwargs: (connected_hosts.append(host) or "mock_stream"),
    )
    stream = backend.connect_tcp("portal.example.edu", 443)
    assert stream == "mock_stream"
    assert connected_hosts == ["93.184.216.34"]

    # Unpinned hostnames are rejected immediately
    with pytest.raises(httpcore.ConnectError):
        backend.connect_tcp("evil-other.edu", 443)

    # 2. Verify automated expiry sweep flags expired route without human intervention
    db = SessionLocal()
    inst_id = uuid.uuid4()
    try:
        db.add(
            Institution(
                id=inst_id,
                official_name=f"Auto Sweep Test Univ {inst_id.hex[:6]}",
                ipeds_unit_id=f"94{inst_id.hex[:4]}",
                country_code="US",
                institution_type="university",
                official_website="https://www.autosweepqa.edu/",
            )
        )
        db.flush()
        rt = ApplicationRoute(
            institution_id=inst_id,
            platform_name="Auto Sweep Portal",
            platform_type="direct_portal",
            country_code="US",
            applicant_type="first_year",
            official_url="https://apply.autosweepqa.edu/",
            source_name="Auto Sweep Test",
            verification_status="verified",
            confidence_level="high",
            pathway_verified=True,
            verified_at=datetime.now(timezone.utc) - timedelta(days=200),
            verification_expires_at=datetime.now(timezone.utc) - timedelta(days=2),
            is_active=True,
        )
        db.add(rt)
        db.commit()
        rt_id = rt.id
    finally:
        db.close()

    try:
        res = routing_health.run_automated_expiry_sweep_once(SessionLocal)
        assert res["flagged_for_reverification"] >= 1
        status_info = routing_health.get_automated_sweep_status()
        assert status_info["runs_completed"] >= 1
        assert status_info["last_run_at"] is not None

        db = SessionLocal()
        try:
            refreshed = db.query(ApplicationRoute).filter(ApplicationRoute.id == rt_id).first()
            assert refreshed.verification_status == "needs_verification"
            assert refreshed.audits[0].action == "verification_expired"
            assert refreshed.audits[0].actor_role == "system"
        finally:
            db.close()
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
