# Global Scholarship & Financial Intelligence Engine

> **Date:** November 23, 2026
> **Status:** Technical Specification — Admissions Intelligence Layer
> **Dependencies:** Universal Student Profile (doc 05), Global University Database (doc 06)

---

## 1. System Vision & Purpose

Financial opacity is the single greatest barrier to global higher education. International students are frequently blindsided by currency fluctuations, hidden mandatory fees, health insurance costs, and restrictions on off-campus employment. Simultaneously, millions of dollars in institutional and foundation scholarships go unawarded due to fragmented discovery.

The Global Scholarship & Financial Intelligence Engine provides:
1. A verified, structured international scholarship database.
2. A deterministic scholarship eligibility matching algorithm.
3. A granular Financial Affordability Calculator calculating Net Out-of-Pocket Cost.
4. Comprehensive global financial aid intelligence (FAFSA, CSS Profile, international student aid restrictions, post-study work regulations).

---

## 2. Global Scholarship Database Schema

```sql
CREATE TABLE scholarships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    name VARCHAR(500) NOT NULL,
    provider_name VARCHAR(300) NOT NULL,
    provider_type VARCHAR(50) NOT NULL
        CHECK (provider_type IN ('university', 'government', 'foundation', 'corporation', 'nonprofit', 'multilateral')),

    description TEXT,
    official_website_url TEXT NOT NULL,
    application_portal_url TEXT,

    -- Award financial taxonomy
    award_type VARCHAR(50) NOT NULL
        CHECK (award_type IN ('full_ride', 'full_tuition', 'fixed_amount', 'tuition_discount_pct', 'stipend', 'renewable_grant')),
    award_amount_min DECIMAL(12,2),
    award_amount_max DECIMAL(12,2),
    award_currency CHAR(3) DEFAULT 'USD',
    is_renewable BOOLEAN DEFAULT FALSE,
    renewal_criteria TEXT,

    -- Expenses covered
    covers_tuition BOOLEAN DEFAULT TRUE,
    covers_fees BOOLEAN DEFAULT FALSE,
    covers_housing BOOLEAN DEFAULT FALSE,
    covers_meals BOOLEAN DEFAULT FALSE,
    covers_books BOOLEAN DEFAULT FALSE,
    covers_health_insurance BOOLEAN DEFAULT FALSE,
    covers_international_travel BOOLEAN DEFAULT FALSE,
    provides_living_stipend BOOLEAN DEFAULT FALSE,

    -- Eligibility targets
    applicant_type VARCHAR(30) DEFAULT 'both'
        CHECK (applicant_type IN ('first_year', 'transfer', 'both', 'graduate')),
    degree_levels JSONB DEFAULT '["bachelors"]', -- associate, bachelors, masters, doctoral
    eligible_majors JSONB DEFAULT '[]', -- empty = open to all majors

    -- Deadlines
    application_deadline DATE,
    academic_year VARCHAR(9) NOT NULL,
    is_deadline_rolling BOOLEAN DEFAULT FALSE,

    -- Provenance & Verification
    source_url TEXT NOT NULL,
    last_verified_at TIMESTAMPTZ NOT NULL,
    verification_status VARCHAR(20) DEFAULT 'verified',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scholarships_provider ON scholarships(provider_type);
CREATE INDEX idx_scholarships_award_type ON scholarships(award_type);
CREATE INDEX idx_scholarships_deadline ON scholarships(application_deadline);
```

### Granular Rule Engine for Eligibility

```sql
CREATE TABLE scholarship_eligibility_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scholarship_id UUID NOT NULL REFERENCES scholarships(id) ON DELETE CASCADE,

    rule_dimension VARCHAR(50) NOT NULL
        CHECK (rule_dimension IN ('citizenship', 'residency', 'destination_country', 'destination_institution',
                                 'minimum_gpa', 'financial_need_level', 'gender', 'underrepresented_group', 'age')),

    rule_operator VARCHAR(20) NOT NULL
        CHECK (rule_operator IN ('equals', 'in', 'not_in', 'greater_than_or_equal', 'less_than_or_equal')),

    rule_value JSONB NOT NULL,
    -- e.g., {"citizenship_codes": ["HT", "JM", "DO"]}
    -- e.g., {"min_gpa": 3.5}
    -- e.g., {"destination_country": "US"}

    is_mandatory BOOLEAN DEFAULT TRUE, -- Mandatory rule vs. preference factor
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scholarship_rules ON scholarship_eligibility_rules(scholarship_id, rule_dimension);
```

---

## 3. Scholarship Matching Engine

The matching engine cross-references a student's Universal Profile against scholarship criteria:

```mermaid
flowchart TD
    STUDENT["Student Universal Profile"] --> PARSE["Extract Demographics, GPA, Citizenship, Destination"]
    PARSE --> FILTER["Database Filter Query"]

    FILTER --> R1{"Hard Criteria Check<br/>Nationality, Destination, Degree Level"}
    R1 -- "Fails" --> EXCLUDE["Excluded"]
    R1 -- "Passes" --> R2{"Academic Check<br/>GPA & Prerequisite Thresholds"}
    R2 -- "Fails" --> EXCLUDE
    R2 -- "Passes" --> R3{"Financial Need Alignment"}

    R3 --> SCORE["Compute Match Score & Rank"]
    SCORE --> OUT["Personalized Scholarship Portfolio"]
```

### Output Ranking Criteria:
1. **Eligibility Alignment:** 100% hard criteria match.
2. **Award Impact:** Prioritizes Full-Ride and Full-Tuition opportunities over small one-time awards.
3. **Application Deadline Feasibility:** Highlights opportunities with adequate preparation time.

---

## 4. Financial Affordability Calculator

The Affordability Calculator establishes a realistic Total Cost of Attendance (TCOA) model that distinguishes **direct billable institutional charges** from **indirect living and travel expenses**.

```mermaid
flowchart LR
    subgraph "Direct Billable Costs"
        T["Tuition"]
        F["Mandatory Fees"]
        H["On-Campus Housing"]
        M["Campus Meal Plan"]
    end

    subgraph "Indirect Living Costs"
        B["Books & Course Materials"]
        INS["Health Insurance (Mandatory for Intl)"]
        TR["Local & International Transportation"]
        P["Personal Expenses & Visa Fees"]
    end

    subgraph "Calculated Affordability"
        TCOA["Total Cost of Attendance (TCOA)"]
        AID["- Confirmed & High-Probability Aid"]
        NET["= Net Out-of-Pocket Remaining Gap"]
    end

    T & F & H & M --> TCOA
    B & INS & TR & P --> TCOA
    TCOA --> NET
    AID --> NET
```

### Detailed Cost Aggregation Formula

$$\text{TCOA} = (\text{Tuition} + \text{Mandatory Fees}) + (\text{Housing} + \text{Meals}) + (\text{Books} + \text{Health Insurance} + \text{Transportation} + \text{Personal})$$

$$\text{Net Annual Cost} = \text{TCOA} - (\text{Institutional Need Aid} + \text{Institutional Merit Aid} + \text{Pell Grant / Govt Aid} + \text{External Scholarships})$$

### Currency Conversion Engine
* Integrated with daily forex rates (ECB / OpenExchangeRates).
* Allows international students to view all budgets in their native currency (e.g., Haitian Gourde `HTG`, Euro `EUR`, Indian Rupee `INR`, Nigerian Naira `NGN`) alongside destination currency (`USD`, `CAD`, `GBP`, `EUR`).
* Automatically flags currency exchange volatility warnings for high-inflation home currencies.

---

## 5. Application Cost Planner

Beyond tuition, applying to universities entails significant up-front cash outflows. The platform aggregates an **Application Budget Forecast**:

| Application Cost Element | Typical Cost Range | Platform Intelligence & Fee Waiver Optimization |
|---|---|---|
| **Institutional Application Fees** | \$50 – \$90 per school | Auto-identifies institutions with no fee for transfer/international or Common App fee-waiver codes. |
| **Official Transcripts** | \$5 – \$20 per transcript | Recommends bundled official electronic delivery (National Student Clearinghouse, Parchment). |
| **Credential Evaluation (WES / ECE)** | \$150 – \$300 | Recommends institutions that conduct in-house evaluation, saving the student \$250+ per application. |
| **Certified Translations** | \$30 – \$75 per page | Identifies institutions accepting certified in-house school translations over notarized commercial services. |
| **Standardized Testing (SAT/ACT/TOEFL)** | \$100 – \$250 per exam | Highlights test-optional policies and Duolingo English Test (\$59) acceptance vs. TOEFL (\$220+). |
| **Score Sending Reports** | \$14 – \$35 per report | Identifies schools permitting self-reported test scores on application forms. |

---

## 6. Financial Aid Intelligence for International & Transfer Applicants

```mermaid
graph TD
    INTL["International Applicant Aid Realities"]
    NEED_BLIND["Need-Blind Universities<br/>(Only ~7 US Institutions for Intl)"]
    NEED_AWARE["Need-Aware Universities<br/>(Admissions chances affected by requested aid)"]
    MERIT_ONLY["Merit-Only Universities<br/>(Admissions separate, but high GPA/test scores required)"]
    NO_AID["No International Aid<br/>(Full tuition proof required for I-20/Visa)"]

    INTL --> NEED_BLIND
    INTL --> NEED_AWARE
    INTL --> MERIT_ONLY
    INTL --> NO_AID
```

### Crucial Global Distinctions:
1. **US Federal Aid (FAFSA):** International students and non-citizens are ineligible for US federal grants (Pell) or direct loans. The platform guides eligible non-citizens (permanent residents, refugees, asylees) to complete FAFSA while ensuring international students do not waste effort on ineligible federal forms.
2. **Transfer Aid Penalties:** Many four-year institutions offer less generous institutional need-based aid to transfer students than first-year students. The platform explicitly benchmarks transfer-specific scholarship programs (e.g., Phi Theta Kappa - PTK Transfer Scholarships).
3. **Visa Proof of Funds (Form I-20 / DS-2019):** To secure an F-1 visa, international students must demonstrate liquid funds covering 100% of the first year's Cost of Attendance. The platform generates an **I-20 Readiness Summary** showing the gap between liquid family funds and university COA.

---

## 7. Provenance & Freshness Governance (Implemented `f1c9e4a2b870`)

`ScholarshipProgram` includes native currency/amount tracking (`native_amount_min`, `native_amount_max`, `award_fixed_usd`, `covers_travel`, `funding_duration_years`, `max_funding_periods`, `renewal_conditions`), sponsoring institution/source provenance (`sponsoring_institution`, `source_type`, `source_version`, `academic_year`, `verification_method`, `verified_by`, `claim_provenance`, `conflict_notes`), and non-destructive freshness classification (`verification_expires_at`, `freshness_status`, `requires_manual_review`).

- **Freshness Classifications (`freshness_governance.py`):** `current`, `approaching_expiration`, `expired`, `source_unavailable`, `conflicting_information`, `requires_manual_review`.
- **Differentiated Expiration Policies:**
  - Scholarship Deadlines: **90 days** (`approaching_window = 14 days`)
  - Scholarship Award Amounts: **120 days** (`approaching_window = 21 days`)
  - Scholarship Eligibility Rules: **180 days** (`approaching_window = 30 days`)
- **Historical Retention:** Expired awards remain in PostgreSQL (`freshness_status = 'expired'`, `is_current = FALSE`) and are never deleted or recommended as active verified aid. Legacy rows lacking explicit expiry or reviewer metadata default honestly to `source_type = 'unknown'` / `freshness_status = 'requires_manual_review'` rather than fabricated dates or reviewers.

---

## 8. Step 2 Eligibility Precedence & Component Net-Price Accounting (`financial_engine.py`)

### Supported Rule Dimensions (`_eval_rule`)
Evaluates 18 rule types against verified `StudentProfile`, `CitizenshipRecord`, `EnrollmentRecord`, `StandardizedTest`, and explicit request inputs without cross-inferring citizenship from residence, residence from citizenship, degree level from age, or transfer status from institution name:
`citizenship`, `excluded_citizenships`, `dual_citizenship`, `country_of_residence`, `residency_state`, `destination_country`, `degree_level`, `applicant_type`, `enrollment_context`, `required_qualifications`, `language_proficiency`, `required_exams` (absent score -> `insufficient_information`, never 0), `age_limit`, `field_of_study`, `geographic_region`, `minimum_gpa`, `financial_need_level`, and separately tracked `renewal` criteria (Year 2+ renewal does not fail initial eligibility), with any unknown/unsupported dimension defaulting to `requires_manual_review`.

### Five Canonical Outcomes & Deterministic Precedence
1. `ineligible` (highest precedence — one decisive failure overrides missing/conditional criteria)
2. `requires_manual_review` (ambiguous, conflicting, or unsupported rule/freshness terms)
3. `insufficient_information` (required student evidence missing or unreported)
4. `conditionally_eligible` (known criteria satisfied; future condition remains)
5. `eligible` (all mandatory criteria verified cleanly)

### Component Allocation, Currency & Duration Rules (`calculate_net_price`)
- **Permitted Expense Scoping:** Tuition-only awards reduce `tuition` (`mandatory_fees` only when `covers_fees=True`); living stipends reduce `room_board`, `books_supplies`, `transportation`, and `personal_expenses` (never tuition/fees); travel awards reduce `transportation` only. Unknown scope (`no covers_*` flags), missing dollar amounts, or non-matching currencies (`currency != target_currency`) move to `unallocated_potential_aid` (`$0` net discount; native currency amounts preserved intact without invented exchange rates).
- **Non-Over-Crediting & Bounds:** Each award decrements remaining category balances so overlapping awards never double-count or produce negative category or total net prices (`>= 0`).
- **Freshness & Duration Safety:** `expired`, `source_unavailable`, `conflicting_information`, and `requires_manual_review` awards never reduce guaranteed or verified Net Price (routed transparently into `review_required_aid`). Multi-year projections (`Years 2+`) repeat only `is_renewable=True` awards with documented `funding_duration_years > 1` or `max_funding_periods > 1`; one-time and unknown-duration awards apply to Year 1 only.

### Illustrative Distinction Examples
| Distinction | Example Behavior |
|---|---|
| **Eligible vs. Conditionally Eligible** | Haitan student with `3.85` GPA & `$25k` income passes all mandatory verified criteria (`eligible`), whereas a student who meets known rules but must submit final matriculation verification (`is_future_condition=True`) receives `conditionally_eligible`. |
| **Insufficient Info vs. Ineligible** | Missing an SAT score produces `insufficient_information` (never graded as `0`), whereas a reported `1200` against a `1350` floor produces `ineligible`. |
| **Verified Tuition Aid vs. Unallocated Potential Aid** | A `$30k` `current` USD tuition-only award offsets up to `$20k` published tuition (`$0` remaining tuition, housing untouched); a `4,000 EUR` grant or unknown-scope award sits in `unallocated_potential_aid` (`$0` USD reduction). |
| **Original COA vs. Estimated Net Price** | Published direct + indirect COA (`$40,000`) minus component-verified applicable aid (`$20,000`) equals estimated Net Price (`$20,000`), displayed explicitly with a non-guarantee advisory. |

### Known Limitations
- Institutional `InstitutionCost` rows from federal IPEDS data combine housing and meals (`room_board`), so meal-only and housing-only caps share that published pool ceiling until institution-split housing/dining schedules are ingested.
- Backend API-generated category labels, warning prose, and rule detail strings remain English when `ar-SA` is active, whereas all UI headings, form controls, status/freshness/cycle badges, tables, and funding sections are localized in Arabic RTL.

---

## 9. Step 3 Global Expansion — Batch 1: Africa & Caribbean (`phase4_batch1_seed.py`)

- **Regional Coverage Expansion:** Added **11** primary-source-verified scholarships (`38` total catalog entries alongside `27` preserved legacy records) across **14/14** target Africa & Caribbean countries (`NG, GH, KE, ZA, ET, RW, SN, CI, HT, JM, TT, BB, BS, DO`), distinguishing CARICOM-only programs (`caricom` region) from broader Caribbean programs, and LDC/Vulnerable Commonwealth PhD eligibility from general Commonwealth Master's eligibility.
- **Claim-Level Freshness Separation (`evaluate_scholarship_claim_breakdown`):** Separately classifies `program_existence`, `eligibility_rules`, `award_amounts`, and `deadlines` so expired cycle deadlines surface transparently (`application_cycle_status = "closed"`) without erasing program visibility or conflating deadlines with expired award amounts. Non-USD native amounts (`GBP`, `EUR`, `CAD`, `ZAR`, `GHS`, `NGN`, `DOP`) and unpublished totals remain isolated (`award_amount_min_usd = NULL`, UI `"Amount varies / not published"` — never `$0` or invented FX).
