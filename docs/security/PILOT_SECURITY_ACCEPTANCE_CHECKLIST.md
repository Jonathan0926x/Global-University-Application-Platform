# UniGlobe Pilot Security Acceptance Checklist

**Date:** November 26, 2026  
**Policy:** Requirements marked **`NOT TESTED IN PROD/STAGING`** reflect controls implemented in code/manifests and tested locally/via mocks whose live infrastructure execution must pass on staging hosts before real students are invited.

| Category | Security Requirement | Outcome | Verification Evidence / Notes |
|---|---|---|---|
| **Authentication (P0)** | Remove hardcoded Clerk user stub (`clerk_verified_user`) | **PASS** | Verified removed in `auth_provider.py` (`test_42_06` & `test_43_jwt_jwks_verification_rotation_and_fail_closed`). |
| **Authentication (P0)** | Genuine RS256 signature verification via JWKS `kid` | **PASS** | Validated with 2048-bit RSA keypairs & mocked JWKS (`test_43_jwt_jwks_verification_rotation_and_fail_closed`). |
| **Authentication (P0)** | Validate `iss`, `aud`, `exp`, `nbf`, `iat`, `sub` claims | **PASS** | Negative assertions passed for wrong issuer/audience, expired, future `nbf`, and missing `sub`. |
| **Authentication (P0)** | Safe JWKS caching & controlled `kid` rotation refresh | **PASS** | Cache hit count verified + key rotation from `kid-1` to `kid-2` passed. |
| **Authentication (P0)** | Reject algorithm substitution (`none`, `HS256` w/ PEM) | **PASS** | Both crafted `alg=none` and `alg=HS256` public-key confusion tokens rejected (`None`). |
| **Authentication (P0)** | Authentication fails closed when JWKS unavailable; never logs raw JWTs | **PASS** | Verified `None` on JWKS connection failure & `caplog` absence check. |
| **Authentication (P0)** | Mock auth unavailable in `staging`/`production` environments | **PASS** | `SecurityConfigurationError` & `401 Unauthorized` verified (`test_43_production_rejects_mock_auth_and_anonymous_requests`). |
| **Authentication (P0)** | Live Clerk tenant token validation end-to-end | **NOT TESTED IN PROD/STAGING** | Requires real staging `CLERK_ISSUER` & synthetic test user session on `staging` host. |
| **Authorization (P0)** | Student profile, enrollment, and course isolation (IDOR fixed) | **PASS** | Fixed missing `profile_id` check on `POST /profile/enrollments/{id}/courses`; verified `404` cross-user (`test_43_cross_student_isolation_and_rbac_enforcement`). |
| **Authorization (P0)** | Document, Application, and Counselor isolation across users | **PASS** | Verified `404` for Student B across all Document, Application, and Counselor endpoints. |
| **Authorization (P0)** | Prevent student role escalation & self-confirmed submissions | **PASS** | Verified `403` for student role on `/admin/*`, evidence review, and `submission_confirmed`; `data_verifier` allowed (`200`). |
| **SSRF & Network (P0)** | Block IPv4/IPv6 private, loopback, link-local, IMDS, CGNAT, NAT64 | **PASS** | Verified across 15 IP classes (`_is_public_routable_ip`) and 24 unsafe URLs (`validate_routing_url`). |
| **SSRF & Network (P0)** | Block octal/hex/short/integer IP notations & embedded creds | **PASS** | `0177.0.0.1`, `0x7f.0.0.1`, `127.1`, `2130706433`, `user:pass@` all rejected. |
| **SSRF & Network (P0)** | DNS rebinding TOCTOU pinning, no auto-redirects, no env proxies | **PASS** | `_PinnedPublicIPBackend` + `follow_redirects=False` + `trust_env=False` verified (`test_audit_retention` & `test_43_ssrf`). |
| **SSRF & Network (P0)** | Firewall dry-run validation (`egress-iptables.sh --dry-run` + K8s policy) | **PASS** | All IPv4/IPv6 private/IMDS CIDR drops verified in script output & deployment checklist created. |
| **SSRF & Network (P0)** | Live kernel `iptables`/K8s `NetworkPolicy` enforcement on worker host | **NOT TESTED IN PROD/STAGING** | macOS dev workstation cannot execute Linux kernel `iptables`/`NetworkPolicy`; run checklist on staging Linux host first. |
| **Document Vault (P1)** | Upload size limit (25 MB), MIME & magic-byte validation, path traversal block | **PASS** | Tested `413` size limit, `415` MIME/double-ext/binary mismatch, `400` malformed PDF & `../` traversal. |
| **Document Vault (P1)** | Encryption at rest (`Fernet` local) & S3/R2 private SSE provider interface | **PASS** | Verified ciphertext on disk (`VAULT_ENCRYPTION_KEY`) and mocked `S3CompatibleVaultStorageProvider` (`ACL=private`, `SSE=AES256`). |
| **Document Vault (P1)** | Short-lived pre-signed download URLs, expiration check & SHA-256 integrity | **PASS** | Verified `presigned-url`, matching bytes + `X-Document-SHA256`, and `403` on expired/tampered links. |
| **Document Vault (P1)** | Malware scan states (`pending_scan`, `scan_failed`, `quarantined`) gate processing | **PASS** | EICAR quarantined cleanly (`quarantine/`), blocking `/download`, `/presigned-url`, `/translate`, syllabus/evidence attach (`422` / `409`). |
| **Document Vault (P1)** | External AI document egress privacy guard | **PASS** | Verified `403` when `allow_external_ai=True` without server opt-in policy. |
| **Document Vault (P1)** | Live ClamAV daemon (`clamav_pilot:3310`) & live Cloudflare R2 / S3 bucket test | **NOT TESTED IN PROD/STAGING** | Unreachable ClamAV fail-closed tested (`scan_failed`); live `clamd` container & live R2 bucket pending staging bring-up. |
| **Pilot Env (P0/P1)** | Non-public pilot Compose topology, isolated DB & backup runbook | **PASS** | Configs written in `infra/pilot/`; NOT deployed publicly; zero real student data used. |
| **Regression (All)** | Backend (`106`), Frontend (`13`), Next.js Build (`16 routes`) | **PASS** | Zero regressions across scholarship eligibility, financial safety, and 10 languages incl. `ar-SA` RTL. |
