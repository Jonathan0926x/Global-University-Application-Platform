# Production Readiness Audit — Phase 3 Milestones 1–7.2

**Date:** November 25, 2026

**Baseline:** `2fcae16` (`main`, initially clean and synchronized with `origin/main`)
**Scope:** Review of the seven reported completed milestones and the M7.1/M7.2 roadmap/progress claims, with focused code review of routing health, verification eligibility, evidence access, and the live `/applications` and `/operations` journeys. This is a targeted readiness audit, not a full penetration test or independent revalidation of all prior milestone claims.

## Findings and disposition

| Priority | Finding | Disposition |
|---|---|---|
| P0 | Health checks followed redirects automatically after validating only the initial URL. A redirect could send the checker to a private destination. | Fixed: reject DNS resolutions containing non-public addresses and disable automatic redirect following. Redirects are recorded for review without fetching the next destination. |
| P1 | Expired routes and routes with unverified applicant pathways could still be returned as verified student recommendations until an administrator ran the expiry sweep. | Fixed: recommendation resolution immediately excludes expired or pathway-unverified routes. |
| P1 | A route remained recommendable after its latest health check was unreachable, errored, or required redirect review. | Fixed: those states are now excluded from verified recommendations pending review. |
| P1 | Audit models describe route and evidence audit rows as immutable, but the schema has cascading parent deletes and no database trigger preventing row updates/deletes. | Fixed (`d8f2a9b41e03`): PostgreSQL `BEFORE INSERT` + `BEFORE UPDATE OR DELETE` triggers enforce append-only retention on `application_route_audits`, `application_status_history`, and `evidence_review_audits`, switching parent FKs to `ON DELETE SET NULL` while preserving `retained_*_id` and `parent_deleted_at`. Reversible migration verified (`upgrade -> downgrade -> upgrade`). |
| P1 | The link checker performs a DNS safety check before the HTTP client resolves the host again. A DNS-rebinding race is therefore still possible without network egress controls or IP pinning. | Fixed: `_PinnedPublicIPBackend(httpcore.SyncBackend)` enforces connection-time DNS validation and pins TCP sockets directly to validated public IP addresses (blocking loopback/private/link-local/IPv4-mapped IPv6 and `trust_env=False` proxies) while preserving TLS SNI. Automated hourly expiry sweeps (`ENABLE_AUTOMATED_EXPIRY_SWEEPS`) also run via FastAPI `lifespan`. |
| P2 | `/operations` remains English in Arabic mode, while `/applications` translates its primary controls and switches to RTL. | Fixed: localized `/operations` across all 10 languages including Arabic (`ar-SA`) RTL, added ARIA `tablist`/`tab`/`tabpanel`, `aria-pressed`, `role="status"`/`role="alert"`, explicit `htmlFor` label bindings, and keyboard navigation checks. |

The evidence review endpoints use `admin`/`data_verifier` role checks. Student evidence operations inspected in this pass are scoped to owned applications and owned Document Vault documents. This source review did not constitute a full authorization penetration test across every API route.

## Verification

- Initial Git state: `main` at `d4111c6` (building on `2fcae16`); `origin/main` synchronized.
- Migration reversibility: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` verified for `d8f2a9b41e03`.
- Backend: **54 passed** across the complete pytest suite (`test_audit_retention.py` covering DB triggers, safe parent deletion retention, pinned-IP anti-rebinding, automated expiry sweep, cross-profile evidence isolation, and controlled E2E upload/reject/re-upload/accept/delete).
- Frontend unit tests: **11 passed** (`src/lib/api-client.test.ts` including `ops.*` multilingual checks).
- Production frontend build: succeeded; **14/14** routes generated.
- Live browser: `/operations` switched cleanly to Arabic (`ar-SA`, `dir="rtl"`), passed keyboard Tab/ARIA checks, showed `14` pending + `1` manually reviewed routes and `Auto Expiry Sweep: ON`, and completed a controlled E2E upload → reject → re-upload → accept (`submission_confirmed`) → disposable cleanup (`DELETE` retained 4 immutable `evidence_review_audits` rows).

## Remaining / Follow-On Operations Hardening

- Configured production outbound firewall artifacts in `infra/firewall/` (`egress-iptables.sh`, `k8s-api-worker-egress-networkpolicy.yaml`, `docker-compose.prod.yml`) blocking RFC1918 private ranges, loopback, CGNAT, link-local, IPv6 private/mapped ranges, and cloud metadata `169.254.169.254/32` as infrastructure defense-in-depth alongside `_PinnedPublicIPBackend`. Apply the script/NetworkPolicy to target production clusters during deployment.

The fixes in this audit preserve the rule that an external redirect is not proof of submission. Only accepted supporting evidence can produce `submission_confirmed`.
