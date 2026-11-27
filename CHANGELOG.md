# Changelog

All notable changes to the **Global University Application Platform** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] - Phase 4 Active

### Planned & Manifest-Hardened — Phase 4.6: Isolated Staging Infrastructure Plan & Validation Gate Readiness
- **Minimum Viable Staging Blueprint (`docs/security/PHASE_4_6_STAGING_INFRASTRUCTURE_PLAN.md`):**
  - Evaluated single hardened Linux VM (`2 vCPU / 4 GB RAM` + Docker Compose) vs. managed Kubernetes, and Cloudflare R2 vs. AWS S3 under zero-spend authorization rules, recommending Ubuntu 24.04 VM + Cloudflare R2 + free-tier Clerk staging tenant + `clamav/clamav:stable` sidecar (`2048M` limit).
- **Reproducible Staging Containers & Firewall Hardening (`infra/pilot/`, `infra/firewall/egress-iptables.sh`):**
  - Added multi-stage non-root (`UID 10001`) `Dockerfile.api` & `Dockerfile.web`, added automatic `migrate_pilot` (`alembic upgrade head`) init container & `web_pilot` read-only/capability-drop hardening in `docker-compose.pilot.yml`, added `DOCKER_EGRESS_BRIDGE` (`DOCKER-USER` chain) support to `egress-iptables.sh`, and added non-destructive `verify_staging_gates.py`.
- **Phase 4.6 Validation Report (`PHASE_4_6_LIVE_SECURITY_VALIDATION_REPORT.md`):**
  - Separated Local Code & Integration (`PASS`: `109` pytest / `13` web / `16` Next.js routes) from Live Infrastructure Validation (`NOT TESTED` for Gates A–D awaiting staging VM & test credentials), retaining an explicit **`NO-GO`** pilot launch recommendation.

### Audited — Phase 4.5: Live Infrastructure Validation & Security Gate Closure Assessment
- **Prerequisite & Reachability Audit (`PHASE_4_5_LIVE_INFRASTRUCTURE_VALIDATION_REPORT.md`, `PILOT_SECURITY_ACCEPTANCE_CHECKLIST.md`):**
  - Verified baseline `a0aa2e0` (`main`, clean working tree, Alembic head `a3c7e9f1b420`) on macOS `Darwin 25.6.0 ARM64`.
  - Documented exact missing external infrastructure prerequisites (`docker`/`kubectl`/`clamd`/`aws`/`clerk` CLI missing; zero `CLERK_*`, `STORAGE_*`, or `CLAMAV_*` staging credentials provisioned) cleanly keeping Gates A–D strictly **`NOT TESTED`** in live infrastructure without conflating local integration tests (`109` pytest / `13` web / `16` Next.js routes) with live staging passes.
  - Maintained honest **`NO-GO`** pilot launch status alongside concrete staging execution runbooks for Clerk staging tenant, Linux `iptables`/K8s `NetworkPolicy`, private R2/S3 bucket, and `clamav/clamav` daemon validation.

### Validated & Audited — Phase 4.4: Staging Validation, ClamAV Fail-Closed Gates & Pilot Go/No-Go Assessment
- **Security Scan Gating & Retry Safety ([document_vault.py](apps/api/app/services/document_vault.py), [documents.py](apps/api/app/api/v1/documents.py), [counselor.py](apps/api/app/services/counselor.py), [requirements_engine.py](apps/api/app/services/requirements_engine.py), [articulation_engine.py](apps/api/app/services/articulation_engine.py)):**
  - Enforced `PolicyFailClosedScanner` when `ENVIRONMENT` is `staging`/`production` and `SCANNER_BACKEND != "clamav"`, preventing silent fallback to `HeuristicMalwareScanner`.
  - Restricted AI Counselor vault ingestion, Requirements Engine document matching, and Transfer Syllabus attachment strictly to `scan_status == "scan_clean"` documents.
  - Added `POST /api/v1/documents/{document_id}/rescan` (forbidding release of `quarantined`/`scan_infected` documents with `422`, while allowing clean recovery from transient `scan_failed`), `DELETE /api/v1/documents/{document_id}` storage cleanup, and `503` fail-closed handling on storage write failures.
- **Integrated Staging Simulation & Adversarial Security Tests ([test_phase4_4_staging_validation_and_adversarial.py](apps/api/tests/test_phase4_4_staging_validation_and_adversarial.py)):**
  - Verified full synthetic Student A/B, Data Verifier, and Admin workflows under `ENVIRONMENT="staging"`, `AUTH_PROVIDER="clerk"`, `SCANNER_BACKEND="clamav"` using RS256 JWTs and an in-process localhost TCP `zINSTREAM\x00` ClamAV socket server (`OK`, `EICAR FOUND`, timeout, malformed reply), redirect `302 -> 169.254.169.254` non-following, and proxy env ignoring (`trust_env=False`).
- **Pilot Go/No-Go Acceptance Documentation (`docs/security/`):**
  - Published [PHASE_4_4_STAGING_VALIDATION_REPORT.md](docs/security/PHASE_4_4_STAGING_VALIDATION_REPORT.md) and [PILOT_GO_NO_GO_REPORT.md](docs/security/PILOT_GO_NO_GO_REPORT.md): **Conditional Code Security PASS (`109 / 109` backend tests, `13 / 13` frontend tests, `16 / 16` built routes)**; **NO-GO for live student onboarding** pending live Linux/staging execution of the 4 external infrastructure gates (Clerk staging tenant, kernel `iptables`/K8s policy, live R2/S3 bucket, live `clamd` daemon).

### Hardened & Verified — Phase 4.3: Production Security Hardening & Controlled Pilot Readiness
- **Genuine Clerk RS256 JWKS Authentication ([auth_provider.py](apps/api/app/core/auth_provider.py), [deps.py](apps/api/app/api/deps.py), [config.py](apps/api/app/config.py)):**
  - Eliminated the `clerk_verified_user` placeholder stub and implemented genuine cryptographic RS256 verification via `PyJWT` + `cryptography` with SSRF-pinned `JWKSKeyCache`, controlled key-rotation refresh on unknown `kid`, strict algorithm allowlisting (blocking `none` and `HS256` key-confusion attacks), `iss`/`aud`/`exp`/`nbf`/`iat`/`sub` validation, and zero raw JWT logging.
  - Enforced fail-closed behavior (`SecurityConfigurationError` when `AUTH_PROVIDER != "clerk"` in `staging`/`production`, and removal of unauthenticated `dev_token` fallback outside explicit local dev/test mock mode).
- **Authorization & IDOR Remediation ([profiles.py](apps/api/app/api/v1/profiles.py)):**
  - Fixed a cross-student IDOR gap in `POST /api/v1/profile/enrollments/{enrollment_id}/courses` by enforcing `EnrollmentRecord.profile_id == profile.id` derived strictly from authenticated `current_user.id`, alongside ignoring client-supplied `profile_completion_pct` on `PATCH /profile`.
- **SSRF & Firewall Deployment Hardening ([routing_seed.py](apps/api/app/ingestion/routing_seed.py), [routing_health.py](apps/api/app/services/routing_health.py), `infra/firewall/PRODUCTION_DEPLOYMENT_CHECKLIST.md`):**
  - Blocked octal/hex/short IPv4 notations (`socket.inet_aton`), trailing-dot hosts, embedded credentials, `.internal`/`.local`/`.arpa` hostnames, CGNAT (`100.64.0.0/10`), NAT64 (`64:ff9b::/96`), IPv6 ULA/IMDS (`fc00::/7`), and strict DNS-pinned IP intersection in `_PinnedPublicIPBackend`. Added production firewall deployment and rollback runbook.
- **Document Vault Encryption, Scanning & Pre-Signed Access (Migration `a3c7e9f1b420`, [document_vault.py](apps/api/app/services/document_vault.py), [documents.py](apps/api/app/api/v1/documents.py), [applications.py](apps/api/app/api/v1/applications.py), [transfer.py](apps/api/app/api/v1/transfer.py), [operations.py](apps/api/app/api/v1/operations.py)):**
  - Added `25 MB` max upload guard, path-traversal blocking, executable/double-extension rejection, MIME & magic-byte validation, local Fernet encryption at rest, `S3CompatibleVaultStorageProvider` (AWS S3 / Cloudflare R2 SSE + private ACL), `GET /documents/{id}/presigned-url` + `/download` with HMAC expiry and SHA-256 integrity checks, malware scanner abstraction (`ClamAVScanner` TCP `zINSTREAM` + EICAR quarantine workflow gating extraction/translation/evidence/syllabus), external AI privacy guard, and structured JSON security logging (`security_logging.py`).
- **Controlled Pilot Readiness & Security Documentation (`infra/pilot/`, `docs/security/`):**
  - Created isolated non-public pilot configuration (`infra/pilot/.env.pilot.example`, `docker-compose.pilot.yml`, `README.md`), `PHASE_4_3_SECURITY_HARDENING_REPORT.md`, and `PILOT_SECURITY_ACCEPTANCE_CHECKLIST.md`.
- **Verification Matrix:** Passed **106 / 106** backend `pytest` tests (`test_phase4_3_security_hardening.py`), **13 / 13** frontend unit tests (`api-client.test.ts`), and **16 / 16** static Next.js production routes.

### Added & Verified — Phase 4.2: Global Scholarship Intelligence, Multilingual Explainability & Pilot Readiness
- **Multilingual Explainability Engine across 10 Locales (`financial_engine.py`, `phase4-reason-codes.ts`, `api-client.ts`, `/financial`):**
  - Replaced unstructured English detail strings with structured `reason_code` (`rule.*`, `cycle.*`, `fresh.*`, `intl_policy.*`) + `params` across all 99 evaluated criteria in `evaluate_single_scholarship` and `classify_cycle_verification_state`.
  - Implemented `PHASE4_REASON_TEMPLATES` in TypeScript covering all 10 platform locales (`en-US`, `es-419`, `fr-FR`, `ht-HT`, `ar-SA`, `zh-Hans`, `hi-IN`, `pt-BR`, `ja-JP`, `de-DE`) and `formatStructuredReason` formatting, achieving zero English-only rule explanation prose in Arabic RTL (`ar-SA`) cards.
  - Preserved authentic official scholarship titles and official source URLs verbatim in their original languages with an ISO language badge (`[en]`, `[es]`, `[de]`) and localized guidance advisory.
- **8-State Application Cycle Verification Breakdown (`financial_engine.py`, `coverage_analytics.py`, `/financial`):**
  - Added `classify_cycle_verification_state` separating active opportunities into 8 honest states without assuming cyclical recurring awards or WAF-blocked portals are open: `confirmed_open` (22), `confirmed_upcoming` (0), `rolling` (2), `previous_cycle_only` (2), `next_cycle_unannounced` (19), `deadline_expired` (16), `source_unavailable` (7), `requires_manual_verification` (1) across the 69-program baseline.
  - Audited and verified `ht_ca_first_year_ug` scenario: Lester B. Pearson and UBC International both evaluate as `eligible` academically, but past November deadlines (`2026-11-08` and `2026-11-15`) place them honestly into `previous_cycle_only` (status: `closed`), while McGill remains `requires_manual_verification` (`conflicting_information`).
- **6-Field Deferred Research Queue Schema (`coverage_analytics.py`, `api-client.ts`, `/financial`):**
  - Upgraded `DRQ-01` through `DRQ-04` with full metadata: `research_objective`, `official_sources_required`, `existing_evidence`, `missing_evidence`, `verification_priority`, and `resolution_mode` (`human_review_required` vs `semi_automated_allowlist`).
- **Multilingual Counselor Integration & External Application Routing (`counselor.py`):**
  - Grounded `MultilingualCounselorService` in deterministic scholarship match results, surfacing verified citations, `/financial` and `/applications` suggested workflows, and explicit non-submission advisories clarifying that UniGlobe never submits applications on behalf of students.
- **Security & Pre-Pilot Governance Audit (`routing_health.py`, `infra/firewall/`, `auth_provider.py`):**
  - Verified `_PinnedPublicIPBackend` SSRF mitigation and `infra/firewall/egress-iptables.sh` cloud metadata blocking (`169.254.169.254/32`). Documented the `ClerkAuthProvider` mock placeholder as an explicit critical pre-pilot blocker.
- **Verification Matrix:** Passed **101 / 101** backend `pytest` tests (`test_phase4_2_multilingual_explainability_and_pilot_readiness.py`), **13 / 13** frontend unit tests (`api-client.test.ts`), **16 / 16** static Next.js production routes, and live Chromium QA (0 console errors, 0 HTTP `>= 500`, zero horizontal overflow in `ar-SA` RTL).

### Improved — Phase 4.1: Student-Level Scholarship Eligibility Intelligence & Coverage Optimization
- **Non-Inference Transfer & Destination Hardening (`financial_engine.py`, `schemas/phase4.py`):**
  - Added 7-way `classify_transfer_pathway` (`explicitly_accepts_transfer`, `ug_transfer_unconfirmed`, `first_year_only`, `community_college_required`, `transfer_restricted_by_institution_or_country`, `graduate_only`, `exchange_only`) and enforced strict manual-review flagging (`requires_manual_review`) when `transfer` applicants evaluate `ug_transfer_unconfirmed` awards (`12` broad `'all'` UG records) rather than inferring transfer eligibility.
  - Added implicit `destination_country` enforcement for awards without explicit `destination_country` rules and deterministic priority sorting on `profile.enrollments` in `_derive_student_context`.
- **Variable vs. Fixed Aid Intelligence & Per-Card Explainability (`financial_engine.py`, `/financial`):**
  - Added 8-category `classify_aid_type` separating fixed statutory/published awards from `css_profile_full_need`, `variable_institutional_need`, `variable_merit`, `tuition_waiver`, and `exchange_only` policies (`is_variable_aid`, `is_amount_verified`, `is_cycle_open`, `is_actionable_for_student`), plus explicit `satisfied_reasons`, `failed_reasons`, `missing_requirements`, `official_supporting_sources`, and non-probability advisories.
- **Student-Level Coverage Analytics, Gaps & Deferred Research Queue (`coverage_analytics.py`, `POST /api/v1/financial/student-coverage`):**
  - Exposed separated non-blended student counters (`programs_matched`, `programs_verified_eligibility`, `programs_verified_funding`, `programs_open_cycle`, `programs_actionable_open_verified`, `programs_insufficient_info`, `programs_manual_review`), prioritized profile coverage gaps (`no_actionable_opportunities`, `no_verified_funding`, `only_expired_cycles`, `only_variable_institutional_aid`, `only_unconfirmed_transfer`) across an `18`-archetype matrix, `confirmed_open_verified_programs` (`7 / 69`), and `DRQ-01`..`DRQ-04` deferred research targets.
  - Surfaced student coverage metrics, gap alerts, aid-type/transfer badges, and Coverage Audit gap panels on `/financial` across all **10** locales incl. `ar-SA` RTL, verified by **95 / 95** backend `pytest`, **12 / 12** frontend `api-client.test.ts`, **16 / 16** Next.js build routes, and live Chromium QA.

### Audited & Remediated — Global Catalog Verification & Coverage Audit (Workstreams A–G)
- **Full 69-Program Remediation & Re-Verification (`phase4_catalog_audit_remediation.py`, `phase4_seed.py`):**
  - Audited all **27** legacy records and re-verified all **42** Batches 1–4 scholarships (`69 / 69` reviewed, **`100%`** 15-field `claim_provenance` completeness, `0` invalid URLs, `0` duplicates).
  - Stripped invented hardcoded USD estimates from all **14** non-USD legacy scholarships (restoring strict native `AUD, CAD, EUR, GBP, JPY` isolation), corrected **France Excellence Eiffel** degree scope to `masters`/`doctoral` only, verified **Imperial UG (`1,000 GBP`)** and **TUM Deutschlandstipendium (`3,600 EUR`)**, updated stale `404` URLs on Cambridge Trust/Yale/UCSD/UC Berkeley/UTokyo PEAK, flagged **McGill** (`conflicting_information`), and tracked `8` HTTP `403`/TLS WAF-blocked official portals honestly under `source_unavailable` / `unavailable_source_programs` without anti-bot bypass.
  - Updated **`verified_funding_coverage`** (`25 / 69` = **`36.2%`**) cleanly separated from **`actionable_coverage`** (`18 / 69` = **`26.1%`** open non-expired calls), while strictly excluding `exchange_mobility` and variable CSS/SAI awards from guaranteed Net Price USD discounts (`calculate_net_price`).
- **Country Catalog Fix (`MA` Morocco vs `MR` Mauritania, `countries_seed.py`, `financial_engine.py`):**
  - Seeded **Morocco (`MA`, `MAD`)**, **Mauritania (`MR`, `MRU`)**, and **27** missing referenced ISO countries; added `"MR"` to `REGION_COUNTRIES["africa"]`; added unique `MA`/`MR` options on `/financial`.
- **Coverage Audit API & Dashboard (`coverage_analytics.py`, `GET /api/v1/financial/coverage-audit`, `/financial`):**
  - Added global analytics endpoint and interactive **Coverage Audit** tab on `/financial`, alongside verification date pills, transfer-pathway badges, `amount_classification` badges, and `freshness_warnings` alerts across all **10** languages incl. `ar-SA` RTL.
  - Verified **91 / 91** backend `pytest` (`test_17a`–`test_17f`), **12 / 12** frontend `api-client.test.ts`, **16 / 16** Next.js routes, live Chromium QA, and structured export [`docs/audits/phase4_catalog_coverage_audit.json`](docs/audits/phase4_catalog_coverage_audit.json).

### Added & Verified — Step 3 (Batch 4): Europe & Erasmus+ Scholarship Expansion
- **Batch 4 Verified Europe & Erasmus+ Expansion (`phase4_batch4_seed.py`, **10** new programs -> **69** total; `verified_funding_coverage` **`24/69` = `34.8%`**):**
  - Seeded **10** official primary-source-verified programs (`<= 12` cap) with complete 15-field `claim_provenance`, **46** deterministic rules, and **41** European/partner country rows (`NO, FI, AT, PT, DK, PL, CZ, GR, IS, LI, HU, RO, BG, HR, SK, SI, EE, LV, LT, CY, MT, LU, AM, AZ, BY, GE, MD, UA...`): **NL Scholarship** (`5,000 EUR` one-time, non-EEA only, open `2027-2028`), **Swiss Government Excellence Scholarships (SERI/FCS)** (`29,400 CHF/yr`, PhD/research max age 35, excl. CH citizens and >1-yr CH residents), **ETH Zurich ESOP** (`27,000 CHF/yr` HS27 + tuition waiver, open Nov 1–30, 2026), **Swedish Institute SISGP** (`144,000–159,000 SEK/yr`, strictly 34 non-EU countries citizen-only, open/upcoming `2027-02-24`), **BI Presidential Scholarship (Norway)** (`100,000 NOK/yr` + full tuition, Grade A, open `2027-03-01`), **University of Turku Tuition Fee Waiver (Finland)** (`750–6,000 EUR/yr` 50% tuition waiver only without living support, strictly non-EU/EEA/CH), **Politecnico di Milano DSU** (`EUR` tiered call closed `2025-2026`), **Spain MEFD Beca General** (`1,700–4,585 EUR` RD 179/2026 statutory grant enforcing independent Spanish residency), **Erasmus Mundus Joint Masters (EMJM)** (`16,800 EUR/yr` full multi-country consortium Master's), and **Erasmus+ Student Mobility Grant** (`exchange_mobility` short-term 2–12 mo non-degree exchange).
  - Expanded `"eu"` (27 states), `"eea"` (30 states), and `"europe"` in `REGION_COUNTRIES` (`financial_engine.py`), wired `has_batch4` in `ensure_phase4_seeded`, added Batch 4 dropdown options + `fin.badge_exchange_only` badge across all **10** UI locales on `/financial`, verified **85 / 85** backend `pytest`, **12 / 12** frontend `api-client.test.ts`, **16 / 16** Next.js build routes, and live Chromium QA (`0` console errors, `0` HTTP `>= 500`, `ar-SA` RTL zero overflow). Stopped cleanly after Batch 4.

### Added & Verified — Step 3 (Batch 3): Asia & Southeast Asia Scholarship Expansion & Verified Funding Coverage
- **Batch 3 Verified Asia & Southeast Asia Expansion (`phase4_batch3_seed.py`, **11** new programs -> **59** total):**
  - Seeded **11** official primary-source-verified scholarships (`<= 12` cap) with complete 15-field `claim_provenance`, **63** deterministic rules, and country coverage across China, India, South Korea, Singapore, Malaysia, Indonesia (`ID` added to `countries`), Pakistan, Bangladesh, Vietnam, and the Philippines: **CAS-ANSO Scholarship (2027 Call — USTC / UCAS / CAS)** (`36,000–84,000 CNY`, open `2027-02-28`), **USTC Fellowship for Undergraduate Programs** (`CNY` unpublished UG table, mandatory `CSCA` + `HSK Level 5`, open `2027-03-31`), **DST INSPIRE-SHE** (`60,000–80,000 INR`, 18 Basic/Natural Sciences only, excludes Engineering/Medicine/CS), **Global Korea Scholarship — Undergraduate (2027 GKS-U, NIIED)** (`13,560,000–14,400,000 KRW`, strict `dual_citizenship` exclusion, foreign HS transcript `>= 2.64/4.0`, CSAT exempt, closed `2026-09-30`), **A*STAR Graduate Scholarship (AGS — PhD)** (`43,200–74,400 SGD`, open `2027-02-01`), **Malaysia International Scholarship (MIS, MOHE)** (`18,000 MYR`, ASEAN + Commonwealth + MOHE list, IELTS `>= 6.0`, closed `2026-05-15`), **Beasiswa KNB (Kemdiktisaintek RI)** (`IDR` unpublished, closed `2026-03-31`), **HEC / BISP Undergraduate Scholarship** (`40,000 PKR`), **UGC PhD Scholarship (Bangladesh)** (`BDT` unpublished, closed `2026-11-15`), **VNU Hanoi Institutional & Partner Scholarships** (`7,500,000–25,000,000 VND`), and **CHED-UniFAST Tertiary Education Subsidy (TES — RA 10931)** (`20,000–27,000 PHP`).
  - Also upgraded Batch 3 rule upserts in `phase4_batch3_seed.py` to keep rule dimensions/values synchronized on re-seed, and added `has_batch3` bootstrap check in `ensure_phase4_seeded`.
- **Strategic Metric — `Verified Funding Coverage` (`freshness_governance.py`, `financial_engine.py`, `schemas/phase4.py`, `/financial`):**
  - Added `compute_verified_funding_coverage` / `_has_verified_funding_coverage` shared helper across `validate_scholarship_catalog` and `match_scholarships_deterministic` calculating the ratio of active programs holding verified, non-expired `eligibility_rules` + `award_amounts` claims with concrete published funding (`16 / 59` = **`27.1%`** baseline).
  - Surfaced `fin.verified_funding_coverage` and `fin.verified_funding_detail` across all **10** UI locales (incl. `zh-Hans`, `hi-IN`, `ja-JP`, `ar-SA` RTL) in `#fin-verified-coverage-bar` alongside expanded Asia/SE Asia country selectors on `/financial`.
  - Verified **80 / 80** backend `pytest`, **12 / 12** frontend `api-client.test.ts`, **16 / 16** Next.js build routes, and live Chromium QA (`0` console errors, `0` HTTP `>= 500`, Arabic `ar-SA` RTL zero overflow). Stopped cleanly before Batch 4 (Europe).

### Added & Verified — Step 3 (Batch 2): Latin America Scholarship Expansion
- **Batch 2 Verified Latin America Expansion (`phase4_batch2_seed.py`, **10** new programs -> **48** total):**
  - Seeded **10** official primary-source-verified scholarships (`<= 12` cap) with complete 15-field `claim_provenance`, **52** deterministic rules, and **19** country entries (`BR, MX, CO, CL, AR, PE, ES, UY, EC, BO, PY, VE, CR, PA, GT, HN, NI, SV, CU`) across Brazil, Mexico, Colombia, Chile, Argentina, Peru, Pacific Alliance, and Ibero-America: **ProUni (MEC Brasil)** (`BRL`, `ENEM >= 450` rule), **CAPES Demanda Social** (`BRL`), **SECIHTI Becas Nacionales** (`192,575.88–256,767.84 MXN`, closed `2026-11-21`), **SECIHTI Extranjero** (`MXN`, closed `2026-05-22`), **ICETEX Beca Colombia 2026-2** (`COP`, excludes `CO` citizens & `CO` residents, age `19–49`, closed `2026-06-05`), **AGCID República de Chile** (`CLP`, excludes `CL`), **Becas Progresar Nivel Superior** (`420,000 ARS/yr`, closed `2026-09-11`), **PRONABEC Beca 18 Convocatoria 2027** (`PEN`, age `< 22`, `ENP >= 84`, closed `2026-10-18`), **Alianza del Pacífico Movilidad Estudiantil** (`UNK` host currency, `pacific_alliance` transfers only, excludes `BR`/`AR`), and **Fundación Carolina Postgrado** (`EUR`, `iberoamerica` residing outside `ES`, closed `2026-03-02`).
  - Added `"pacific_alliance"` and `"iberoamerica"` to `REGION_COUNTRIES` (`financial_engine.py`) and updated `ensure_phase4_seeded` to ensure idempotent Batch 2 presence.
  - Preserved native currencies (`BRL, MXN, COP, CLP, ARS, PEN, EUR, UNK`) without fabricated USD conversions and without unsupported GPA scale conversions (`ENEM` / `ENP` evaluated via native `required_exams`).
- **Financial Dashboard & QA (`/financial`):** Expanded citizenship, residence, and destination selectors with Batch 2 countries (`CO, CL, AR, PE, ES` + `BR, MX`), verified **75 / 75** backend `pytest`, **12 / 12** frontend `api-client.test.ts` (across all 10 locales), **16 / 16** Next.js build routes, and live browser QA (`0` console errors, `0` HTTP `>= 500`, Arabic `ar-SA` RTL zero overflow). Stopped cleanly before Batch 3 (Asia & Southeast Asia).

### Added & Verified — Step 3 (Batch 0 + Batch 1): Global Scholarship Expansion (Africa & Caribbean)
- **Batch 0 Global Source Audit & Claim-Level Freshness Hardening (`freshness_governance.py`, `financial_engine.py`, `schemas/phase4.py`):**
  - Audited all **27** baseline scholarships (`AU: 1, CA: 3, DE: 3, FR: 2, GB: 4, JP: 1, US: 13`) preserving legacy `requires_manual_review` / `unknown` honesty with zero fabricated cycle dates or reviewers.
  - Added independent claim-domain tracking (`evaluate_scholarship_claim_breakdown` separating `program_existence`, `eligibility_rules`, `award_amounts`, and `deadlines`), expanded `UNOFFICIAL_AGGREGATOR_HOSTS` (`scholars4dev.com`, `afterschoolafrica.com`, `opportunitydesk.org`, `opportunitiesforafricans.com`, `iefa.org`), and ensured closed cycle deadlines surface honestly (`application_cycle_status = "closed"`) without blocking `program_existence` visibility while `calculate_net_price` still excludes expired `award_amounts` sub-claims.
  - Added `caricom` region distinction (`REGION_COUNTRIES`) separating CARICOM-restricted awards from broader Caribbean scholarships.
- **Batch 1 Verified Africa & Caribbean Expansion (`phase4_batch1_seed.py`, **11** new programs -> **38** total):**
  - Seeded **11** live primary-source-verified scholarships (`<= 12` cap) with complete 15-field `claim_provenance`, **61** deterministic rules, and **14 / 14** target Africa/Caribbean country records (`NG, GH, KE, ZA, ET, RW, SN, CI, HT, JM, TT, BB, BS, DO`): **Chevening Scholarships**, **CSC Commonwealth Master's** (`20,544–24,000 GBP`), **CSC Commonwealth PhD (LDCs & Vulnerable States)** (`NG, RW` eligible; middle-income excluded), **The Mandela Rhodes Scholarship** (`ZAR`, African citizens age 19–29), **Ashesi University Need-Based Aid & Mastercard Foundation Scholars Program** (`GHS`), **PTDF In-Country Scholarship Scheme (ISS)** (`NGN`), **DAAD EPOS** (`11,904–16,800 EUR`), **P. J. Patterson Endowment Fund** (`$2,000–$3,000 USD`), **UWI Toronto Gala Scholarship** (`3,000 CAD` isolated cleanly from USD), **AFUWI Undergraduate Scholarship** (`$2,000–$5,000 USD`, closed `2026-08-14` deadline), and **MESCyT Becas Internacionales** (`DOP`).
- **Multilingual Financial Dashboard Updates (`/financial`, `phase4-translations.ts`):**
  - Expanded citizenship, residence, and destination selectors with Batch 1 African and Caribbean countries, added native currency display, sponsor/academic cycle badges (`Cycle Closed`), and localized unpublished-amount messaging across all 10 languages incl. `ar-SA` RTL (never `$0`).
- **Verification:** **71 / 71** backend `pytest` (including **test_phase4_global_scholarship_expansion.py**), **12 / 12** web unit tests, **16 / 16** Next.js build routes, and live browser QA (`0` console errors, `0` HTTP `>= 500`, Arabic RTL zero overflow). Execution stopped cleanly before Batch 2.

### Fixed & Hardened — Step 2: Scholarship Eligibility Engine & Net Price Accounting Accuracy
- **Comprehensive Deterministic Eligibility Rule Evaluators (`financial_engine.py`, `schemas/phase4.py`, `api/v1/financial.py`):**
  - Extended `_eval_rule` across **18** rule dimensions (`excluded_citizenships`, `dual_citizenship`, `country_of_residence`, `degree_level`, `enrollment_context` incl. `currently_enrolled`/`final_year_undergraduate`/`full_time`/`community_college`/`first_year`/`transfer`/`graduate`, `required_qualifications`, `language_proficiency`, `required_exams`, `age_limit`, `field_of_study`, `geographic_region`, and separated `renewal` criteria, alongside `citizenship`, `residency_state`, `destination_country`, `applicant_type`, `minimum_gpa`, `financial_need_level`).
  - Enforced strict evidence boundaries: never infers citizenship from residence, residence from citizenship, degree level from age, transfer status from institution name, or absent exam scores as zero; flags unsupported or conflicting rule definitions rather than silently ignoring them.
  - Added **5** explicit evaluation outcomes with deterministic precedence (`ineligible` > `requires_manual_review` > `insufficient_information` > `conditionally_eligible` > `eligible`) and structured explanations (`rule_evaluations`, `renewal_evaluations`, `failed_reasons`, `missing_requirements`, `conditional_requirements`, `manual_review_reasons`, `student_evidence_used`).
- **End-to-End Degree-Level & Component-Aware Net Price Accounting (`calculate_net_price`):**
  - Fixed `degree_level` propagation through `NetPriceCalculateRequest` and `match_scholarships_deterministic`, filtering `InstitutionCost` and scholarship eligibility by degree level before allocation.
  - Enforced component-level ceilings so tuition-only awards reduce tuition/fees only (never housing/living costs), living stipends & travel allowances reduce living/transportation costs only (never tuition), and category & total net prices can never over-credit or go negative.
  - Separated funding honestly into `verified_applicable_aid`, `conditional_aid`, `insufficient_info_aid`, `review_required_aid`, and `unallocated_potential_aid`, preventing `expired`, `source_unavailable`, `conflicting_information`, `requires_manual_review`, unknown-scope, missing-amount, and non-matching currency awards from reducing guaranteed or verified Net Price, and restricting multi-year projections to documented `is_renewable` + `funding_duration_years`/`max_funding_periods` terms.
- **Full Multilingual & Arabic RTL Financial Dashboard (`/financial`, `phase4-translations.ts`):**
  - Localized remaining English labels, form controls, 6 status summary cards, Freshness badges, category-allocation table headers, and segregated funding buckets across all 10 UniGlobe languages including `ar-SA` RTL (`dir="rtl"`, zero horizontal overflow).
- **Verification:** **67 / 67** backend `pytest` (including **test_phase4_eligibility_financial_accuracy.py**), **12 / 12** frontend `api-client.test.ts` unit tests, **16 / 16** Next.js build routes, and live browser QA across `/financial` & `/credentials` (`0` console errors, `0` HTTP `>= 400`).

### Added — Step 1: Phase 4 Schema Migration, Data Provenance & Freshness Governance (`f1c9e4a2b870`)
- **Reversible Provenance & Structure Migration (`f1c9e4a2b870` on `e4a7c2d901b5`):**
  - Extended `scholarship_programs` with `sponsoring_institution`, `source_type`, `source_version`, `academic_year`, `award_fixed_usd`, `native_amount_min`, `native_amount_max`, `covers_travel`, `funding_duration_years`, `max_funding_periods`, `renewal_conditions`, `verification_method`, `verified_by`, `verification_expires_at`, `freshness_status`, `requires_manual_review`, `claim_provenance`, and `conflict_notes`.
  - Extended `grade_conversion_rules`, `credential_recognition_rules`, and `country_qualifications` with `issuing_authority`, `education_level`, `grading_structure` / `highest_grade` / `subject_structure` / `exam_structure`, `academic_duration`, `framework_version`, `equivalency_classification`, `verified_by`, `verification_expires_at`, and `freshness_status`.
  - Verified upgrade -> downgrade -> upgrade reversibility cleanly; preserved all existing records without fabricating reviewer identities, source versions, currencies, or expiration timestamps (marking unestablished legacy metadata honestly as `unknown` / `requires_manual_review`).
- **Freshness Governance & Independent Validation (`freshness_governance.py`, `financial_engine.py`, `credential_engine.py`, `schemas/phase4.py`):**
  - Enforced **6** canonical freshness states (`current`, `approaching_expiration`, `expired`, `source_unavailable`, `conflicting_information`, `requires_manual_review`) and differentiated expiration intervals (`90d` scholarship deadlines, `120d` award amounts, `180d` eligibility rules, `365d` qualification frameworks/recognition, `730d` grade conversion brackets).
  - Guaranteed non-destructive historical preservation during sweeps (`sweep_phase4_freshness` marks expired records `expired`/`is_current=False` without deleting rows and excludes them from active eligibility matching).
  - Implemented `validate_scholarship_catalog`, `validate_credential_catalog`, and `is_valid_official_url` to independently audit URLs, duplicates, provenance completeness, expirations, and conflicts.
- **Verification:** Verified Alembic `upgrade -> downgrade -> upgrade`, **63 / 63** backend `pytest` (including 4 new provenance/freshness/validation tests in `test_phase4_provenance_and_freshness.py`), and **12 / 12** frontend unit tests.

### Added & Audited — Phase 4 Scholarship Audit, Institutional Expansion & Profile-Linked Credentials
- **Scholarship Rule & Net Price Audit (`phase4_seed.py`, `financial_engine.py`, `schemas/phase4.py`):**
  - Audited previously seeded awards against cited sources: restricted `Fulbright Foreign Student Program (Graduate & Research)` to `masters`/`doctoral` (`degree_level`), excluding it from undergraduate Net Price calculations; enforced `requires_us_community_college` (`enrollment_context`) for `Jack Kent Cooke Undergraduate Transfer Scholarship`; marked MIT full-need aid as non-statutory (`is_guaranteed_statutory=False`, conservative income-aware scaling capped at Total COA); replaced bundled UCLA entry with guaranteed `UC Blue and Gold Opportunity Plan (UCLA)`; narrowed OAS strictly to upper-division transfer (`applicant_type="transfer"`); separated TUM Deutschlandstipendium living stipend (`covers_tuition=False`) from non-EU tuition disclosure; and fixed institution linkage names (`University College London`, `Ludwig-Maximilians-Universität München`, `The University of Melbourne`).
  - Expanded verified institutional coverage across **27** total scholarship records in PostgreSQL (adding Yale, Princeton, UC San Diego, UBC, Cambridge Trust, Imperial College London, Heidelberg/Baden-Württemberg, and Université Paris-Saclay).
- **Profile-Linked Credential Evaluation & Degree Filter (`/credentials`, `/financial`):**
  - Added `GET /api/v1/credentials/profile-evaluate` (`evaluate_profile_credentials` in `credential_engine.py`) to automatically infer native grading scales and run Dual-View + gatekeeping evaluations across authenticated student `EnrollmentRecord`s, rendered on `/credentials` across all 10 languages including Arabic RTL (`ar-SA`).
  - Exposed `degree_level` selector (`bachelors`, `masters`, `doctoral`) in `/financial` (`Scholarship Eligibility Matcher`).
- **Verification:** **59 / 59** backend `pytest` (`test_phase4_financial_and_credentials.py`), **12 / 12** frontend unit tests, **16 / 16** Next.js build routes, and live browser QA (`0` console errors, `0` HTTP `>= 400`, Arabic RTL `dir="rtl"` zero horizontal overflow). **Prerequisite before production launch:** deploy outbound API worker firewall rules (`infra/firewall/`).

### Added — Outbound Worker Firewall & Phase 4 Foundation (Scholarships, Net Price & Credentials)
- **Production API Worker Outbound Firewall (`infra/firewall/`):**
  - Added Linux `iptables`/`ip6tables` defense-in-depth egress rules (`egress-iptables.sh`) and Kubernetes `NetworkPolicy` (`k8s-api-worker-egress-networkpolicy.yaml`) plus hardened compose network segmentation (`docker-compose.prod.yml`) blocking RFC1918 private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback, CGNAT, link-local, IPv6 ULA/link-local/mapped ranges, and cloud metadata `169.254.169.254`.
- **Phase 4 Schema & Verified Global Seed Catalog (`e4a7c2d901b5`, `phase4_seed.py`):**
  - Extended `scholarship_programs` with structured award min/max amounts, coverage flags, statutory/guaranteed indicators, GPA floors, and citizenship/residency/destination targets alongside `scholarship_eligibility_rules`; added `grade_conversion_rules` and `credential_recognition_rules`.
  - Seeded **16** verified US & global scholarships (institutional need/merit, UC/UMich/CCPG state programs, Federal Pell Grant, Jack Kent Cooke Transfer, Fulbright, OAS/Rowe Fund, Pearson UofT, McGill Mastercard, Reach Oxford, TUM, Sorbonne/Campus France, UTokyo PEAK), **11** native grading scales (`FR 0–20`, `HT 0–20`, `DE 1.0–6.0`, `GB A-Levels`, `IN %` & `10-pt CGPA`, `IB /45`, `CA %`, `NG WAEC`, `BR 0–10`, `AU ATAR`), and **12** bilateral credential recognition gatekeeping records.
- **Deterministic Engines, APIs & Multilingual UI (`/financial`, `/credentials`):**
  - Implemented `match_scholarships_deterministic` and `calculate_net_price` (`app/services/financial_engine.py`, `app/api/v1/financial.py`), plus dual-view grade & recognition evaluator `evaluate_credential` (`app/services/credential_engine.py`, `app/api/v1/credentials.py`).
  - Built `/financial` (Scholarship Matcher + Net Price Calculator) and `/credentials` (Dual-View International Credential Evaluator) wired into `Header.tsx` across all 10 languages including Arabic RTL (`ar-SA`).
- **Verification:** **58 / 58** backend `pytest` (`test_phase4_financial_and_credentials.py`), **12 / 12** frontend unit tests, **16 / 16** Next.js build routes, and live browser QA.

---

## [0.7.3-m7] - 2026-11-25

### Security, Retention & Localization — Production Readiness Audit Resolution (`docs/16_PRODUCTION_READINESS_AUDIT_MILESTONE_7.md`)
- **Database-Enforced Append-Only Audit Retention (`d8f2a9b41e03`):**
  - Added PostgreSQL `BEFORE INSERT` (`audit_populate_retained_ids`) and `BEFORE UPDATE OR DELETE` (`prevent_audit_mutation`) triggers on `application_route_audits`, `application_status_history`, and `evidence_review_audits` blocking all direct row updates and deletes.
  - Switched parent foreign keys from `ON DELETE CASCADE` to nullable `ON DELETE SET NULL` alongside `retained_route_id`, `retained_application_id`, `retained_evidence_id`, `parent_deleted_at`, and SQLAlchemy `passive_deletes="all"` so legitimate parent deletion cleanly preserves immutable audit records.
- **DNS-Rebinding Closure & Automated Expiry Sweeps (`routing_health.py`, `main.py`, `config.py`):**
  - Added `_PinnedPublicIPBackend(httpcore.SyncBackend)` pinning TCP connections strictly to pre-validated global public IP addresses with `trust_env=False` and connection-time DNS verification while preserving TLS SNI/cert verification.
  - Wired `automated_expiry_sweep_loop` into FastAPI `lifespan` (`ENABLE_AUTOMATED_EXPIRY_SWEEPS`, `ROUTE_EXPIRY_SWEEP_INTERVAL_SECONDS`) and surfaced live sweep status in `/operations`.
- **Operations Console Localization, RTL & Accessibility (`operations-translations.ts`, `operations/page.tsx`):**
  - Localized `/operations` across all 10 UniGlobe languages including Arabic RTL (`ar-SA`, `dir="rtl"`), with ARIA `tablist`/`tab`/`tabpanel`, `aria-pressed`, `role="status"`/`role="alert"`, and explicit `<label htmlFor>` bindings.
- **Verification:** `alembic` reversible migration test (`upgrade -> downgrade -> upgrade`), **54 / 54** backend `pytest` (`test_audit_retention.py` + `test_milestone7_application_routing.py`), **11 / 11** frontend unit tests, **14 / 14** Next.js build routes, and live Arabic RTL + E2E upload/reject/re-upload/accept/delete browser QA.

---

## [0.7.2-m7] - 2026-11-24

### Added — Milestone 7.2: Route Link-Health, Expiration, Pathway Verification, Redirect Tracking & Reverification
- **Schema & Migration (`c3e8a4f19d72`):**
  - Extended `application_routes` with `verification_expires_at` (180-day default validity), `last_health_check_at`, `last_health_check_status` (`healthy` / `redirected` / `unreachable` / `error`), `last_health_check_http_code`, `pathway_verified`, `final_redirect_url`, and `redirect_chain_length`.
  - Backfilled `verification_expires_at` for all verified routes (`verified_at + 180 days`) and marked curated flagship/centralized portals `pathway_verified = TRUE` while leaving IPEDS auto-verified routes flagged as pathway-unverified until explicitly confirmed.
- **Health, Expiration, Redirect & Reverification Governance (`routing_health.py`, `routing_verification.py`, `base.py`, `operations.py`):**
  - Added SSRF-safe HTTP HEAD/GET link-health checks (`POST /api/v1/admin/routing/{id}/health-check` and `POST /api/v1/admin/routing/health-check`) tracking HTTP response codes, redirect chain length, final destination URL, and cross-domain redirect audit alerts.
  - Added verification expiration sweeps (`POST /api/v1/admin/routing/expire-stale`) and automatic reverification triggers in `IngestionPipeline` (`apps/api/app/ingestion/base.py`) when an institution's `official_website`, `admissions_website`, or `application_portal_url` changes.
  - Added explicit pathway applicability verification (`POST /api/v1/admin/routing/{id}/pathway` + `pathway_verified` / `applicant_type` fields on `POST /api/v1/admin/routing/{id}/review`).
- **Operations Console Visibility (`/operations`):**
  - Updated `GET /api/v1/admin/routing/queue` (`limit` up to `500`/`1000`, `manual_review` and `expired` filters) and `/operations` UI so all **14** pending `needs_verification` routes plus manually reviewed routes (`manual_verifier` / `manual_rejected`) stay visible in the dashboard without silent exclusion, complete with health/expiration/pathway/redirect badges and controls.
  - Verified with **50** passing backend `pytest` tests (`tests/test_milestone7_application_routing.py`), **10** passing frontend unit tests, and clean Next.js `pnpm build` (**14/14** routes).

---

## [0.7.1-m7] - 2026-11-24

### Added — Milestone 7.1: Routing Data Quality & Confirmation Verification Operations
- **Routing Data Quality Verification Pipeline (`9b4f21c8e310`, `routing_verification.py`):**
  - Audited all **400** NCES IPEDS `needs_verification` routes using deterministic provenance, strict HTTPS (`scheme_secure=True`), exact registrable-domain matching against verified institutional websites, and an allowlist of official state/centralized admission systems (`commonapp.org`, `calstate.edu`, `universityofcalifornia.edu`, `applytexas.org`, `opencccapply.net`, `laccd.edu`, `wisconsin.edu`, `cuny.edu`, `cfnc.org`, `gafutures.xap.com`).
  - Promoted **385** IPEDS routes to `verified` (**317** `ipeds_domain_match`, **68** `ipeds_state_system`), lifting verified directory coverage from `28/428` to **`414/428` (96.7%)** after manual verifier promotion of Indiana University (`413` batch + `1` manual review), while holding the **14** third-party CRM (`force.com`, `elluciancrmrecruit.com`) and cross-domain candidates explicitly in `needs_verification` for human verifier inspection.
  - Added immutable `application_route_audits` logging every automatic and manual verification/rejection decision.
- **Confirmation Verification Operations (`evidence_ops.py`, `operations.py`, `/operations`):**
  - Enabled `data_verifier` role alongside `admin` in `MockAuthProvider` (`mock_verifier_<email>`) and `require_admin_claims`; students receive `403 Forbidden` on all reviewer/routing queues and cannot inspect other students' Document Vault artifacts.
  - Enforced standardized rejection taxonomies (`EVIDENCE_REJECTION_REASONS` & `ROUTE_REJECTION_REASONS`) requiring a valid `rejection_reason_code` plus actionable notes on every rejection (`400 Bad Request` if omitted).
  - Added immutable `evidence_review_audits` tracking every upload, acceptance, and rejection (`actor_role`, `actor_email` scrubbed from student views while preserved for operations audits), Vault artifact inspection (`GET /api/v1/admin/evidence/{id}/document`), reviewer queues (`/api/v1/admin/evidence/queue`, `/api/v1/admin/routing/queue`), and `/operations` RBAC-gated Verifier Console alongside structured rejection badges + `Re-upload Proof` on `/applications`.
  - Verified with **49** passing backend `pytest` tests (`tests/test_milestone7_application_routing.py`), **10** passing frontend unit tests, Next.js `pnpm build` (**14/14** routes), and live browser QA on `/operations` & `/applications`.

---

## [0.7.0-m7] - 2026-11-24

### Added — Phase 3 Milestone 7: Official Application Routing Directory & External Confirmation Flow
- **Routing & Confirmation Lifecycle Schema (`61d97d129fb9`):**
  - Added `application_routes` (curated institutional portals and centralized platforms with `verification_status`, `confidence_level`, `source_name`, `verified_at`, `last_checked_at`, and international applicant guidance), `application_status_history` (immutable actor/role audit trail), and `application_submission_evidence` (Document Vault proof linkage and verifier review state `pending` / `accepted` / `rejected`).
  - Extended `applications` (`selected_route_id`, `external_portal_url`, `external_platform_name`, `redirected_at`, `student_reported_submitted_at`, `submission_confirmed_at`, `external_confirmation_number`).
- **Official Application Routing Directory & URL Safety (`routing_seed.py`, `routing.py`):**
  - Seeded **428** routing rows (**8** centralized platforms including `Common App`, `Common App for Transfer`, `UC Application`, `UCAS`, `OUAC`, `Études en France`, `uni-assist`, `Cal State Apply`; **20** curated institutional portals; **400** IPEDS `needs_verification` candidates flagged separately from verified routes).
  - Enforced structural URL validation (`validate_routing_url` / `POST /api/v1/routing/validate-url`) rejecting empty strings, `javascript:`/`file:`/`ftp:` schemes, whitespace, localhost, and raw IP literals, while excluding unverified links from `verified_routes`.
- **Honest 6-State External Lifecycle, Document Vault Evidence & RBAC (`routing_engine.py`, `applications.py`):**
  - Enforced transitions across `not_started`, `preparing`, `ready_to_apply`, `redirected_to_external_portal`, `student_reported_submitted`, and `submission_confirmed`.
  - Clicking external launch (`POST /api/v1/applications/{id}/redirect`) records only `redirected_to_external_portal` and blocks unverified redirects without explicit `acknowledge_unverified=true`.
  - Student submission self-reporting (`POST /api/v1/applications/{id}/report-submission`) and Document Vault confirmation uploads (`POST /api/v1/applications/{id}/evidence`) move strictly to `student_reported_submitted` (`pending` evidence) — student attempts to self-confirm `submission_confirmed` or review evidence return `403 Forbidden` via `require_admin_claims`.
- **Student UI (`/applications`, Header, `/first-year`, `/matching`) & Verification:**
  - Built `/applications` dual-tab UI (`My Applications Tracker` + `Official Routing Directory`), replaced the hardcoded UC portal link in `/first-year`, wired `/matching` `Route & Apply` quick links, and added `nav.applications` / `applications.*` keys across all 10 languages including Arabic RTL (`ar-SA`).
  - Verified with **47** passing backend `pytest` tests (`4` new in `test_milestone7_application_routing.py`), **10** passing frontend unit tests, Next.js `pnpm build`, and 5 live browser scenarios (0 console errors, 0 HTTP >= 400).

---

## [0.6.0-m6] - 2026-11-24

### Added — Phase 3 Milestone 6: pgvector RAG Multilingual AI Counselor
- **Hybrid `pgvector` + FTS RAG Schema & Migration (`eddfbde391c1`):**
  - Added `rag_knowledge_chunks` (`Vector(384)` HNSW cosine index + PostgreSQL `TSVECTOR` GIN index + `content_hash` idempotency + `epistemic_tier` / `source_type` / `is_outdated` / `has_conflict` metadata) and `scholarship_programs` (`8` curated official domestic & international aid policies).
  - Extended `counselor_conversations` (`active_institution_id`, `active_applicant_type`, `active_topic`) and `counselor_messages` (`epistemic_breakdown`) for multi-turn contextual follow-ups and structured provenance.
- **Zero-Cost (`$0`) Multilingual Embeddings & Knowledge Indexer (`embeddings.py`, `rag_indexer.py`):**
  - Expanded local 384-dim feature-hashing tokenizer with Latin accents, Arabic Unicode, Devanagari, CJK, subword 3-grams, and multilingual admissions/tuition/scholarship/transfer concept bridges.
  - Seeded & indexed **1,689** verified chunks across requirements (`94`), deadlines (`25`), scholarships (`8`), country qualifications (`11`), articulation agreements (`4`), and prioritized institutional overviews/costs/programs (`1,547` chunks) with on-demand indexing for all `6,699` institutions.
- **Retrieval-Grounded Counselor Service, Security & UI (`/counselor`):**
  - Separates **Official Institutional Facts**, **Historical Patterns**, **Personalized AI Interpretation**, and **Missing / Conflicting / Outdated Warnings**; detects uncurated requirements and `DataQualityFlag` conflicts without fabricating answers.
  - Loads `StudentProfile`, native GPA scales (`16.5/20`, `4.0`, etc.), courses, Document Vault extractions, Milestone 3 checklists, Milestone 4 transfer analyses, and Milestone 5 recommendations strictly scoped by `profile_id`.
  - Added `GET/DELETE /api/v1/counselor/conversations/{id}` (strict `profile_id` ownership check) and `POST /api/v1/counselor/rag/search`.
  - Rebuilt `/counselor` UI with light theme + Arabic RTL support, multi-turn `conversation_id` memory sidebar, source-typed citation cards, and workflow deep links (`Ask AI Counselor` from `/matching`).
  - Verified with **43** passing backend `pytest` tests, **9** frontend unit tests, Next.js production build, and live browser conversations across English follow-ups, Haitian Creole, Harvard uncurated guardrails, and Arabic RTL.

---

## [0.5.0-m5] - 2026-11-24

### Added — Phase 3 Milestone 5: Four-Dimensional Explainable University Matching Engine
- **Matching Schema & Migration (`84ea3bee96d4`):**
  - Added `matching_preferences` (criteria, budget, country/institution type preferences, and per-dimension priority weights) and `university_recommendations` (cached composite + 4 dimension scores, category classification, explanation breakdown, and per-student shortlist/dismiss state with unique `(profile_id, institution_id)` constraint).
- **Explainable 4-Dimension Matching Engine (`apps/api/app/services/matching_engine.py`):**
  - Independently evaluates **Academic Fit** (`0.30` default; CIP major alignment, international GPA normalization for `0–20` FR/HT, `0–100%`, German `1.0–6.0`, US `4.0`, and SAT/ACT test-blind vs. optional vs. required), **Financial Compatibility** (`0.25` default; distinguishes published IPEDS/institution COA from composite estimates and international aid limits), **Admissions Readiness** (`0.25` default; reuses Milestone 3 `evaluate_dynamic_checklist`), and **Transfer & Credit Compatibility** (`0.20` default; reuses Milestone 4 `evaluate_student_transfer_profile`, Tier 1/2/3 & degree applicability).
  - First-Year safeguard: marks Transfer Compatibility `not_applicable` (`weight_applied = 0.0`) and proportionally re-normalizes active dimension weights without penalty.
  - Missing-data safeguard: tags missing inputs as `insufficient_information` (reducing `data_confidence_score` and classifying sparse inputs as `insufficient_data`) rather than silent negative penalties, and exposes exact `calculation_formula` arithmetic without deceptive admission probability claims.
- **Matching REST APIs & Student UI (`apps/api/app/api/v1/matching.py`, `/matching`):**
  - Added `GET/PUT /api/v1/matching/preferences`, `POST /api/v1/matching/run`, `POST /api/v1/matching/evaluate/{institution_id}`, `POST /api/v1/matching/recommendations/{institution_id}/save`, `GET /api/v1/matching/shortlist`, and `POST /api/v1/matching/compare`.
  - Built `/matching` frontend dashboard, `MatchExplanationPanel.tsx`, `ComparisonPanel.tsx`, and added `nav.matching` across Header navigation and `UI_TRANSLATIONS` (10 languages including Arabic RTL).
  - Verified with **38** passing backend `pytest` tests, **8** passing frontend unit tests, Next.js production build, and live browser testing (First-Year, Transfer, Shortlist, Comparison, and Arabic RTL).

---

## [0.5.0-m4] - 2026-11-24

### Added — Phase 3 Milestone 4: Transfer Articulation & Global Credit Intelligence Engine
- **3-Tier Transfer Schema & pgvector HNSW Index (`a70efe4e6454`):**
  - Added `course_catalog` (`Vector(384)` semantic embeddings + HNSW cosine index), `articulation_agreements`, and `course_equivalencies` (`equivalency_tier` 1–3, degree applicability flags), plus extended `courses` with `learning_outcomes` and nullable `syllabus_document_id` FK.
- **Course Catalogs, EULA-Compliant ASSIST Connector & Seeder:**
  - Built `AssistOrgConnector` requiring authorized `ASSIST_API_KEY` (`help@assist.org`) under the ASSIST EULA and refusing restricted web scraping.
  - Seeded **52** course catalog entries across **9** US & international institutions (De Anza, SMC, UC Berkeley, UCLA, SFSU, UMich, U of Toronto, TUM, Sorbonne), **4** articulation agreements, and **33** Tier 1/2 equivalencies (**30** Tier 1 published California CC -> UC/CSU, **3** Tier 2 historical UMich patterns).
- **3-Tier Matching, Credit Systems & Degree Applicability Engine (`articulation_engine.py`):**
  - Preserves `us_quarter`, `us_semester`, `ects`, `ca_credit`, and `uk_cat` original credit values alongside informational normalized semester credits.
  - Strictly distinguishes Tier 1 Official, Tier 2 Historical, Tier 3 AI-Predicted (`50%` semantic outcome similarity, `20%` credit match, `15%` subject, `15%` level), and Unverified coursework (`requires_syllabus`).
  - Separates accepted units from Major, GE, Elective-only, and Non-Applicable/Duplicate credits; detects duplicate coursework; adds syllabus parsing & `POST /transfer/courses/{id}/attach-syllabus`.
  - Upgraded `/transfer` dashboard (`TransferCreditIntelligencePanel.tsx`) and `/api/v1/transfer/*` endpoints; verified with **32** passing backend pytest tests, **7** frontend unit tests, Next.js build, and live browser simulator checks.

---

## [0.5.0-m3] - 2026-11-24

### Added — Phase 3 Milestone 3: Global Admissions Requirements Intelligence Engine
- **Normalized Requirements & Deadlines Schema (`84eae1d08b41`):**
  - Added `requirement_templates`, `institution_requirements`, `requirement_conditions`, `deadlines`, and `country_qualifications`, and extended `application_requirement_status` with nullable provenance/auto-matching columns (`institution_requirement_id`, `satisfied_by_document_id`, `satisfied_by_profile_field`, `auto_matched`, `verification_status`, `source_url`).
- **Source-Verified Global Requirements & National Qualifications (`apps/api/app/ingestion/requirements_seed.py`):**
  - Seeded **27** reusable requirement templates, **11** country qualification & national exam frameworks across **9** priority countries (`US`, `CA`, `GB`, `FR`, `DE`, `HT`, `IN`, `AU`, `JP`), **94** verified institutional and program-specific requirements across **21** universities (e.g., UC Berkeley, UCLA, UMich, MIT, De Anza College, University of Toronto, McGill, UBC, Oxford, Cambridge, UCL, Sorbonne Université, Paris-Saclay, TUM, LMU Munich, UEH, Quisqueya University, University of Delhi, IIT Kharagpur, University of Melbourne, University of Tokyo), **36** conditional rules, and **25** deadlines.
  - Explicitly refuses to fabricate requirements when an institution is uncurated (`requirements_unverified` / `coverage_notice`).
- **Dynamic Checklist Engine, APIs & Grounded Multilingual Counselor:**
  - Implemented `apps/api/app/services/requirements_engine.py` evaluating `StudentProfile` GPAs, semester/quarter credits, completed terms, major prerequisites (`Economics`, `Computer Science`), UC 7-course breadth, English/French/German/Japanese proficiency conditions, secondary vs. college Document Vault transcripts, and missing-data safeguards.
  - Added `GET /api/v1/institutions/{id}/requirements`, `GET /api/v1/institutions/{id}/checklist`, `GET /api/v1/qualifications`, `GET /api/v1/deadlines/upcoming`, and `POST /api/v1/applications/{id}/refresh-checklist`.
  - Grounded `MultilingualCounselorService` in PostgreSQL requirements/deadlines with real verified citations across English, Haitian Creole, French, Spanish, and Arabic.
  - Upgraded `/universities/[id]`, `/first-year`, `/transfer`, and `/counselor` UIs; verified with 29 backend `pytest` tests, 7 frontend unit tests, Next.js build, and live browser testing.

---

## [0.5.0-m2] - 2026-11-24

### Added — Phase 3 Milestone 2: U.S. Institutional Dataset Ingestion & Directory UI
- **Schema Extension & Reversible Migration (`77ffb27f3bc8`):**
  - Extended `institutions` with College Scorecard outcomes and admissions indicators (`net_price_calculator_url`, `application_portal_url`, `open_admissions`, `calendar_system`, `undergrad_application_fee`, `completion_rate_4yr`, `completion_rate_less_4yr`, `retention_rate`, `median_earnings_10yr`, `median_debt`, `pct_international`, `pct_pell`, `student_demographics`, `avg_net_price`, `cost_of_attendance`, `ope6_id`, `data_reporting_year`, `primary_source`) plus B-tree search indexes (`control_type`, `tuition_in_state`, `tuition_out_of_state`, `total_enrollment`).
- **NCES IPEDS & College Scorecard Connectors (`apps/api/app/ingestion/`):**
  - Implemented `IPEDSConnector` ingesting 2023–2024 `HD2023`, `IC2023`, `IC2023_AY`, `ADM2023`, and `DRVEF2023` bulk federal files (`fetched=6059`, `created=6055`, `updated=4`, `7,074` itemized cost rows).
  - Implemented `CollegeScorecardConnector` (`bulk` CSV + `DEMO_KEY` REST API mode) coercing `PrivacySuppressed` to SQL `NULL`, linking `1,296` branch campuses via `MAIN=0` / `ope6_id`, and upserting `21,434` CIP `academic_programs` rows (`fetched=6272`, `created=585`, `updated=5687`).
  - Added source authority ranking (`official_website > ipeds > government_db > college_scorecard > manual_entry > api > openalex_ror`), stale-year protection, non-duplicating `conflicting_data` audit flags (`477` detected), and `deduplicate_us_non_ipeds` collapsing 4 seed/OpenAlex duplicates into canonical IPEDS records (`6,699` total verified institutions: `6,644` U.S. + `55` international).
- **Directory Search & Intelligence Detail UI:**
  - Added `GET /api/v1/institutions/filters` and enhanced `GET /api/v1/institutions/search` (`enrollment_min`, `enrollment_max`, `sort`).
  - Upgraded `/universities` (paginated catalog with 7 faceted filters and explicit `Not Reported` null handling) and launched `/universities/[id]` (affordability, admissions benchmarks, enrollment & outcomes, associated campuses, CIP classifications, itemized cost tables, and SHA-256 provenance trail).
  - Verified with 25 passing backend `pytest` tests, 7 passing frontend tests, Next.js `15.5.29` production build, and live Chromium UI verification.

---

## [0.5.0-m1] - 2026-11-24

### Added — Phase 3 Milestone 1: Global Institutional DB & Ingestion Infrastructure
- **Database Schema & Reversible Migration (`5f3c21a2d902`):**
  - Enabled PostgreSQL `pg_trgm` and `unaccent` extensions alongside `pgvector`.
  - Added `countries` table (ISO 3166-1 alpha-2, currencies, languages, higher-ed ministries, accreditation bodies) seeded with 33 global country authorities.
  - Extended `institutions` with multi-campus hierarchy (`parent_institution_id`, `campus_name`, `is_main_campus`), canonical global identifiers (`ipeds_unit_id`, `ope_id`, `ucas_code`, `ror_id`, `openalex_id`, `external_ids`), admission percentiles, `data_completeness_score`, and PostgreSQL `tsvector` FTS trigger + GIN/trigram indexes.
  - Added `academic_programs`, versioned `institution_costs`, `ingestion_runs`, non-destructive `data_provenance` (SHA-256 `data_hash` + `previous_value`), and `data_quality_flags`.
- **Extensible Ingestion Pipeline (`apps/api/app/ingestion/`):**
  - Implemented `BaseInstitutionConnector`, `IngestionPipeline` (idempotent upserts, non-destructive change logging, completeness scoring, quality flag detection), and CLI runner (`app.ingestion.cli`).
  - Built and verified CC0 `OpenAlexRorConnector` ingesting real multi-country university data (US, CA, HT, FR, GB, DE, IN, NG, BR, MX, JP, AU) with 100% re-run idempotency.
- **Institutional Search, Provenance & Admin RBAC APIs:**
  - Added `GET /api/v1/countries`, faceted `GET /api/v1/institutions/search`, `GET /api/v1/institutions/{id}`, `GET /api/v1/institutions/{id}/provenance`, and role-protected `GET /api/v1/admin/quality-flags` & `GET /api/v1/admin/ingestion-runs`.
  - Verified with 20 passing backend pytest tests and 7 passing frontend tests.

---

## [0.4.1] - 2026-11-24

### Quality Assurance & End-to-End Audit
- **Full Internationalization Capabilities Audit:**
  - Audited all 8 internationalization capabilities across 7 application routes (`/`, `/dashboard`, `/first-year`, `/transfer`, `/counselor`, `/documents`, `/universities`, `/profile`).
  - Expanded registry to 36 global languages across 3 verified tiers (`fully_supported`: 10, `beta_preview`: 8, `discovery`: 18).
  - Verified RTL layouts across Arabic (`ar-SA`), Hebrew (`he-IL`), Persian (`fa-IR`), and Urdu (`ur-PK`) with dynamic layout mirroring.
- **Document Vault Heuristic Fix & Multi-Language Ingestion:**
  - Resolved language detection substring collision where French transcripts containing `"notes"` falsely triggered Haitian Creole detection (`"not"` substring).
  - Authored authentic sample transcripts in English, French, Haitian Creole, Spanish, and Arabic.
  - Implemented end-to-end automated pytest suite (`test_e2e_document_audit.py`) verifying SHA-256 cryptographic checksums, immutable disk storage preservation, academic entity extraction, and side-by-side translation generation.
- **Mobile Viewport Responsiveness:**
  - Implemented mobile navigation menu toggle and drawer in `Header.tsx`, giving mobile and tablet users complete access to all 7 application portals.
- **AI Counselor Grounded Citations Verification:**
  - Audited multilingual responses and validated that all official citation URLs (`assist.org`, `universityofcalifornia.edu`, `cdss.berkeley.edu`, `wes.org`, `icas-ca.org`) resolve to active university resources.
- **Automated Test Suite Expansion:**
  - 15/15 backend pytest tests passing (including end-to-end multi-language document vault and citations audit).
  - 7/7 frontend node unit tests passing.
  - Next.js 15 production build generating 11/11 static routes without errors.


---

## [0.4.0] - 2026-11-24

### Added
- **Global Language Library & BCP 47 Registry:**
  - Centralized language registry (`apps/web/src/lib/i18n/languages.ts` and `apps/api/app/core/i18n.py`) supporting 35+ languages across ISO 639-1/3 and BCP 47 tags.
  - Native and English name search, script families (`Latn`, `Arab`, `Deva`, `Hans`, `Hebr`, `Ethi`), text direction metadata, and translation readiness tiers (`fully_supported`, `beta_preview`, `discovery`).
- **Right-to-Left (RTL) Layout System:**
  - Automated document direction switching (`dir="rtl"` vs. `dir="ltr"`), dynamic element alignment, CSS logical properties, and bidirectional typography.
- **Regional Formatting Engine:**
  - Strict isolation between display language, regional formatting locale, and reference currency (`formatNumber`, `formatCurrency`, `formatDate`, `formatGPA`).
  - Guaranteed invariant: Changing display language or reference currency never silently recalculates official university tuition amounts or GPA scales.
- **Persistent User Language Preferences:**
  - Centralized preference store via `UserPreference` relational model and REST APIs (`GET/PUT /api/v1/preferences`).
  - Persistent guest fallback in `localStorage` and device synchronization for authenticated profiles; manual selections override auto-detection without repeated geolocation prompts.
- **Multilingual AI Admissions Counselor:**
  - Conversational counseling engine (`apps/api/app/services/counselor.py` and `apps/web/src/app/counselor/page.tsx`) with dynamic language switching.
  - Multilingual reasoning in Haitian Creole, Spanish, French, Arabic, Hindi, Mandarin, and English.
  - Verification grounded in official published sources (Assist.org, University of California Transfer Pathways, UC Berkeley CDSS, WES / AACRAO Edge).
  - Explicit non-binding admissions disclaimers and clickable citations to official university requirement pages.
- **Secure Academic Document Vault & Translation Integrity:**
  - Immutably preserves original student transcripts with cryptographic SHA-256 integrity checksums; original files are never overwritten or substituted by translations.
  - Four distinct representations maintained: Original Document, Extracted Entities & Metadata, Translated Academic Record, and Human Verification Status.
  - Domain parser identifying academic institutions, qualifications (Haitian Baccalauréat, French Bac, US Community College ADT), grading scales (0-20 scale, 4.0 scale), and course records.
  - Side-by-side comparison interface (`apps/web/src/app/documents/page.tsx`) with transparent machine-translation disclaimers and qualitative confidence badges (`High Confidence`, `Needs Review`, `Human Verification Required`).
- **Comprehensive Automated Testing:**
  - 13 automated backend tests in pytest covering language registries, preference persistence, counselor reasoning, citations preservation, and document vault immutability.
  - 6 automated frontend unit tests covering language lookups, RTL detection, formatting isolation, and UI dictionary translations.
  - Monorepo `turbo test` running 19 automated tests with 100% pass rate.


---

## [0.3.0] - 2026-11-23

### Added
- **Monorepo Architecture (Turborepo & pnpm):**
  - Root `package.json`, `pnpm-workspace.yaml`, and `turbo.json` with pipeline orchestration for `build`, `dev`, `lint`, and `test`.
  - Shared `@platform/tsconfig` package with standard, base, and Next.js compiler configurations.
  - Multi-tier `docker-compose.yml` defining PostgreSQL 16+ with `pgvector` and Redis cache.
- **Backend Architecture & APIs (FastAPI + Python 3.13):**
  - Modular FastAPI application (`apps/api`) with structured v1 API routing and async lifespan handlers.
  - SQLAlchemy 2.0 relational models: `User`, `StudentProfile`, `CitizenshipRecord`, `EducationalSystem`, `GradingSystem`, `EnrollmentRecord`, `Course`, `Institution`, `Application`, `ApplicationRequirementStatus`, `StandardizedTest`, `ExtracurricularActivity`.
  - Alembic migration environment with initial migration (`f957cf5e4815_initial_schema.py`) executing against PostgreSQL with pgvector.
  - Auth provider abstraction (`IAuthProvider`, `MockAuthProvider`, `ClerkAuthProvider`) decoupling vendor auth from core application logic.
  - Seeded initial catalog of higher education institutions (UC Berkeley, UCLA, San Francisco State University, De Anza College).
  - REST endpoints for health checks (`/api/v1/health`), auth session resolution (`/api/v1/session`), universal profile management (`/api/v1/profile`), and application workspaces (`/api/v1/applications`).
- **Frontend Architecture & Student OS (Next.js 15+ App Router):**
  - Complete Next.js App Router application (`apps/web`) with Tailwind CSS, Lucide icons, and Radix UI components.
  - Global responsive navigation header (`src/components/navigation/Header.tsx`) linking Student OS, First-Year, Transfer, Universities, and Universal Profile.
  - Unified Student OS Dashboard (`/dashboard`) displaying profile completion, active application workspaces, pathway badges, and real-time requirement progress.
  - Dedicated First-Year Admissions route (`/first-year`) with high school coursework, standardized test tracking, and essay workspaces.
  - Dedicated Transfer Admissions route (`/transfer`) with community college coursework intake, GPA calculations, and IGETC/CSU-GE articulation trackers.
  - Universal Student Profile management page (`/profile`) supporting multi-script name fields, legal identity, academic enrollment history, and dual pathway strategy.
  - Global University Discovery Catalog (`/universities`) with search, pathway filtering, and one-click application workspace generation.
- **Automated Testing & Verification:**
  - Automated pytest test suite in `apps/api/tests` covering auth provider tokens, health checks, profile creation, first-year workflows, transfer workflows, and requirement checklists (9 tests, 100% pass).
  - Automated frontend test suite in `apps/web/src/lib/api-client.test.ts` executed via Node.js native test runner and type stripping (3 tests, 100% pass).
  - Monorepo-wide test orchestration via `turbo test` (12 tests total passing).
  - Verified live execution of backend (`http://127.0.0.1:8000`) and frontend (`http://localhost:3000`) with healthy database connectivity.


---

## [0.2.0] - 2026-11-23

### Added
- **Master Technical Specifications (Batch 3–5):**
  - `09_INTERNATIONAL_EDUCATION_INTELLIGENCE.md`: Foreign credential evaluation methodology, international grade conversions, and secondary school diploma normalization.
  - `10_UNIVERSITY_MATCHING_ENGINE.md`: Multi-dimensional compatibility scoring, reach/target/safety balancing, and admission probability engine.
  - `11_AI_COUNSELOR_AND_AGENT_ARCHITECTURE.md`: RAG-grounded conversational counseling agent, institutional citation enforcement, and ethical AI guardrails.
  - `12_GLOBAL_SCHOLARSHIP_AND_FINANCIAL_ENGINE.md`: Institutional financial aid benchmarking, Net Price calculation engine, and international student visa financial readiness (I-20 proof of funds).
  - `13_SECURITY_AND_PRIVACY_ARCHITECTURE.md`: FERPA/GDPR compliance framework, encryption architecture, RBAC matrices, and threat mitigation triggers.
  - `14_SYSTEM_ARCHITECTURE.md`: End-to-end cloud infrastructure, Next.js/FastAPI monorepo topology, database scaling tiers, and disaster recovery.
  - `15_DEVELOPMENT_ROADMAP.md`: Phased execution blueprint defining 5 delivery milestones from MVP foundation to global launch.
- **Project Progress Tracker:**
  - `PROJECT_PROGRESS.md`: Single source of truth tracking 19 development workstreams across status, priority, dependencies, acceptance criteria, and next actions.
- **GitHub Collaboration Infrastructure:**
  - `CONTRIBUTING.md`: Engineering workflow standards, branch naming conventions, private repository guidelines, and prioritized development backlog.
  - `.github/ISSUE_TEMPLATE/bug_report.md`: Standardized defect reporting template.
  - `.github/ISSUE_TEMPLATE/feature_request.md`: Standardized feature and specification proposal template.
  - `.github/pull_request_template.md`: Comprehensive pull request verification checklist.

### Changed
- `README.md`: Redesigned with complete 3-pillar architectural diagrams, documentation index with verified links, development status matrix, and roadmap summary.
- `docs/01_PROJECT_STATUS_AND_GAP_ANALYSIS.md`: Updated Section 7 Document Tracker to reflect that all 15 master specifications are complete and verified.

---

## [0.1.0] - 2026-11-23

### Added
- **Initial Repository Foundation & Strategic Specifications (Batch 1–2):**
  - `README.md`: Initial platform mission and architectural overview.
  - `.gitignore`: Comprehensive full-stack ignore rules for secrets, credentials, student PII, and build artifacts.
  - `.env.example`: Sanitized developer environment configuration template.
  - `01_PROJECT_STATUS_AND_GAP_ANALYSIS.md`: Comprehensive inventory, competitive audit, and gap assessment.
  - `02_REVISED_STRATEGIC_ANALYSIS.md` & `deep-dives/REVISED_STRATEGIC_ANALYSIS_FULL.md`: Market opportunity, empirical higher education transfer sizing, unit economics, and risk matrices.
  - `03_BRAND_IDENTITY_AND_NAMING_REPORT.md`: Brand identity evaluations of 25 candidate names across 5 archetypes and trademark clearance roadmap.
  - `04_GO_TO_MARKET_STRATEGY.md` & `deep-dives/GO_TO_MARKET_STRATEGY_FULL.md`: 5-phase wedge go-to-market plan prioritizing California community college transfers.
  - `05_UNIVERSAL_STUDENT_PROFILE_SPECIFICATION.md` & `deep-dives/UNIVERSAL_STUDENT_PROFILE_SPECIFICATION_FULL.md`: Canonical student profile relational schemas (PostgreSQL 16) and REST API contracts.
  - `06_GLOBAL_UNIVERSITY_DATABASE_ARCHITECTURE.md`: Institutional directory schema, IPEDS database integration, and articulation graph structure.
  - `07_APPLICATION_REQUIREMENT_ENGINE.md`: Deterministic requirement validation engine, course prerequisite trees, and validation rules.
  - `08_TRANSFER_INTELLIGENCE_ARCHITECTURE.md`: 3-tier transfer credit equivalency architecture (Verified / Observed / Predicted).
  - `history/UNIVIA-Strategic-Analysis.md`: Archived foundational strategic analysis retained for project history.
- Reconciled initial remote commit `835059a` with local foundation commit `86d86b0` via merge commit `305f6c2`.
