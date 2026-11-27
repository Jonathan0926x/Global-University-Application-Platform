# UniGlobe — Pilot Go / No-Go Acceptance Report

**Assessment Date:** November 26, 2026  
**Platform Version:** Phase 4.4 (`main` after `c502f29`)  
**Decision Standard:** Security must be demonstrated in an integrated environment, never assumed from local unit mocks or unexecuted config files.

---

## 1. Executive Go / No-Go Recommendation

| Milestone Scope | Decision | Rationale |
|---|---|---|
| **Application & Code Security Readiness** | **CONDITIONAL PASS** | All 109 backend tests (`pytest`), 13 frontend unit tests, and 16 Next.js routes pass. Cryptographic RS256 JWKS auth, cross-student isolation (IDOR fixed), SSRF pinning, Document Vault scan gating, and fail-closed ClamAV policy are verified in code & local staging-mode integration tests. |
| **Live External Staging / Public Pilot Launch** | **NO-GO (Hold Pending 4 Live Infra Gates)** | This macOS workstation lacks Docker/Linux `iptables`, live Clerk tenant credentials, live R2/S3 bucket credentials, and a live `clamd` container. Zero live external infrastructure tests could be executed here; onboarding real students before those 4 live gates pass would violate UniGlobe's acceptance standard. |

---

## 2. Explicit `PASS` / `FAIL` / `NOT TESTED` Acceptance Matrix

| Security Gate | Scope / Layer | Outcome | Concrete Evidence / Blocker |
|---|---|---:|---|
| **Clerk RS256/JWKS Verification Logic** | Local Staging Integration | **PASS** | `ClerkAuthProvider` verified across RSA-2048 tokens, key rotation, wrong `iss`/`aud`/`exp`/`nbf`/`alg=none`/`HS256` (`test_43_jwt_jwks_*`, `test_44_e2e_staging_*`). |
| **Mock & Dev Fallback Blocked in Staging/Prod** | Local Staging Integration | **PASS** | `ENVIRONMENT="staging"` + `AUTH_PROVIDER="clerk"` returns `401` on omitted header & `dev_token`; `mock` provider raises `SecurityConfigurationError`. |
| **Live External Clerk Staging Tenant E2E** | Live Staging Infra | **NOT TESTED** | No live Clerk staging issuer or secret key provisioned on workstation. |
| **Student Isolation, IDOR & RBAC Enforcement** | Local Staging Integration | **PASS** | Student A/B, `data_verifier`, `admin` tested across Profiles/Enrollments, Vault, Applications, Counselor, `/admin/*` (`404`/`403`/`200`). |
| **Application SSRF & Alternate IP Defense** | Local Integration | **PASS** | 24 unsafe URLs (octal/hex/short/decimal/credentials/internal TLDs), 15 IP classes (IPv4/IPv6/CGNAT/NAT64/ULA/IMDS), DNS rebinding, `302 -> IMDS`, `trust_env=False` all verified. |
| **Linux Host `iptables` / K8s `NetworkPolicy`** | Live Staging Infra | **NOT TESTED** | `--dry-run` & YAML manifest pass, but macOS host lacks Linux kernel `iptables` & K8s cluster (`DOCKER_UNAVAILABLE`). |
| **Document Vault Validation & Quarantine Gates** | Local Staging Integration | **PASS** | `25 MB` limit, MIME/magic-byte checks, EICAR -> `quarantined`, retry blocked (`422`), excluded from Counselor (`counselor.py`), Requirements (`requirements_engine.py`), and Transfer (`articulation_engine.py`). |
| **ClamAV TCP Wire Protocol & Fail-Closed Policy** | Local Socket Integration | **PASS** | Real TCP `zINSTREAM\x00` daemon (`OK`, `FOUND`, timeout, garbage, refused) + `PolicyFailClosedScanner` prohibiting heuristic fallback in staging. |
| **Live `clamav/clamav` Container Daemon** | Live Staging Infra | **NOT TESTED** | Container runtime unavailable locally (`DOCKER_UNAVAILABLE`, `clamd not found`). |
| **S3 / R2 Encryption, SSE, ACL & `503` Failure Handling** | Local Mocked Contract | **PASS** | `S3CompatibleVaultStorageProvider` verified (`ACL=private`, `SSE=AES256`, pre-signed TTL, `503` fail-closed on put error, `DELETE /documents/{id}`). |
| **Live Cloudflare R2 / AWS S3 Bucket Test** | Live Staging Infra | **NOT TESTED** | No live staging bucket/credentials provisioned on workstation. |
| **Product Regression (10 Locales, RTL, Matching, Net Price)** | Full Test + Build | **PASS** | `109 / 109` pytest, `13 / 13` `node:test`, `16 / 16` Next.js production routes. |

---

## 3. Mandatory Steps to Transition from `NO-GO` to `GO` on Staging Host

Run these 4 exact validations on a Linux staging VM/cluster using [infra/pilot/docker-compose.pilot.yml](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/infra/pilot/docker-compose.pilot.yml) before opening a controlled pilot to real students:

1. **Provision Isolated Staging Secrets (via Secret Manager, never git):** Populate `.env.pilot` from [`.env.pilot.example`](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/infra/pilot/.env.pilot.example) with a real Clerk staging tenant (`CLERK_ISSUER`, `CLERK_AUDIENCE`), private R2/S3 bucket credentials, and high-entropy `VAULT_SIGNING_SECRET`.
2. **Enforce Outbound Firewall on Linux Staging Host:** Execute `sudo -E bash infra/firewall/egress-iptables.sh --apply` (or `kubectl apply -f infra/firewall/k8s-api-worker-egress-networkpolicy.yaml`) and run the `curl http://169.254.169.254/` block verification under the worker UID.
3. **Verify Live `clamav_pilot` & Private R2/S3 Bucket:** Start `docker compose -f infra/pilot/docker-compose.pilot.yml up -d`, upload a synthetic `.pdf` and an `EICAR` test `.txt` through the API authenticated with a real Clerk staging token, confirm `s3://...` private SSE upload + `scan_clean` pre-signed download + `EICAR` quarantine + public S3 URL `403 AccessDenied`.
4. **Record Outcomes & Re-Sign Checklist:** Update all four `NOT TESTED` rows in [PILOT_SECURITY_ACCEPTANCE_CHECKLIST.md](file:///Users/jonathangermain/.gemini/antigravity/scratch/Global-University-Application-Platform/docs/security/PILOT_SECURITY_ACCEPTANCE_CHECKLIST.md) with observed staging logs and re-issue a `GO` sign-off prior to inviting pilot cohort users.
