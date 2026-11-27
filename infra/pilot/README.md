# UniGlobe Controlled Pilot Environment & Runbook

This directory defines UniGlobe's **isolated, non-public staging/pilot topology**.  
**Rule:** Real students MUST NOT be onboarded until all items in [PILOT_SECURITY_ACCEPTANCE_CHECKLIST.md](../../docs/security/PILOT_SECURITY_ACCEPTANCE_CHECKLIST.md) show explicit validated `PASS`.

## Architecture & Controls
- **Isolated Database:** Uses dedicated `uniglobe_pilot` database (`postgres_pilot` on `pilot_internal` non-routable Docker network). Never connected to production data.
- **No Public Exposure:** `api_pilot` (`127.0.0.1:18000`) and `web_pilot` (`127.0.0.1:13000`) bind strictly to loopback, requiring VPN, Cloudflare Access, or SSH bastion authentication.
- **Real Authentication Enforced:** `ENVIRONMENT=staging` and `AUTH_PROVIDER=clerk` (attempting `mock` raises `SecurityConfigurationError`).
- **Malware Scanning Sidecar:** Dedicated `clamav_pilot` daemon (`CLAMAV_HOST=clamav_pilot:3310`) connected strictly over `pilot_internal`.
- **Private Encrypted Vault:** `STORAGE_PROVIDER=cloudflare_r2` (or `s3`) with private ACL, SSE encryption, and short-lived pre-signed URLs.

## Synthetic Pilot E2E Validation Scenarios (Run Against Synthetic Test Accounts Only)
1. **Student Registration & Login:** Authenticate synthetic pilot user via Clerk test tenant RS256 JWT; confirm auto-provisioned `User` with `role="student"`.
2. **Profile Creation:** `POST /api/v1/profile` initializes synthetic Haitian first-year / CC transfer profile.
3. **Academic Credential Upload:** Upload clean `.pdf` transcript; confirm SHA-256 checksum, encrypted private storage, and extraction without public URL exposure.
4. **Document Malware Scanning:** Upload EICAR test string -> verify automatic `quarantined` state, download blocked (`422`), extraction/translation blocked (`422`).
5. **Scholarship Matching:** `POST /api/v1/financial/scholarships/match` returns deterministic results with 10-locale reason codes and closed-cycle guards.
6. **Counselor Interactions:** `POST /api/v1/counselor/chat` grounds answers in verified citations with external portal non-submission policy.
7. **Application Portal Redirects:** `POST /api/v1/applications/{id}/redirect` transitions to `redirected_to_external_portal`, never `submission_confirmed`.
8. **Profile Access Restrictions:** Second synthetic Clerk account receives `404` on User 1's enrollments/courses, documents, applications, and counselor conversations.
9. **Logout & Token Expiration:** Expired JWT (`exp < now`) rejected with `401 Unauthorized`.
10. **Unauthorized Endpoint Access:** Student role attempting `/api/v1/admin/*` or self-confirming submission receives `403 Forbidden`.

## Backup & Recovery Procedure
1. **Encrypted Database Backup (Daily Cron):**
   ```bash
   docker exec uniglobe_postgres_pilot pg_dump -U uniglobe_pilot -Fc uniglobe_pilot \
     | gpg --batch --yes --symmetric --cipher-algo AES256 -o /secure/backups/pilot_$(date +%F).dump.gpg
   ```
2. **Database Restore Verification (Weekly Restore Drill into Scratch DB):**
   ```bash
   gpg -d /secure/backups/pilot_latest.dump.gpg | pg_restore -U uniglobe_pilot -d uniglobe_pilot_verify --clean --if-exists
   ```
3. **Vault Object Storage Versioning:** Enable R2/S3 bucket versioning + Object Lock governance mode and restrict IAM credentials to `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` (for quarantine moves only) on the pilot prefix.
