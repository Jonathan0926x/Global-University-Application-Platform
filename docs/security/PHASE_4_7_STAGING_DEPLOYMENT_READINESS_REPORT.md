# UniGlobe — Phase 4.7 Staging Deployment Readiness Audit Report

**Date:** November 26, 2026  
**Baseline Audited:** `main` (`b50370a`, Alembic head `a3c7e9f1b420`) -> Hardened in Phase 4.7  
**Target Environment:** Isolated Ubuntu 24.04 Linux Staging Host (Docker Compose) behind SSH Bastion / Private Tunnel  
**Provisioning Status:** **Zero external resources provisioned or purchased**  
**Staging Readiness Verdict:** **`READY FOR INFRASTRUCTURE AUTHORIZATION`** *(manifest/firewall defects remediated locally)*  
**Pilot Launch Verdict:** **`NO-GO`** *(Gates A–D and live 12-step E2E remain `NOT TESTED` until provisioned staging execution completes)*

---

## 1. Executive Summary & Readiness Decision

A full static and operational audit of `infra/pilot/`, `infra/firewall/`, Next.js/FastAPI build integration, Document Vault storage/malware controls, and database migration ordering uncovered **six concrete deployment defects** that would have caused staging build failures, SSR/CORS breakage, broken Docker DNS under host firewall rules, or silent degraded healthchecks on a clean Linux host.

Every defect was fixed locally without weakening any security control:

| Defect Found During Audit | Root Cause | Phase 4.7 Fix Applied |
|---|---|---|
| **Missing workspace package & wrong filter in `Dockerfile.web`** | `apps/web/package.json` depends on `@platform/tsconfig` (`workspace:*`) and has name `@platform/web`, but `Dockerfile.web` omitted `packages/tsconfig`, passed `--filter web...`, overwrote `/app/node_modules` symlinks during runner copy, and used `npx next start`. | Pinned `pnpm@12.23.0`, copied `packages/tsconfig`, fixed `--filter @platform/web...`, preserved `/app/node_modules` + `/app/apps/web`, added `NEXT_PUBLIC_*` build `ARG`s, and switched entrypoint to `./node_modules/.bin/next start`. |
| **Missing `.dockerignore`** | No root `.dockerignore` existed, risking inclusion of `.git`, `.env*`, local `data/vault/`, `node_modules/`, and `tests/` in image contexts. | Added root [`.dockerignore`](../../.dockerignore) excluding `.git`, `.env*`, `data/`, caches, build outputs, `docs/`, and test directories. |
| **Hardcoded Next.js rewrite destination & staging CORS gap** | `apps/web/next.config.ts` hardcoded `http://127.0.0.1:8000/api/v1/:path*` (broken inside `web_pilot`), and `CORS_ORIGINS` defaulted only to port `3000`, omitting `127.0.0.1:13000`. | Updated `apps/web/next.config.ts` to honor `INTERNAL_API_URL=http://api_pilot:8000/api/v1`, aligned `.next/cache` tmpfs to `/app/apps/web/.next/cache`, and added `CORS_ORIGINS` + `NEXT_PUBLIC_*` defaults to `infra/pilot/.env.pilot.example`. |
| **Degraded API healthcheck accepted as healthy** | `/api/v1/health` returns HTTP `200` even when `"status": "degraded"` on DB errors; `api_pilot` healthcheck only checked `urlopen(...)` HTTP status. | Updated `api_pilot` healthcheck in `docker-compose.pilot.yml` to parse JSON and exit `1` unless `data.get("status") == "healthy"`. Also hardened `migrate_pilot` (`read_only`, `cap_drop: ALL`, `tmpfs`, resource limits) and set explicit CPU/memory limits on all services. |
| **Docker DNS & IPv6 `DOCKER-USER` gaps in `egress-iptables.sh`** | `127.0.0.0/8` rejection blocked Docker embedded DNS `127.0.0.11:53` when `DOCKER_EGRESS_BRIDGE` was set; `ip6tables` lacked `DOCKER-USER` attachment and pre-flight root/chain validation ran only after chain creation/flushing. | Added `preflight_live` checks (`EUID`, `iptables`/`ip6tables`, `DOCKER-USER` presence), explicitly allowed `127.0.0.11:53` UDP/TCP before `BLOCKED_IPV4_CIDRS` when `DOCKER_EGRESS_BRIDGE` is set, and attached `ip6tables` `DOCKER-USER` filtering. |
| **Relative URL & redirect handling in `verify_staging_gates.py`** | Download probe used top-level `httpx.get` instead of the isolated `follow_redirects=False, trust_env=False` client and failed to verify `is_encrypted=True` or handle relative local URLs. | Updated `verify_staging_gates.py` to enforce `is_encrypted is True` and reuse the non-redirecting, proxy-isolated `httpx.Client`. |

---

## 2. Docker & Container Security Audit

Audited files: [`Dockerfile.api`](../../infra/pilot/Dockerfile.api), [`Dockerfile.web`](../../infra/pilot/Dockerfile.web), [`docker-compose.pilot.yml`](../../infra/pilot/docker-compose.pilot.yml), [`.dockerignore`](../../.dockerignore).

| Service | Non-Root User | Root FS Read-Only | Dropped Caps & `no-new-privileges` | Networks | Exposed Ports | Resource Limits | Security Posture & Justified Exceptions |
|---|---|---|---|---|---|---|---|
| **`api_pilot`** | `10001:10001` (`uniglobe`) | Yes (`tmpfs`: `/tmp` `64m`, `noexec,nosuid`) | `cap_drop: ALL`, `no-new-privileges:true` | `pilot_internal`, `pilot_public_egress` | `127.0.0.1:18000:8000` | `768M` / `1.0 CPU` | Strictly loopback-bound; no Docker socket mounted; Python bytecode disabled (`PYTHONDONTWRITEBYTECODE=1`). |
| **`migrate_pilot`** | `10001:10001` (`uniglobe`) | Yes (`tmpfs`: `/tmp` `64m`, `noexec,nosuid`) | `cap_drop: ALL`, `no-new-privileges:true` | `pilot_internal` | None | `512M` / `0.5 CPU` | One-shot `alembic upgrade head` (`restart: "no"`); exits after DB migration; never exposed externally. |
| **`web_pilot`** | `10001:10001` (`uniglobe`) | Yes (`tmpfs`: `/tmp`, `/app/apps/web/.next/cache` `64m`, `noexec,nosuid`) | `cap_drop: ALL`, `no-new-privileges:true` | `pilot_internal` | `127.0.0.1:13000:3000` | `512M` / `0.75 CPU` | Runs `./node_modules/.bin/next start` as `10001`; proxies `/api/backend/*` internally to `http://api_pilot:8000/api/v1/*`. |
| **`postgres_pilot`** | Upstream `postgres` (`999`) | **Exception** (`pgdata_pilot` writable) | `no-new-privileges:true` | `pilot_internal` (`internal: true`) | None | `768M` / `1.0 CPU` | **Justified exception:** upstream `pgvector/pgvector:pg16` initializes sockets/WAL inside `/var/lib/postgresql/data` and `/var/run/postgresql`; isolated from internet egress via `internal: true`. |
| **`clamav_pilot`** | Upstream `/init` -> `clamav` | **Exception** (`clamav_db_pilot` + runtime sockets writable) | `no-new-privileges:true` | `pilot_internal` (`internal: true`) | None | `2048M` / `1.0 CPU` | **Justified exception:** `clamav/clamav:stable` writes signature databases (`/var/lib/clamav`), Unix/TCP runtime state, and drops privileges from its `/init` supervisor. **Exception note:** signature updates (`freshclam`) inside `internal: true` cannot reach ClamAV CDN unless operator seeds/updates signatures via temporary host volume sync or sidecar maintenance window — document this during initial boot. |

> [!NOTE]
> **ClamAV `freshclam` + `pilot_internal` Operational Detail:** Because `clamav_pilot` sits strictly on `pilot_internal` (`internal: true`), initial signature bootstrap or daily signature refreshes cannot open outbound HTTP connections from inside `clamav_pilot`. Either pre-seed `clamav_db_pilot` on first provision or run a controlled one-shot `freshclam` container attached to an egress-permitted update job into the shared `clamav_db_pilot` volume before relying on live virus definitions.

---

## 3. Network Enforcement & Firewall Audit

Audited files: [`egress-iptables.sh`](../../infra/firewall/egress-iptables.sh), [`k8s-api-worker-egress-networkpolicy.yaml`](../../infra/firewall/k8s-api-worker-egress-networkpolicy.yaml), [`docker-compose.pilot.yml`](../../infra/pilot/docker-compose.pilot.yml).

1. **Docker Bridge Segmentation:** `pilot_internal` (`internal: true`) has no default gateway to the internet, isolating `postgres_pilot`, `clamav_pilot`, `migrate_pilot`, and `web_pilot`. Only `api_pilot` attaches to `pilot_public_egress` (`br-uniglobe-pilot-egress`).
2. **Kernel Egress Rules (`UNIGLOBE_API_EGRESS` / `UNIGLOBE_API_EGRESS_V6`):**
   - **Verified `--dry-run` behavior (after Phase 4.7 hardening):** Emits `conntrack ESTABLISHED,RELATED ACCEPT`, Docker embedded DNS `127.0.0.11:53` UDP/TCP `ACCEPT` (only when `DOCKER_EGRESS_BRIDGE` is set, ordered BEFORE `127.0.0.0/8`), explicit `REJECT` on `169.254.169.254/32`, `169.254.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `100.64.0.0/10`, `0.0.0.0/8`, `224.0.0.0/4`, `240.0.0.0/4`, plus IPv6 `::1/128`, `fe80::/10`, `fc00::/7`, `ff00::/8`, and IPv4-mapped metadata/RFC1918/loopback ranges. Permits only outbound TCP `443` and `80`, then `DROP`.
   - **Pre-flight Fail-Safe (`--apply` / `--verify`):** Fails cleanly prior to modifying any chain if non-root, missing `iptables`/`ip6tables`, or if `DOCKER_EGRESS_BRIDGE` is set before Docker has created `DOCKER-USER`.
   - **Remaining Live Gap (Gate B):** Cannot execute kernel packet tests on macOS host. Live Linux verification must confirm: (a) `docker compose up -d` creates `br-uniglobe-pilot-egress` and `DOCKER-USER` *before* running `egress-iptables.sh --apply`, (b) `curl http://169.254.169.254/` inside `api_pilot` fails/rejects, (c) external HTTPS (`https://api.clerk.com` / R2 endpoint) succeeds, and (d) host `systemd` unit (`After=docker.service` + `Requires=docker.service`) re-applies `egress-iptables.sh --apply` cleanly across host reboots and Docker daemon restarts.

---

## 4. Document Vault Scanning & Private Storage Audit

Audited files: [`document_vault.py`](../../apps/api/app/services/document_vault.py), [`documents.py`](../../apps/api/app/api/v1/documents.py).

- **Upload Validation & Integrity:** Enforces `VAULT_MAX_UPLOAD_SIZE_BYTES` (`25 MB`), filename sanitization, blocked executable extensions/binary magic headers, strict extension/MIME/magic-byte signature validation (`%PDF-`, PNG, JPEG, DOCX `PK`, UTF-8 non-null text), and pre-storage `SHA-256` computation (`file_sha256`), re-verified on download (`500` on mismatch).
- **Private Encrypted Object Storage (`S3CompatibleVaultStorageProvider`):**
  - `put_bytes()` passes `ACL="private"` and `ServerSideEncryption="AES256"` (or `aws:kms` when `STORAGE_KMS_KEY_ID` is set). Returns `s3://...` or `cloudflare_r2://...` without exposing public URLs. Write failure aborts upload with HTTP `503` fail-closed.
  - `generate_presigned_download_url()` enforces clamped TTL (`30–900` seconds, default `300`) and attachment `Content-Disposition`.
  - `delete_document()` calls `provider.delete_bytes(...)` prior to `db.delete(doc)`.
  - **Operator Bucket Compatibility Note:** AWS S3 buckets created with the newer default `BucketOwnerEnforced` setting (ACLs disabled) reject `ACL="private"` on `PutObject` / `CopyObject`. During Gate C provisioning, use **Cloudflare R2** (primary recommendation, tolerates S3 `ACL="private"` and `$0` egress) or configure any AWS S3 staging bucket with **Block Public Access ON + Object Ownership = `BucketOwnerPreferred`** (`ACLs enabled` private-only), OR evaluate removing `ACL` if standardizing solely on `BucketOwnerEnforced` IAM policies later.
- **ClamAV Scanning & Quarantine Gating:**
  - `get_malware_scanner()` returns `PolicyFailClosedScanner` whenever `ENVIRONMENT` is `staging`/`production` and `SCANNER_BACKEND != "clamav"`.
  - `ClamAVScanner` streams bytes over TCP (`CLAMAV_HOST:CLAMAV_PORT`, `zINSTREAM\x00`), returning `scan_failed` if unreachable/malformed and `scan_infected` -> `quarantined` on `FOUND`.
  - `move_to_quarantine()` copies object under `quarantine/{profile_id}/...` with private SSE and removes the original key.
  - `assert_document_accessible()` blocks download (`presigned-url`, `/download`), AI extraction/translation, counselor access, requirements matching, and transfer attachment (`422` for quarantined/infected, `409` for `pending_scan`/`scan_failed`), and `POST /documents/{id}/rescan` rejects quarantined files (`422`).
- **Remaining Live Gap (Gates C & D):** Requires live private R2/S3 bucket CORS/Public-Access `403` verification and live `clamav_pilot` TCP `3310` signature load + EICAR scan on Linux.

---

## 5. Auth, Startup Ordering & Database Migration Lifecycle

Audited files: [`auth_provider.py`](../../apps/api/app/core/auth_provider.py), [`main.py`](../../apps/api/app/main.py), [`health.py`](../../apps/api/app/api/v1/health.py), [`a3c7e9f1b420_phase4_3_document_vault_security.py`](../../apps/api/alembic/versions/a3c7e9f1b420_phase4_3_document_vault_security.py).

- **Fail-Closed Auth & JWKS:** `get_auth_provider()` raises `SecurityConfigurationError` in `staging`/`production` if `AUTH_PROVIDER != "clerk"`. `MockAuthProvider.verify_token()` independently returns `None` if `_is_production_like()`. `ClerkAuthProvider` enforces asymmetric RSA (`RS256` default), `kid` presence, SSRF-pinned `JWKSKeyCache`, controlled unknown-`kid` refresh rate-limiting (`10s` min interval), and `sub`/`exp`/`nbf`/`iat`/`iss` checks with optional `aud`.
- **Container Startup Sequence:**
  1. `postgres_pilot` starts on `pilot_internal` and passes `pg_isready` (`uniglobe_pilot`).
  2. `migrate_pilot` runs `alembic upgrade head` (to `a3c7e9f1b420`) under UID `10001`, read-only FS; exits `0`.
  3. `clamav_pilot` loads signatures and passes `clamdcheck.sh` (`start_period: 120s`, `2048M` limit).
  4. `api_pilot` starts ONLY after `migrate_pilot` exits `0` (`service_completed_successfully`) and `clamav_pilot` is `healthy`. Healthcheck now verifies JSON `"status" == "healthy"` (`SELECT 1` DB check).
  5. `web_pilot` starts ONLY after `api_pilot` is `healthy`.
- **Migration Rollback Safety:** Verified `a3c7e9f1b420` implements complete `downgrade()` removing the index and all 9 Document Vault security columns cleanly. Operator pre-migration backup (`pg_dump -Fc`) and rollback command (`alembic downgrade f1c9e4a2b870` or `pg_restore`) are documented in the authorization checklist.

---

## 6. Complete Staging Environment Variable & Secrets Inventory

Template file: [`infra/pilot/.env.pilot.example`](../../infra/pilot/.env.pilot.example)

| Variable | Classification | Required Value / Format (Staging) | Storage / Injection Rule |
|---|---|---|---|
| `ENVIRONMENT` | Non-secret Config | `staging` (prohibits Mock Auth & Heuristic Scanner) | Host `.env.pilot` (`0600`, gitignored) |
| `PROJECT_NAME` | Non-secret Config | `"UniGlobe Pilot (Controlled Staging)"` | `.env.pilot` |
| `NEXT_PUBLIC_APP_URL` | Build-time Public | `http://127.0.0.1:13000` (or private staging tunnel origin) | Compose `build.args` + `.env.pilot` |
| `NEXT_PUBLIC_API_URL` | Build-time Public | `http://127.0.0.1:18000/api/v1` (or private tunnel API URL) | Compose `build.args` + `.env.pilot` |
| `INTERNAL_API_URL` | Internal Service URL | `http://api_pilot:8000/api/v1` (set in Compose env) | `docker-compose.pilot.yml` |
| `CORS_ORIGINS` | Non-secret Config | `["http://127.0.0.1:13000","http://localhost:13000"]` | `.env.pilot` |
| `AUTH_PROVIDER` | Security Config | `clerk` | `.env.pilot` |
| `ALLOW_DEV_MOCK_DEFAULT_USER` | Security Config | `false` | `.env.pilot` |
| `CLERK_ISSUER` | Internal Config | `https://<staging-domain>.clerk.accounts.dev` | `.env.pilot` |
| `CLERK_JWKS_URL` | Internal Config | `https://<staging-domain>.clerk.accounts.dev/.well-known/jwks.json` | `.env.pilot` |
| `CLERK_AUDIENCE` | Security Config | `uniglobe-pilot-api` (or omit only if intentional per token template) | `.env.pilot` |
| `CLERK_ACCEPTED_ALGORITHMS` | Security Config | `RS256` | `.env.pilot` |
| `CLERK_JWKS_CACHE_TTL_SECONDS`, `CLERK_CLOCK_SKEW_SECONDS`, `CLERK_MAX_IAT_AGE_SECONDS` | Security Config | `3600`, `30`, `86400` | `.env.pilot` |
| `CLERK_SECRET_KEY` | **HIGH-SENSITIVITY SECRET** | Dedicated staging `sk_test_...` | Secret manager -> `.env.pilot` (`0600`) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Build-time Staging Key | Dedicated staging `pk_test_...` | Compose `build.args` + `.env.pilot` |
| `POSTGRES_DB`, `POSTGRES_USER` | Internal Config | `uniglobe_pilot`, `uniglobe_pilot` | `.env.pilot` |
| `POSTGRES_PASSWORD`, `DATABASE_URL` | **HIGH-SENSITIVITY SECRET** | 32+ char random password; `postgresql://uniglobe_pilot:<pw>@postgres_pilot:5432/uniglobe_pilot` | `.env.pilot` (`0600`); **never prod DB** |
| `STORAGE_PROVIDER`, `STORAGE_BUCKET_NAME`, `STORAGE_REGION`, `STORAGE_ENDPOINT` | Internal Config | `cloudflare_r2` (or `s3`), `uniglobe-pilot-vault-private`, `auto`, `https://<acct>.r2.cloudflarestorage.com` | `.env.pilot` |
| `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY` | **HIGH-SENSITIVITY SECRET** | Bucket-scoped staging R2/IAM keys (`PutObject`, `GetObject`, `DeleteObject`) | `.env.pilot` (`0600`) |
| `STORAGE_KMS_KEY_ID` | Optional Config | AWS KMS ARN (only if `STORAGE_PROVIDER=s3` with CMK) | `.env.pilot` |
| `VAULT_SIGNING_SECRET` | **HIGH-SENSITIVITY SECRET** | 64-char `secrets.token_hex(32)` | `.env.pilot` (`0600`) |
| `VAULT_ENCRYPTION_KEY` | Optional Secret | Fernet key (required only if falling back to local storage) | `.env.pilot` (`0600`) |
| `VAULT_PRESIGNED_TTL_SECONDS`, `VAULT_MAX_UPLOAD_SIZE_BYTES` | Security Config | `300`, `26214400` | `.env.pilot` |
| `SCANNER_BACKEND`, `CLAMAV_HOST`, `CLAMAV_PORT`, `CLAMAV_TIMEOUT_SECONDS`, `DOCUMENT_ASYNC_SCAN`, `ALLOW_EXTERNAL_AI_DOCUMENT_EGRESS` | Security Config | `clamav`, `clamav_pilot`, `3310`, `10`, `false`, `false` | `.env.pilot` |
| `ENABLE_AUTOMATED_EXPIRY_SWEEPS`, `ROUTE_EXPIRY_SWEEP_INTERVAL_SECONDS` | Runtime Config | `true`, `3600` | `.env.pilot` |
| `SENTRY_DSN` | Internal Secret/Config | Isolated staging DSN | `.env.pilot` |

---

## 7. Final Decisions

1. **Staging Infrastructure Authorization Readiness:** **`READY FOR INFRASTRUCTURE AUTHORIZATION`** — all container, monorepo workspace build, Next.js rewrite, CORS, healthcheck, firewall DNS/IPv6/pre-flight, and smoke-script gaps have been identified and fixed locally.
2. **Controlled Pilot Launch Status:** **`NO-GO`** — remains locked until the authorized staging infrastructure is provisioned, all four external gates (Clerk staging, Linux firewall, private R2/S3 bucket, live `clamav_pilot`) pass live tests, and the 12-step staging E2E workflow succeeds with real observed logs.
