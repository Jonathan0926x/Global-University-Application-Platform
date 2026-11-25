# Global University Application & Admissions Intelligence Platform

> **"One Student Profile. Every University. One Global Platform."**<br/>
> *AI-powered global university discovery, application management, and transfer intelligence infrastructure.*

---

## 🌍 Platform Overview

Higher education admissions and transfer systems operate as fragmented, regional monopolies characterized by extreme information asymmetry, siloed institutional software, and manual evaluation bottlenecks. Students worldwide are forced to navigate conflicting admission requirements, repetitive application forms, opaque transfer articulation agreements, and exorbitant credential evaluation fees.

The **Global University Application & Admissions Intelligence Platform** is architected as the world's first unified global admissions operating system. Its mission is to make higher education accessible, transparent, and navigable to students worldwide through a centralized application management and admissions intelligence ecosystem.

The platform is built around one core architectural principle:
> **A student should never have to navigate the complexity of the global higher education system alone.**

---

## 🏛️ Core Product Pillars

```mermaid
flowchart TD
    subgraph Pillar1["1. Student Operating System (Student OS)"]
        SO1["Universal Student Profile (USP)"]
        SO2["First-Year Application Portal"]
        SO3["Transfer Application Portal"]
        SO4["Centralized Application & Deadline Tracker"]
        SO5["Academic Document & Transcript Locker"]
    end

    subgraph Pillar2["2. Admissions Intelligence"]
        AI1["3-Tier Transfer Credit Equivalency Engine"]
        AI2["International Credential & GPA Conversion"]
        AI3["University Compatibility & Matching Engine"]
        AI4["AI Admissions Guidance & Essay Studio"]
        AI5["Global Scholarship & Affordability Engine"]
    end

    subgraph Pillar3["3. Global University Infrastructure"]
        UI1["Worldwide University Directory (IPEDS + Global)"]
        UI2["Verified Institutional Admissions Requirements"]
        UI3["Direct Verified Application Links"]
        UI4["Institutional Data Ingestion & Verification Feeds"]
        UI5["Enterprise CRM Integration Rails (Slate/Salesforce)"]
    end

    Pillar1 <--> Pillar2
    Pillar2 <--> Pillar3
    Pillar1 <--> Pillar3

    style Pillar1 fill:#0f172a,stroke:#3b82f6,stroke-width:2px,color:#fff
    style Pillar2 fill:#0f172a,stroke:#10b981,stroke-width:2px,color:#fff
    style Pillar3 fill:#0f172a,stroke:#8b5cf6,stroke-width:2px,color:#fff
```

### 1. Student Operating System (Student OS)
* **Universal Student Profile:** Canonical academic identity containing personal demographics, educational history, standardized coursework, extracurricular activities, and verified transcripts.
* **First-Year Application Portal:** Tailored application pathways for secondary school graduates, supporting holistic admissions criteria, essays, and recommendation letter tracking.
* **Transfer Application Portal:** Dedicated workflow for community college and university transfer students, tracking earned college credits, prerequisites, and general education completion.
* **Application & Deadline Tracker:** Real-time visibility into application statuses, upcoming deadlines, document submission checklists, and institutional decisions.
* **Academic Document Organization:** Encrypted document locker for high school transcripts, college transcripts, syllabi, test score reports, and financial aid paperwork.

### 2. Admissions Intelligence
* **Transfer Credit Intelligence:** A three-tier equivalency engine (Verified official articulation, Observed historical transfers, and AI-Predicted syllabus similarity) solving the 43% credit loss problem.
* **International Credential & GPA Interpretation:** Country-specific academic conversion scales (e.g., French Baccalauréat, UK A-Levels, Indian CBSE/ICSE, Haitian Baccalauréat) normalized to standard benchmarks.
* **University Matching Engine:** Multi-dimensional compatibility scoring balancing academic profile, affordability, transfer articulation pathways, campus environment, and career goals.
* **AI College Counselor:** RAG-grounded conversational agent providing real-time admissions advice with strict institutional citations and ethical guardrails preventing hallucination.
* **Global Scholarship & Affordability Analysis:** Personalized net price calculation, institutional merit scholarship eligibility, and international student financial readiness modeling (I-20 / visa verification).

### 3. Global University Infrastructure
* **Worldwide University Directory:** Comprehensive database covering over 4,000 US degree-granting institutions and expanding to major higher education institutions worldwide.
* **Verified Institutional Records:** Standardized curriculum requirements, minimum GPA thresholds, prerequisite coursework, and standardized testing policies.
* **Official Application Links:** Direct routing to official university admissions portals, avoiding misleading third-party aggregators.
* **Institutional Ingestion & Verification Rails:** Data pipelines consuming public datasets (IPEDS, ASSIST.org), state transfer databases, and institutional feeds.
* **Enterprise Integration (Future):** Authorized API connectors for institutional CRMs (Slate, Salesforce Education Cloud) for verified data dispatch.

---

## 🛠️ Technology Architecture

> [!NOTE]
> **Active Engineering Build (Phase 3, Milestones 1–7.2 Complete):** UniGlobe runs Next.js 15 App Router, FastAPI + SQLAlchemy 2.0, PostgreSQL + `pgvector` (`6,699` global/US institutions, `94` verified requirements, `3-Tier` transfer articulation, `4-Dimensional` matching at `/matching`, hybrid `pgvector` + FTS RAG Multilingual AI Counselor at `/counselor`, the Official Application Routing Directory & 6-state Honest External Confirmation Tracker at `/applications`, and the RBAC-gated Verification & Trust Operations Console with link-health, expiration, pathway, redirect, and reverification governance at `/operations`). Follow [Development Roadmap](docs/15_DEVELOPMENT_ROADMAP.md) and [`PROJECT_PROGRESS.md`](PROJECT_PROGRESS.md) for current milestone status.

```
+-----------------------------------------------------------------------------------+
|                         CLIENT LAYER (Planned: Next.js 14+)                       |
|   App Router | TypeScript | Tailwind CSS | shadcn/ui | React Hook Form | TanStack |
+------------------------------------------+----------------------------------------+
                                           | HTTPS / WSS
                                           v
+-----------------------------------------------------------------------------------+
|                     API GATEWAY & BACKEND (Planned: FastAPI)                      |
|       Python 3.12+ | Pydantic v2 | AsyncIO | SQLAlchemy 2.0 | Celery Tasks        |
+---------------------+--------------------+--------------------+-------------------+
                      |                    |                    |
                      v                    v                    v
+-------------------------------+ +------------------+ +----------------------------+
|  RELATIONAL & VECTOR STORE    | |  MESSAGE & CACHE | |      OBJECT STORAGE        |
|  PostgreSQL 16+ with pgvector | |    Redis 7.2+    | | Encrypted S3 / Cloudflare  |
|  (ACID Records + Similarity)  | |  (Tokens, Queue) | | R2 (Transcripts & Documents|
+-------------------------------+ +------------------+ +----------------------------+
```

| Layer | Technology | Implementation State | Architectural Purpose |
|---|---|---|---|
| **Frontend** | Next.js 15+ (App Router), TypeScript, Tailwind CSS | ✅ **Live & Tested** | Server & Client components, multilingual i18n, RTL support, responsive UI |
| **Backend** | Python 3.13 (FastAPI), Pydantic v2, SQLAlchemy 2.0 | ✅ **Live & Tested** | Asynchronous REST APIs, validation, multilingual counseling, document vault |
| **Database** | PostgreSQL 17 with `pgvector` & Alembic | ✅ **Live & Tested** | 19 relational tables, migrations, foreign credential and course tracking |
| **Auth** | Provider Abstraction (`MockAuthProvider`, `Clerk`) | ✅ **Live & Tested** | Decoupled vendor layer, bearer claims, automated user provisioning |
| **Document Vault** | Sandboxed Object Storage + SHA-256 Checksums | ✅ **Live & Tested** | Original document preservation, entity parsing, side-by-side translation |
| **AI Counselor** | Grounded Admissions Reasoning Service | ✅ **Live & Tested** | Multilingual admissions counseling with official citations (Assist.org, UC Pathways) |

---

## 📊 Development Status

The platform tracks work across distinct verification states:

| Status Category | Current State | Description |
|---|---|---|
| **1. Strategic & Technical Documentation** | ✅ **Complete (15/15)** | All 15 foundational specifications and deep-dive models completed. |
| **2. Architecture Foundation (Phase 1)** | ✅ **Complete & Tested** | Turborepo monorepo, Next.js 15, FastAPI, PostgreSQL 17 + pgvector, Alembic. |
| **3. Internationalization & Vault (Phase 2)** | ✅ **Complete & E2E Audited** | 36-language BCP 47 registry, 4 RTL layouts (ar, he, fa, ur), Multilingual Counselor, Document Vault with SHA-256 integrity, mobile drawer. |
| **4. Global Intelligence, Matching, RAG Counselor & Routing (Phase 3 M1–M7)** | ✅ **Complete & Tested** | `6,699` institutions, `94` verified requirements, `33` Tier 1/2 equivalencies + `pgvector` Tier 3 matching, 4D Match Engine (`/matching`), Hybrid RAG Counselor (`/counselor`), **428** seeded routes (**414** verified / **14** CRM & cross-domain queued for manual review), 6-state confirmation tracker (`/applications`), and RBAC verifier console (`/operations`). |
| **5. Automated Test Verification** | ✅ **59 Tests Passing** | **49** backend `pytest` tests + **10** frontend `node:test` unit tests (100% pass) + live browser QA. |
| **6. Live Services** | ✅ **Operational & Verified** | Web at `http://localhost:3000` & API at `http://127.0.0.1:8000`. |


---

## 📚 Master Documentation Index

All 15 master strategic and technical specifications are located in the [`docs/`](docs/) directory:

### Foundation & Strategy (Batch 1)
* [01. Project Status and Gap Analysis](docs/01_PROJECT_STATUS_AND_GAP_ANALYSIS.md) — Comprehensive pre-development inventory and workstream audit.
* [02. Revised Strategic Analysis](docs/02_REVISED_STRATEGIC_ANALYSIS.md) — Market opportunity, competitive landscape, and economic model. *(Deep-Dive: [Full Strategic Analysis](docs/deep-dives/REVISED_STRATEGIC_ANALYSIS_FULL.md))*
* [03. Brand Identity and Naming Report](docs/03_BRAND_IDENTITY_AND_NAMING_REPORT.md) — Evaluation of 25 name candidates across 5 naming archetypes with trademark clearance roadmap.

### Core Architecture & Strategy (Batch 2)
* [04. Go-to-Market Strategy](docs/04_GO_TO_MARKET_STRATEGY.md) — 5-phase wedge go-to-market plan prioritizing US community college transfers. *(Deep-Dive: [Full GTM Playbook](docs/deep-dives/GO_TO_MARKET_STRATEGY_FULL.md))*
* [05. Universal Student Profile Specification](docs/05_UNIVERSAL_STUDENT_PROFILE_SPECIFICATION.md) — Canonical student data model and projection layer. *(Deep-Dive: [Full SQL & API Specification](docs/deep-dives/UNIVERSAL_STUDENT_PROFILE_SPECIFICATION_FULL.md))*
* [06. Global University Database Architecture](docs/06_GLOBAL_UNIVERSITY_DATABASE_ARCHITECTURE.md) — Higher education database schema, IPEDS integration, and global institution entities.

### Engines & Intelligence (Batch 3)
* [07. Application Requirement Engine](docs/07_APPLICATION_REQUIREMENT_ENGINE.md) — Deterministic requirement parser, eligibility matrix, and validation rules.
* [08. Transfer Intelligence Architecture](docs/08_TRANSFER_INTELLIGENCE_ARCHITECTURE.md) — 3-tier transfer credit equivalency engine tackling the 43% credit loss problem.
* [09. International Education Intelligence](docs/09_INTERNATIONAL_EDUCATION_INTELLIGENCE.md) — Global academic credential interpretation, foreign grade scales, and secondary diplomas.

### AI, Matching & Financials (Batch 4)
* [10. University Compatibility & Matching Engine](docs/10_UNIVERSITY_MATCHING_ENGINE.md) — Multi-dimensional compatibility scoring and strategic reach/target/safety balancing.
* [11. AI Counselor & Agent Architecture](docs/11_AI_COUNSELOR_AND_AGENT_ARCHITECTURE.md) — RAG-based AI counselor with institutional source citations and ethical guardrails.
* [12. Global Scholarship & Financial Engine](docs/12_GLOBAL_SCHOLARSHIP_AND_FINANCIAL_ENGINE.md) — Institutional aid benchmarking, Net Price calculation, and visa proof-of-funds (I-20) readiness.

### Infrastructure & Roadmap (Batch 5)
* [13. Security & Privacy Architecture](docs/13_SECURITY_AND_PRIVACY_ARCHITECTURE.md) — FERPA/GDPR compliance, encryption at rest/transit, RBAC, and threat mitigation.
* [14. System Architecture Specification](docs/14_SYSTEM_ARCHITECTURE.md) — End-to-end cloud infrastructure, monorepo design, database topology, and scaling tiers.
* [15. Development Roadmap](docs/15_DEVELOPMENT_ROADMAP.md) — Phased engineering delivery plan across 5 milestones from MVP foundation to global launch.

### Historical Documentation
* [UNIVIA Strategic Analysis (Archive)](docs/history/UNIVIA-Strategic-Analysis.md) — Initial foundational report retained solely for historical documentation.

---

## 🗺️ Upcoming Engineering Roadmap

| Phase | Milestone | Primary Deliverables | Target Horizon |
|---|---|---|---|
| **Phase 1** | **Foundational Architecture** | Monorepo setup, Auth (Clerk/Auth0), Core PostgreSQL schema, Universal Student Profile CRUD | Month 1–2 |
| **Phase 2** | **Directory & Requirements** | IPEDS data ingestion (4,000+ US institutions), deterministic requirement validation engine | Month 2–3 |
| **Phase 3** | **Transfer Intelligence MVP** | California ASSIST.org ingestion, Tier 1/2 course equivalency lookup, OCR transcript parser | Month 3–4 |
| **Phase 4** | **AI Counselor & Affordability** | RAG-grounded AI counselor, Net Price calculator, scholarship discovery matching | Month 4–5 |
| **Phase 5** | **Global Readiness & Beta** | International credential engine (UK, France, India), security audit, pilot beta launch | Month 5–6 |

---

## 🔒 Security, Privacy & Repository Governance

* **Private Repository:** This repository contains proprietary architecture, data models, and business logic. Visibility must remain **PRIVATE**.
* **FERPA & GDPR Compliance:** Strict consent-based data sharing, end-to-end document encryption, zero plain-text PII storage, and immutable audit logs.
* **Repository Hygiene:** All API keys, credentials, local environment files (`.env*`), applicant uploads, and database files are strictly ignored via [`.gitignore`](.gitignore).
* **Progress Tracking:** All active engineering tasks, dependencies, and verification criteria are tracked in [`PROJECT_PROGRESS.md`](PROJECT_PROGRESS.md).

---

## 📄 License & Confidentiality

Proprietary and confidential. Copyright © 2026 Jonathan Germain (`Jonathan0926x`). All rights reserved.
Unauthorized reproduction, distribution, or public transmission of this codebase or its specifications is strictly prohibited.
