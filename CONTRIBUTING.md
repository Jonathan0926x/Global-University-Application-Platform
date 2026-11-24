# Contributing to Global University Application Platform

> **Notice:** This repository is **PRIVATE and PROPRIETARY**. Access is restricted to authorized contributors and development team members.

Thank you for contributing to the **Global University Application & Admissions Intelligence Platform**. This document establishes our internal development standards, Git workflow, security protocols, and prioritized engineering backlog.

---

## 🔒 Security & Confidentiality Rules

1. **Private Repository Guarantee:** Never change repository visibility to public or fork to personal external accounts.
2. **Zero Credentials in Git:** Never commit API keys, access tokens, database passwords, private keys, `.env` files, or production secrets. Always use `.env.example` as a template for local variables.
3. **FERPA & Student Privacy:** Real student transcripts, personal identification details, or confidential applicant records must never enter the repository or unencrypted local caches. Use synthetic mock fixtures for automated testing.
4. **Automated Pre-Commit Checks:** Always run `git diff --cached --check` and verify no secrets are present before committing.

---

## 🌿 Git Branching & Workflow

We follow a structured trunk-based / feature-branch workflow:

1. **Main Branch (`main`):**
   - Protected branch representing verified, tested code and specifications.
   - Direct pushes to `main` are restricted once branch protection is enabled.
2. **Feature Branches:**
   - Create branches off `main` using descriptive prefixes:
     - `feat/<short-description>` (e.g., `feat/monorepo-scaffold`)
     - `fix/<short-description>` (e.g., `fix/auth-middleware-jwt`)
     - `docs/<short-description>` (e.g., `docs/update-progress-tracker`)
     - `test/<short-description>` (e.g., `test/equivalency-engine-fixtures`)
3. **Pull Request Protocol:**
   - Open a Pull Request into `main` using the provided [Pull Request Template](.github/pull_request_template.md).
   - Link the relevant milestone issue and workstream from [`PROJECT_PROGRESS.md`](PROJECT_PROGRESS.md).
   - Ensure all automated checks pass before merging.

---

## 📝 Commit Message Conventions

Commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) standard:

```text
<type>(<scope>): <short imperative description>

[optional body explaining context and rationale]

[optional footer referencing issues or breaking changes]
```

**Common Types:**
- `feat`: New user-facing feature or API endpoint.
- `fix`: Bug fix.
- `docs`: Documentation updates or specifications.
- `refactor`: Code reorganization with no functional changes.
- `test`: Adding or modifying automated test suites.
- `chore`: Tooling, build scripts, or dependency updates.

---

## 🎯 Prioritized Development Backlog

All development follows the 8 prioritized engineering milestones established in our roadmap:

### Milestone 1: Technical Foundation & Scaffolding (Phase 1)
- [ ] Initialize Turborepo / pnpm monorepo structure (`apps/web`, `apps/api`, `packages/*`).
- [ ] Scaffold Next.js 14+ frontend application with Tailwind CSS & shadcn/ui.
- [ ] Scaffold FastAPI backend application with Pydantic v2 settings and CORS.
- [ ] Setup PostgreSQL 16+ database container with `pgvector` extension.
- [ ] Setup Alembic database migration tooling.

### Milestone 2: Authentication & Student Profiles (Phase 1)
- [ ] Integrate Clerk / Auth0 authentication with JWT validation middleware.
- [ ] Implement canonical Universal Student Profile (USP) database tables and migrations.
- [ ] Build multi-step Student Profile wizard in Next.js.
- [ ] Author CRUD API endpoints for student demographics, education history, and activities.

### Milestone 3: First-Year & Transfer Application Portals (Phase 1–2)
- [ ] Build Community College Transfer intake portal (college credits, grades, prerequisites).
- [ ] Build First-Year secondary school academic history intake portal.
- [ ] Create Centralized Application Tracker dashboard with status rings and deadlines.
- [ ] Implement Document Vault UI for student-uploaded files.

### Milestone 4: University Database & Discovery Engine (Phase 2)
- [ ] Build IPEDS ETL pipeline to ingest 4,000+ US degree-granting institutions.
- [ ] Implement fast university search and filter API (<150ms latency).
- [ ] Create university detail pages displaying verified admissions criteria.
- [ ] Integrate verified official application links for institutional portals.

### Milestone 5: Application Requirements & Validation Engine (Phase 2)
- [ ] Implement deterministic requirement validation engine (`RequirementParser`).
- [ ] Build prerequisite tree evaluator (satisfaction checks, minimum grades, credit caps).
- [ ] Create dynamic applicant checklist generator tailored per university.
- [ ] Author test suite validating requirement evaluation logic against real catalog samples.

### Milestone 6: Transfer Credit Intelligence & OCR Engine (Phase 3)
- [ ] Ingest California ASSIST.org articulation tables into PostgreSQL articulation schema.
- [ ] Build Tier 1 / Tier 2 course-to-course equivalency search interface.
- [ ] Build client-side encrypted upload pipeline to Cloudflare R2.
- [ ] Implement asynchronous transcript OCR extraction worker using multimodal vision models.

### Milestone 7: AI College Counselor & Financial Intelligence (Phase 4)
- [ ] Build RAG-grounded conversational counseling API using `pgvector` embeddings.
- [ ] Implement strict citation verification and anti-hallucination guardrails.
- [ ] Build institutional Net Price Calculator engine.
- [ ] Implement international student visa financial readiness summary (Form I-20 COA gap).

### Milestone 8: Security Hardening, Audit & Beta Release (Phase 5)
- [ ] Conduct end-to-end security audit and penetration testing.
- [ ] Verify FERPA / GDPR compliance and automated audit logging.
- [ ] Implement brute-force rate-limiting and anomaly detection middleware.
- [ ] Deploy staging environment and launch closed beta pilot with community college students.

---

## 🛠️ Code Style & Quality Standards

- **TypeScript / React:** ESLint + Prettier. Strict type checking (`noImplicitAny: true`). Server components by default.
- **Python:** Ruff for linting and formatting. Type hints required (`mypy --strict`).
- **SQL / Migrations:** Every schema alteration requires a reversible migration script with both upgrade and downgrade paths.
