#!/usr/bin/env python3
"""
Non-destructive Staging Gate Smoke Verifier (Gates A, C, D + Auth Fail-Closed).
Run ONLY against an isolated provisioned staging host with synthetic test credentials.
NEVER stores or prints raw JWTs or secrets.
"""

import hashlib
import os
import sys
import httpx


EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def main() -> int:
    api_base = os.environ.get("STAGING_API_URL", "http://127.0.0.1:18000/api/v1").rstrip("/")
    tok_a = os.environ.get("STAGING_STUDENT_A_JWT", "").strip()
    tok_b = os.environ.get("STAGING_STUDENT_B_JWT", "").strip()
    if not tok_a or not tok_b:
        print("ABORT: STAGING_STUDENT_A_JWT and STAGING_STUDENT_B_JWT must be set in env.")
        return 2

    hdr_a = {"Authorization": f"Bearer {tok_a}"}
    hdr_b = {"Authorization": f"Bearer {tok_b}"}

    with httpx.Client(timeout=15.0, follow_redirects=False, trust_env=False) as client:
        # 1. Fail-closed anonymous & dev_token checks (Gate A)
        assert client.get(f"{api_base}/profile").status_code == 401
        assert client.get(f"{api_base}/profile", headers={"Authorization": "Bearer dev_token"}).status_code == 401
        print("PASS: Staging rejects anonymous and dev_token requests (401)")

        # 2. Live Clerk session validation
        s = client.get(f"{api_base}/session", headers=hdr_a)
        assert s.status_code == 200 and s.json().get("authenticated") is True
        print("PASS: Live Clerk JWT accepted cleanly for Student A")

        # 3. Clean upload -> ClamAV scan_clean + S3/R2 private SSE + presigned download (Gates C & D)
        pdf_bytes = b"%PDF-1.4\nSynthetic Staging Transcript\n"
        up_clean = client.post(
            f"{api_base}/documents/upload",
            headers=hdr_a,
            files={"file": ("staging_clean.pdf", pdf_bytes, "application/pdf")},
            data={"document_category": "transcript"},
        )
        assert up_clean.status_code == 201
        doc = up_clean.json()
        assert doc["scan_status"] == "scan_clean"
        assert doc["is_encrypted"] is True
        assert doc["file_sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
        ps = client.get(f"{api_base}/documents/{doc['id']}/presigned-url", headers=hdr_a)
        assert ps.status_code == 200
        dl_url = ps.json()["download_url"]
        if dl_url.startswith("/"):
            root_origin = api_base.rsplit("/api/v1", 1)[0]
            dl = client.get(f"{root_origin}{dl_url}", headers=hdr_a)
        else:
            dl = client.get(dl_url)
        assert dl.status_code == 200 and dl.content == pdf_bytes
        # Cross-student access MUST return 404
        assert client.get(f"{api_base}/documents/{doc['id']}/presigned-url", headers=hdr_b).status_code == 404
        print("PASS: Clean upload scanned, SSE stored, presigned downloaded & cross-user isolated")

        # 4. EICAR live ClamAV quarantine + blocked download/rescan (Gate D)
        up_eicar = client.post(
            f"{api_base}/documents/upload",
            headers=hdr_a,
            files={"file": ("eicar.txt", b"Header\n" + EICAR, "text/plain")},
            data={"document_category": "transcript"},
        )
        assert up_eicar.status_code == 201
        ed = up_eicar.json()
        assert ed["scan_status"] == "quarantined"
        assert client.post(f"{api_base}/documents/{ed['id']}/rescan", headers=hdr_a).status_code == 422
        print("PASS: Live ClamAV EICAR quarantine and retry lock verified")

    print("ALL SCRIPTED LIVE STAGING GATES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
