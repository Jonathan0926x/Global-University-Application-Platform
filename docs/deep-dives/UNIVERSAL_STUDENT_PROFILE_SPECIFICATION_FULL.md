# UNIVERSAL STUDENT PROFILE SPECIFICATION
**Document ID:** SPEC-USP-2026-V1.0
**Status:** DRAFT / PENDING ARCHITECTURE REVIEW
**Classification:** Core System Architecture Specification
**Platform Working Name:** [PLATFORM NAME]
**Target Tech Stack:** Python 3.12+ (FastAPI), PostgreSQL 16+ (with pgvector), Redis 7.2+, S3-Compatible Encrypted Object Storage, Auth0/Clerk, Next.js 14+ (App Router, TypeScript)
**Dependencies:** Global University Infrastructure Database (`SPEC-GUID-V1`), Admissions Intelligence Engine (`SPEC-AIE-V1`), Document OCR & Verification Pipeline (`SPEC-DOC-V1`)

---

## 1. Executive Summary & Design Principles

### 1.1 Platform Role in the Three-Tier Ecosystem
The **Universal Student Profile (USP)** serves as the canonical single-source-of-truth for all student-supplied, institution-verified, and document-extracted data within the `[PLATFORM NAME]` platform. It functions at the convergence of three interconnected product pillars:

1. **Student OS:** The operational layer where students construct, manage, refine, and audit their academic identity, portfolio, essays, and application portfolios.
2. **Admissions Intelligence:** The analytical layer executing real-time GPA conversion, prerequisite gap analysis, articulation graph traversal, and admissions probability modeling against target university admission criteria.
3. **Global University Infrastructure:** The ingestion, projection, and dispatch layer responsible for transforming the universal profile into bespoke schemas mandated by external application aggregators (e.g., Common Application, UC Application, ApplyTexas, Coalition, UK UCAS, Ontario OUAC) and direct university enterprise portals.

```
+-----------------------------------------------------------------------------------+
|                                    STUDENT OS                                     |
|  [Demographics] [Coursework] [Transcripts] [Activities] [Tests] [Essays] [Recs]   |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                     UNIVERSAL STUDENT PROFILE (CANONICAL CORE)                    |
|  - Relational Backbone (PostgreSQL 16)   - Document-Linked Lineage (S3/pgvector)  |
|  - International System Support          - Cryptographic Consent & Audit Log      |
+--------------------+-------------------------------------+------------------------+
                     |                                     |
                     v                                     v
+------------------------------------+   +------------------------------------------+
|      ADMISSIONS INTELLIGENCE       |   |      FIELD MAPPING & PROJECTION ENGINE   |
| - Articulation & Equivalency Graph |   | - Application-Specific Schemas (Common   |
| - International Grading Normalizer |   |   App, UC, UCAS, ApplyTexas, Direct)     |
| - Transfer Credit Gap Analysis     |   | - Dynamic Truncation & Overrides         |
| - Prerequisite Validation Engine   |   | - Selective Disclosure & Redaction       |
+------------------------------------+   +--------------------+---------------------+
                                                              |
                                                              v
                                         +------------------------------------------+
                                         |     TARGET APPLICATION DISPATCH & EXPORT |
                                         |  - PESC XML / SPEEDE / Common App SDS    |
                                         |  - Secure PDF Dossier / JSON-LD Data Pak |
                                         +------------------------------------------+
```

---

### 1.2 Core Architectural Principles

#### Principle 1: One Canonical Profile, Unlimited Polymorphic Projections
Students input demographic, academic, and experiential records exactly once. The system does not mutate or duplicate canonical records to satisfy idiosyncratic institutional requirements; instead, the **Field Mapping Engine** compiles the canonical profile into an ephemeral or versioned **Application Projection** conforming strictly to the recipient's schema.

#### Principle 2: Native Internationalization Without US-Centric Bias
Traditional US platforms enforce Anglo-centric assumptions: fixed first/middle/last name structures, high school graduation dates constrained to May/June, credit hours fixed to 3-credit semester courses, and 4.0 cumulative GPA scales. The USP treats the US academic framework as merely one regional implementation of a generalized, multi-modal international model.

#### Principle 3: First-Year and Transfer Parity from Day One
Transfer students represent ~1.2 million higher education students annually in the US alone (with 480,000 to 500,000 originating from community colleges). Traditional application systems treat transfer as an afterthought or an awkward variant of high school applications. The USP models transfer-specific data as first-class citizens:
- Inter-institutional course articulation tracking.
- Prerequisite fulfillment graphs (e.g., California IGETC/CSU-GE, Texas Core).
- Syllabus document storage and OCR analysis for unarticulated credit evaluation.
- Distinction between lower-division and upper-division coursework.
- Academic renewal, repeated courses, and non-punitive withdrawals.

#### Principle 4: Student-Controlled Purpose-Bound Privacy
Sensitive attributes (race, ethnicity, gender identity, household income, citizenship/visa status, disciplinary history) are governed by fine-grained Access Control Lists (ACLs). Data sharing is strictly opt-in and bound by purpose limitations. In compliance with *SFFA v. Harvard (2023)* and international data privacy regimes (GDPR, FERPA, CCPA), the system supports automated aggregate masking (e.g., suppressing race/ethnicity flags from university review interfaces while preserving them for post-admission compliance reporting).

#### Principle 5: Lineage, Verification, and Document-Backed Provenance
Every academic record, grade, and test score maintains a cryptographic link to its primary source document (e.g., official transcript PDF, College Board electronic score report). The data model differentiates between:
- `SELF_REPORTED`: Entered manually by the student.
- `EXTRACTED`: Parsed via OCR / Document AI with confidence intervals.
- `STUDENT_VERIFIED`: Confirmed by the student post-extraction.
- `INSTITUTION_VERIFIED`: Backed by digitally signed EDI/PESC XML or trusted registrar upload.

#### Principle 6: Temporal Immutability on Submission
Once an application profile is formally submitted to an institution, its state is frozen into an immutable cryptographic snapshot. Changes made to the canonical profile post-submission do not alter previously submitted applications, maintaining legal audit compliance while allowing continuous profile updates for subsequent applications.

---

## 2. PostgreSQL Relational & JSONB Data Model

### 2.1 Extension and Schema Initialization

```sql
-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create dedicated schema
CREATE SCHEMA IF NOT EXISTS usp;
SET search_path TO usp, public;
```

---

### 2.2 Global Custom Types and Enums

```sql
-- User and Profile Enums
CREATE TYPE user_role AS ENUM (
    'STUDENT',
    'COUNSELOR',
    'RECOMMENDER',
    'UNIVERSITY_ADMISSIONS',
    'PLATFORM_ADMIN'
);

CREATE TYPE verification_status AS ENUM (
    'UNVERIFIED',
    'SELF_REPORTED',
    'OCR_EXTRACTED',
    'STUDENT_CONFIRMED',
    'OFFICIAL_DOCUMENT_MATCHED',
    'THIRD_PARTY_VERIFIED'
);

CREATE TYPE application_cycle_type AS ENUM (
    'FALL',
    'SPRING',
    'SUMMER',
    'WINTER',
    'ROLLING'
);

CREATE TYPE applicant_type AS ENUM (
    'FIRST_YEAR',
    'TRANSFER_COMMUNITY_COLLEGE',
    'TRANSFER_FOUR_YEAR',
    'INTERNATIONAL_FIRST_YEAR',
    'INTERNATIONAL_TRANSFER',
    'POST_BACCALAUREATE',
    'NON_DEGREE'
);

CREATE TYPE calendar_system_type AS ENUM (
    'SEMESTER',
    'QUARTER',
    'TRIMESTER',
    'ANNUAL_LINEAR',
    'MODULAR_BLOCK',
    'CONTINUOUS'
);

CREATE TYPE test_type_enum AS ENUM (
    'SAT',
    'ACT',
    'TOEFL_IBT',
    'IELTS_ACADEMIC',
    'DUOLINGO_DET',
    'PTE_ACADEMIC',
    'AP',
    'IB_DIPLOMA',
    'A_LEVEL',
    'AS_LEVEL',
    'IGCSE_GCSE',
    'GAOKAO',
    'ABITUR',
    'FRENCH_BACCALAUREATE',
    'INDIAN_CBSE_XII',
    'INDIAN_CISCE_XII',
    'GRE',
    'GMAT'
);

CREATE TYPE activity_category_enum AS ENUM (
    'ACADEMIC',
    'ART_VISUAL',
    'ATHLETICS_VARSITY',
    'ATHLETICS_CLUB',
    'CAREER_EXPLORATION',
    'COMMUNITY_SERVICE',
    'DANCE',
    'DEBATE_SPEECH',
    'ENVIRONMENTAL',
    'FAMILY_RESPONSIBILITIES',
    'GOVERNMENT_POLITICS',
    'INTERNSHIP',
    'JOURNALISM_PUBLICATION',
    'LEADERSHIP',
    'MUSIC_INSTRUMENTAL',
    'MUSIC_VOCAL',
    'RELIGIOUS_SPIRITUAL',
    'RESEARCH',
    'ROBOTICS_STEM',
    'THEATRE_DRAMA',
    'WORK_PAID',
    'OTHER'
);

CREATE TYPE recommender_relationship_enum AS ENUM (
    'COUNSELOR',
    'ACADEMIC_TEACHER',
    'COLLEGE_PROFESSOR',
    'RESEARCH_SUPERVISOR',
    'EMPLOYER_SUPERVISOR',
    'COMMUNITY_LEADER',
    'PEER',
    'OTHER'
);

CREATE TYPE document_category_enum AS ENUM (
    'TRANSCRIPT_HIGH_SCHOOL_UNOFFICIAL',
    'TRANSCRIPT_HIGH_SCHOOL_OFFICIAL',
    'TRANSCRIPT_COLLEGE_UNOFFICIAL',
    'TRANSCRIPT_COLLEGE_OFFICIAL',
    'COURSE_SYLLABUS',
    'STANDARDIZED_TEST_REPORT',
    'PASSPORT_BIO_PAGE',
    'NATIONAL_ID',
    'FINANCIAL_CERTIFICATION',
    'BANK_STATEMENT',
    'PORTFOLIO_ARTIFACT',
    'DISABILITY_DOCUMENTATION',
    'MILITARY_SEPARATION_DD214',
    'RESIDENCY_AFFIDAVIT',
    'OTHER'
);
```

---

### 2.3 Core Account and Profile Tables

#### 2.3.1 `users`
Tracks system identities authenticated via Clerk, Auth0, or external IdPs.

```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_provider_id VARCHAR(128) NOT NULL UNIQUE, -- e.g., 'auth0|64f...' or 'user_2N...'
    primary_email VARCHAR(255) NOT NULL UNIQUE,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    phone_number VARCHAR(32),
    phone_verified BOOLEAN NOT NULL DEFAULT FALSE,
    role user_role NOT NULL DEFAULT 'STUDENT',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    last_sign_in_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_users_auth_provider ON users(auth_provider_id);
CREATE INDEX idx_users_primary_email ON users(primary_email);
```

#### 2.3.2 `student_profiles`
The canonical demographic anchor. Models international names, multi-script typography, pronouns, and baseline socioeconomic classifications.

```sql
CREATE TABLE student_profiles (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,

    -- Canonical Name Model (Comprehensive International Support)
    given_name VARCHAR(100) NOT NULL,
    middle_names VARCHAR(150),
    family_name VARCHAR(100) NOT NULL,
    second_family_name VARCHAR(100), -- Maternal surname (Spanish / Portuguese traditions)
    preferred_name VARCHAR(100),
    former_legal_name VARCHAR(255),
    name_prefix VARCHAR(30),         -- e.g., Mr., Ms., Mx., Sheikh
    name_suffix VARCHAR(30),         -- e.g., Jr., III, Esq.

    -- Native Script (e.g., Hanzi, Kanji, Cyrillic, Arabic, Devanagari)
    native_script_full_name VARCHAR(255),
    native_script_language_code VARCHAR(10), -- ISO 639-1 / BCP 47 (e.g., 'zh-Hans', 'ja', 'ar')

    -- Identity & Demographics
    date_of_birth DATE NOT NULL,
    birth_sex CHAR(1) CHECK (birth_sex IN ('M', 'F', 'X', 'U')), -- X = Intersex/Non-binary, U = Undisclosed
    gender_identity VARCHAR(50),
    pronouns VARCHAR(50),            -- e.g., 'they/them/theirs'

    -- Contact & Physical Address
    primary_language VARCHAR(50) NOT NULL DEFAULT 'English',
    languages_spoken JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- JSONB Schema: [{"language": "Spanish", "proficiency": "NATIVE"}, {"language": "Mandarin", "proficiency": "INTERMEDIATE"}]

    current_address JSONB NOT NULL,
    -- JSONB Schema: {"street_1": "...", "street_2": "...", "city": "...", "subdivision": "...", "postal_code": "...", "country_iso3": "USA"}
    permanent_address JSONB,
    address_matches_permanent BOOLEAN NOT NULL DEFAULT TRUE,

    -- Lifecycle and Cohort Tracking
    primary_applicant_type applicant_type NOT NULL DEFAULT 'FIRST_YEAR',
    target_start_term application_cycle_type NOT NULL DEFAULT 'FALL',
    target_start_year SMALLINT NOT NULL CHECK (target_start_year BETWEEN 2024 AND 2035),

    -- US-Specific & Socioeconomic Context (Protected Fields, Controlled Visibility)
    us_ssn_encrypted BYTEA,          -- PGP encrypted with platform KMS key
    itin_encrypted BYTEA,
    first_generation_college BOOLEAN NOT NULL DEFAULT FALSE,
    us_military_status VARCHAR(50) DEFAULT 'NONE', -- Active, Veteran, Dependent
    foster_care_history BOOLEAN DEFAULT FALSE,
    disability_status_disclosed BOOLEAN DEFAULT FALSE,

    -- Dynamic Metadata
    profile_completion_percentage NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT chk_profile_completion CHECK (profile_completion_percentage BETWEEN 0.00 AND 100.00)
);

CREATE INDEX idx_student_profiles_user ON student_profiles(user_id);
CREATE INDEX idx_student_profiles_names ON student_profiles(family_name, given_name);
```

#### 2.3.3 `citizenship_records`
Handles multi-citizenship, non-immigrant visas, SEVIS tracking, and state/provincial residency.

```sql
CREATE TABLE citizenship_records (
    citizenship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,

    country_iso3 CHAR(3) NOT NULL, -- ISO 3166-1 alpha-3
    citizenship_status VARCHAR(50) NOT NULL, -- CITIZEN, PERMANENT_RESIDENT, DUAL_CITIZEN, NON_CITIZEN_VISA, REFUGEE, ASYLEE, UNDOCUMENTED
    is_primary_citizenship BOOLEAN NOT NULL DEFAULT TRUE,

    -- Passport & Travel Documents
    passport_number_encrypted BYTEA,
    passport_issuing_country CHAR(3),
    passport_expiration_date DATE,
    national_id_number_encrypted BYTEA,

    -- US Visa / International Student Context
    us_visa_type VARCHAR(20),       -- F-1, J-1, H-4, None
    currently_residing_in_us BOOLEAN NOT NULL DEFAULT FALSE,
    us_initial_entry_date DATE,
    current_sevis_id VARCHAR(20),   -- Form I-20 ID
    current_i20_sponsoring_institution VARCHAR(255),

    -- State / Local Residency for Tuition Purposes (Crucial for Community College Transfer)
    us_state_of_residence VARCHAR(2), -- 2-letter state code (e.g., 'CA', 'TX')
    residence_start_date DATE,
    claimed_in_state_tuition BOOLEAN NOT NULL DEFAULT FALSE,
    residency_documentation_status verification_status NOT NULL DEFAULT 'UNVERIFIED',

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_profile_country_citizenship UNIQUE (profile_id, country_iso3)
);

CREATE INDEX idx_citizenship_profile ON citizenship_records(profile_id);
```

---

### 2.4 Educational Institutions & Educational History

#### 2.4.1 `educational_institutions`
Global institution catalog entity referencing IPEDS, CEEB, UCAS, and regional bodies.

```sql
CREATE TABLE educational_institutions (
    institution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_identifiers JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- JSONB Schema: {"ipeds": "110635", "ceeb": "4833", "opeid": "00131200", "ucas": "B78", "hesa": "0134"}

    legal_name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    country_iso3 CHAR(3) NOT NULL,
    subdivision_code VARCHAR(10),     -- US State, Canadian Province, UK Region (e.g., 'CA', 'ON', 'ENG')
    city VARCHAR(100) NOT NULL,

    institution_type VARCHAR(50) NOT NULL,
    -- 'SECONDARY_SCHOOL', 'COMMUNITY_COLLEGE', 'FOUR_YEAR_UNIVERSITY', 'VOCATIONAL_TECHNICAL', 'LANGUAGE_INSTITUTE'

    control_type VARCHAR(30) NOT NULL,     -- 'PUBLIC', 'PRIVATE_NONPROFIT', 'PRIVATE_FORPROFIT'
    carnegie_classification VARCHAR(100),  -- e.g., 'Associate's Colleges: High Transfer-Mixed Traditional/Nontraditional'
    calendar_system calendar_system_type NOT NULL DEFAULT 'SEMESTER',

    is_accredited BOOLEAN NOT NULL DEFAULT TRUE,
    accreditation_agency VARCHAR(255),     -- e.g., 'WASC Senior College and University Commission'
    articulation_network_member BOOLEAN NOT NULL DEFAULT FALSE, -- Member of state-wide articulation (e.g., California ASSIST)

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_inst_country_subdivision ON educational_institutions(country_iso3, subdivision_code);
CREATE INDEX idx_inst_ext_ids ON educational_institutions USING gin(external_identifiers);
CREATE INDEX idx_inst_name_trgm ON educational_institutions USING gin(display_name gin_trgm_ops);
```

#### 2.4.2 `enrollment_records`
Tracks the student's high school and post-secondary educational history, graduation status, and honors.

```sql
CREATE TABLE enrollment_records (
    enrollment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,
    institution_id UUID NOT NULL REFERENCES educational_institutions(institution_id),

    level_of_study VARCHAR(50) NOT NULL, -- 'HIGH_SCHOOL', 'ASSOCIATE_DEGREE', 'BACHELORS', 'POST_SECONDARY_NON_DEGREE'
    degree_awarded_or_pursued VARCHAR(100), -- 'High School Diploma', 'Associate in Science for Transfer (AS-T)', 'None'
    major_or_program_name VARCHAR(150),

    start_date DATE NOT NULL,
    end_date DATE,
    is_current_enrollment BOOLEAN NOT NULL DEFAULT FALSE,
    graduation_date DATE,
    has_graduated BOOLEAN NOT NULL DEFAULT FALSE,

    counselor_name VARCHAR(100),
    counselor_email VARCHAR(255),
    counselor_phone VARCHAR(32),

    disciplinary_action_reported BOOLEAN NOT NULL DEFAULT FALSE,
    disciplinary_explanation TEXT,

    verification_status verification_status NOT NULL DEFAULT 'UNVERIFIED',
    verified_document_id UUID, -- Foreign key resolved later to documents table

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_enrollment_profile ON enrollment_records(profile_id);
CREATE INDEX idx_enrollment_institution ON enrollment_records(institution_id);
```

---

### 2.5 Academic Records, Courses, and Grading Systems

#### 2.5.1 `grading_systems`
International grading catalog defining mathematical conversions, boundary values, and passing thresholds.

```sql
CREATE TABLE grading_systems (
    grading_system_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_iso3 CHAR(3) NOT NULL,
    system_name VARCHAR(100) NOT NULL, -- e.g., 'US Standard 4.0 Scale', 'French 0-20 Scale', 'UK Honours Classification'

    scale_type VARCHAR(30) NOT NULL,   -- 'NUMERIC_CONTINUOUS', 'NUMERIC_DISCRETE', 'LETTER_GRADE', 'DESCRIPTIVE'
    min_passing_value NUMERIC(6,3) NOT NULL,
    max_value NUMERIC(6,3) NOT NULL,

    -- Grade Conversion Table
    grade_definitions JSONB NOT NULL,
    /* JSONB Schema Example:
    [
      {"grade": "A+", "us_equivalent": 4.0, "percentage_min": 97.0, "description": "Outstanding"},
      {"grade": "A",  "us_equivalent": 4.0, "percentage_min": 93.0, "description": "Excellent"},
      {"grade": "16-20", "us_equivalent": 4.0, "french_label": "Très Bien", "min": 16.0, "max": 20.0}
    ]
    */

    calculation_rules JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Schema: {"includes_failing_grades_in_gpa": true, "honors_weight_added": 1.0, "ap_weight_added": 1.0}

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_grading_sys_country ON grading_systems(country_iso3);
```

#### 2.5.2 `academic_records`
Summary transcripts per enrollment. Holds cumulative GPAs, weighted/unweighted values, class rank, and credit totals.

```sql
CREATE TABLE academic_records (
    record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enrollment_id UUID NOT NULL REFERENCES enrollment_records(enrollment_id) ON DELETE CASCADE,
    grading_system_id UUID NOT NULL REFERENCES grading_systems(grading_system_id),

    -- Cumulative GPA metrics
    cumulative_gpa_unweighted NUMERIC(4,3),
    cumulative_gpa_weighted NUMERIC(4,3),
    gpa_scale NUMERIC(4,2) NOT NULL DEFAULT 4.00,

    -- Standardized Calculated Platform GPA (Admissions Intelligence Normalization)
    platform_normalized_gpa_4_0 NUMERIC(4,3),

    -- Class Rank
    class_rank_numeric INTEGER,
    class_size INTEGER,
    class_rank_decile SMALLINT CHECK (class_rank_decile BETWEEN 1 AND 10),
    class_rank_weighting VARCHAR(20) DEFAULT 'UNWEIGHTED', -- 'WEIGHTED', 'UNWEIGHTED', 'NONE'

    -- Credit Summary (Crucial for Transfer Evaluation)
    total_credits_attempted NUMERIC(6,2) NOT NULL DEFAULT 0.00,
    total_credits_earned NUMERIC(6,2) NOT NULL DEFAULT 0.00,
    transferable_credits_earned NUMERIC(6,2) NOT NULL DEFAULT 0.00,
    remedial_credits_earned NUMERIC(6,2) NOT NULL DEFAULT 0.00,

    is_final_transcript BOOLEAN NOT NULL DEFAULT FALSE,
    verification_status verification_status NOT NULL DEFAULT 'UNVERIFIED',

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_acad_rec_enrollment ON academic_records(enrollment_id);
```

#### 2.5.3 `academic_terms`
Discretizes coursework into academic terms (semesters, quarters, years, modular blocks).

```sql
CREATE TABLE academic_terms (
    term_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    academic_record_id UUID NOT NULL REFERENCES academic_records(record_id) ON DELETE CASCADE,

    term_name VARCHAR(50) NOT NULL, -- e.g., 'Fall 2024', 'Year 11 / Term 2'
    term_type application_cycle_type NOT NULL DEFAULT 'FALL',
    academic_year SMALLINT NOT NULL, -- 2024 representing 2024-2025
    grade_level VARCHAR(20) NOT NULL, -- '9', '10', '11', '12', 'FRESHMAN', 'SOPHOMORE', 'JUNIOR'

    term_gpa NUMERIC(4,3),
    term_credits_earned NUMERIC(5,2),

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_terms_academic_record ON academic_terms(academic_record_id);
```

#### 2.5.4 `courses`
Atomic course units taken or in progress. Models articulation references, transfer flags, syllabus links, and grading metadata.

```sql
CREATE TABLE courses (
    course_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term_id UUID NOT NULL REFERENCES academic_terms(term_id) ON DELETE CASCADE,
    grading_system_id UUID REFERENCES grading_systems(grading_system_id),

    course_code VARCHAR(30) NOT NULL,    -- e.g., 'MATH 101', 'ENGL 1A', 'CS 61A'
    course_title VARCHAR(200) NOT NULL,  -- e.g., 'Single Variable Calculus I'

    -- Course Rigor Level
    course_level VARCHAR(30) NOT NULL DEFAULT 'REGULAR',
    -- 'REGULAR', 'HONORS', 'AP', 'IB_SL', 'IB_HL', 'A_LEVEL', 'AS_LEVEL',
    -- 'DUAL_ENROLLMENT', 'COMMUNITY_COLLEGE_LOWER_DIV', 'UNIVERSITY_UPPER_DIV', 'REMEDIAL'

    academic_subject_area VARCHAR(50) NOT NULL,
    -- 'MATHEMATICS', 'ENGLISH_LANGUAGE_ARTS', 'NATURAL_SCIENCES', 'SOCIAL_SCIENCES',
    -- 'FOREIGN_LANGUAGES', 'FINE_ARTS', 'COMPUTER_SCIENCE', 'INTERDISCIPLINARY', 'OTHER'

    -- Credit & Volume Tracking
    credits_attempted NUMERIC(5,2) NOT NULL,
    credits_earned NUMERIC(5,2) NOT NULL,
    credit_type calendar_system_type NOT NULL DEFAULT 'SEMESTER',

    -- Grades
    grade_reported VARCHAR(15) NOT NULL,  -- Raw grade: 'A', '94', '15.5', 'Distinction', 'IP' (In Progress)
    grade_standardized_us NUMERIC(4,3),   -- Computed 4.0 scale equivalent
    is_in_progress BOOLEAN NOT NULL DEFAULT FALSE,
    is_planned BOOLEAN NOT NULL DEFAULT FALSE,
    was_repeated BOOLEAN NOT NULL DEFAULT FALSE,
    repeat_replaces_gpa BOOLEAN NOT NULL DEFAULT FALSE,

    -- Transfer & Articulation Fields
    is_transferable_flag BOOLEAN DEFAULT FALSE,
    general_ed_category VARCHAR(50),      -- e.g., 'CSU_GE_AREA_B4', 'IGETC_AREA_2A', 'TEXAS_CORE_020'
    articulated_target_course_id VARCHAR(100), -- Canonical cross-institution course ID

    -- Provenance & Syllabus Verification
    syllabus_document_id UUID,            -- Document reference for transfer credit petitions
    verification_status verification_status NOT NULL DEFAULT 'UNVERIFIED',

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_courses_term ON courses(term_id);
CREATE INDEX idx_courses_code ON courses(course_code);
CREATE INDEX idx_courses_subject ON courses(academic_subject_area);
```

---

### 2.6 Standardized Tests & International Qualifications

#### 2.6.1 `standardized_tests`
Stores standardized test scores and international qualifying examinations with flexible JSONB sub-scores.

```sql
CREATE TABLE standardized_tests (
    test_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,

    test_type test_type_enum NOT NULL,
    test_date DATE NOT NULL,
    is_official_score BOOLEAN NOT NULL DEFAULT FALSE,

    -- Test Identifiers for Official Score Matching
    registration_or_trf_number VARCHAR(100), -- College Board ID, ACT ID, IELTS TRF, TOEFL Registration

    -- Primary Composite Score
    composite_score VARCHAR(20) NOT NULL,    -- '1520' (SAT), '34' (ACT), '112' (TOEFL), '8.5' (IELTS), 'A*' (A-Levels)
    percentile_rank SMALLINT CHECK (percentile_rank BETWEEN 1 AND 99),

    -- Sub-Scores and Section Breakdowns
    sub_scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    /* Examples by test type:
       SAT: {"math": 780, "reading_writing": 740}
       ACT: {"english": 35, "math": 34, "reading": 36, "science": 32, "stem": 33}
       TOEFL: {"reading": 29, "listening": 30, "speaking": 26, "writing": 27}
       IELTS: {"listening": 8.5, "reading": 9.0, "writing": 7.5, "speaking": 8.0, "overall": 8.5}
       IB: {"subject": "Physics HL", "predicted_grade": 7, "final_grade": 7}
       A_LEVEL: {"subject": "Further Mathematics", "exam_board": "Edexcel", "grade": "A*"}
       GAOKAO: {"total": 685, "province": "Sichuan", "chinese": 128, "math": 145, "english": 142, "comprehensive": 270}
    */

    -- Future / Planned Test Tracking
    is_planned_future_sitting BOOLEAN NOT NULL DEFAULT FALSE,

    verification_status verification_status NOT NULL DEFAULT 'UNVERIFIED',
    verified_document_id UUID,

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_tests_profile_type ON standardized_tests(profile_id, test_type);
```

---

### 2.7 Extracurriculars, Employment, Volunteer, and Honors

#### 2.7.1 `extracurricular_activities`
Captures activities, leadership roles, time commitments, and category mappings.

```sql
CREATE TABLE extracurricular_activities (
    activity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,

    category activity_category_enum NOT NULL DEFAULT 'OTHER',
    organization_name VARCHAR(150) NOT NULL,
    position_or_leadership_title VARCHAR(100) NOT NULL,

    -- Description (Multi-tier lengths for cross-application mapping)
    canonical_description TEXT NOT NULL,       -- Full detailed description (unconstrained)
    short_description VARCHAR(150),           -- Common App constrained (150 chars)
    expanded_description VARCHAR(350),        -- UC Application constrained (350 chars)

    -- Time Commitment
    grade_levels_active VARCHAR(20)[] NOT NULL DEFAULT '{}', -- e.g., ARRAY['9', '10', '11', '12'] or ARRAY['COLLEGE_YEAR_1']
    hours_per_week NUMERIC(4,1) NOT NULL CHECK (hours_per_week BETWEEN 0.1 AND 168.0),
    weeks_per_year SMALLINT NOT NULL CHECK (weeks_per_year BETWEEN 1 AND 52),
    participated_during_school_year BOOLEAN NOT NULL DEFAULT TRUE,
    participated_during_summer BOOLEAN NOT NULL DEFAULT FALSE,
    plan_to_participate_in_college BOOLEAN NOT NULL DEFAULT FALSE,

    -- Ordering and Priority
    ordinal_rank SMALLINT NOT NULL DEFAULT 1,
    is_primary_highlight BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_activities_profile ON extracurricular_activities(profile_id);
```

#### 2.7.2 `employment_records`
Captures paid employment, internships, work-study, and family business contributions.

```sql
CREATE TABLE employment_records (
    employment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,

    employer_name VARCHAR(150) NOT NULL,
    job_title VARCHAR(100) NOT NULL,
    employment_type VARCHAR(50) NOT NULL DEFAULT 'PART_TIME', -- 'FULL_TIME', 'PART_TIME', 'INTERNSHIP', 'FAMILY_SUPPORT'

    start_date DATE NOT NULL,
    end_date DATE,
    is_current BOOLEAN NOT NULL DEFAULT FALSE,

    hours_per_week NUMERIC(4,1) NOT NULL CHECK (hours_per_week BETWEEN 0.1 AND 80.0),
    job_responsibilities TEXT NOT NULL,
    is_related_to_intended_major BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_employment_profile ON employment_records(profile_id);
```

#### 2.7.3 `volunteer_records`
Captures unpaid civic engagement, community service, and verified service hours.

```sql
CREATE TABLE volunteer_records (
    volunteer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,

    organization_name VARCHAR(150) NOT NULL,
    role_title VARCHAR(100) NOT NULL,
    cause_area VARCHAR(100) NOT NULL,         -- e.g., 'Youth Literacy', 'Healthcare Outreach'

    start_date DATE NOT NULL,
    end_date DATE,
    is_ongoing BOOLEAN NOT NULL DEFAULT FALSE,

    total_hours_completed NUMERIC(6,1) NOT NULL CHECK (total_hours_completed >= 0.0),
    impact_summary TEXT NOT NULL,

    supervisor_name VARCHAR(100),
    supervisor_email VARCHAR(255),
    is_hours_verified BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_volunteer_profile ON volunteer_records(profile_id);
```

#### 2.7.4 `awards_and_honors`
Academic, artistic, athletic, and civic awards.

```sql
CREATE TABLE awards_and_honors (
    award_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,

    award_title VARCHAR(150) NOT NULL,
    granting_organization VARCHAR(150) NOT NULL,
    date_received DATE NOT NULL,

    level_of_recognition VARCHAR(30) NOT NULL, -- 'SCHOOL', 'LOCAL_REGIONAL', 'STATE_PROVINCIAL', 'NATIONAL', 'INTERNATIONAL'
    grade_levels_awarded VARCHAR(20)[] NOT NULL DEFAULT '{}',

    description TEXT,
    is_academic_award BOOLEAN NOT NULL DEFAULT TRUE,
    ordinal_rank SMALLINT NOT NULL DEFAULT 1,

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_awards_profile ON awards_and_honors(profile_id);
```

---

### 2.8 Essays, Recommendations, Documents, and Applications

#### 2.8.1 `essays` and `essay_versions`
Supports version control, prompt categorization, AI-assisted feedback, and word count monitoring.

```sql
CREATE TABLE essays (
    essay_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,

    essay_title VARCHAR(200) NOT NULL,
    prompt_source VARCHAR(100) NOT NULL, -- 'COMMON_APP_PERSONAL_ESSAY', 'UC_PIQ_1', 'UNIVERSITY_SUPPLEMENTAL', 'CUSTOM'
    prompt_text TEXT NOT NULL,

    target_institution_id UUID REFERENCES educational_institutions(institution_id),
    word_count_limit INTEGER,
    character_count_limit INTEGER,

    active_version_id UUID,              -- Forward pointer to current active essay_version
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE essay_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    essay_id UUID NOT NULL REFERENCES essays(essay_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,

    content_raw TEXT NOT NULL,           -- Plain text or Markdown
    content_rich JSONB,                  -- TipTap / ProseMirror structured document format

    word_count INTEGER NOT NULL,
    character_count INTEGER NOT NULL,

    ai_feedback_summary JSONB DEFAULT '{}'::jsonb,
    -- Schema: {"clarity_score": 88, "tone": "reflective", "suggestions": [...]}

    plagiarism_check_tokens JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_essay_version UNIQUE (essay_id, version_number)
);

CREATE INDEX idx_essays_profile ON essays(profile_id);
CREATE INDEX idx_essay_versions_essay ON essay_versions(essay_id);
```

#### 2.8.2 `recommendation_requests`
Manages recommender invitations, FERPA rights waivers, and delivery status.

```sql
CREATE TABLE recommendation_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,

    recommender_name VARCHAR(100) NOT NULL,
    recommender_email VARCHAR(255) NOT NULL,
    recommender_title VARCHAR(100),
    organization_or_school VARCHAR(150),
    relationship recommender_relationship_enum NOT NULL,

    -- FERPA & Confidentiality Rights
    waive_access_rights BOOLEAN NOT NULL DEFAULT TRUE,
    ferpa_agreement_timestamp TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    -- Secure Access Workflow
    access_token_hash VARCHAR(128) NOT NULL UNIQUE,
    token_expires_at TIMESTAMPTZ NOT NULL,

    request_status VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    -- 'DRAFT', 'INVITATION_SENT', 'OPENED', 'IN_PROGRESS', 'SUBMITTED', 'DECLINED', 'EXPIRED'

    invitation_sent_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ,
    recommendation_document_id UUID, -- Resolved to documents table

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_rec_requests_profile ON recommendation_requests(profile_id);
CREATE INDEX idx_rec_requests_token ON recommendation_requests(access_token_hash);
```

#### 2.8.3 `documents`
Encrypted object metadata for uploaded transcripts, syllabi, test sheets, and passports.

```sql
CREATE TABLE documents (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,

    document_category document_category_enum NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    file_size_bytes BIGINT NOT NULL,

    -- S3 Storage Coordinates & Security
    s3_bucket VARCHAR(100) NOT NULL,
    s3_storage_key VARCHAR(500) NOT NULL UNIQUE,
    kms_encryption_key_id VARCHAR(255) NOT NULL,
    sha256_checksum VARCHAR(64) NOT NULL,

    -- OCR and Machine Extraction Payload
    ocr_processed BOOLEAN NOT NULL DEFAULT FALSE,
    ocr_confidence_score NUMERIC(5,2),
    ocr_extracted_payload JSONB DEFAULT '{}'::jsonb,

    -- Embeddings for Syllabus Vector Search (Course Articulation Matching)
    document_embedding vector(1536), -- OpenAI text-embedding-3-large or Gemini embedding

    verification_status verification_status NOT NULL DEFAULT 'UNVERIFIED',
    verified_by_user_id UUID REFERENCES users(user_id),
    verified_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_documents_profile ON documents(profile_id);
CREATE INDEX idx_documents_category ON documents(document_category);
CREATE INDEX idx_documents_sha256 ON documents(sha256_checksum);
```

#### 2.8.4 `application_profiles` (The Projection Layer)
The pivotal customization entity that binds the canonical profile to a specific university program application.

```sql
CREATE TABLE application_profiles (
    application_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,
    institution_id UUID NOT NULL REFERENCES educational_institutions(institution_id),

    target_program_id VARCHAR(100),       -- Foreign ID to Program Database
    target_degree_level VARCHAR(50) NOT NULL DEFAULT 'UNDERGRADUATE',
    admission_plan VARCHAR(50) NOT NULL,  -- 'EARLY_DECISION', 'EARLY_ACTION', 'REGULAR_DECISION', 'TRANSFER_ROLLING'
    cycle_term application_cycle_type NOT NULL DEFAULT 'FALL',
    cycle_year SMALLINT NOT NULL,

    submission_deadline TIMESTAMPTZ NOT NULL,
    application_status VARCHAR(30) NOT NULL DEFAULT 'IN_PREPARATION',
    -- 'IN_PREPARATION', 'READY_FOR_REVIEW', 'SUBMITTED', 'ACCEPTED', 'WAITLISTED', 'DENIED', 'WITHDRAWN'

    -- Target Application System
    target_system_type VARCHAR(50) NOT NULL DEFAULT 'DIRECT_PORTAL',
    -- 'COMMON_APP', 'UC_APPLICATION', 'APPLY_TEXAS', 'UCAS', 'OUAC', 'DIRECT_PORTAL'

    -- Application Projection Overrides & Selections (JSONB)
    selected_activities UUID[] DEFAULT '{}',     -- Array of activity_id in desired priority order
    selected_awards UUID[] DEFAULT '{}',         -- Array of award_id in desired priority order
    selected_test_scores UUID[] DEFAULT '{}',    -- Array of test_id (Score choice policy)
    attached_essays JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- JSONB Schema: [{"prompt_id": "common_app_1", "essay_id": "...", "version_id": "..."}]

    field_overrides JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- JSONB Schema: {"intended_major": "Computer Science", "alternate_major": "Data Science"}

    -- Immutable Submission Snapshot
    is_submitted BOOLEAN NOT NULL DEFAULT FALSE,
    submitted_at TIMESTAMPTZ,
    submission_snapshot_s3_key VARCHAR(500),    -- Canonical frozen snapshot JSON stored in S3
    submission_manifest_hash VARCHAR(64),       -- SHA-256 of the submission package

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT uq_profile_institution_cycle UNIQUE (profile_id, institution_id, cycle_term, cycle_year)
);

CREATE INDEX idx_app_profiles_profile ON application_profiles(profile_id);
CREATE INDEX idx_app_profiles_institution ON application_profiles(institution_id);
```

#### 2.8.5 `requirement_field_mappings` & `application_system_schemas`
Drives the Field Mapping Engine by encoding target schema specifications and translation rules.

```sql
CREATE TABLE application_system_schemas (
    system_schema_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_code VARCHAR(50) NOT NULL UNIQUE, -- 'COMMON_APP', 'UC_APP', 'APPLY_TEXAS', 'UCAS', 'OUAC'
    display_name VARCHAR(100) NOT NULL,
    schema_version VARCHAR(20) NOT NULL,

    -- Full JSON Schema validation definition for this target system
    validation_json_schema JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE requirement_field_mappings (
    mapping_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_schema_id UUID NOT NULL REFERENCES application_system_schemas(system_schema_id) ON DELETE CASCADE,

    target_field_name VARCHAR(100) NOT NULL,  -- e.g., 'Activities[i].ActivityDescription'
    source_canonical_path VARCHAR(255) NOT NULL, -- JSONPath into Universal Student Profile

    transformation_rule VARCHAR(50) NOT NULL DEFAULT 'DIRECT_COPY',
    -- 'DIRECT_COPY', 'TRUNCATE', 'CONCATENATE', 'LOOKUP_TRANSFORM', 'LLM_REFORMAT', 'SUM'

    transformation_parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Schema: {"max_length": 150, "strip_html": true, "fallback_path": "..."}

    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order SMALLINT NOT NULL DEFAULT 1,

    CONSTRAINT uq_schema_target_field UNIQUE (system_schema_id, target_field_name)
);

CREATE INDEX idx_field_mappings_schema ON requirement_field_mappings(system_schema_id);
```

#### 2.8.6 `profile_privacy_settings` & `application_consents`
Controls field-level visibility, demographic masking, and compliance audit logging.

```sql
CREATE TABLE profile_privacy_settings (
    setting_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,

    field_identifier VARCHAR(100) NOT NULL, -- e.g., 'demographics.race_ethnicity', 'financial.household_income'
    visibility_level VARCHAR(30) NOT NULL DEFAULT 'APPLICATION_SPECIFIC_CONSENT',
    -- 'ALWAYS_HIDDEN', 'APPLICATION_SPECIFIC_CONSENT', 'AGGREGATE_RESEARCH_ONLY', 'ALWAYS_SHARED'

    auto_mask_for_admissions BOOLEAN NOT NULL DEFAULT FALSE, -- e.g., Post-SFFA race masking

    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_profile_field_privacy UNIQUE (profile_id, field_identifier)
);

CREATE TABLE application_consents (
    consent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL REFERENCES application_profiles(application_id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES student_profiles(profile_id) ON DELETE CASCADE,

    shared_scopes VARCHAR(50)[] NOT NULL,
    -- ARRAY['ACADEMICS', 'OFFICIAL_TRANSCRIPTS', 'STANDARDIZED_TESTS', 'DISCIPLINARY_DISCLOSURE', 'FINANCIAL_NEED']

    signed_consent_text TEXT NOT NULL,
    student_ip_address INET NOT NULL,
    user_agent VARCHAR(500) NOT NULL,
    signed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    ferpa_disclosure_consented BOOLEAN NOT NULL DEFAULT TRUE,
    gdpr_processing_lawful_basis VARCHAR(50) NOT NULL DEFAULT 'EXPLICIT_CONSENT',

    -- Digital Signature Verification
    signature_fingerprint VARCHAR(128) NOT NULL
);

CREATE INDEX idx_consents_application ON application_consents(application_id);
```

---

### 2.9 Complete Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    users ||--o| student_profiles : "has"
    student_profiles ||--o{ citizenship_records : "holds"
    student_profiles ||--o{ enrollment_records : "attends"
    student_profiles ||--o{ standardized_tests : "takes"
    student_profiles ||--o{ extracurricular_activities : "performs"
    student_profiles ||--o{ employment_records : "works"
    student_profiles ||--o{ volunteer_records : "serves"
    student_profiles ||--o{ awards_and_honors : "earns"
    student_profiles ||--o{ essays : "authors"
    student_profiles ||--o{ recommendation_requests : "requests"
    student_profiles ||--o{ documents : "uploads"
    student_profiles ||--o{ application_profiles : "submits"
    student_profiles ||--o{ profile_privacy_settings : "configures"

    educational_institutions ||--o{ enrollment_records : "registers"
    educational_institutions ||--o{ application_profiles : "receives"

    enrollment_records ||--o| academic_records : "yields"
    grading_systems ||--o{ academic_records : "evaluates"
    grading_systems ||--o{ courses : "grades"

    academic_records ||--o{ academic_terms : "divides_into"
    academic_terms ||--o{ courses : "contains"

    essays ||--o{ essay_versions : "versions"

    application_system_schemas ||--o{ requirement_field_mappings : "defines"
    application_profiles ||--o{ application_consents : "authorizes"

    users {
        uuid user_id PK
        varchar auth_provider_id UK
        varchar primary_email UK
        user_role role
        boolean is_active
    }

    student_profiles {
        uuid profile_id PK
        uuid user_id FK
        varchar given_name
        varchar family_name
        varchar second_family_name
        varchar native_script_full_name
        date date_of_birth
        char birth_sex
        applicant_type primary_applicant_type
        numeric profile_completion_percentage
    }

    citizenship_records {
        uuid citizenship_id PK
        uuid profile_id FK
        char country_iso3
        varchar citizenship_status
        boolean is_primary_citizenship
        varchar us_state_of_residence
    }

    educational_institutions {
        uuid institution_id PK
        jsonb external_identifiers
        varchar display_name
        char country_iso3
        varchar institution_type
        calendar_system_type calendar_system
        boolean articulation_network_member
    }

    enrollment_records {
        uuid enrollment_id PK
        uuid profile_id FK
        uuid institution_id FK
        varchar level_of_study
        date start_date
        date end_date
        boolean has_graduated
    }

    academic_records {
        uuid record_id PK
        uuid enrollment_id FK
        uuid grading_system_id FK
        numeric cumulative_gpa_unweighted
        numeric platform_normalized_gpa_4_0
        numeric total_credits_earned
        numeric transferable_credits_earned
    }

    academic_terms {
        uuid term_id PK
        uuid academic_record_id FK
        varchar term_name
        smallint academic_year
        varchar grade_level
    }

    courses {
        uuid course_id PK
        uuid term_id FK
        varchar course_code
        varchar course_title
        varchar course_level
        numeric credits_earned
        varchar grade_reported
        numeric grade_standardized_us
        boolean is_transferable_flag
        varchar general_ed_category
    }

    standardized_tests {
        uuid test_id PK
        uuid profile_id FK
        test_type_enum test_type
        date test_date
        varchar composite_score
        jsonb sub_scores
    }

    extracurricular_activities {
        uuid activity_id PK
        uuid profile_id FK
        activity_category_enum category
        varchar organization_name
        varchar position_or_leadership_title
        text canonical_description
        varchar short_description
        varchar expanded_description
        numeric hours_per_week
        smallint weeks_per_year
    }

    essays {
        uuid essay_id PK
        uuid profile_id FK
        varchar essay_title
        varchar prompt_source
        text prompt_text
    }

    essay_versions {
        uuid version_id PK
        uuid essay_id FK
        integer version_number
        text content_raw
        integer word_count
    }

    documents {
        uuid document_id PK
        uuid profile_id FK
        document_category_enum document_category
        varchar s3_storage_key
        varchar sha256_checksum
        jsonb ocr_extracted_payload
        vector document_embedding
    }

    application_profiles {
        uuid application_id PK
        uuid profile_id FK
        uuid institution_id FK
        varchar target_system_type
        varchar application_status
        uuid_array selected_activities
        jsonb attached_essays
        jsonb field_overrides
        boolean is_submitted
    }

    application_system_schemas {
        uuid system_schema_id PK
        varchar system_code UK
        jsonb validation_json_schema
    }

    requirement_field_mappings {
        uuid mapping_id PK
        uuid system_schema_id FK
        varchar target_field_name
        varchar source_canonical_path
        varchar transformation_rule
        jsonb transformation_parameters
    }
```

---

## 3. The Field Mapping & Projection Engine

### 3.1 Mapping Challenge and Architecture
Application portals enforce heterogeneous, mutually incompatible character limits, taxonomies, and structures:

| Application System | Activity Count | Activity Description Limit | Honors / Awards Limit | Personal Statement / Essay Limit |
| :--- | :--- | :--- | :--- | :--- |
| **Common Application** | Max 10 | 150 characters | Max 5 | 650 words (choose 1 of 7 prompts) |
| **UC Application** | Max 20 total (Activities + Awards) | 350 characters | Included in 20 total | 4 Personal Insight Questions (350 words each) |
| **ApplyTexas** | Variable | 300 characters | Up to 10 | 3 essays (500-700 words each) |
| **UK UCAS** | No activities list (integrated into personal statement) | N/A | N/A | 4,000 characters / 47 lines personal statement |
| **Direct Portals** | Custom | Custom | Custom | Institutional supplementals |

To solve this, the **Field Mapping Engine** operates a deterministic, multi-stage compiler:

```
[Universal Student Profile]
            |
            v
+-----------------------+
| 1. CANONICAL RESOLVER | ---> Resolves JSONPath sources (e.g. `$.activities[?(@.category=='LEADERSHIP')]`)
+-----------+-----------+
            |
            v
+-----------------------+
| 2. TAXONOMY MAPPER    | ---> Normalizes enums (e.g. `ROBOTICS_STEM` -> Common App `Science/Math`)
+-----------+-----------+
            |
            v
+-----------------------+
| 3. CONSTRAINT CLAMPER | ---> Enforces character/word bounds; flags truncation warnings
+-----------+-----------+
            |
            v
+-----------------------+
| 4. OVERRIDE MERGER    | ---> Layers student-specified per-application edits & ordering
+-----------+-----------+
            |
            v
+-----------------------+
| 5. JSON SCHEMA VALID. | ---> Validates against target portal's official OpenAPI / JSON Schema
+-----------+-----------+
            |
            v
[Application-Specific Projection]
```

---

### 3.2 Field Mapping Specification & Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ApplicationSystemMappingRules",
  "type": "object",
  "properties": {
    "system_code": { "type": "string", "enum": ["COMMON_APP", "UC_APP", "APPLY_TEXAS", "UCAS"] },
    "mappings": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["target_field", "source_path", "transformation"],
        "properties": {
          "target_field": { "type": "string" },
          "source_path": { "type": "string" },
          "transformation": {
            "type": "object",
            "required": ["rule"],
            "properties": {
              "rule": {
                "type": "string",
                "enum": ["DIRECT", "ENUM_LOOKUP", "CLAMP_TEXT", "DATE_FORMAT", "COMPOSITE_BUILDER", "LLM_CONDENSE"]
              },
              "lookup_table": { "type": "object", "additionalProperties": { "type": "string" } },
              "max_characters": { "type": "integer" },
              "date_output_format": { "type": "string" },
              "template": { "type": "string" }
            }
          }
        }
      }
    }
  }
}
```

---

### 3.3 Auto-Suggest Field Mapping & Condensation Algorithm

The mapping engine automatically projects unconstrained canonical activities into constrained target schemas. Below is the production implementation in Python (FastAPI service tier).

```python
"""
Mapping Engine Core: Resolves canonical profiles to target application schemas
with length clamping, enum alignment, and semantic suggestions.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import re

class TargetFieldConstraint(BaseModel):
    field_name: str
    max_length: Optional[int] = None
    max_words: Optional[int] = None
    required: bool = True
    target_enum_values: Optional[List[str]] = None

class ActivityItem(BaseModel):
    activity_id: str
    category: str
    organization: str
    role_title: str
    canonical_description: str
    short_description: Optional[str] = None
    expanded_description: Optional[str] = None
    hours_per_week: float
    weeks_per_year: int
    grades_active: List[str]

class TargetActivityProjection(BaseModel):
    position_leadership: str
    organization_name: str
    description: str
    activity_type: str
    hours_per_week: int
    weeks_per_year: int
    truncation_applied: bool
    requires_user_review: bool
    review_notes: List[str] = []

# Taxonomy Translation Matrix
COMMON_APP_ACTIVITY_MAP = {
    "ROBOTICS_STEM": "Science/Math",
    "COMMUNITY_SERVICE": "Community Service (Volunteer)",
    "ATHLETICS_VARSITY": "Athletics: JV/Varsity",
    "DEBATE_SPEECH": "Speech/Debate",
    "WORK_PAID": "Work (Paid)",
    "LEADERSHIP": "Student Govt./Politics",
    "FAMILY_RESPONSIBILITIES": "Family Responsibilities"
}

def resolve_activity_for_target(
    activity: ActivityItem,
    target_system: str, # "COMMON_APP" or "UC_APP"
    student_override_text: Optional[str] = None
) -> TargetActivityProjection:
    """
    Deterministically transforms a canonical activity into a target system projection.
    """
    review_notes = []
    truncation_applied = False

    if target_system == "COMMON_APP":
        max_desc_len = 150
        max_role_len = 50
        max_org_len = 100
        target_category = COMMON_APP_ACTIVITY_MAP.get(activity.category, "Other Club/Activity")

        # Priority: 1. Explicit override, 2. Pre-authored short description, 3. Clamped canonical
        if student_override_text:
            selected_desc = student_override_text
        elif activity.short_description:
            selected_desc = activity.short_description
        else:
            selected_desc = activity.canonical_description

    elif target_system == "UC_APP":
        max_desc_len = 350
        max_role_len = 60
        max_org_len = 60
        target_category = activity.category # UC groups into 6 broad buckets

        if student_override_text:
            selected_desc = student_override_text
        elif activity.expanded_description:
            selected_desc = activity.expanded_description
        else:
            selected_desc = activity.canonical_description
    else:
        raise ValueError(f"Unsupported target system: {target_system}")

    # Clamping and Validation
    if len(selected_desc) > max_desc_len:
        # Find nearest sentence or word boundary
        truncated = selected_desc[:max_desc_len]
        last_space = truncated.rfind(' ')
        if last_space > 0:
            truncated = truncated[:last_space]
        selected_desc = truncated.rstrip(",.;-")
        truncation_applied = True
        review_notes.append(
            f"Content exceeded {max_desc_len} characters. Automatically clamped to word boundary."
        )

    role_clamped = activity.role_title[:max_role_len].strip()
    if len(activity.role_title) > max_role_len:
        review_notes.append(f"Role title clamped to {max_role_len} characters.")

    org_clamped = activity.organization[:max_org_len].strip()

    return TargetActivityProjection(
        position_leadership=role_clamped,
        organization_name=org_clamped,
        description=selected_desc,
        activity_type=target_category,
        hours_per_week=round(activity.hours_per_week),
        weeks_per_year=activity.weeks_per_year,
        truncation_applied=truncation_applied,
        requires_user_review=truncation_applied or (len(review_notes) > 0),
        review_notes=review_notes
    )
```

---

## 4. RESTful API Specification (FastAPI / OpenAPI 3.1)

All endpoints require JWT bearer authentication issued via Auth0 or Clerk. Request and response bodies are formatted as JSON conforming to JSON:API / REST standards.

```
Base URL: https://api.[PLATFORM NAME].io/api/v1
```

---

### 4.1 Endpoint Catalog

```
+---------------------------------------------------------------------------------------------------------+
| METHOD | ROUTE                                          | DESCRIPTION                                    |
+--------+------------------------------------------------+------------------------------------------------+
| GET    | /profile                                       | Retrieve complete canonical profile            |
| PATCH  | /profile/{section}                             | Atomic section update (demographics, etc.)     |
| GET    | /profile/completion                            | Calculate overall & target-specific completion |
| POST   | /applications/{application_id}/projection      | Compile application-specific projection        |
| GET    | /applications/{application_id}/preview         | Preview admissions committee dossier view      |
| POST   | /documents/upload                              | Obtain presigned S3 URL & initiate OCR queue   |
| GET    | /documents/{document_id}/ocr-status            | Poll document AI extraction payload            |
| POST   | /profile/export                                | Export profile as JSON-LD, PDF, or PESC XML    |
+---------------------------------------------------------------------------------------------------------+
```

---

### 4.2 Endpoint Specifications and Pydantic Schemas

#### 4.2.1 `GET /api/v1/profile`
Retrieves the complete universal profile, aggregating demographic, citizenship, academic, activity, test, essay, and document records.

**Request Headers:**
```http
Authorization: Bearer <jwt_token>
X-Request-ID: 7a82b0e4-18c2-48e7-9d7a-1299955fa98b
```

**Response (200 OK):**
```json
{
  "profile_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "user_id": "e4eaaaf2-d142-11e1-b3e4-080027620cdd",
  "demographics": {
    "given_name": "Carlos",
    "middle_names": "Eduardo",
    "family_name": "Santana",
    "second_family_name": "Morales",
    "preferred_name": "Carlos",
    "native_script_full_name": null,
    "date_of_birth": "2005-06-14",
    "birth_sex": "M",
    "primary_language": "Spanish",
    "languages_spoken": [
      { "language": "Spanish", "proficiency": "NATIVE" },
      { "language": "English", "proficiency": "FLUENT" }
    ],
    "current_address": {
      "street_1": "1230 Mission College Blvd",
      "city": "Santa Clara",
      "subdivision": "CA",
      "postal_code": "95054",
      "country_iso3": "USA"
    }
  },
  "applicant_context": {
    "primary_applicant_type": "TRANSFER_COMMUNITY_COLLEGE",
    "target_start_term": "FALL",
    "target_start_year": 2025,
    "first_generation_college": true
  },
  "citizenship": [
    {
      "citizenship_id": "42fae930-1b77-4389-9439-d3091df881f2",
      "country_iso3": "MEX",
      "citizenship_status": "PERMANENT_RESIDENT",
      "is_primary": true,
      "us_state_of_residence": "CA",
      "claimed_in_state_tuition": true
    }
  ],
  "enrollments": [
    {
      "enrollment_id": "71a06709-6447-4977-846c-fbe3ff70cf27",
      "institution": {
        "institution_id": "f5e92150-1372-466d-b8d0-252f8623b08e",
        "name": "De Anza College",
        "ceeb": "4286",
        "ipeds": "113856"
      },
      "level_of_study": "COMMUNITY_COLLEGE",
      "degree_pursued": "Associate in Science for Transfer (AS-T) - Computer Science",
      "start_date": "2023-09-15",
      "is_current": true,
      "academic_records": {
        "cumulative_gpa_unweighted": 3.88,
        "transferable_credits_earned": 45.0,
        "total_credits_attempted": 45.0
      }
    }
  ],
  "profile_completion_percentage": 92.50
}
```

---

#### 4.2.2 `PATCH /api/v1/profile/{section}`
Performs atomic, idempotent partial updates on designated profile sections (`demographics`, `citizenship`, `activities`, `tests`, `essays`).

**URI Parameter:**
`section` (string, required): Enum: `demographics`, `citizenship`, `academics`, `activities`, `honors`.

**Request Body (Pydantic Schema):**
```python
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List

class DemographicsPatchRequest(BaseModel):
    given_name: Optional[str] = Field(None, min_length=1, max_length=100)
    family_name: Optional[str] = Field(None, min_length=1, max_length=100)
    second_family_name: Optional[str] = Field(None, max_length=100)
    preferred_name: Optional[str] = Field(None, max_length=100)
    native_script_full_name: Optional[str] = Field(None, max_length=255)
    native_script_language_code: Optional[str] = Field(None, max_length=10)
    gender_identity: Optional[str] = Field(None, max_length=50)
    pronouns: Optional[str] = Field(None, max_length=50)
    current_address: Optional[dict] = None
```

**Response (200 OK):**
```json
{
  "status": "SUCCESS",
  "section": "demographics",
  "updated_at": "2026-11-23T05:22:45.120Z",
  "recalculated_completion_percentage": 94.00
}
```

---

#### 4.2.3 `GET /api/v1/profile/completion`
Dynamic profile completeness evaluation engine. Assesses completeness globally and against specific target application platforms.

**Query Parameters:**
`target_system` (optional): `COMMON_APP`, `UC_APP`, `APPLY_TEXAS`, `UCAS`.

**Response (200 OK):**
```json
{
  "global_score": 88.5,
  "is_submittable_globally": false,
  "target_evaluations": {
    "UC_APPLICATION": {
      "system_code": "UC_APP",
      "completion_percentage": 100.0,
      "is_ready_for_submission": true,
      "blocking_missing_fields": [],
      "recommended_actions": [
        "Review activity descriptions clamped to 350 characters"
      ]
    },
    "COMMON_APPLICATION": {
      "system_code": "COMMON_APP",
      "completion_percentage": 75.0,
      "is_ready_for_submission": false,
      "blocking_missing_fields": [
        "essays.common_app_personal_statement",
        "recommendations.counselor_invitation_sent"
      ],
      "recommended_actions": [
        "Select and complete 1 of 7 Common App personal prompts",
        "Invite secondary school counselor"
      ]
    }
  }
}
```

---

#### 4.2.4 `POST /api/v1/applications/{application_id}/projection`
Compiles, clamps, and validates the canonical profile into a target-ready application projection.

**Request Body:**
```json
{
  "selected_activity_ids": [
    "51c6b1b0-13a8-4eb4-b33e-114c000f684c",
    "83a54b9d-472b-4e1b-9d4e-128b7e28fcf5"
  ],
  "activity_text_overrides": {
    "51c6b1b0-13a8-4eb4-b33e-114c000f684c": "President of Computer Science Club; coordinated regional hackathon with 400 attendees and mentored CC students."
  },
  "attached_essays": [
    {
      "prompt_id": "UC_PIQ_1",
      "essay_id": "2d3e4f5a-6b7c-8d9e-0f1a-2b3c4d5e6f7a",
      "version_id": "3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f"
    }
  ]
}
```

**Response (200 OK):**
```json
{
  "projection_id": "c1f8a847-ec56-4dc5-b467-3363401d020e",
  "application_id": "97e68fa7-8ccb-449a-bd3f-7e8c07c21124",
  "target_system": "UC_APPLICATION",
  "validation_status": "VALID",
  "validation_errors": [],
  "warnings": [
    {
      "field": "activities[0].description",
      "warning_type": "TRUNCATION_WARNING",
      "message": "Description was truncated to 350 characters to comply with UC limits."
    }
  ],
  "compiled_at": "2026-11-23T05:25:10Z"
}
```

---

#### 4.2.5 `POST /api/v1/documents/upload`
Initiates secure upload lifecycle. Returns a pre-signed S3 PUT URL with strict SHA-256 integrity validation and enqueues background OCR.

**Request Body:**
```json
{
  "document_category": "TRANSCRIPT_COLLEGE_OFFICIAL",
  "original_filename": "de_anza_transcript_2025.pdf",
  "mime_type": "application/pdf",
  "file_size_bytes": 1428570,
  "sha256_checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

**Response (201 Created):**
```json
{
  "document_id": "670c5e7b-ef21-4fa2-9cc8-5e4635905ea1",
  "presigned_upload_url": "https://s3.us-west-2.amazonaws.com/usp-documents-vault/de_anza_transcript_2025.pdf?X-Amz-Algorithm=...",
  "upload_expiration_seconds": 900,
  "required_headers": {
    "Content-Type": "application/pdf",
    "x-amz-server-side-encryption": "aws:kms",
    "x-amz-server-side-encryption-aws-kms-key-id": "arn:aws:kms:us-west-2:123456789012:key/usp-key"
  }
}
```

---

#### 4.2.6 `POST /api/v1/profile/export`
Exports the canonical student dossier into machine-readable or archival formats.

**Request Body:**
```json
{
  "export_format": "PESC_XML",
  "include_documents": true,
  "target_institution_id": "f5e92150-1372-466d-b8d0-252f8623b08e",
  "purpose": "OFFICIAL_ADMISSIONS_REVIEW"
}
```

Supported formats:
- `JSON_LD`: Standard Universal Student Profile JSON conforming to W3C Verifiable Credentials schema.
- `PDF_DOSSIER`: Cryptographically signed, high-fidelity PDF portfolio.
- `PESC_XML`: Postsecondary Electronic Standards Council College Transcript standard (US/Canada).
- `SPEEDE_EDI`: ANSI ASC X12 EDI 130/131 format for registrar-to-registrar data exchange.

---

## 5. Privacy, Security, and Consent Framework

### 5.1 Zero-Trust Architecture & Field-Level Encryption

The Universal Student Profile handles sensitive personally identifiable information (PII), academic records protected by the **Family Educational Rights and Privacy Act (FERPA)**, and protected health/demographic data under international data protection regimes (**GDPR**, **CCPA/CPRA**).

```
[Client Application]
         |
         | (TLS 1.3 / Strict Certificate Pinning)
         v
[FastAPI Gateway / Auth0 JWT Token Validator]
         |
         v
[Envelope Encryption Service (AWS KMS / Cloud HSM)]
    |--> Generates 256-bit AES-GCM Data Encryption Keys (DEKs)
    |--> Encrypts PII Fields: SSN, Passport Number, ITIN, National ID
    |--> Signs Audit Logs with Nonce & Timestamp
         |
         v
[PostgreSQL 16 Multi-Tenant Store] (Encrypted at Rest with AES-256)
```

1. **Envelope Encryption:** Sensitive identifiers (`us_ssn_encrypted`, `passport_number_encrypted`, `itin_encrypted`) are encrypted at the application layer prior to database insertion using AES-256-GCM. The Data Encryption Key (DEK) is rotated every 90 days via AWS KMS or HashiCorp Vault.
2. **Access Control Lists (ACL):** Fine-grained column- and row-level security (RLS) ensures that counseling staff, recommenders, and admissions personnel only access records matching explicit student authorization scopes.

---

### 5.2 Granular Visibility Matrix & Demographic Masking

Following the landmark US Supreme Court decision in *Students for Fair Admissions, Inc. v. President and Fellows of Harvard College (2023)*, admissions offices in the United States are legally barred from considering race or ethnicity during holistic admissions evaluations. The USP architecture resolves this by enforcing an **Admissions Review Masking Layer**:

```
+-----------------------------------+--------------------+------------------------+--------------------------+
| Profile Field                     | Student View       | High School Counselor  | Admissions Reader Interface |
+-----------------------------------+--------------------+------------------------+--------------------------+
| Full Legal Name                   | Full Display       | Full Display           | Full Display             |
| Date of Birth                     | Full Display       | Full Display           | Age Only (Calculated)    |
| Race / Ethnicity                  | Editable / Opt-in  | Visible if Permitted   | MASKED / REDACTED        |
| Household Income / Pell Status    | Editable           | MASKED                 | MASKED (Need-Blind Apps) |
| Disciplinary Record               | Editable           | Editable / Verifiable  | Visible if Consented     |
| Transcripts & Articulated Courses | Full Display       | Full Display           | Full Display             |
| Standardized Test Scores          | Full Display       | Full Display           | Selected Scores Only     |
+-----------------------------------+--------------------+------------------------+--------------------------+
```

---

### 5.3 Cryptographic Consent & Audit Trail

Before an application projection is released to any university or application portal, the student must execute a digitally signed consent agreement.

```json
{
  "consent_event": {
    "consent_id": "b78b0f85-3b9e-4c74-a690-349f7b3b9b47",
    "timestamp": "2026-11-23T05:30:15.821Z",
    "profile_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "target_institution": "University of California, Berkeley",
    "authorized_scopes": [
      "ACADEMIC_HISTORY_POST_SECONDARY",
      "STANDARDIZED_TEST_SCORES",
      "COMMUNITY_COLLEGE_ARTICULATION_RECORDS",
      "OFFICIAL_TRANSCRIPTS"
    ],
    "withheld_scopes": [
      "HOUSEHOLD_INCOME_FINANCIAL_AID",
      "DISABILITY_ACCOMMODATION_HISTORY"
    ],
    "ferpa_waiver_statement": "I hereby waive my right under FERPA 34 CFR Part 99 to inspect letters of recommendation submitted on my behalf.",
    "ferpa_waiver_elected": true,
    "ip_address": "198.51.100.42",
    "sha256_package_hash": "a4d3f5e718294a28bb7c83f9821d3f0a552277aa44bb5566cc778899aabbccdd"
  }
}
```

---

### 5.4 GDPR Article 17 (Right to Erasure) vs. Academic Retention Mandates

The platform resolves the conflict between a student's Right to Erasure (GDPR Art. 17 / CCPA) and legal accreditation retention mandates:

1. **Pre-Submission (Draft State):** Complete hard deletion. If a student deletes their profile prior to submitting any applications, all relational rows, S3 document objects, and vector embeddings are purged via cascading deletes and cryptographic shredding within 72 hours.
2. **Post-Submission (Submitted Application):** Immutability requirement. Once submitted to an accredited institution, an application becomes an official educational record owned jointly by the institution under FERPA / State Higher Education Record Retention acts (often requiring 5–7 years of preservation). The canonical user account is deactivated, direct identifiers are anonymized in platform intelligence training sets, but the submitted application snapshot remains frozen and accessible solely to the recipient institution for compliance and verification purposes.

---

## 6. International Educational Architectures & Harmonization

### 6.1 International Name System Harmonization

Western application systems routinely truncate or corrupt names from cultures that do not follow the Anglo-American "Given Name - Middle Name - Surname" convention. The USP implements an international name resolution model:

```
+-------------------------------------------------------------------------------------------------------+
| CULTURE / TRADITION | CONVENTION                        | USP CANONICAL MODEL RECONCILIATION          |
+---------------------+-----------------------------------+---------------------------------------------+
| Spanish / Hispanic  | Dual Surname (Paternal + Maternal)| `family_name` = Paternal,                   |
|                     | e.g., Gabriel García Márquez      | `second_family_name` = Maternal             |
+---------------------+-----------------------------------+---------------------------------------------+
| Chinese / East Asian| Family Name First                 | `family_name` = 王 (Wang),                  |
|                     | e.g., 王小明 (Wang Xiaoming)       | `given_name` = 小明 (Xiaoming),             |
|                     |                                   | `native_script_full_name` = "王小明"        |
+---------------------+-----------------------------------+---------------------------------------------+
| Arabic / Patronymic | Personal + Father + Grandfather   | `given_name` = Ahmed,                       |
|                     | e.g., Ahmed bin Tariq al-Mansoor  | `middle_names` = "bin Tariq",               |
|                     |                                   | `family_name` = "al-Mansoor"                |
+---------------------+-----------------------------------+---------------------------------------------+
| South Indian /      | Mononym or Single Name            | `family_name` = "Suharto",                  |
| Indonesian          | e.g., Sukarno, Suharto            | `given_name` = "[NOT APPLICABLE]" (Flagged) |
+---------------------+-----------------------------------+---------------------------------------------+
```

---

### 6.2 Temporal Calendars and Admissions Intake Cycles

Academic calendars vary globally by hemisphere, climate, and national governance:

```mermaid
flowchart TD
    subgraph Northern["Northern Hemisphere (US, UK, Europe, China)"]
        direction LR
        N1["Term 1 / Fall (Sep - Dec)"] --> N2["Winter Recess (Dec - Jan)"]
        N2 --> N3["Term 2 / Spring (Jan - May)"] --> N4["Summer Session (Jun - Aug)"]
    end

    subgraph Southern["Southern Hemisphere (Australia, South Africa, Latin America)"]
        direction LR
        S1["Semester 1 / Autumn (Feb - Jun)"] --> S2["Winter Recess (Jul)"]
        S2 --> S3["Semester 2 / Spring (Aug - Nov)"] --> S4["Summer Holiday (Dec - Jan)"]
    end

    subgraph EastAsia["East Asian Spring Intake (Japan, South Korea)"]
        direction LR
        E1["Term 1 / Spring Entrance (Apr - Jul)"] --> E2["Summer Vacation (Aug)"]
        E2 --> E3["Term 2 / Fall (Sep - Jan)"] --> E4["Spring Break (Feb - Mar)"]
    end
```

| Region / Model | Academic Year Start | Academic Year End | Primary Intake Term | Secondary Intake Term | Articulation Transition Offset |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Northern Hemisphere** (US, Canada, UK, Europe, China) | Late August / September | May / June | Fall (Aug - Sep) | Spring (Jan - Feb) | Baseline 0-month alignment |
| **Southern Hemisphere** (Australia, New Zealand, South Africa, Brazil) | Late February / March | November / December | Semester 1 (Feb - Mar) | Semester 2 (Jul - Aug) | +6 months phase shift |
| **East Asia (Spring Entrance)** (Japan, South Korea) | April 1st | Mid-March | Spring (April) | Fall (September - October) | +7 months / -5 months shift |
| **Indian Linear Board System** (CBSE / State Boards) | July / August | April / May | Monsoon / Fall (Jul - Aug) | Rarely offered | +1-2 months lag |

**System Handling:**
- The engine decouples academic terms from rigid calendar years. Courses are indexed by `academic_year` (e.g., 2024-2025) and `cycle_type` (`FALL`, `SPRING`, `ANNUAL_LINEAR`).
- Transfer evaluation algorithms adjust credit progression timelines when students transition between Southern and Northern hemisphere institutions (e.g., preventing a student graduating in December in Australia from being marked as having an educational gap before matriculating in August in the US).

---

### 6.3 International Grading Harmonization Engine

Grading systems are fundamentally non-linear across jurisdictions. A grade of 16/20 in the French Baccalaureate represents the top 2-5% of students nationally (*Mention Très Bien*), whereas an arithmetic conversion (16/20 = 80% = B-) would catastrophically misrepresent the student's academic standing in the US system.

The Admissions Intelligence normalizer applies statistical percentile band mapping rather than naive arithmetic division:

```
+--------------------+------------------------+---------------------+------------------+---------------------+
| US 4.0 Standard    | UK Honours / A-Levels  | French System (0-20)| Indian CBSE (%)  | German Abitur (1-6) |
+--------------------+------------------------+---------------------+------------------+---------------------+
| 4.00 (A / A+)      | First Class / A*       | 16.0 - 20.0 (Très B)| 90% - 100%       | 1.0 - 1.3 (Sehr Gut)|
| 3.70 (A-)          | Upper Second (2:1) / A | 14.0 - 15.9 (Bien)  | 80% - 89%        | 1.4 - 2.0 (Gut)     |
| 3.30 (B+)          | Lower Second (2:2) / B | 12.0 - 13.9 (A.Bien)| 70% - 79%        | 2.1 - 2.7 (Befried) |
| 3.00 (B)           | Third Class / C        | 10.0 - 11.9 (Pass)  | 60% - 69%        | 2.8 - 3.3 (Ausreich)|
| < 2.00 (F)         | Fail / U               | < 10.0 (Échec)      | < 40% (Fail)     | > 4.0 (Mangelhaft)  |
+--------------------+------------------------+---------------------+------------------+---------------------+
```

#### Modified Bavarian Formula for German / ECTS Grade Conversion
When converting German Abitur or inverse European numeric scales to the US standard:

$$N = 1 + 3 \times \frac{P_{\max} - P}{P_{\max} - P_{\min}}$$

Where:
- $N$ = Computed US Equivalent Grade
- $P_{\max}$ = Maximum achievable grade in foreign system (e.g., 1.0 in Germany)
- $P_{\min}$ = Minimum passing grade in foreign system (e.g., 4.0 in Germany)
- $P$ = Student's actual foreign grade

---

### 6.4 Credit & Volume Normalization (US Semester vs. ECTS vs. CATS)

International systems vary widely in how they quantify academic workload:
- **US Semester Credit Hours:** 1 credit = 1 contact hour per week over 15 weeks (~45-50 total learning hours). A standard bachelor's degree requires 120 semester credits.
- **European Credit Transfer and Accumulation System (ECTS):** 1 ECTS credit = 25–30 hours of total student workload. An academic year requires exactly 60 ECTS credits.
- **UK Credit Accumulation and Transfer Scheme (CATS):** 1 CATS credit = 10 learning hours. 120 CATS = 60 ECTS = 30 US Semester Credits.
- **No-Credit Holistic Systems:** Many national curricula (e.g., UK A-Levels, French Baccalaureate, Indian State Boards) award terminal examination certificates rather than discrete course credit hours.

**Conversion Formula in Admissions Intelligence Layer:**

$$\text{US Semester Credits} = \text{ECTS} \times 0.50 = \frac{\text{CATS}}{4}$$

---

### 6.5 Transfer Articulation Engine: Community College & International Transfer

Transfer applicants lose an average of **43% of their accumulated credits** during transfer, delaying graduation and increasing tuition debt. The USP contains native data structures to interface with state articulation engines (such as California's ASSIST.org) and generalizes them globally:

```
                                  +---------------------------------+
                                  | Community College Course Taken: |
                                  | MATH 1A (De Anza College)       |
                                  +----------------+----------------+
                                                   |
                                                   v
                           +-----------------------------------------------+
                           |        ARTICULATION GRAPH RESOLUTION          |
                           | Matches: C-ID (Course Identification Number)  |
                           | System: C-ID MATH 210 (Single Variable Calc)  |
                           +-----------------------+-----------------------+
                                                   |
                   +-------------------------------+-------------------------------+
                   |                                                               |
                   v                                                               v
+------------------------------------+           +-------------------------------------------------+
| TARGET A: UC Berkeley              |           | TARGET B: Stanford University (Private / Out)   |
| Agreement: Articulated Major Req   |           | Agreement: No Pre-Existing Articulation         |
| Status: Direct Equivalency MATH 1A |           | Status: Syllabus AI Extraction & Match          |
| Credits Awarded: 5.0 Quarter -> 3.3|           | Embeddings Similarity: 0.94 vs Stanford MATH 19 |
| Prerequisite Met: Calculus I       |           | Action: Generates Faculty Review Petition Dossier|
+------------------------------------+           +-------------------------------------------------+
```

---

## 7. Implementation Limitations, Edge Cases, and Architectural Tradeoffs

### 7.1 PostgreSQL JSONB vs. Relational Normalization Tradeoffs

| Architectural Decision | Approach Taken | Rationale & Tradeoffs |
| :--- | :--- | :--- |
| **Coursework & Terms** | Strictly Relational (`academic_terms`, `courses`) | Normalized tables allow indexing on `course_code`, `academic_subject_area`, and `is_transferable_flag` for high-speed SQL joins against articulation databases. Tradeoff: Complex deep joins when serializing complete profiles. |
| **Address & Demographics** | Hybrid Relational + JSONB (`languages_spoken`, `current_address`) | Flexible schema permits international postal variations (e.g., Japanese prefectures, UK postcodes, UAE non-addressed locales) without endless nullable columns. |
| **Standardized Test Scores** | Relational Anchor + JSONB Sub-scores | Each test type (SAT vs. IELTS vs. Gaokao) has completely divergent section metrics. Relational composite scores allow sorting/filtering, while JSONB holds sub-scores. |
| **Application Overrides** | Denormalized JSONB (`field_overrides`) | Avoids creating 20+ shadow tables for application-specific text overrides. Preserves high write performance during application submission periods. |

---

### 7.2 Transcript Verification Boundaries and Fraud Prevention

Self-reported coursework is vulnerable to inflation or fabrication. The USP enforces strict verification boundary states:

```
[Student Uploads PDF Transcript]
               |
               v
[AWS Textract / Gemini Multimodal OCR]
  - Confidence Score Threshold: >= 92%
  - Flags Anomalies: Missing watermarks, font mismatch, arithmetic discrepancies
               |
               v
+-------------------------------+-------------------------------+
| Match Found in Electronic EDI | No Match (Paper / Scan Only)  |
| (PESC / National Clearinghouse|                               |
+---------------+---------------+---------------+---------------+
                |                               |
                v                               v
[Status: OFFICIAL_DOCUMENT_MATCHED]  [Status: OCR_EXTRACTED]
(Auto-locks course grades)           (Requires Student Confirmation;
                                     Must be verified by counselor)
```

**Tamper-Evident Document Hashing:**
All uploaded documents compute a SHA-256 cryptographic digest immediately upon landing in memory, logged into `documents.sha256_checksum`. Any downstream alteration of the PDF payload in S3 triggers an integrity failure and invalidates all associated verified courses.

---

### 7.3 Managing Annual Schema Churn Across Application Aggregators

Aggregators like the Common Application alter their supplemental essay prompts, character constraints, and question trees annually on **August 1st**.

**Architectural Solution:**
- Schema definitions are decoupled from application code and stored as versioned JSON Schema documents in `application_system_schemas` (e.g., `COMMON_APP_2025_V1`, `COMMON_APP_2026_V1`).
- The `requirement_field_mappings` table binds canonical profile JSONPaths to target schema properties dynamically.
- Annual platform updates require zero database schema migrations; updates are deployed as new schema rows loaded via automated configuration pipelines.

---

## 8. Verification and Deliverable Checklist

- [x] Complete system architecture and placement in 3-pillar ecosystem.
- [x] 7 foundational design principles established.
- [x] Complete PostgreSQL 16+ DDL covering all 20+ entities with constraints, checks, foreign keys, and indexes.
- [x] Detailed Mermaid ER diagram displaying all relationships, cardinality, and keys.
- [x] Field Mapping Engine architecture, schema definition, and Python/FastAPI condensation algorithm.
- [x] Comprehensive RESTful API specification with OpenAPI-compliant endpoints, request/response models, and Pydantic schemas.
- [x] Multi-tier privacy architecture, SFFA-compliant demographic masking, and cryptographic consent logging.
- [x] Internationalization framework: multi-script name modeling, hemispheric calendar synchronization, non-linear grading scales, and credit conversion.
- [x] Transfer credit articulation intelligence and ASSIST.org generalization.
- [x] Realistic engineering tradeoffs, limitations, and edge-case resolutions.
