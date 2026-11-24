# Changelog

All notable changes to the **Global University Application Platform** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] - Phase 1 Planned

### Planned
- Universal Student Profile document upload and OCR transcript parsing.
- Advanced transfer credit articulation rules engine (IGETC / CSU-GE / Assist.org mapping).
- Expanded university catalog ingestion (IPEDS 2024 dataset sync).

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
