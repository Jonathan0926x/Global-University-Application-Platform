# Changelog

All notable changes to the **Global University Application Platform** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] - Phase 3 Complete / Phase 4 Planning

### Planned
- Phase 4: Financial Affordability Engine & Production Verifier Console.

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
