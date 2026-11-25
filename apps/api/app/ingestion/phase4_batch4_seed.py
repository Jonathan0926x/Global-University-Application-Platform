"""
Phase 4, Step 3 — Batch 4 Global Scholarship Expansion Seeder (Europe & Erasmus+).

Contains strictly official-primary-source-verified scholarships covering:
Netherlands (NL / EUR), Switzerland (CH / CHF), Sweden (SE / SEK), Norway (NO / NOK),
Finland (FI / EUR), Italy (IT / EUR), Spain (ES / EUR), and Erasmus+ (BE/EU / EUR —
strictly separating full-degree Erasmus Mundus Joint Masters from short-term Erasmus+
student exchange mobility grants).
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.country import Country
from app.models.rag import ScholarshipEligibilityRule, ScholarshipProgram

BATCH4_VERIFIED_AT = datetime(2026, 11, 25, 15, 45, tzinfo=timezone.utc)
BATCH4_ELIG_EXPIRES_AT = BATCH4_VERIFIED_AT + timedelta(days=180)
BATCH4_AMT_EXPIRES_AT = BATCH4_VERIFIED_AT + timedelta(days=120)
BATCH4_DEADLINE_EXPIRES_AT = BATCH4_VERIFIED_AT + timedelta(days=90)

BATCH4_COUNTRY_NAMES: Dict[str, str] = {
    "NL": "Netherlands",
    "CH": "Switzerland",
    "SE": "Sweden",
    "NO": "Norway",
    "FI": "Finland",
    "IT": "Italy",
    "ES": "Spain",
    "BE": "Belgium",
    "AT": "Austria",
    "PT": "Portugal",
    "DK": "Denmark",
    "PL": "Poland",
    "CZ": "Czechia",
    "GR": "Greece",
    "IE": "Ireland",
    "IS": "Iceland",
    "LI": "Liechtenstein",
    "HU": "Hungary",
    "RO": "Romania",
    "BG": "Bulgaria",
    "HR": "Croatia",
    "SK": "Slovakia",
    "SI": "Slovenia",
    "EE": "Estonia",
    "LV": "Latvia",
    "LT": "Lithuania",
    "CY": "Cyprus",
    "MT": "Malta",
    "LU": "Luxembourg",
    "AM": "Armenia",
    "AZ": "Azerbaijan",
    "BY": "Belarus",
    "GE": "Georgia",
    "MD": "Moldova",
    "UA": "Ukraine",
    "UZ": "Uzbekistan",
    "LR": "Liberia",
    "TZ": "Tanzania",
    "ZW": "Zimbabwe",
    "IQ": "Iraq",
    "JO": "Jordan",
}

EU_27_COUNTRIES = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
]

EEA_30_COUNTRIES = EU_27_COUNTRIES + ["IS", "LI", "NO"]
EEA_AND_CH_COUNTRIES = EEA_30_COUNTRIES + ["CH"]

SI_SISGP_34_COUNTRIES = [
    "AM", "AZ", "BD", "BY", "BO", "BR", "CO", "EC", "EG", "ET",
    "GE", "GT", "ID", "IQ", "JO", "KE", "LR", "MY", "MX", "MD",
    "MA", "NG", "PE", "PH", "RW", "SN", "ZA", "TZ", "TH", "UG",
    "UA", "UZ", "VN", "ZM",
]

ERASMUS_DESTINATIONS = EEA_30_COUNTRIES + ["TR", "MK", "RS"]


def _ensure_batch4_countries(db: Session) -> None:
    existing = {row[0] for row in db.query(Country.code).all()}
    added = False
    for code, name in BATCH4_COUNTRY_NAMES.items():
        if code not in existing:
            db.add(Country(code=code, name=name, currency_code="EUR"))
            added = True
    if added:
        db.flush()


def _build_batch4_claim_provenance(
    *,
    source_url: str,
    source_type: str,
    deadline_expires_iso: Optional[str] = None,
    notes: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    ver_iso = BATCH4_VERIFIED_AT.isoformat()
    elig_exp_iso = BATCH4_ELIG_EXPIRES_AT.isoformat()
    amt_exp_iso = BATCH4_AMT_EXPIRES_AT.isoformat()
    dl_exp_iso = deadline_expires_iso or BATCH4_DEADLINE_EXPIRES_AT.isoformat()
    extra = notes or {}

    def _entry(exp: str, key: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "verified_at": ver_iso,
            "expires_at": exp,
            "source_url": source_url,
            "source_type": source_type,
            "verification_method": "manual_primary_source_fetch",
        }
        if key in extra:
            payload["note"] = extra[key]
        return payload

    return {
        "program_existence": _entry(elig_exp_iso, "program_existence"),
        "sponsor": _entry(elig_exp_iso, "sponsor"),
        "citizenship_eligibility": _entry(elig_exp_iso, "citizenship_eligibility"),
        "residency_eligibility": _entry(elig_exp_iso, "residency_eligibility"),
        "destination_country": _entry(elig_exp_iso, "destination_country"),
        "degree_level": _entry(elig_exp_iso, "degree_level"),
        "applicant_type": _entry(elig_exp_iso, "applicant_type"),
        "award_amount": _entry(amt_exp_iso, "award_amount"),
        "award_amounts": _entry(amt_exp_iso, "award_amount"),
        "currency": _entry(amt_exp_iso, "currency"),
        "funding_scope": _entry(amt_exp_iso, "funding_scope"),
        "funding_duration": _entry(elig_exp_iso, "funding_duration"),
        "renewal": _entry(elig_exp_iso, "renewal"),
        "deadlines": _entry(dl_exp_iso, "deadlines"),
        "application_cycle": _entry(dl_exp_iso, "application_cycle"),
        "academic_year": _entry(elig_exp_iso, "academic_year"),
        "eligibility_rules": _entry(elig_exp_iso, "citizenship_eligibility"),
    }


BATCH4_EUROPE_SCHOLARSHIPS: List[Dict[str, Any]] = [
    # 1. Netherlands — NL Scholarship (Incoming Bachelor's & Master's)
    {
        "country_code": "NL",
        "title": "NL Scholarship (Incoming Non-EEA Bachelor's & Master's — Study in NL / OCW)",
        "sponsoring_institution": "Dutch Ministry of Education, Culture and Science (OCW) / Nuffic & Participating Dutch HEIs",
        "applicant_type": "first_year",
        "funding_type": "partial_grant",
        "provider_type": "government",
        "award_type": "one_time_grant",
        "covers_international": True,
        "award_currency": "EUR",
        "native_amount_min": 5000.00,
        "native_amount_max": 5000.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "€5,000 EUR fixed one-time first-year grant (explicitly NOT a full-tuition scholarship)",
        "eligibility_summary": "Official 2027–2028 Dutch government/university incoming award (€5,000 first-year grant only) strictly for non-EEA citizens applying to full-time Bachelor's or Master's degrees at participating Dutch universities without a prior Dutch degree. Application period currently open.",
        "covers_tuition": False,
        "covers_fees": False,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": False,
        "funding_duration_years": 1.0,
        "max_funding_periods": 1,
        "is_renewable": False,
        "renewal_conditions": "Non-renewable €5,000 grant paid in Year 1 only; students must fund remaining institutional tuition and living expenses.",
        "academic_year": "2027-2028",
        "application_deadline_date": date(2027, 5, 1),
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": False,
        "eligible_citizenships": [],
        "eligible_destination_countries": ["NL"],
        "degree_levels": ["bachelors", "masters"],
        "is_guaranteed_statutory": False,
        "source_name": "Study in NL — NL Scholarship Official Portal",
        "source_url": "https://www.studyinnl.org/finances/nl-scholarship",
        "source_type": "government_portal",
        "source_version": "nl-scholarship-2027-2028",
        "claim_provenance": _build_batch4_claim_provenance(
            source_url="https://www.studyinnl.org/finances/nl-scholarship",
            source_type="government_portal",
            deadline_expires_iso="2027-05-01T23:59:59+02:00",
            notes={
                "award_amount": "Verified directly on studyinnl.org: €5,000 EUR received once in Year 1; explicitly states 'this is not a full-tuition scholarship'.",
                "deadlines": "Study in NL confirms 2027-2028 window is currently open; university-specific closing dates vary (typically Feb–May 2027).",
            },
        ),
        "rules": [
            ("excluded_citizenships", "not_in", {"countries": EEA_30_COUNTRIES}, "Strictly non-EEA citizenship required (EU/EEA nationals excluded)", True),
            ("destination_country", "in", {"countries": ["NL"]}, "Full-time Bachelor's or Master's at a participating Dutch research/applied-sciences university", True),
            ("degree_level", "in", {"levels": ["bachelors", "masters"]}, "Full-time Bachelor's or Master's degree program", True),
            ("applicant_type", "in", {"types": ["first_year"]}, "Incoming Year 1 degree entrant (must hold no prior degree from a Dutch education institution)", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Must meet institutional selection criteria of a participating Dutch university for 2027-2028 and hold no prior Netherlands diploma."}, "Participating Dutch HEI admission & no prior NL degree", True),
        ],
    },
    # 2. Switzerland — Swiss Government Excellence Scholarships (SERI / FCS — Research & Doctoral)
    {
        "country_code": "CH",
        "title": "Swiss Government Excellence Scholarships (SERI / FCS — Research, PhD & Postdoc)",
        "sponsoring_institution": "Swiss Confederation / State Secretariat for Education, Research and Innovation (SERI) / FCS (ESKAS)",
        "applicant_type": "all",
        "funding_type": "full_funding",
        "provider_type": "government",
        "award_type": "fellowship",
        "covers_international": True,
        "award_currency": "CHF",
        "native_amount_min": 29400.00,
        "native_amount_max": 29400.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "CHF 2,450/month (29,400 CHF/year annualized) + health insurance (non-EU/EFTA), flight allowance & housing allowance",
        "eligibility_summary": "Federal Swiss postgraduate research/PhD fellowship (2027–2028 opened Aug 20, 2026) open to Master's graduates (max age 35) from 183 countries with a Swiss professor supervisor. Excludes Swiss citizens, applicants residing in Switzerland > 1 year by Sept start, and standard BA/taught-MA degrees.",
        "covers_tuition": True,
        "covers_fees": False,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": True,
        "provides_living_stipend": True,
        "covers_travel": True,
        "funding_duration_years": 3.0,
        "max_funding_periods": 3,
        "is_renewable": True,
        "renewal_conditions": "12-month research/postdoc or up to 3-year PhD fellowships renewed annually upon satisfactory host-supervisor progress.",
        "academic_year": "2027-2028",
        "application_deadline_date": None,
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": False,
        "eligible_citizenships": [],
        "eligible_destination_countries": ["CH"],
        "degree_levels": ["doctoral"],
        "is_guaranteed_statutory": False,
        "source_name": "SERI / SBFI Swiss Government Excellence Portal",
        "source_url": "https://www.sbfi.admin.ch/en/swiss-government-excellence-scholarships",
        "source_type": "government_portal",
        "source_version": "sbfi-eskas-2027-2028",
        "claim_provenance": _build_batch4_claim_provenance(
            source_url="https://www.sbfi.admin.ch/en/swiss-government-excellence-scholarships",
            source_type="government_portal",
            notes={
                "award_amount": "Verified directly on sbfi.admin.ch: CHF 2,450/month living allowance (29,400 CHF/yr).",
                "residency_eligibility": "SBFI FAQ strictly excludes applicants who have been in Switzerland for > 1 year at September scholarship start.",
                "deadlines": "2027-2028 call opened August 20, 2026; Swiss embassy deadlines vary by country.",
            },
        ),
        "rules": [
            ("excluded_citizenships", "not_in", {"countries": ["CH"]}, "Foreign postgraduate scholars only (Swiss citizens excluded)", True),
            ("country_of_residence", "not_in", {"excluded_countries": ["CH"]}, "Must not already reside in Switzerland for > 1 year prior to September start (residency verified independently)", True),
            ("destination_country", "in", {"countries": ["CH"]}, "Swiss cantonal university, ETHZ, EPFL, UAS, or ETH Domain research institute", True),
            ("degree_level", "in", {"levels": ["doctoral"]}, "Postgraduate Research / PhD / Postdoc fellowships (standard UG/taught Master's excluded; Art track limited to select states)", True),
            ("age_limit", "between", {"max_age": 35, "reference_date": "2027-09-01"}, "Maximum age 35 for research/PhD applicants", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Requires completed Master's degree, formal support letter from a supervising professor at a Swiss host university, and nomination via the home Swiss diplomatic mission."}, "Swiss professor supervisor support letter & embassy filing", True),
        ],
    },
    # 3. Switzerland — ETH Zurich Excellence Scholarship & Opportunity Programme (ESOP)
    {
        "country_code": "CH",
        "title": "ETH Zurich Excellence Scholarship & Opportunity Programme (ESOP — Master's)",
        "sponsoring_institution": "ETH Zurich & ETH Zurich Foundation",
        "applicant_type": "first_year",
        "funding_type": "full_funding",
        "provider_type": "university",
        "award_type": "full_ride",
        "covers_international": True,
        "award_currency": "CHF",
        "native_amount_min": 27000.00,
        "native_amount_max": 27000.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "CHF 13,500/semester from Autumn 2027 (CHF 27,000/yr) living/study grant + full ETH Zurich Master's tuition fee waiver (3–4 semesters)",
        "eligibility_summary": "Premier ETH Zurich taught Master's merit scholarship (HS27 window OPEN Nov 1 – Nov 30, 2026!) granting CHF 13,500/sem plus full tuition waiver (~60 awards) to top 10% Bachelor's graduates of any nationality without a prior Master's degree.",
        "covers_tuition": True,
        "covers_fees": True,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": False,
        "funding_duration_years": 2.0,
        "max_funding_periods": 4,
        "is_renewable": True,
        "renewal_conditions": "Covers full regular Master's duration (3–4 semesters) subject to continuous Master's enrollment at ETH Zurich.",
        "academic_year": "2027-2028",
        "application_deadline_date": date(2026, 11, 30),
        "is_deadline_rolling": False,
        "min_gpa_4": 3.7,
        "requires_financial_need": False,
        "eligible_citizenships": [],
        "eligible_destination_countries": ["CH"],
        "degree_levels": ["masters"],
        "is_guaranteed_statutory": False,
        "source_name": "ETH Zurich Financial Aid Office — ESOP",
        "source_url": "https://ethz.ch/students/en/studies/financial/scholarships/excellencescholarship.html",
        "source_type": "official_institutional",
        "source_version": "esop-hs27-official",
        "claim_provenance": _build_batch4_claim_provenance(
            source_url="https://ethz.ch/students/en/studies/financial/scholarships/excellencescholarship.html",
            source_type="official_institutional",
            deadline_expires_iso="2026-11-30T11:59:00+01:00",
            notes={
                "award_amount": "Verified directly on ethz.ch: 'from HS27 onwards 13'500 CHF per semester' (27,000 CHF/yr) plus tuition fee waiver.",
                "deadlines": "First HS27 application window actively OPEN Nov 1 – Nov 30, 2026 (11:59 CET).",
            },
        ),
        "rules": [
            ("destination_country", "in", {"countries": ["CH"]}, "First-time full-time Master's program (excl. MAS) at ETH Zurich, Switzerland", True),
            ("degree_level", "in", {"levels": ["masters"]}, "Consecutive or external Master's degree (Master's holders and continuing ETH MA students excluded)", True),
            ("applicant_type", "in", {"types": ["first_year"]}, "Incoming Master's admission window applicant", True),
            ("minimum_gpa", "gte", {"min_gpa": 3.7}, "Very good Bachelor's standing (top 10% / Grade A equivalent)", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Requires original Master's thesis pre-proposal with citations, two professor reference letters, eApply submission in Window 1 (Nov 1–30), and no existing Master's degree."}, "Master's thesis pre-proposal, 2 references & no prior Master's", True),
        ],
    },
    # 4. Sweden — Swedish Institute Scholarship for Global Professionals (SISGP 2027–2028)
    {
        "country_code": "SE",
        "title": "Swedish Institute Scholarship for Global Professionals (SISGP 2027–2028)",
        "sponsoring_institution": "Swedish Institute (Svenska institutet, Government Agency)",
        "applicant_type": "first_year",
        "funding_type": "full_funding",
        "provider_type": "government",
        "award_type": "full_ride",
        "covers_international": True,
        "award_currency": "SEK",
        "native_amount_min": 144000.00,
        "native_amount_max": 159000.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "SEK 12,000/month living allowance (144,000 SEK/yr) + one-time travel grant (SEK 15,000, or SEK 10,000 EaP; €0 extra if residing in SE) + direct full Swedish university tuition (excludes health insurance)",
        "eligibility_summary": "Official 2027–2028 Swedish government Master's scholarship (SI portal Feb 8–24, 2027; University Admissions by Jan 15, 2027) strictly for citizens of 34 eligible countries liable for Swedish tuition (excludes EU/EEA/SE/US). Home-country residence NOT required; requires 3,000+ hrs work + leadership.",
        "covers_tuition": True,
        "covers_fees": False,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": True,
        "funding_duration_years": 2.0,
        "max_funding_periods": 2,
        "is_renewable": True,
        "renewal_conditions": "Covers awarded 1-year or 2-year SI-eligible English-taught Master's program without extensions or programme transfers.",
        "academic_year": "2027-2028",
        "application_deadline_date": date(2027, 2, 24),
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": False,
        "eligible_citizenships": SI_SISGP_34_COUNTRIES,
        "eligible_destination_countries": ["SE"],
        "degree_levels": ["masters"],
        "is_guaranteed_statutory": False,
        "source_name": "Swedish Institute (si.se) — SISGP Official Guidelines",
        "source_url": "https://si.se/en/apply/scholarships/swedish-institute-scholarships-for-global-professionals/",
        "source_type": "government_portal",
        "source_version": "sisgp-2027-2028",
        "claim_provenance": _build_batch4_claim_provenance(
            source_url="https://si.se/en/apply/scholarships/swedish-institute-scholarships-for-global-professionals/",
            source_type="government_portal",
            deadline_expires_iso="2027-02-24T14:59:00+01:00",
            notes={
                "award_amount": "Verified directly on si.se: SEK 12,000/month + full tuition + SEK 15,000 travel grant (SEK 10,000 EaP; omitted if already living in SE); excludes insurance.",
                "residency_eligibility": "Explicitly citizenship-based across 34 countries; si.se confirms 'you do not need to reside in the country at the time of the application'.",
                "deadlines": "University Admissions Oct 16, 2026 – Jan 15, 2027; SI Scholarship Portal open Feb 8 – Feb 24, 2027 (14:59 CET).",
            },
        ),
        "rules": [
            ("citizenship", "in", {"countries": SI_SISGP_34_COUNTRIES}, "Strictly citizen of one of the 34 SI SISGP 2027-2028 eligible countries (EU/EEA/SE excluded)", True),
            ("destination_country", "in", {"countries": ["SE"]}, "Full-time SI-eligible English-taught Master's in Sweden via UniversityAdmissions.se", True),
            ("degree_level", "in", {"levels": ["masters"]}, "1-year or 2-year full-time Master's degree in Governance, Public Health, Entrepreneurship or STEM", True),
            ("applicant_type", "in", {"types": ["first_year"]}, "Incoming Master's cohort (autumn intake, tuition-fee liable student)", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Must be liable to pay tuition fees in Sweden, admitted to an SI-listed Master's by April 1, 2027, hold >= 3,000 hours verified work experience (from max 3 employers; waived hour floor only for AM/AZ/BY/GE/MD/UA), and documented leadership experience."}, "Tuition liability, >=3,000 hrs work, leadership & SI admission", True),
        ],
    },
    # 5. Norway — BI Presidential Scholarship (BI Norwegian Business School)
    {
        "country_code": "NO",
        "title": "BI Presidential Scholarship (BI Norwegian Business School — Full-Time Master's)",
        "sponsoring_institution": "BI Norwegian Business School (Oslo / Bergen / Trondheim), Norway",
        "applicant_type": "first_year",
        "funding_type": "full_funding",
        "provider_type": "university",
        "award_type": "tuition_plus_stipend",
        "covers_international": True,
        "award_currency": "NOK",
        "native_amount_min": 100000.00,
        "native_amount_max": 100000.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "NOK 50,000/semester living stipend (100,000 NOK/yr for international fee-paying MSc recipients) + full 2-year Master's tuition coverage",
        "eligibility_summary": "Norwegian full-degree MSc merit scholarship (deadline March 1, 2027; Norway provides no universal national government grants for non-EEA degree students). Requires Grade 'A' ECTS GPA, simultaneous admission application, and 30 ECTS + B progression.",
        "covers_tuition": True,
        "covers_fees": True,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": False,
        "funding_duration_years": 2.0,
        "max_funding_periods": 4,
        "is_renewable": True,
        "renewal_conditions": "Full 30 ECTS progression per semester and minimum cumulative GPA of 'B' on the BI ECTS scale each semester.",
        "academic_year": "2027-2028",
        "application_deadline_date": date(2027, 3, 1),
        "is_deadline_rolling": False,
        "min_gpa_4": 3.7,
        "requires_financial_need": False,
        "eligible_citizenships": [],
        "eligible_destination_countries": ["NO"],
        "degree_levels": ["masters"],
        "is_guaranteed_statutory": False,
        "source_name": "BI Norwegian Business School — Scholarships",
        "source_url": "https://www.bi.no/en/programmes-and-individual-courses/scholarships/bi-presidential-scholarships/",
        "source_type": "official_institutional",
        "source_version": "bi-presidential-2026-oct",
        "claim_provenance": _build_batch4_claim_provenance(
            source_url="https://www.bi.no/en/programmes-and-individual-courses/scholarships/bi-presidential-scholarships/",
            source_type="official_institutional",
            deadline_expires_iso="2027-03-01T23:59:59+01:00",
            notes={
                "award_amount": "Verified directly on bi.no: Full tuition + NOK 50,000/semester living stipend for international MSc recipients (domestic/Lånekassen-eligible candidates treated under domestic tuition terms).",
                "deadlines": "Annual deadline March 1 confirmed on bi.no (updated Oct 20, 2026).",
            },
        ),
        "rules": [
            ("destination_country", "in", {"countries": ["NO"]}, "Full-time 1st-year M.Sc. at BI Oslo, Bergen, or Trondheim (excl. BI-Luiss Joint Master)", True),
            ("degree_level", "in", {"levels": ["masters"]}, "First graduate Master's degree (prior Master's holders ineligible)", True),
            ("applicant_type", "in", {"types": ["first_year"]}, "Incoming Master's admission cohort (upload CV + 1-page letter with application by March 1)", True),
            ("minimum_gpa", "gte", {"min_gpa": 3.7}, "Minimum overall GPA of 'A' on ECTS/equivalent grading scale", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Must accept BI admission offer and seek a first graduate degree; candidates eligible for Lånekassen student loan/fee reduction are classified under domestic rules rather than international stipend schedule."}, "BI admission acceptance, first MSc & Lånekassen classification", True),
        ],
    },
    # 6. Finland — University of Turku International Tuition Fee Waiver Scholarship
    {
        "country_code": "FI",
        "title": "University of Turku (UTU) International Tuition Fee Waiver Scholarship (Finland)",
        "sponsoring_institution": "University of Turku (Turun yliopisto, Finland)",
        "applicant_type": "first_year",
        "funding_type": "tuition_waiver",
        "provider_type": "university",
        "award_type": "tuition_waiver",
        "covers_international": True,
        "award_currency": "EUR",
        "native_amount_min": 750.00,
        "native_amount_max": 6000.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "50% EUR tuition fee waiver on published UTU 2026 fees (€1,500–€12,000/yr = €750–€6,000/yr fee reduction; does NOT cover living costs)",
        "eligibility_summary": "Official Finnish university tuition waiver (Study in Finland confirms Finland provides no government BA/MA full scholarships or living stipends). Grants 50% tuition exemption strictly to non-EU/EEA/Swiss students subject to Finnish tuition fees; residence permit for studies does NOT grant fee exemption.",
        "covers_tuition": True,
        "covers_fees": False,
        "covers_housing": False,
        "covers_meals": False,
        "covers_health_insurance": False,
        "provides_living_stipend": False,
        "covers_travel": False,
        "funding_duration_years": 2.0,
        "max_funding_periods": 3,
        "is_renewable": True,
        "renewal_conditions": "Continued merit-based tuition waiver subject to required annual ECTS completion in Finland.",
        "academic_year": "2026-2027",
        "application_deadline_date": None,
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": False,
        "eligible_citizenships": [],
        "eligible_destination_countries": ["FI"],
        "degree_levels": ["bachelors", "masters"],
        "is_guaranteed_statutory": False,
        "source_name": "University of Turku — Scholarships & Tuition Fees",
        "source_url": "https://www.utu.fi/en/study-at-utu/scholarships-and-tuition-fees",
        "source_type": "official_institutional",
        "source_version": "utu-tuition-waiver-2026",
        "claim_provenance": _build_batch4_claim_provenance(
            source_url="https://www.utu.fi/en/study-at-utu/scholarships-and-tuition-fees",
            source_type="official_institutional",
            notes={
                "award_amount": "50% of UTU published annual tuition fees (€1,500 to €12,000 -> €750 to €6,000 EUR waiver); both studyinfinland.fi and utu.fi confirm living costs are never covered.",
                "citizenship_eligibility": "EU/EEA/Swiss citizens, EU Blue Card/permanent Finnish residents, and exchange students are tuition-exempt in Finland and ineligible for fee-waiver scholarships; a Finnish Type-A permit granted for studies does NOT confer exemption.",
            },
        ),
        "rules": [
            ("excluded_citizenships", "not_in", {"countries": EEA_AND_CH_COUNTRIES}, "Strictly non-EU/EEA/Swiss citizens liable for English-taught Finnish tuition fees", True),
            ("destination_country", "in", {"countries": ["FI"]}, "English-taught Bachelor's or Master's degree at University of Turku, Finland", True),
            ("degree_level", "in", {"levels": ["bachelors", "masters"]}, "Tuition-charging Bachelor's or Master's degree (doctoral and Finnish/Swedish-taught degrees are tuition-free)", True),
            ("applicant_type", "in", {"types": ["first_year"]}, "Degree-seeking admission applicant (exchange students are exempt from tuition)", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Must be subject to Finnish tuition fees (EU Blue Card, permanent residence, or non-study continuous residence permit exemptions do not apply; study-purpose Type-A permit remains tuition-liable) and self-fund all living costs."}, "Tuition liability verification & independent living-cost proof", True),
        ],
    },
    # 7. Italy — Politecnico di Milano DSU Regional Financial Aid (Diritto allo Studio Universitario)
    {
        "country_code": "IT",
        "title": "Politecnico di Milano DSU Regional Financial Aid (Diritto allo Studio Universitario)",
        "sponsoring_institution": "Politecnico di Milano / Regione Lombardia (DSU Regional Right-to-Study)",
        "applicant_type": "all",
        "funding_type": "need_based",
        "provider_type": "university",
        "award_type": "need_and_merit",
        "covers_international": True,
        "award_currency": "EUR",
        "native_amount_min": None,
        "native_amount_max": None,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "Tiered EUR cash scholarship (local / commuter / away-from-home bands) + full university tuition exemption + discounted residence & meals (exact EUR brackets set per annual Lombardy DSU Call; 2025/2026 closed)",
        "eligibility_summary": "Need- and merit-based Lombardy regional right-to-study aid at Politecnico di Milano open to Italian, EU, and international Bachelor's/Master's students below the annual ISEE Universitario income limit (merit CFU required for Years 2+). Last 2025/2026 call marked [CLOSED].",
        "covers_tuition": True,
        "covers_fees": False,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": False,
        "funding_duration_years": 3.0,
        "max_funding_periods": 3,
        "is_renewable": True,
        "renewal_conditions": "Annual renewal requires maintaining ISEE below call threshold AND achieving minimum ECTS/CFU academic credits per degree year.",
        "academic_year": "2025-2026",
        "application_deadline_date": date(2025, 9, 30),
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": True,
        "eligible_citizenships": [],
        "eligible_destination_countries": ["IT"],
        "degree_levels": ["bachelors", "masters"],
        "is_guaranteed_statutory": False,
        "source_name": "Politecnico di Milano — DSU Financial Aid",
        "source_url": "https://www.polimi.it/en/students/tuition-fees-scholarships-and-financial-aid/university-financial-aid-diritto-allo-studio-universitario-dsu",
        "source_type": "official_institutional",
        "source_version": "polimi-dsu-2025-2026-closed",
        "claim_provenance": _build_batch4_claim_provenance(
            source_url="https://www.polimi.it/en/students/tuition-fees-scholarships-and-financial-aid/university-financial-aid-diritto-allo-studio-universitario-dsu",
            source_type="official_institutional",
            deadline_expires_iso="2025-09-30T23:59:59+02:00",
            notes={
                "award_amount": "Summary portal confirms tuition exemption, away/commuter/local EUR bands & residence/dining benefits without inline EUR figures (delegated to closed Call PDF); maintained null.",
                "deadlines": "Polimi portal marks A.A. 2025/2026 Call [CLOSED]; awaiting next Lombardy call opening.",
            },
        ),
        "rules": [
            ("destination_country", "in", {"countries": ["IT"]}, "Enrolled full-time in Bachelor's or Laurea Magistrale at Politecnico di Milano, Italy", True),
            ("degree_level", "in", {"levels": ["bachelors", "masters"]}, "Bachelor of Science or Master of Science degree", True),
            ("financial_need_level", "in", {"levels": ["high", "moderate"]}, "Certified ISEE 'for university use' (or equivalent legalized foreign family income/asset dossier) within Lombardy ceiling", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Year 1 determined by verified ISEE economic bracket; Year 2+ requires minimum annual CFU credits. Students are allocated local, commuter, or away-from-home status by official residence distance."}, "ISEE Universitario / foreign income dossier & CFU merit", True),
        ],
    },
    # 8. Spain — MEFD Beca General para Estudios Universitarios (Grado y Máster)
    {
        "country_code": "ES",
        "title": "MEFD Beca General para Estudios Universitarios (Grado y Máster — España)",
        "sponsoring_institution": "Ministerio de Educación, Formación Profesional y Deportes (MEFD), Gobierno de España",
        "applicant_type": "all",
        "funding_type": "need_and_merit",
        "provider_type": "government",
        "award_type": "tuition_plus_stipend",
        "covers_international": True,
        "award_currency": "EUR",
        "native_amount_min": 1700.00,
        "native_amount_max": 4585.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "Beca matrícula (full 1st-enrollment public university credits) + €1,700 fixed income + €2,700 change-of-residence + €50–€125 academic excellence + >=€60 variable grant (RD 179/2026)",
        "eligibility_summary": "Spanish statutory university grant (RD 179/2026; excludes PhD/titles propios) for Spanish nationals, EU citizens permanently residing/working in Spain (non-resident EU gets tuition credit only), or non-EU holders of legal residence permits as of Dec 31, 2025 (student 'estancia' visa excluded).",
        "covers_tuition": True,
        "covers_fees": False,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": False,
        "funding_duration_years": 4.0,
        "max_funding_periods": 5,
        "is_renewable": True,
        "renewal_conditions": "Annual renewal requires meeting Umbral 1–3 household income/patrimony limits, 60-credit enrollment norm, and pass rates.",
        "academic_year": "2026-2027",
        "application_deadline_date": None,
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": True,
        "eligible_citizenships": [],
        "eligible_destination_countries": ["ES"],
        "degree_levels": ["bachelors", "masters"],
        "is_guaranteed_statutory": True,
        "source_name": "MEFD España — Becas y Ayudas Universitarias",
        "source_url": "https://www.becaseducacion.gob.es/becas-y-ayudas/universidad-grado-master/tipos-de-becas.html",
        "source_type": "government_portal",
        "source_version": "rd-179-2026-beca-general",
        "claim_provenance": _build_batch4_claim_provenance(
            source_url="https://www.becaseducacion.gob.es/becas-y-ayudas/universidad-grado-master/tipos-de-becas.html",
            source_type="government_portal",
            notes={
                "award_amount": "Verified directly on becaseducacion.gob.es (RD 179/2026): €1,700 renta + €2,700 residencia + €50–€125 excelencia + >=€60 cuantía variable + beca matrícula.",
                "citizenship_eligibility": "que-necesitas.html: Spanish citizens, EU citizens with permanent residence or work in Spain (otherwise tuition waiver only), or non-EU citizens with legal residence permit on Dec 31, 2025 ('autorización de estancia' study visa explicitly insufficient).",
            },
        ),
        "rules": [
            ("country_of_residence", "in", {"countries": ["ES"]}, "Permanent/legal residence in Spain required for full grant (non-resident students abroad ineligible; non-EU student 'estancia' visa excluded)", True),
            ("destination_country", "in", {"countries": ["ES"]}, "Official Grado or Máster Universitario at an accredited Spanish university (excludes Doctorado)", True),
            ("degree_level", "in", {"levels": ["bachelors", "masters"]}, "Official undergraduate Grado or Master's degree (third-cycle PhD excluded)", True),
            ("financial_need_level", "in", {"levels": ["high", "moderate"]}, "Household income and patrimony within Umbral 1–3 statutory ceilings (RD 179/2026)", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Must hold no prior equal/higher degree, enroll in >=60 ECTS (minimum 30 with reduced aid), and meet EU permanent residence/work or non-EU Dec 31, 2025 legal 'residencia' permit (student estancia insufficient)."}, "Spanish/EU permanent residence or pre-2026 non-EU residencia permit", True),
        ],
    },
    # 9. Erasmus+ Full-Degree — Erasmus Mundus Joint Masters (EMJM) Full Scholarship
    {
        "country_code": "BE",
        "title": "Erasmus Mundus Joint Masters (EMJM) Full-Degree Scholarship (Erasmus+)",
        "sponsoring_institution": "European Commission (EACEA) & Erasmus+ Joint Master Consortia",
        "applicant_type": "all",
        "funding_type": "full_funding",
        "provider_type": "official_agency",
        "award_type": "full_ride",
        "covers_international": True,
        "award_currency": "EUR",
        "native_amount_min": 16800.00,
        "native_amount_max": 16800.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "€1,400 EUR/month (€16,800/year, up to 24 months / €33,600 total) student living & travel unit contribution + full consortium Master's tuition waiver + insurance",
        "eligibility_summary": "Official full-degree European Union Erasmus+ joint Master's scholarship (60–120 ECTS across >=3 universities in >=3 countries) open to top Bachelor's graduates of ALL nationalities worldwide (both EU/EEA and non-EU). Distinct from short-term Erasmus+ exchange mobility.",
        "covers_tuition": True,
        "covers_fees": True,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": True,
        "provides_living_stipend": True,
        "covers_travel": True,
        "funding_duration_years": 2.0,
        "max_funding_periods": 2,
        "is_renewable": True,
        "renewal_conditions": "Awarded for full 1 to 2 academic year Joint Master's duration (max 24 months); 75% EU-country residency rule only limits identical-country host tracks per Programme Guide.",
        "academic_year": "2027-2028",
        "application_deadline_date": None,
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": False,
        "eligible_citizenships": [],
        "eligible_destination_countries": ERASMUS_DESTINATIONS,
        "degree_levels": ["masters"],
        "is_guaranteed_statutory": False,
        "source_name": "European Commission — Erasmus+ Programme Guide (EMJM)",
        "source_url": "https://erasmus-plus.ec.europa.eu/programme-guide/part-b/key-action-2/erasmus-mundus",
        "source_type": "official_agency",
        "source_version": "erasmus-emjm-1400-eur",
        "claim_provenance": _build_batch4_claim_provenance(
            source_url="https://erasmus-plus.ec.europa.eu/programme-guide/part-b/key-action-2/erasmus-mundus",
            source_type="official_agency",
            notes={
                "award_amount": "Verified directly in EC Erasmus+ Programme Guide: 'The scholarship is calculated as: 1 400 Euros/month x DS' (up to 24 months = €33,600 EUR max + full participation costs).",
                "deadlines": "Consortium-specific EMJM deadlines vary (typically Oct–Mar); apply directly to chosen consortium.",
            },
        ),
        "rules": [
            ("destination_country", "in", {"countries": ERASMUS_DESTINATIONS}, "Multi-country Joint Master consortium spanning >=3 universities in Erasmus+ Programme/Partner states", True),
            ("degree_level", "in", {"levels": ["masters"]}, "Full-degree 60, 90, or 120 ECTS Erasmus Mundus Joint Master (single joint or multiple Master's diplomas)", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Requires completed Bachelor's degree, admission by chosen EMJM consortium, study mobility across >=2 consortium countries other than residence country, and no prior EMJM scholarship award."}, "Bachelor's degree, multi-country consortium offer & non-repeat rule", True),
        ],
    },
    # 10. Erasmus+ Short-Term Mobility / Exchange ONLY — Student Mobility Grant
    {
        "country_code": "BE",
        "title": "Erasmus+ Higher Education Student Mobility Grant (Short-Term Exchange Only)",
        "sponsoring_institution": "European Commission / National Erasmus+ Agencies & Participating Sending Universities",
        "applicant_type": "all",
        "funding_type": "exchange_mobility",
        "provider_type": "official_agency",
        "award_type": "mobility_grant",
        "covers_international": True,
        "award_currency": "EUR",
        "native_amount_min": None,
        "native_amount_max": None,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "EXCHANGE MOBILITY ONLY (2–12 months; NOT a full-degree scholarship): host exchange fee waiver + variable EUR monthly contribution toward travel & living costs determined by sending HEI country group",
        "eligibility_summary": "Official EU short-term student exchange mobility grant (minimum 2 months to maximum 12 months per study cycle; or 5–30 days blended) strictly for students ALREADY registered at a participating Erasmus+ HEI. Does NOT fund full external degrees; grant rates vary by origin/destination living costs.",
        "covers_tuition": True,
        "covers_fees": False,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": True,
        "funding_duration_years": 1.0,
        "max_funding_periods": 1,
        "is_renewable": False,
        "renewal_conditions": "Non-degree exchange capped at 12 months per EQF study cycle (24 months for one-cycle courses such as Medicine/Architecture).",
        "academic_year": "2026-2027",
        "application_deadline_date": None,
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": False,
        "eligible_citizenships": [],
        "eligible_destination_countries": ERASMUS_DESTINATIONS,
        "degree_levels": ["bachelors", "masters", "doctoral"],
        "is_guaranteed_statutory": False,
        "source_name": "European Commission — Erasmus+ Studying Abroad Mobility",
        "source_url": "https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals/students/studying-abroad",
        "source_type": "official_agency",
        "source_version": "erasmus-plus-ka1-mobility",
        "claim_provenance": _build_batch4_claim_provenance(
            source_url="https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals/students/studying-abroad",
            source_type="official_agency",
            notes={
                "award_amount": "Variable EUR monthly mobility contribution (sending-HEI & country-group dependent; omitted as single fixed EUR figure because ec.europa.eu leaves exact band rates to national agencies/distance).",
                "funding_scope": "Strictly short-term exchange mobility (2–12 months, host tuition/exam waiver only) for already-registered students — NEVER a full-degree funding package.",
            },
        ),
        "rules": [
            ("destination_country", "in", {"countries": ERASMUS_DESTINATIONS}, "Inter-institutional Erasmus+ partner host university exchange destination", True),
            ("degree_level", "in", {"levels": ["bachelors", "masters", "doctoral"]}, "Exchange period during an existing Short-Cycle, Bachelor, Master, or Doctoral program (NOT standalone degree admission)", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "EXCHANGE MOBILITY ONLY (NOT FULL-DEGREE): Applicant must ALREADY be enrolled in a recognized degree at a participating Erasmus+ sending university and be selected by that home institution's international office (no central EU application)."}, "Home Erasmus+ HEI enrollment & internal exchange nomination", True),
        ],
    },
]


def seed_phase4_batch4_europe(db: Session) -> Dict[str, int]:
    """
    Idempotently seed all 10 Batch 4 Europe & Erasmus+ verified programs
    and ensure all referenced European/partner country codes exist cleanly.
    """
    _ensure_batch4_countries(db)

    created = 0
    updated = 0
    rules_created = 0

    for item in BATCH4_EUROPE_SCHOLARSHIPS:
        sch = (
            db.query(ScholarshipProgram)
            .filter(ScholarshipProgram.title == item["title"])
            .first()
        )
        fields = {
            "institution_id": None,
            "country_code": item["country_code"],
            "title": item["title"],
            "sponsoring_institution": item["sponsoring_institution"],
            "applicant_type": item["applicant_type"],
            "funding_type": item["funding_type"],
            "provider_type": item["provider_type"],
            "award_type": item["award_type"],
            "covers_international": item["covers_international"],
            "award_currency": item["award_currency"],
            "native_amount_min": item["native_amount_min"],
            "native_amount_max": item["native_amount_max"],
            "award_amount_min_usd": item["award_amount_min_usd"],
            "award_amount_max_usd": item["award_amount_max_usd"],
            "award_fixed_usd": None,
            "max_award_info": item["max_award_info"],
            "eligibility_summary": item["eligibility_summary"],
            "covers_tuition": item["covers_tuition"],
            "covers_fees": item["covers_fees"],
            "covers_housing": item["covers_housing"],
            "covers_meals": item["covers_meals"],
            "covers_health_insurance": item["covers_health_insurance"],
            "provides_living_stipend": item["provides_living_stipend"],
            "covers_travel": item["covers_travel"],
            "funding_duration_years": item["funding_duration_years"],
            "max_funding_periods": item["max_funding_periods"],
            "is_renewable": item["is_renewable"],
            "renewal_conditions": item["renewal_conditions"],
            "academic_year": item["academic_year"],
            "application_deadline_date": item["application_deadline_date"],
            "is_deadline_rolling": item["is_deadline_rolling"],
            "min_gpa_4": item["min_gpa_4"],
            "requires_financial_need": item["requires_financial_need"],
            "eligible_citizenships": item["eligible_citizenships"],
            "eligible_residency_states": [],
            "eligible_destination_countries": item["eligible_destination_countries"],
            "degree_levels": item["degree_levels"],
            "is_guaranteed_statutory": item["is_guaranteed_statutory"],
            "source_name": item["source_name"],
            "source_url": item["source_url"],
            "source_type": item["source_type"],
            "source_version": item["source_version"],
            "verification_method": "manual_primary_source_fetch",
            "verified_by": None,
            "verified_at": BATCH4_VERIFIED_AT,
            "verification_expires_at": BATCH4_ELIG_EXPIRES_AT,
            "freshness_status": "current",
            "requires_manual_review": False,
            "claim_provenance": item["claim_provenance"],
            "conflict_notes": None,
            "is_verified": True,
            "is_current": True,
        }

        if not sch:
            sch = ScholarshipProgram(**fields)
            db.add(sch)
            db.flush()
            created += 1
        else:
            for k, v in fields.items():
                setattr(sch, k, v)
            updated += 1

        existing_by_label = {
            r.human_label: r
            for r in db.query(ScholarshipEligibilityRule)
            .filter(ScholarshipEligibilityRule.scholarship_id == sch.id)
            .all()
        }
        for dim, op, val, label, mandatory in item.get("rules", []):
            existing_rule = existing_by_label.get(label)
            if existing_rule is None:
                db.add(
                    ScholarshipEligibilityRule(
                        scholarship_id=sch.id,
                        rule_dimension=dim,
                        rule_operator=op,
                        rule_value=val,
                        human_label=label,
                        is_mandatory=mandatory,
                    )
                )
                rules_created += 1
            else:
                existing_rule.rule_dimension = dim
                existing_rule.rule_operator = op
                existing_rule.rule_value = val
                existing_rule.is_mandatory = mandatory

    db.commit()
    return {
        "batch4_created": created,
        "batch4_updated": updated,
        "batch4_rules_created": rules_created,
    }
