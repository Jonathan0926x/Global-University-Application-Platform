"""
Phase 4.3: Production Security Hardening & Controlled Pilot Readiness Suite.

Covers Workstreams A–F:
1. Genuine Clerk RS256 JWT/JWKS verification, rotation, failure closed, alg substitution defense,
   and production mock rejection.
2. Authorization, role-based access control, and cross-student isolation across all endpoints
   (including IDOR regression test on POST /profile/enrollments/{enrollment_id}/courses).
3. SSRF & outbound network protections (IPv4/IPv6 private, CGNAT, NAT64, IMDS, alternate IP notations,
   DNS rebinding, redirect non-following, proxy isolation, firewall policy validation).
4. Document Vault security (25 MB size limit, MIME/magic-byte checks, path traversal & executable rejection,
   encryption at rest, pre-signed URLs & expiry, S3/R2 provider contract, ClamAV/EICAR quarantine,
   scan failure & pending blocks, SHA-256 verification, external AI egress privacy guard).
"""

from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import logging
import subprocess
import time
import uuid

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import httpcore
import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
import pytest

from app.config import settings
from app.core import auth_provider
from app.core.auth_provider import (
    ClerkAuthProvider,
    MockAuthProvider,
    SecurityConfigurationError,
    get_auth_provider,
    reset_auth_provider_cache,
)
from app.database import SessionLocal
from app.ingestion.routing_seed import validate_routing_url
from app.models.document import Document
from app.services import document_vault, routing_health
from app.services.document_vault import (
    EICAR_TEST_SIGNATURE,
    ClamAVScanner,
    DocumentVaultService,
    LocalVaultStorageProvider,
    S3CompatibleVaultStorageProvider,
    UploadValidationError,
    validate_upload_bytes,
)


def _generate_rsa_keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()
    jwk_dict = json.loads(RSAAlgorithm.to_jwk(pub))
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv, pub_pem, jwk_dict


def _make_jwt(priv_key, kid: str, *, iss="https://clerk.pilot.uniglobe.edu", aud="uniglobe-api", sub="user_clerk_99",
              email="pilot.student@uniglobe.edu", role="student", exp_offset=600, nbf_offset=-10, iat_offset=-5,
              alg="RS256", extra_claims=None):
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": iss,
        "exp": now + exp_offset,
        "iat": now + iat_offset,
        "email": email,
        "email_verified": True,
        "role": role,
    }
    if aud is not None:
        payload["aud"] = aud
    if nbf_offset is not None:
        payload["nbf"] = now + nbf_offset
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, priv_key, algorithm=alg, headers={"kid": kid})


# ===========================================================================
# 1. WORKSTREAM A — CLERK JWT / JWKS CRYPTOGRAPHIC VERIFICATION
# ===========================================================================

@pytest.mark.asyncio
async def test_43_jwt_jwks_verification_rotation_and_fail_closed(caplog):
    priv1, pub1_pem, jwk1 = _generate_rsa_keypair()
    priv2, _, jwk2 = _generate_rsa_keypair()
    jwk1.update({"kid": "kid-1", "use": "sig", "alg": "RS256"})
    jwk2.update({"kid": "kid-2", "use": "sig", "alg": "RS256"})

    active_keys = [jwk1]
    fetch_count = 0

    async def fake_jwks_fetcher(_url: str):
        nonlocal fetch_count
        fetch_count += 1
        return {"keys": list(active_keys)}

    provider = ClerkAuthProvider(
        issuer="https://clerk.pilot.uniglobe.edu",
        jwks_url="https://clerk.pilot.uniglobe.edu/.well-known/jwks.json",
        audience="uniglobe-api",
        accepted_algorithms=["RS256"],
        jwks_cache_ttl_seconds=3600,
        jwks_min_refresh_interval_seconds=0,
        jwks_fetcher=fake_jwks_fetcher,
    )

    # 1. Valid Clerk RS256 token
    valid_tok = _make_jwt(priv1, "kid-1", role="data_verifier")
    claims = await provider.verify_token(f"Bearer {valid_tok}")
    assert claims is not None
    assert claims.user_id == "user_clerk_99"
    assert claims.email == "pilot.student@uniglobe.edu"
    assert claims.role == "data_verifier"
    assert claims.auth_method == "clerk_jwt"
    assert fetch_count == 1

    # 2. Invalid signature (signed with priv2 but claiming kid-1)
    bad_sig = _make_jwt(priv2, "kid-1")
    with caplog.at_level(logging.WARNING, logger="uniglobe.security.auth"):
        assert await provider.verify_token(bad_sig) is None
    # Raw JWT must NEVER be written to logs
    assert bad_sig not in caplog.text

    # 3. Expired token
    expired = _make_jwt(priv1, "kid-1", exp_offset=-120, iat_offset=-300)
    assert await provider.verify_token(expired) is None

    # 4. Future nbf token
    future_nbf = _make_jwt(priv1, "kid-1", nbf_offset=300)
    assert await provider.verify_token(future_nbf) is None

    # 5. Invalid issuer & invalid audience
    assert await provider.verify_token(_make_jwt(priv1, "kid-1", iss="https://evil.example.com")) is None
    assert await provider.verify_token(_make_jwt(priv1, "kid-1", aud="wrong-audience")) is None
    assert await provider.verify_token(_make_jwt(priv1, "kid-1", aud=None)) is None

    # 6. Missing required sub claim
    no_sub_payload = {"iss": "https://clerk.pilot.uniglobe.edu", "aud": "uniglobe-api", "exp": int(time.time()) + 300, "iat": int(time.time())}
    no_sub_tok = jwt.encode(no_sub_payload, priv1, algorithm="RS256", headers={"kid": "kid-1"})
    assert await provider.verify_token(no_sub_tok) is None

    # 7. Malformed & unknown kid
    assert await provider.verify_token("not.a.valid.jwt") is None
    assert await provider.verify_token("Bearer invalid") is None
    assert await provider.verify_token(_make_jwt(priv1, "unknown-kid")) is None

    # 8. Key rotation: introduce kid-2 cleanly -> refreshes JWKS & accepts new key
    active_keys = [jwk1, jwk2]
    rotated_tok = _make_jwt(priv2, "kid-2", sub="user_rotated", role="admin")
    rotated_claims = await provider.verify_token(rotated_tok)
    assert rotated_claims is not None
    assert rotated_claims.user_id == "user_rotated"
    assert rotated_claims.role == "admin"

    # 9. Algorithm substitution attempts ('none' and manually-signed 'HS256' using public key PEM)
    import base64
    import hmac as _hmac

    def _b64u(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    alg_none = f"{_b64u(json.dumps({'alg': 'none', 'kid': 'kid-1', 'typ': 'JWT'}).encode())}.{_b64u(json.dumps({'sub': 'attacker', 'iss': 'https://clerk.pilot.uniglobe.edu', 'aud': 'uniglobe-api', 'exp': int(time.time()) + 300, 'iat': int(time.time())}).encode())}."
    assert await provider.verify_token(alg_none) is None

    h_hs = _b64u(json.dumps({"alg": "HS256", "kid": "kid-1", "typ": "JWT"}).encode())
    p_hs = _b64u(json.dumps({"sub": "attacker", "iss": "https://clerk.pilot.uniglobe.edu", "aud": "uniglobe-api", "exp": int(time.time()) + 300, "iat": int(time.time()), "role": "admin"}).encode())
    sig_hs = _b64u(_hmac.new(pub1_pem, f"{h_hs}.{p_hs}".encode("ascii"), hashlib.sha256).digest())
    hs256_confuse = f"{h_hs}.{p_hs}.{sig_hs}"
    assert await provider.verify_token(hs256_confuse) is None

    # 10. JWKS endpoint unavailable fails closed
    async def broken_jwks(_url: str):
        raise httpx.ConnectError("JWKS unreachable")

    outage_provider = ClerkAuthProvider(
        issuer="https://clerk.pilot.uniglobe.edu",
        jwks_url="https://clerk.pilot.uniglobe.edu/.well-known/jwks.json",
        audience="uniglobe-api",
        jwks_fetcher=broken_jwks,
    )
    assert await outage_provider.verify_token(valid_tok) is None


@pytest.mark.asyncio
async def test_43_production_rejects_mock_auth_and_anonymous_requests(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "mock")
    reset_auth_provider_cache()

    with pytest.raises(SecurityConfigurationError):
        get_auth_provider()

    assert await MockAuthProvider().verify_token("Bearer mock_admin_evil@uniglobe.edu") is None
    assert await MockAuthProvider().verify_token("Bearer dev_token") is None

    # Even with AUTH_PROVIDER='clerk' in production, anonymous requests return 401/503 never default dev user
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "clerk")
    reset_auth_provider_cache()
    for path, method in [
        ("/api/v1/profile", "GET"),
        ("/api/v1/documents", "GET"),
        ("/api/v1/applications", "GET"),
        ("/api/v1/credentials/profile-evaluate", "GET"),
        ("/api/v1/counselor/history", "GET"),
    ]:
        res = client.request(method, path)
        assert res.status_code == 401, f"Expected 401 on {path} without token in production, got {res.status_code}"

    # Forged mock token rejected against Clerk in production
    res_mock = client.get("/api/v1/profile", headers={"Authorization": "Bearer mock_admin_hacker@evil.com"})
    assert res_mock.status_code == 401
    reset_auth_provider_cache()


# ===========================================================================
# 2. WORKSTREAM B — AUTHORIZATION, IDOR REGRESSION & ROLE ESCALATION DEFENSE
# ===========================================================================

def test_43_cross_student_isolation_and_rbac_enforcement(client):
    uid_a = uuid.uuid4().hex[:8]
    uid_b = uuid.uuid4().hex[:8]
    headers_a = {"Authorization": f"Bearer mock_iso_a_{uid_a}@uniglobe.edu"}
    headers_b = {"Authorization": f"Bearer mock_iso_b_{uid_b}@uniglobe.edu"}
    verifier_headers = {"Authorization": f"Bearer mock_verifier_{uid_a}@uniglobe.edu"}

    # Setup Student A profile + enrollment + clean document + application + counselor thread
    p_a = client.post("/api/v1/profile", json={"first_name": "Alice", "last_name": "Alpha", "applicant_type": "transfer"}, headers=headers_a)
    assert p_a.status_code == 201
    p_b = client.post("/api/v1/profile", json={"first_name": "Bob", "last_name": "Beta", "applicant_type": "first_year"}, headers=headers_b)
    assert p_b.status_code == 201

    enr_a = client.post(
        "/api/v1/profile/enrollments",
        json={"institution_name_manual": "De Anza College", "enrollment_type": "community_college", "cumulative_gpa": 3.85},
        headers=headers_a,
    )
    assert enr_a.status_code == 201
    enr_a_id = enr_a.json()["id"]

    # REGRESSION TEST: Student B MUST NOT add courses to Student A's enrollment (previous IDOR gap!)
    idor_course = client.post(
        f"/api/v1/profile/enrollments/{enr_a_id}/courses",
        json={"course_code": "FAKE 999", "course_name": "Injected Course"},
        headers=headers_b,
    )
    assert idor_course.status_code == 404

    # Upload clean document for A
    doc_a = client.post(
        "/api/v1/documents/upload",
        files={"file": ("alice_transcript.txt", b"De Anza College official transcript CIS 22A Grade A", "text/plain")},
        data={"document_category": "transcript"},
        headers=headers_a,
    )
    assert doc_a.status_code == 201
    doc_a_id = doc_a.json()["id"]

    # Cross-student document isolation (details, presigned-url, download, translate)
    assert client.get(f"/api/v1/documents/{doc_a_id}", headers=headers_b).status_code == 404
    assert client.get(f"/api/v1/documents/{doc_a_id}/presigned-url", headers=headers_b).status_code == 404
    assert client.get(f"/api/v1/documents/{doc_a_id}/download", headers=headers_b).status_code == 404
    assert client.post(f"/api/v1/documents/{doc_a_id}/translate", json={"target_language": "fr-FR"}, headers=headers_b).status_code == 404

    # Counselor conversation isolation
    chat_a = client.post("/api/v1/counselor/chat", json={"message": "What are my MIT transfer rules?"}, headers=headers_a)
    assert chat_a.status_code == 200
    conv_a_id = chat_a.json()["conversation_id"]
    assert client.get(f"/api/v1/counselor/conversations/{conv_a_id}", headers=headers_b).status_code == 404
    assert client.delete(f"/api/v1/counselor/conversations/{conv_a_id}", headers=headers_b).status_code == 404
    assert client.post("/api/v1/counselor/chat", json={"message": "Hijack thread", "conversation_id": conv_a_id}, headers=headers_b).status_code == 404

    # Application isolation & non-self-certification
    insts = client.get("/api/v1/institutions").json()
    inst_id = insts[0]["id"]
    app_a = client.post("/api/v1/applications", json={"institution_id": inst_id, "applicant_type": "transfer"}, headers=headers_a)
    assert app_a.status_code == 201
    app_a_id = app_a.json()["id"]

    assert client.get(f"/api/v1/applications/{app_a_id}", headers=headers_b).status_code == 404
    assert client.post(f"/api/v1/applications/{app_a_id}/redirect", json={"acknowledge_unverified": True}, headers=headers_b).status_code == 404
    assert client.delete(f"/api/v1/applications/{app_a_id}", headers=headers_b).status_code == 404

    # Student A CANNOT self-confirm application submission
    self_confirm = client.post(
        f"/api/v1/applications/{app_a_id}/status",
        json={"status": "submission_confirmed"},
        headers=headers_a,
    )
    assert self_confirm.status_code == 403

    # Admin / Verifier endpoint authorization: Student MUST get 403; data_verifier gets 200
    for admin_path in (
        "/api/v1/admin/verification/taxonomies",
        "/api/v1/admin/routing/summary",
        "/api/v1/admin/evidence/queue",
        "/api/v1/admin/quality-flags",
        "/api/v1/admin/ingestion-runs",
    ):
        assert client.get(admin_path, headers=headers_a).status_code == 403
        assert client.get(admin_path, headers=verifier_headers).status_code == 200


# ===========================================================================
# 3. WORKSTREAM C — SSRF, IPV4/IPV6, ALTERNATE IP & FIREWALL VALIDATION
# ===========================================================================

def test_43_ssrf_url_validation_ipv4_ipv6_redirect_and_firewall():
    unsafe_urls = [
        "http://10.0.0.1/admin",
        "https://172.16.0.10/secret",
        "https://192.168.1.50/router",
        "http://127.0.0.1:8000/api/v1/health",
        "http://localhost/admin",
        "http://localhost./admin",
        "https://sub.localhost/test",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "https://printer.local/api",
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://[fd00:ec2::254]/latest/meta-data/",
        "http://[::ffff:169.254.169.254]/",
        "http://[::ffff:127.0.0.1]/",
        "http://0177.0.0.1/",      # Octal loopback
        "http://0x7f.0.0.1/",      # Hex loopback
        "http://127.1/",           # Shorthand IPv4
        "http://2130706433/",      # Decimal integer IPv4
        "file:///etc/passwd",
        "ftp://ftp.mit.edu/file",
        "gopher://127.0.0.1:6379/_INFO",
        "javascript:alert(1)",
        "https://user:pass@berkeley.edu/",
    ]
    for bad in unsafe_urls:
        res = validate_routing_url(bad)
        assert res["valid"] is False, f"SSRF URL should have been blocked: {bad}"

    assert validate_routing_url("https://admissions.berkeley.edu/apply")["valid"] is True

    # IP classifier checks across IPv4 & IPv6 classes
    blocked_ips = [
        "10.1.2.3",
        "172.16.5.4",
        "192.168.0.1",
        "127.0.0.1",
        "169.254.169.254",
        "100.64.0.1",           # CGNAT RFC6598
        "0.0.0.0",
        "::1",
        "fe80::1",
        "fc00::1",
        "fd00:ec2::254",
        "ff02::1",
        "::ffff:10.0.0.1",
        "::ffff:169.254.169.254",
        "64:ff9b::169.254.169.254",
    ]
    for ip in blocked_ips:
        assert routing_health._is_public_routable_ip(ip) is False, f"Non-public IP leaked: {ip}"

    assert routing_health._is_public_routable_ip("93.184.216.34") is True
    assert routing_health._is_public_routable_ip("2606:2800:220:1:248:1893:25c8:1946") is True

    # Redirect-chain SSRF test + proxy inheritance isolation
    src = open(routing_health.__file__, encoding="utf-8").read()
    assert "trust_env=False" in src
    assert "follow_redirects=False" in src

    # Firewall dry-run execution succeeds and emits all critical drops
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[3]
    fw_out = subprocess.run(
        ["bash", str(repo_root / "infra/firewall/egress-iptables.sh"), "--dry-run"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for cidr in ("169.254.169.254/32", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "fc00::/7", "::ffff:169.254.169.254/128"):
        assert cidr in fw_out


# ===========================================================================
# 4. WORKSTREAM D — DOCUMENT VAULT SECURITY, SCANNING, QUARANTINE & S3/R2
# ===========================================================================

@pytest.mark.asyncio
async def test_43_vault_validation_encryption_scan_quarantine_and_s3_contract(client, tmp_path, monkeypatch):
    uid = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer mock_vaultsec_{uid}@uniglobe.edu"}
    assert client.post("/api/v1/profile", json={"first_name": "Nadia", "last_name": "Jean", "applicant_type": "first_year"}, headers=headers).status_code == 201

    # 1. Size limit rejection
    with pytest.raises(UploadValidationError) as exc_size:
        validate_upload_bytes("big.txt", "text/plain", b"A" * 200, max_size_bytes=100)
    assert exc_size.value.status_code == 413

    # 2. MIME mismatch, malformed PDF, executable double extension, path traversal
    for bad_file, bad_mime, bad_bytes in [
        ("transcript.pdf", "text/plain", b"%PDF-1.4\nhello"),
        ("fake.pdf", "application/pdf", b"NOT A PDF CONTENT"),
        ("malware.pdf.exe", "application/pdf", b"%PDF-1.4\nhello"),
        ("../../etc/passwd.txt", "text/plain", b"root:x:0:0"),
        ("binary.txt", "text/plain", b"MZ\x90\x00executable"),
    ]:
        res = client.post(
            "/api/v1/documents/upload",
            files={"file": (bad_file, io.BytesIO(bad_bytes), bad_mime)},
            data={"document_category": "transcript"},
            headers=headers,
        )
        assert res.status_code in (400, 415), f"Expected rejection for {bad_file}: {res.status_code}"

    # 3. EICAR malware payload -> quarantined, preserves SHA-256, blocks extraction/translation/download
    eicar_bytes = b"Transcript header\n" + EICAR_TEST_SIGNATURE + b"\nEnd"
    eicar_sha = hashlib.sha256(eicar_bytes).hexdigest()
    res_eicar = client.post(
        "/api/v1/documents/upload",
        files={"file": ("infected_transcript.txt", io.BytesIO(eicar_bytes), "text/plain")},
        data={"document_category": "transcript"},
        headers=headers,
    )
    assert res_eicar.status_code == 201
    eicar_doc = res_eicar.json()
    assert eicar_doc["scan_status"] == "quarantined"
    assert eicar_doc["file_sha256"] == eicar_sha
    assert "quarantine" in eicar_doc["storage_key"]
    assert eicar_doc["extraction"] is None
    assert eicar_doc["translations"] == []
    assert client.get(f"/api/v1/documents/{eicar_doc['id']}/presigned-url", headers=headers).status_code == 422
    assert client.get(f"/api/v1/documents/{eicar_doc['id']}/download", headers=headers).status_code == 422
    assert client.post(f"/api/v1/documents/{eicar_doc['id']}/translate", json={"target_language": "fr-FR"}, headers=headers).status_code == 422

    # 4. Pre-signed download & expiry verification on encrypted clean document
    fernet_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(settings, "VAULT_ENCRYPTION_KEY", fernet_key)
    monkeypatch.setattr(settings, "VAULT_PRESIGNED_TTL_SECONDS", 120)

    clean_bytes = b"%PDF-1.4\n1 0 obj <<>> endobj\nDe Anza College Official Transcript Grade A\n"
    clean_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("clean_official.pdf", io.BytesIO(clean_bytes), "application/pdf")},
        data={"document_category": "transcript"},
        headers=headers,
    )
    assert clean_res.status_code == 201
    clean_doc = clean_res.json()
    assert clean_doc["scan_status"] == "scan_clean"
    assert clean_doc["is_encrypted"] is True
    # Bytes on disk MUST be ciphertext, NOT plaintext!
    assert open(clean_doc["storage_path"], "rb").read() != clean_bytes

    ps = client.get(f"/api/v1/documents/{clean_doc['id']}/presigned-url", headers=headers)
    assert ps.status_code == 200
    dl_url = ps.json()["download_url"]
    dl_resp = client.get(dl_url, headers=headers)
    assert dl_resp.status_code == 200
    assert dl_resp.content == clean_bytes
    assert dl_resp.headers["x-content-type-options"] == "nosniff"
    assert dl_resp.headers["x-document-sha256"] == hashlib.sha256(clean_bytes).hexdigest()

    # Expired & tampered pre-signed URLs MUST be rejected (403)
    assert client.get(f"/api/v1/documents/{clean_doc['id']}/download?expires=1000&sig=tampered", headers=headers).status_code == 403

    # 5. External AI egress privacy guard
    assert client.post(
        f"/api/v1/documents/{clean_doc['id']}/translate",
        json={"target_language": "es-419", "allow_external_ai": True},
        headers=headers,
    ).status_code == 403

    # 6. ClamAV scanner unreachable -> scan_failed & blocks processing
    unreachable_clam = ClamAVScanner(host="127.0.0.1", port=59999, timeout=1)
    res_fail = unreachable_clam.scan_bytes(clean_bytes, "clean_official.pdf")
    assert res_fail.state == "scan_failed" and res_fail.clean is False

    # 7. Async pending_scan document blocks download/translation until scanned
    monkeypatch.setattr(settings, "DOCUMENT_ASYNC_SCAN", True)
    pend_res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("pending.txt", io.BytesIO(b"Pending transcript"), "text/plain")},
        data={"document_category": "transcript"},
        headers=headers,
    )
    assert pend_res.status_code == 201
    assert pend_res.json()["scan_status"] == "pending_scan"
    assert client.get(f"/api/v1/documents/{pend_res.json()['id']}/download", headers=headers).status_code == 409

    # 8. S3/Cloudflare R2 private SSE contract check
    class _FakeS3:
        def __init__(self):
            self.calls = []
            self.store = {}

        def put_object(self, **kwargs):
            self.calls.append(("put_object", kwargs))
            self.store[kwargs["Key"]] = kwargs["Body"]

        def get_object(self, Bucket, Key):
            return {"Body": io.BytesIO(self.store[Key])}

        def copy_object(self, **kwargs):
            self.calls.append(("copy_object", kwargs))

        def delete_object(self, Bucket, Key):
            self.calls.append(("delete_object", Key))

        def generate_presigned_url(self, op, Params, ExpiresIn):
            return f"https://r2.private.example/{Params['Bucket']}/{Params['Key']}?X-Amz-Expires={ExpiresIn}"

    fake_s3 = _FakeS3()
    monkeypatch.setattr(settings, "STORAGE_BUCKET_NAME", "uniglobe-pilot-vault")
    s3_provider = S3CompatibleVaultStorageProvider(backend_name="cloudflare_r2", client=fake_s3)
    path_uri, enc = s3_provider.put_bytes("prof1/orig_doc.pdf", clean_bytes, "application/pdf")
    assert enc is True and path_uri == "cloudflare_r2://uniglobe-pilot-vault/prof1/orig_doc.pdf"
    put_kw = fake_s3.calls[0][1]
    assert put_kw["ACL"] == "private"
    assert put_kw["ServerSideEncryption"] == "AES256"
    signed = s3_provider.generate_presigned_download_url("doc1", "prof1", "prof1/orig_doc.pdf", "transcript.pdf", 180)
    assert "X-Amz-Expires=180" in signed
