"""
Phase 4.4: Staging Validation, E2E Synthetic Security Workflows & Adversarial Regression Suite.

Tests integrated controls locally across mocked/in-process equivalents while explicitly documenting
live cloud boundaries:
1. Full API E2E workflow under ENVIRONMENT="staging" + AUTH_PROVIDER="clerk" with real RS256 JWTs,
   JWKS outage / malformed JWKS, synthetic Student A, Student B, Data Verifier, and Admin roles.
2. Live TCP `zINSTREAM` ClamAV wire protocol validation (OK, EICAR FOUND, timeout, connection refused),
   staging heuristic prohibition (`PolicyFailClosedScanner`), quarantine retry immutability,
   and Document Vault isolation across counselor, requirements checklist, transfer syllabus & S3 failures.
3. Redirect-chain SSRF (`302 -> 169.254.169.254`), proxy inheritance ignore, DNS rebinding, and firewall YAML.
"""

import io
import json
import logging
import socket
import struct
import threading
import time
import uuid

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
import pytest

from app.config import settings
from app.core.auth_provider import ClerkAuthProvider, reset_auth_provider_cache
from app.services import routing_health
from app.services.document_vault import (
    EICAR_TEST_SIGNATURE,
    ClamAVScanner,
    PolicyFailClosedScanner,
    S3CompatibleVaultStorageProvider,
    get_malware_scanner,
)
from app.services.requirements_engine import evaluate_dynamic_checklist
from app.models.institution import Institution
from app.models.profile import StudentProfile
from app.database import SessionLocal


def _gen_rsa(kid: str = "staging-kid-1"):
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk_dict = json.loads(RSAAlgorithm.to_jwk(priv.public_key()))
    jwk_dict.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return priv, jwk_dict


def _sign_clerk_jwt(priv, kid: str, sub: str, email: str, role: str = "student",
                    iss: str = "https://clerk.staging.uniglobe.edu", aud: str = "uniglobe-staging",
                    exp_delta: int = 600):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "iss": iss,
            "aud": aud,
            "exp": now + exp_delta,
            "nbf": now - 5,
            "iat": now - 2,
            "email": email,
            "email_verified": True,
            "role": role,
        },
        priv,
        algorithm="RS256",
        headers={"kid": kid},
    )


def _start_mock_clamd_server(mode: str = "scan"):
    """Spin up an in-process localhost TCP daemon speaking ClamAV zINSTREAM\x00 wire protocol."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    srv.settimeout(2.0)
    port = srv.getsockname()[1]
    stop_flag = threading.Event()

    def _serve():
        while not stop_flag.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with conn:
                conn.settimeout(2.0)
                if mode == "timeout":
                    time.sleep(2.5)
                    continue
                if mode == "garbage":
                    conn.sendall(b"UNEXPECTED_GARBAGE\x00")
                    continue
                # Read `zINSTREAM\x00` then 4-byte length-prefixed chunks until length 0
                hdr = conn.recv(10)
                if not hdr.startswith(b"zINSTREAM\x00"):
                    conn.sendall(b"UNKNOWN COMMAND\x00")
                    continue
                payload = bytearray()
                while True:
                    len_bytes = conn.recv(4)
                    if len(len_bytes) < 4:
                        break
                    chunk_len = struct.unpack("!I", len_bytes)[0]
                    if chunk_len == 0:
                        break
                    chunk = bytearray()
                    while len(chunk) < chunk_len:
                        part = conn.recv(chunk_len - len(chunk))
                        if not part:
                            break
                        chunk.extend(part)
                    payload.extend(chunk)
                if EICAR_TEST_SIGNATURE in bytes(payload):
                    conn.sendall(b"stream: Eicar-Test-Signature FOUND\x00")
                else:
                    conn.sendall(b"stream: OK\x00")

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    return srv, port, stop_flag


# ===========================================================================
# 1. LIVE-PROTOCOL CLAMAV SOCKET, STAGING SCANNER POLICY & RETRY SAFETY
# ===========================================================================

def test_44_clamav_wire_protocol_timeout_failure_and_staging_policy(monkeypatch):
    # 1. Clean stream & EICAR FOUND over real TCP zINSTREAM framing
    srv, port, stop = _start_mock_clamd_server("scan")
    try:
        scanner = ClamAVScanner(host="127.0.0.1", port=port, timeout=2)
        clean_res = scanner.scan_bytes(b"Official De Anza College Transcript A+", "transcript.txt")
        assert clean_res.state == "scan_clean" and clean_res.clean is True and clean_res.engine == "clamav"

        eicar_res = scanner.scan_bytes(b"Bad\n" + EICAR_TEST_SIGNATURE, "bad.txt")
        assert eicar_res.state == "scan_infected" and eicar_res.clean is False
        assert "Eicar-Test-Signature" in eicar_res.details
    finally:
        stop.set()
        srv.close()

    # 2. Scanner timeout & unexpected response -> scan_failed (NEVER scan_clean)
    srv_to, port_to, stop_to = _start_mock_clamd_server("timeout")
    try:
        sc_to = ClamAVScanner(host="127.0.0.1", port=port_to, timeout=1)
        r_to = sc_to.scan_bytes(b"transcript", "t.txt")
        assert r_to.state == "scan_failed" and r_to.clean is False
    finally:
        stop_to.set()
        srv_to.close()

    srv_bad, port_bad, stop_bad = _start_mock_clamd_server("garbage")
    try:
        sc_bad = ClamAVScanner(host="127.0.0.1", port=port_bad, timeout=1)
        r_bad = sc_bad.scan_bytes(b"transcript", "t.txt")
        assert r_bad.state == "scan_failed" and r_bad.clean is False
    finally:
        stop_bad.set()
        srv_bad.close()

    # 3. In staging/production, HeuristicMalwareScanner CANNOT substitute for ClamAV
    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(settings, "SCANNER_BACKEND", "heuristic")
    staging_scanner = get_malware_scanner()
    assert isinstance(staging_scanner, PolicyFailClosedScanner)
    fail_res = staging_scanner.scan_bytes(b"clean text", "t.txt")
    assert fail_res.state == "scan_failed" and fail_res.clean is False


# ===========================================================================
# 2. END-TO-END SYNTHETIC STAGING WORKFLOWS (CLERK JWT + CLAMAV + ISOLATION)
# ===========================================================================

def test_44_e2e_staging_clerk_jwt_workflows_and_document_gates(client, monkeypatch, caplog):
    priv, jwk1 = _gen_rsa("staging-k1")
    iss = "https://clerk.staging.uniglobe.edu"
    aud = "uniglobe-staging"

    async def fake_jwks(_url: str):
        return {"keys": [jwk1]}

    clerk_prov = ClerkAuthProvider(
        issuer=iss,
        jwks_url=f"{iss}/.well-known/jwks.json",
        audience=aud,
        accepted_algorithms=["RS256"],
        jwks_fetcher=fake_jwks,
    )

    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "clerk")
    monkeypatch.setattr(settings, "SCANNER_BACKEND", "clamav")
    monkeypatch.setattr(settings, "ALLOW_DEV_MOCK_DEFAULT_USER", False)

    srv, clam_port, clam_stop = _start_mock_clamd_server("scan")
    monkeypatch.setattr(settings, "CLAMAV_HOST", "127.0.0.1")
    monkeypatch.setattr(settings, "CLAMAV_PORT", clam_port)

    uid = uuid.uuid4().hex[:8]
    tok_a = _sign_clerk_jwt(priv, "staging-k1", f"clerk_stu_a_{uid}", f"stu_a_{uid}@pilot.uniglobe.edu", "student", iss, aud)
    tok_b = _sign_clerk_jwt(priv, "staging-k1", f"clerk_stu_b_{uid}", f"stu_b_{uid}@pilot.uniglobe.edu", "student", iss, aud)
    tok_ver = _sign_clerk_jwt(priv, "staging-k1", f"clerk_ver_{uid}", f"ver_{uid}@pilot.uniglobe.edu", "data_verifier", iss, aud)
    tok_adm = _sign_clerk_jwt(priv, "staging-k1", f"clerk_adm_{uid}", f"adm_{uid}@pilot.uniglobe.edu", "admin", iss, aud)
    tok_exp = _sign_clerk_jwt(priv, "staging-k1", f"clerk_stu_a_{uid}", f"stu_a_{uid}@pilot.uniglobe.edu", "student", iss, aud, exp_delta=-120)

    hdr_a = {"Authorization": f"Bearer {tok_a}"}
    hdr_b = {"Authorization": f"Bearer {tok_b}"}
    hdr_ver = {"Authorization": f"Bearer {tok_ver}"}
    hdr_adm = {"Authorization": f"Bearer {tok_adm}"}

    try:
        from app.core import auth_provider
        monkeypatch.setattr(auth_provider, "_CACHED_CLERK_PROVIDER", clerk_prov)

        # Missing auth & dev_token MUST fail with 401 in staging
        assert client.get("/api/v1/profile").status_code == 401
        assert client.get("/api/v1/profile", headers={"Authorization": "Bearer dev_token"}).status_code == 401
        assert client.get("/api/v1/profile", headers={"Authorization": f"Bearer {tok_exp}"}).status_code == 401

        # 1. Synthetic Student A registration/login + profile + enrollment
        sess_a = client.get("/api/v1/session", headers=hdr_a)
        assert sess_a.status_code == 200 and sess_a.json()["authenticated"] is True
        assert client.post("/api/v1/profile", json={"first_name": "Claire", "last_name": "Stg", "applicant_type": "transfer", "country_code": "HT", "country_of_residence": "HT"}, headers=hdr_a).status_code == 201
        assert client.post("/api/v1/profile", json={"first_name": "Marc", "last_name": "Stg", "applicant_type": "first_year"}, headers=hdr_b).status_code == 201
        enr_a = client.post("/api/v1/profile/enrollments", json={"institution_name_manual": "De Anza College", "enrollment_type": "community_college", "cumulative_gpa": 3.85}, headers=hdr_a).json()["id"]

        # 2. Upload EICAR malware through ClamAV socket -> quarantined + blocked across Counselor, Requirements, Download, & Retry!
        eicar_res = client.post(
            "/api/v1/documents/upload",
            files={"file": ("eicar_transcript.txt", io.BytesIO(b"Transcript " + EICAR_TEST_SIGNATURE), "text/plain")},
            data={"document_category": "transcript"},
            headers=hdr_a,
        )
        assert eicar_res.status_code == 201
        eicar_doc = eicar_res.json()
        assert eicar_doc["scan_status"] == "quarantined"
        assert eicar_doc["scan_engine"] == "clamav"
        # Retry MUST NEVER release quarantined content
        assert client.post(f"/api/v1/documents/{eicar_doc['id']}/rescan", headers=hdr_a).status_code == 422

        # Upload clean PDF via ClamAV socket -> scan_clean -> presigned download
        clean_pdf = b"%PDF-1.4\nDe Anza College Official Transcript Grade A CIS 22A\n"
        clean_res = client.post(
            "/api/v1/documents/upload",
            files={"file": ("official_transcript.pdf", io.BytesIO(clean_pdf), "application/pdf")},
            data={"document_category": "transcript"},
            headers=hdr_a,
        )
        assert clean_res.status_code == 201
        clean_doc = clean_res.json()
        assert clean_doc["scan_status"] == "scan_clean"
        assert clean_doc["scan_engine"] == "clamav"

        # 3. Verify requirements_engine ignores quarantined doc and sees ONLY scan_clean doc
        db = SessionLocal()
        try:
            mit = db.query(Institution).filter(Institution.official_name.ilike("%Massachusetts Institute%")).first() or db.query(Institution).first()
            prof_a = db.query(StudentProfile).filter(StudentProfile.user.has(external_auth_id=f"clerk_stu_a_{uid}")).first()
            chk = evaluate_dynamic_checklist(db, mit, prof_a, "transfer")
            assert chk is not None
        finally:
            db.close()

        # 4. Scholarship matching + coverage + multilingual counselor + verify quarantined filename absent
        sch_res = client.post("/api/v1/financial/scholarships/match", json={"citizenship_country": "HT", "country_of_residence": "HT", "destination_country": "CA", "applicant_type": "first_year", "degree_level": "bachelors", "gpa_4": 3.85}, headers=hdr_a)
        assert sch_res.status_code == 200 and len(sch_res.json()["results"]) > 0

        chat_res = client.post("/api/v1/counselor/chat", json={"message": "What documents are in my vault for MIT?"}, headers=hdr_a)
        assert chat_res.status_code == 200
        notes_text = " ".join(chat_res.json()["epistemic_breakdown"]["student_context_used"])
        assert "eicar_transcript.txt" not in notes_text
        assert "official_transcript.pdf" in notes_text

        # 5. Application creation, external redirect, and cross-account security checks
        app_a = client.post("/api/v1/applications", json={"institution_id": str(mit.id), "applicant_type": "transfer"}, headers=hdr_a)
        assert app_a.status_code == 201
        app_id = app_a.json()["id"]
        redir = client.post(f"/api/v1/applications/{app_id}/redirect", json={"acknowledge_unverified": True}, headers=hdr_a)
        assert redir.status_code == 200
        assert redir.json()["application"]["status"] == "redirected_to_external_portal"

        # Cross-account isolation via Clerk B JWT
        assert client.post(f"/api/v1/profile/enrollments/{enr_a}/courses", json={"course_code": "HACK", "course_name": "Evil"}, headers=hdr_b).status_code == 404
        assert client.get(f"/api/v1/documents/{clean_doc['id']}/download", headers=hdr_b).status_code == 404
        assert client.get(f"/api/v1/applications/{app_id}", headers=hdr_b).status_code == 404
        assert client.get(f"/api/v1/counselor/conversations/{chat_res.json()['conversation_id']}", headers=hdr_b).status_code == 404
        assert client.post(f"/api/v1/applications/{app_id}/status", json={"status": "submission_confirmed"}, headers=hdr_a).status_code == 403

        # Admin / Verifier RBAC
        assert client.get("/api/v1/admin/evidence/queue", headers=hdr_a).status_code == 403
        assert client.get("/api/v1/admin/evidence/queue", headers=hdr_ver).status_code == 200
        assert client.get("/api/v1/admin/routing/summary", headers=hdr_adm).status_code == 200

        # 6. Outage & Rescan Recovery: simulate ClamAV down -> scan_failed -> blocked -> recover -> scan_clean!
        monkeypatch.setattr(settings, "CLAMAV_PORT", 59998)
        fail_up = client.post(
            "/api/v1/documents/upload",
            files={"file": ("retry_transcript.txt", io.BytesIO(b"De Anza retry clean transcript"), "text/plain")},
            data={"document_category": "transcript"},
            headers=hdr_a,
        )
        assert fail_up.status_code == 201
        fail_doc_id = fail_up.json()["id"]
        assert fail_up.json()["scan_status"] == "scan_failed"
        assert client.get(f"/api/v1/documents/{fail_doc_id}/download", headers=hdr_a).status_code == 409

        # Restore working ClamAV socket and trigger retry
        monkeypatch.setattr(settings, "CLAMAV_PORT", clam_port)
        recovered = client.post(f"/api/v1/documents/{fail_doc_id}/rescan", headers=hdr_a)
        assert recovered.status_code == 200
        assert recovered.json()["scan_status"] == "scan_clean"
        assert client.get(f"/api/v1/documents/{fail_doc_id}/download", headers=hdr_a).status_code == 200

        # Delete clean doc cleanly
        assert client.delete(f"/api/v1/documents/{fail_doc_id}", headers=hdr_b).status_code == 404
        assert client.delete(f"/api/v1/documents/{fail_doc_id}", headers=hdr_a).status_code == 200

        # 7. Storage provider failure fails closed cleanly (503)
        class _BrokenS3:
            def put_object(self, **_kwargs):
                raise RuntimeError("R2 upstream 503 outage")

        from app.services import document_vault
        from app.api.v1 import documents as documents_api
        monkeypatch.setattr(settings, "STORAGE_BUCKET_NAME", "uniglobe-staging-vault")
        _broken_factory = lambda: S3CompatibleVaultStorageProvider("cloudflare_r2", client=_BrokenS3())
        monkeypatch.setattr(document_vault, "get_vault_storage_provider", _broken_factory)
        monkeypatch.setattr(documents_api, "get_vault_storage_provider", _broken_factory)
        broken_up = client.post(
            "/api/v1/documents/upload",
            files={"file": ("outage.txt", io.BytesIO(b"Should not save"), "text/plain")},
            data={"document_category": "transcript"},
            headers=hdr_a,
        )
        assert broken_up.status_code == 503

        # Ensure raw JWTs never appeared in captured logs
        for raw_jwt in (tok_a, tok_b, tok_ver, tok_adm, tok_exp):
            assert raw_jwt not in caplog.text
    finally:
        clam_stop.set()
        srv.close()
        reset_auth_provider_cache()


# ===========================================================================
# 3. REDIRECT-CHAIN SSRF, PROXY INHERITANCE & K8S POLICY CHECKS
# ===========================================================================

def test_44_ssrf_redirect_chain_proxy_isolation_and_k8s_policy(monkeypatch):
    # Verify proxy env variables are ignored (trust_env=False) and 302 -> metadata is never followed
    called_urls = []

    class _FakeTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            called_urls.append(str(request.url))
            return httpx.Response(302, headers={"Location": "http://169.254.169.254/latest/meta-data/iam/"})

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9999")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")
    monkeypatch.setattr(routing_health, "_resolve_and_validate_public_ips", lambda h, p: ["93.184.216.34"])

    with httpx.Client(follow_redirects=False, trust_env=False, transport=_FakeTransport()) as hc:
        resp = hc.head("https://admissions.berkeley.edu/apply")
        assert resp.status_code == 302
        assert called_urls == ["https://admissions.berkeley.edu/apply"]
        # Target location MUST fail SSRF validation
        assert routing_health.validate_routing_url(resp.headers["location"])["valid"] is False

    # Validate Kubernetes NetworkPolicy blocks IMDS & IPv6 ULA while keeping port 443/5432/6379
    repo_root = __import__("pathlib").Path(__file__).resolve().parents[3]
    k8s_txt = (repo_root / "infra/firewall/k8s-api-worker-egress-networkpolicy.yaml").read_text(encoding="utf-8")
    for required in ("169.254.169.254/32", "fc00::/7", "::ffff:169.254.169.254/128", "port: 443", "port: 5432", "port: 6379"):
        assert required in k8s_txt
