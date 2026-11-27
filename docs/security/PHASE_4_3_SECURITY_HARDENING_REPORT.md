# UniGlobe — Phase 4.3 Security Hardening & Controlled Pilot Readiness Report

**Project:** UniGlobe — Global University Application & Admissions Intelligence Platform  
**Milestone:** Phase 4.3 (`Production Security Hardening & Controlled Pilot Readiness`)  
**Execution Date:** November 26, 2026  
**Alembic Migration Head:** `a3c7e9f1b420` (revises `f1c9e4a2b870`, reversible)

---

## 1. Initial Security Baseline & Audit Findings Resolved

Auditing the Phase 4.2 codebase (`1fa16b1`) identified both the three previously logged deployment blockers and one critical cross-student authorization vulnerability discovered during endpoint inspection:

1. **IDOR Vulnerability Fixed (`apps/api/app/api/v1/profiles.py:167`):** `POST /api/v1/profile/enrollments/{enrollment_id}/courses` queried `EnrollmentRecord.id == enrollment_id` without checking `EnrollmentRecord.profile_id == profile.id`, allowing an authenticated user to inject courses into another student's enrollment. **Resolved:** Ownership is now derived strictly from `current_user.id -> StudentProfile.id` and enforced on every enrollment query (regression-tested with `404` for unauthorized users).
2. **Clerk Placeholder Stub Replaced (`apps/api/app/core/auth_provider.py`):** Removed the hardcoded `clerk_verified_user` identity completely and replaced it with genuine RS256 JWT / JWKS cryptographic verification (`PyJWT` + `cryptography`).
3. **Production Mock Auth Bypass Eliminated (`apps/api/app/api/deps.py`, `auth_provider.py`):** Removed silent unauthenticated `dev_token` fallback in non-mock or production/staging environments and enforced `SecurityConfigurationError` whenever `ENVIRONMENT in ("production", "staging")` with `AUTH_PROVIDER != "clerk"`.
4. **URL Validation Alternate-IP & Host Gaps Fixed (`apps/api/app/ingestion/routing_seed.py`, `routing_health.py`):** Closed gaps where octal/hex/short IPv4 notations (`0177.0.0.1`, `0x7f.0.0.1`, `127.1`), trailing dots (`localhost.`), `.internal`/`.local` suffixes, and CGNAT/NAT64 IPs (`100.64.0.0/10`, `64:ff9b::/96`) could pass validation before DNS checks.
5. **Document Vault Hardened (`apps/api/app/services/document_vault.py`, `documents.py`, `applications.py`, `transfer.py`, `operations.py`):** Implemented upload validation (`25 MB` max, path traversal neutralization, executable/double-extension rejection, MIME vs. magic-byte verification), storage provider abstraction (Local encrypted + S3/Cloudflare R2 private SSE), short-lived signed/pre-signed downloads, malware scanner abstraction + quarantine workflow, and external AI privacy guard.

---

## 2. Authentication Architecture & Clerk RS256/JWKS Verification

- **Files:** [auth_provider.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/core/auth_provider.py), [deps.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/api/deps.py), [config.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/config.py)
- **JWKS Configuration:** Configured via environment variables `CLERK_ISSUER`, `CLERK_JWKS_URL` (defaults cleanly to `${CLERK_ISSUER}/.well-known/jwks.json`), `CLERK_AUDIENCE`, `CLERK_ACCEPTED_ALGORITHMS` (`RS256` default; asymmetric `RS*` whitelist only), `CLERK_JWKS_CACHE_TTL_SECONDS` (`3600`), `CLERK_CLOCK_SKEW_SECONDS` (`30`), and `CLERK_MAX_IAT_AGE_SECONDS` (`86400`).
- **Verification Pipeline:**
  1. Strips `Bearer ` and rejects malformed JWT structure (`count(".") != 2`). Never logs raw JWT tokens.
  2. Parses unverified header and enforces strict algorithm allowlist (`RS256`, rejecting `alg=none` and `HS256` HMAC key-confusion attacks) plus required `kid`.
  3. Fetches public RSA signing keys via `JWKSKeyCache`, protected by an `asyncio.Lock` and `_PinnedPublicIPBackend` SSRF defense-in-depth (`follow_redirects=False`, `trust_env=False`).
  4. **Key Rotation:** An unrecognized `kid` triggers a controlled JWKS refresh (cooldown-guarded) so Clerk key rotations succeed transparently while failing closed if still absent or if JWKS is unreachable.
  5. Validates cryptographic RS256 signature, `exp`, `nbf`, `iat`, `iss`, and `aud` (when configured), and extracts `role` exclusively from server-signed JWT metadata (`"student"`, `"data_verifier"`, `"admin"`).
  6. Fails closed (`None` -> HTTP `401 Unauthorized`). `MockAuthProvider` is rejected outright (`SecurityConfigurationError`) in `staging`/`production`.

---

## 3. Authorization & Student Data Isolation Model

All authenticated routes derive ownership strictly from `current_user.id` -> `StudentProfile.user_id` via `get_current_user` / `get_current_profile`. Clients cannot pass arbitrary `profile_id` or elevate roles:

| Endpoint Group | Isolation / Authorization Enforcement | Negative Test Coverage |
|---|---|---|
| **Profiles & Enrollments** ([profiles.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/api/v1/profiles.py)) | `profile.user_id == current_user.id`; `add_course_record` enforces `EnrollmentRecord.profile_id == profile.id`; `profile_completion_pct` ignored on `PATCH`. | Verified Student B gets `404` writing to Student A's `enrollment_id`. |
| **Document Vault** ([documents.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/api/v1/documents.py)) | Every query scopes `Document.profile_id == profile.id`; `/presigned-url` and `/download` validate ownership + scan state + SHA-256 + signed HMAC expiry. | Verified Student B gets `404` on `/documents/{id}`, `/presigned-url`, `/download`, `/translate`. |
| **Applications & Routing** ([applications.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/api/v1/applications.py)) | `_get_owned_application` enforces `Application.profile_id == profile.id`; students receive `403` attempting `submission_confirmed`. | Verified cross-student `404` & `403` on self-confirm and evidence review. |
| **AI Counselor** ([counselor.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/api/v1/counselor.py)) | `CounselorConversation.profile_id == profile.id` enforced on `/chat`, `/history`, `/conversations/{id}`, `DELETE`. | Verified Student B gets `404` viewing, hijacking, or deleting Student A's threads. |
| **Financial & Credentials** ([financial.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/api/v1/financial.py), [credentials.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/api/v1/credentials.py)) | Profile-bound endpoints use `get_current_profile`; production/staging reject unauthenticated calls with `401`. | Verified `401` when `AUTH_PROVIDER=clerk` without valid JWT. |
| **Operations / Verifier RBAC** ([operations.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/api/v1/operations.py)) | Gated by `require_admin_claims` (`role in ("admin", "data_verifier")`, active account check). | Verified `student` gets `403` and `data_verifier` gets `200` on permitted review endpoints. |

---

## 4. SSRF Defenses & Outbound Network Security

- **Application Layer ([routing_seed.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/ingestion/routing_seed.py), [routing_health.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/services/routing_health.py)):**
  - `validate_routing_url` blocks non-HTTP(S) schemes, embedded credentials, trailing dots, internal suffixes (`.localhost`, `.local`, `.internal`, `.arpa`), IDNA tricks, raw IPv4/IPv6 literals, AND alternate octal/hex/short IPv4 notations via `socket.inet_aton`.
  - `_is_public_routable_ip` enforces global public routability while blocking RFC1918, loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`, `fe80::/10`), cloud IMDS (`169.254.169.254`, `fd00:ec2::254`), CGNAT (`100.64.0.0/10`), ULA (`fc00::/7`), NAT64 (`64:ff9b::/96`), and IPv4-mapped IPv6 equivalents (`::ffff:*`).
  - `_PinnedPublicIPBackend` re-checks DNS at TCP socket connection time against pre-resolved pinned public IPs (`strict_allowed` intersection), blocking TOCTOU DNS rebinding. HTTP clients set `follow_redirects=False` and `trust_env=False`.
- **Network / Host Layer (`infra/firewall/`):**
  - `egress-iptables.sh` (`--dry-run` verified locally) and `k8s-api-worker-egress-networkpolicy.yaml` enforce kernel/CNI egress drops on worker nodes. See [PRODUCTION_DEPLOYMENT_CHECKLIST.md](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/infra/firewall/PRODUCTION_DEPLOYMENT_CHECKLIST.md) for host permissions, allowed domain allowlists, health checks, and rollback commands.
  - **Status:** Host-level firewall execution in staging/production remains pending target Linux host provisioning (`NOT TESTED` against live Linux kernel iptables).

---

## 5. Document Vault Security, Encryption & Malware Scanning

- **Upload Validation (`validate_upload_bytes`):** Enforces configurable `25 MB` max payload (`VAULT_MAX_UPLOAD_SIZE_BYTES`), blocks `..`, `/`, `\`, null bytes, executable/script extensions (`.exe`, `.sh`, `.html`, `.svg`, double extensions `.pdf.exe`), validates MIME-to-extension matching, and inspects file magic bytes (`%PDF-`, PNG, JPEG, DOCX ZIP, UTF-8 text).
- **Storage Provider Abstraction (`IVaultStorageProvider`):**
  - `LocalVaultStorageProvider`: isolates files by `profile_id` with `0700`/`0600` permissions, supports Fernet encryption at rest (`VAULT_ENCRYPTION_KEY`), and issues short-lived HMAC-SHA256 signed download URLs (`VAULT_PRESIGNED_TTL_SECONDS`).
  - `S3CompatibleVaultStorageProvider`: uses `boto3` for private AWS S3 / Cloudflare R2 buckets (`ACL="private"`, `ServerSideEncryption="AES256"` / `"aws:kms"`, short-lived `generate_presigned_url`, quarantine prefix moves). **Verified via mocked S3 client unit tests; live R2/S3 credentials/bucket connectivity remains pending pilot provisioning.**
- **Malware Scanning & Quarantine (`IMalwareScanner`):**
  - Supports explicit document states: `uploaded`, `pending_scan`, `scan_clean`, `scan_infected`, `scan_failed`, `quarantined`.
  - `ClamAVScanner` connects over TCP `zINSTREAM` (`CLAMAV_HOST:CLAMAV_PORT`) and fails closed (`scan_failed`) when unreachable. `HeuristicMalwareScanner` detects EICAR test signatures, PE/ELF/Mach-O headers, and `<script` injections locally.
  - Infected files move immediately to `quarantine/{profile_id}/` with `quarantined_at` recorded; extraction, translation, pre-signed download, syllabus attachment, and submission evidence attachment are strictly blocked for `quarantined`, `pending_scan`, and `scan_failed` documents.
- **Privacy & Integrity:** Every upload records `file_sha256` and re-verifies checksums on download (`X-Content-Type-Options: nosniff`, `Cache-Control: no-store`). External AI document egress (`allow_external_ai=True`) is blocked (`403`) unless explicitly opted in and allowed by `ALLOW_EXTERNAL_AI_DOCUMENT_EGRESS`.

---

## 6. Logging, Monitoring & Controlled Pilot Environment

- **Structured Security Telemetry ([security_logging.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/app/core/security_logging.py)):** Emits structured JSON security events (`vault_upload`, `vault_quarantine`, `vault_presigned_url`, `vault_integrity_mismatch`, Clerk rejection notices) with automatic secret/JWT redaction.
- **Controlled Pilot Topology ([infra/pilot/](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/infra/pilot/README.md)):** Dedicated non-public Docker Compose stack (`127.0.0.1:18000` / `13000`), isolated `uniglobe_pilot` PostgreSQL database, mandatory `clamav_pilot` sidecar, Clerk staging configuration (mock auth prohibited), backup/restore drill commands, and 10 synthetic test scenarios.

---

## 7. Verification Summary & Remaining Pre-Pilot Risks

- **Executed Automated Tests After Final Edits:**
  - **`pytest -v` (`apps/api`):** **`106 / 106` passed** (`0` failed), including 5 comprehensive multi-case security tests in [test_phase4_3_security_hardening.py](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/apps/api/tests/test_phase4_3_security_hardening.py).
  - **`node --test` (`apps/web/src/lib/api-client.test.ts`):** **`13 / 13` passed** across all 10 locales incl. `ar-SA` RTL.
  - **Next.js Production Build (`pnpm build`):** **`16 / 16` routes** compiled cleanly with zero lint/type errors.
- **Remaining Infrastructure Validation Before Inviting Pilot Students:**
  1. Provision staging/pilot secrets in Secret Manager (`CLERK_ISSUER`, `CLERK_JWKS_URL`, R2/S3 credentials, `VAULT_SIGNING_SECRET`, `VAULT_ENCRYPTION_KEY`) and execute live synthetic end-to-end tests against real Clerk RS256 tokens and real R2/S3 bucket ACLs.
  2. Start `clamav_pilot` daemon in staging and verify live `EICAR` detection across the TCP `3310` boundary.
  3. Apply and verify kernel `egress-iptables.sh --apply` or Kubernetes `NetworkPolicy` on Linux staging/production worker hosts.
