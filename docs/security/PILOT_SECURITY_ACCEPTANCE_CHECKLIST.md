# UniGlobe Pilot Security Acceptance Checklist

**Last Updated:** November 26, 2026 (Phase 4.5 Gate Audit)  
**Strict Verification Rule:** Requirements validated only via mocks, localhost sockets, or `--dry-run` remain **`NOT TESTED` (Live Staging Infra)** until actually executed against live staging infrastructure. Real student onboarding stays **`NO-GO`** until zero live gates remain `NOT TESTED` or `FAIL`.

| Category | Security Requirement | Local Code / Integration | Live Staging Infra Gate | Evidence / Missing Staging Prerequisite |
|---|---|---|---|---|
| **Gate A — Auth (P0)** | Remove hardcoded Clerk user stub (`clerk_verified_user`) | **PASS** | — | Removed in `auth_provider.py` (`test_42_06`, `test_43_jwt_jwks_*`) |
| **Gate A — Auth (P0)** | RS256/JWKS verification, `iss`/`aud`/`exp`/`nbf`/`iat`, key rotation & `alg=none`/`HS256` rejection | **PASS** | — | Verified w/ in-memory RSA-2048 & mocked JWKS (`test_43`, `test_44`) |
| **Gate A — Auth (P0)** | Mock auth & `dev_token` fallback rejected in staging/prod; JWKS outage fails closed; zero raw JWT logs | **PASS** | — | Verified (`SecurityConfigurationError` & `401` across protected endpoints) |
| **Gate A — Auth (P0)** | **Live Clerk staging tenant registration, login, JWKS fetch, rotation & logout** | — | **NOT TESTED** | Blocked: no live Clerk staging `CLERK_ISSUER` / credentials provisioned on macOS workstation |
| **Authorization (P0)** | Profile, Enrollment/Course IDOR fix, Documents, Applications, Counselor isolation & RBAC | **PASS** | **NOT TESTED (w/ live Clerk)** | Verified `404`/`403`/`200` locally (`test_43`, `test_44`); live Clerk multi-user E2E pending Gate A |
| **Gate B — Network (P0)** | Block IPv4/IPv6 private, loopback, link-local, IMDS, CGNAT, NAT64, octal/hex/short IP, DNS rebinding, `302 -> IMDS`, `trust_env=False` | **PASS** | — | Verified across 24 URLs, 15 IP classes, `_PinnedPublicIPBackend` (`test_audit_retention`, `test_43`, `test_44`) |
| **Gate B — Network (P0)** | **Live Linux kernel `iptables`/`ip6tables` or Kubernetes `NetworkPolicy` enforcement & rollback** | **PASS (`--dry-run` / YAML)** | **NOT TESTED** | Blocked: host is macOS `Darwin 25.6.0` w/ `docker: MISSING`, `kubectl: MISSING` |
| **Gate C — Storage (P1)** | `25 MB` size guard, path traversal, executable/MIME/magic-byte check, Fernet local encryption, short-lived signed URLs & SHA-256 verify | **PASS** | — | Verified in `test_43` & `test_44` (`413`/`415`/`400`/`403`/`200`) |
| **Gate C — Storage (P1)** | External AI document egress privacy guard & storage write failure `503` fail-closed | **PASS** | — | Verified in `test_43` & `test_44` |
| **Gate C — Storage (P1)** | **Live private Cloudflare R2 / AWS S3 bucket ACL (`403` public), SSE encryption, signed URL expiry & deletion** | **PASS (mock S3)** | **NOT TESTED** | Blocked: no live staging bucket or `STORAGE_*` credentials available |
| **Gate D — Malware (P1)** | Staging/prod heuristic prohibition (`PolicyFailClosedScanner`), EICAR quarantine, retry immutability (`422`), scan-clean gating across Counselor/Requirements/Transfer | **PASS** | — | Verified against localhost TCP `zINSTREAM` daemon (`test_44`) |
| **Gate D — Malware (P1)** | **Live `clamav/clamav` container daemon TCP `3310` scan, EICAR detection & outage recovery** | **PASS (local TCP socket)** | **NOT TESTED** | Blocked: `docker: MISSING`, `clamd: MISSING`, `clamscan: MISSING` |
| **Regression (All)** | Existing product features, 10 languages, Arabic RTL, scholarship/financial safety & production build | **PASS (`109` pytest / `13` web / `16` routes)** | **NOT TESTED (live staging stack)** | Local suite & Next.js build verified clean at `a0aa2e0` |

**Current Acceptance Verdict (Phase 4.5):** **`NO-GO` for Public / Live Pilot** until all **`NOT TESTED`** staging infrastructure gates (A, B, C, D) are executed on a provisioned Linux staging environment and updated with live observed evidence.
