# Changelog

All notable changes to the **Global University Application Platform** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] - Phase 3 In Progress (Milestones 2–7)

### Planned
- Milestone 2: Bulk US institutional ingestion (NCES IPEDS / Urban Institute / College Scorecard) + frontend Global University Intelligence UI.
- Milestone 3: Admissions Requirements Engine (First-Year & Transfer conditional rules and versioned deadlines).
- Milestone 4: 3-Tier Transfer Articulation Engine (ASSIST.org API-keyed connector + `pgvector` Tier 3 predictions).
- Milestone 5: 4-Dimensional Explainable University Matching Engine (Reach / Target / Likely).
- Milestone 6: Live `pgvector` RAG Multilingual AI Counselor (`$0` local embedding default).
- Milestone 7: Application Routing directory, link verification, and honest external confirmation flow.

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
