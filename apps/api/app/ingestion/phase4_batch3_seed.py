"""
Phase 4, Step 3 — Batch 3 Global Scholarship Expansion Seeder (Asia & Southeast Asia).

Contains strictly official-primary-source-verified scholarships covering:
China (CN), India (IN), South Korea (KR), Singapore (SG), Malaysia (MY),
Indonesia (ID), Pakistan (PK), Bangladesh (BD), Vietnam (VN), and the Philippines (PH),
seeded with complete 15-field claim provenance, preserved native currencies
(CNY, INR, KRW, SGD, MYR, IDR, PKR, BDT, VND, PHP), and deterministic eligibility rules.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.country import Country
from app.models.rag import ScholarshipEligibilityRule, ScholarshipProgram

BATCH3_VERIFIED_AT = datetime(2026, 11, 25, 14, 0, tzinfo=timezone.utc)
BATCH3_ELIG_EXPIRES_AT = BATCH3_VERIFIED_AT + timedelta(days=180)
BATCH3_AMT_EXPIRES_AT = BATCH3_VERIFIED_AT + timedelta(days=120)
BATCH3_DEADLINE_EXPIRES_AT = BATCH3_VERIFIED_AT + timedelta(days=90)

BATCH3_COUNTRY_NAMES: Dict[str, str] = {
    "CN": "China",
    "IN": "India",
    "KR": "South Korea",
    "SG": "Singapore",
    "MY": "Malaysia",
    "ID": "Indonesia",
    "PK": "Pakistan",
    "BD": "Bangladesh",
    "VN": "Vietnam",
    "PH": "Philippines",
    "TH": "Thailand",
    "KH": "Cambodia",
    "LA": "Laos",
    "MM": "Myanmar",
    "BN": "Brunei",
    "LK": "Sri Lanka",
    "NP": "Nepal",
    "BT": "Bhutan",
    "MV": "Maldives",
    "JP": "Japan",
}


def _ensure_batch3_countries(db: Session) -> None:
    existing = {row[0] for row in db.query(Country.code).all()}
    added = False
    for code, name in BATCH3_COUNTRY_NAMES.items():
        if code not in existing:
            db.add(Country(code=code, name=name, currency_code="USD"))
            added = True
    if added:
        db.flush()


def _build_batch3_claim_provenance(
    *,
    source_url: str,
    source_type: str,
    deadline_expires_iso: Optional[str] = None,
    notes: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    ver_iso = BATCH3_VERIFIED_AT.isoformat()
    elig_exp_iso = BATCH3_ELIG_EXPIRES_AT.isoformat()
    amt_exp_iso = BATCH3_AMT_EXPIRES_AT.isoformat()
    dl_exp_iso = deadline_expires_iso or BATCH3_DEADLINE_EXPIRES_AT.isoformat()
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


MIS_EXTRA_COUNTRIES = [
    "CN", "KR", "JP", "AF", "AL", "DZ", "AZ", "BH", "BR", "CL", "EG", "GE",
    "HK", "HU", "IR", "IQ", "JO", "KZ", "XK", "KW", "KG", "LY", "MA", "PS",
    "QA", "RU", "SA", "SN", "RS", "SD", "SY", "TJ", "TL", "TN", "TR", "TM",
    "AE", "UZ", "YE",
]

MIS_ELIGIBLE_CITIZENSHIPS = list(
    dict.fromkeys(
        [
            "SG", "ID", "PH", "VN", "TH", "KH", "LA", "MM", "BN",
            "IN", "PK", "BD", "LK", "MV", "GB", "CA", "AU", "NZ",
            "NG", "GH", "KE", "ZA", "RW", "JM", "BB", "TT", "BS", "BZ", "GY",
        ]
        + MIS_EXTRA_COUNTRIES
    )
)

BATCH3_ASIA_PACIFIC_SCHOLARSHIPS: List[Dict[str, Any]] = [
    # 1. China — CAS-ANSO Scholarship (2027 Call — USTC / UCAS / CAS)
    {
        "country_code": "CN",
        "title": "CAS-ANSO Scholarship (2027 Call — USTC / UCAS / CAS)",
        "sponsoring_institution": "Alliance of National and International Science Organizations (ANSO) & Chinese Academy of Sciences (CAS)",
        "applicant_type": "all",
        "funding_type": "full_funding",
        "provider_type": "government",
        "award_type": "full_ride",
        "covers_international": True,
        "award_currency": "CNY",
        "native_amount_min": 36000.00,
        "native_amount_max": 84000.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "3,000 RMB/month Master's (36,000 CNY/yr up to 36 mo) or 6,000–7,000 RMB/month PhD (72,000–84,000 CNY/yr up to 48 mo) + tuition waiver + medical insurance + one-way airfare",
        "eligibility_summary": "Official 2027 Call (open Nov 17, 2026 – Feb 28, 2027) funding Master's (100/yr) and PhD (300/yr, incl. ANSO-CAS-TWAS/UNESCO LDC quota) at USTC, UCAS, and CAS institutes for non-Chinese nationals (PhD born after Jan 1, 1992; Master's after Jan 1, 1997).",
        "covers_tuition": True,
        "covers_fees": True,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": True,
        "provides_living_stipend": True,
        "covers_travel": True,
        "funding_duration_years": 4.0,
        "max_funding_periods": 4,
        "is_renewable": True,
        "renewal_conditions": "Subject to annual USTC/UCAS qualification tests (6,000 RMB/mo advances to 7,000 RMB/mo after PhD qualifying exam); concurrent CSC scholarship strictly prohibited.",
        "academic_year": "2027",
        "application_deadline_date": date(2027, 2, 28),
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": False,
        "eligible_citizenships": [],
        "eligible_destination_countries": ["CN"],
        "degree_levels": ["masters", "doctoral"],
        "is_guaranteed_statutory": False,
        "source_name": "ANSO — CAS-ANSO Scholarship 2027 Call",
        "source_url": "https://www.anso.org.cn/programmes/talent/scholarship/",
        "source_type": "official_agency",
        "source_version": "cas-anso-2027-call",
        "claim_provenance": _build_batch3_claim_provenance(
            source_url="https://www.anso.org.cn/programmes/talent/scholarship/",
            source_type="official_agency",
            deadline_expires_iso="2027-02-28T23:59:59+08:00",
            notes={
                "award_amount": "Verified directly on ANSO 2027 Call: 3,000 RMB/mo Master's; 6,000 or 7,000 RMB/mo PhD + tuition waiver + insurance + travel.",
                "deadlines": "2027 call open Nov 17, 2026 through Feb 28, 2027 (Beijing time).",
            },
        ),
        "rules": [
            ("excluded_citizenships", "not_in", {"countries": ["CN"]}, "Non-Chinese citizens only (PRC nationals excluded)", True),
            ("destination_country", "in", {"countries": ["CN"]}, "Full-time graduate study at USTC, UCAS, or CAS institutes in China", True),
            ("degree_level", "in", {"levels": ["masters", "doctoral"]}, "Master's (up to 36 mo) or Doctoral PhD (up to 48 mo)", True),
            ("age_limit", "between", {"max_age": 34, "reference_date": "2027-01-01"}, "PhD applicants born after 1992-01-01 (Master's after 1997-01-01)", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Must meet USTC/UCAS international admission standards (incl. English/Chinese proficiency) and hold no simultaneous CSC or other Chinese government scholarship."}, "USTC/UCAS admission & non-dual-scholarship rule", True),
        ],
    },
    # 2. China — USTC Fellowship for Undergraduate Programs (CSC / USTC Full & Partial)
    {
        "country_code": "CN",
        "title": "USTC Fellowship for Undergraduate Programs (CSC / USTC Full & Partial)",
        "sponsoring_institution": "University of Science and Technology of China (USTC)",
        "applicant_type": "first_year",
        "funding_type": "full_funding",
        "provider_type": "university",
        "award_type": "full_ride",
        "covers_international": True,
        "award_currency": "CNY",
        "native_amount_min": None,
        "native_amount_max": None,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "Full tuition waiver + comprehensive medical insurance + monthly living stipend + free dorm (Class A) or tuition waiver (Class B) in CNY (exact UG CNY scale unpublished on 2027 notice)",
        "eligibility_summary": "2027 international undergraduate admission & fellowship at USTC (open Oct 25, 2026 – Mar 31, 2027) for non-Chinese citizens under age 25 holding HSK Level 5 and mandatory CSCA assessment (replaces domestic Gaokao for foreign UG applicants).",
        "covers_tuition": True,
        "covers_fees": True,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": True,
        "provides_living_stipend": True,
        "covers_travel": False,
        "funding_duration_years": 4.0,
        "max_funding_periods": 4,
        "is_renewable": True,
        "renewal_conditions": "Reviewed annually based on undergraduate academic standing and Chinese Ministry of Education fellowship guidelines.",
        "academic_year": "2027",
        "application_deadline_date": date(2027, 3, 31),
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": False,
        "eligible_citizenships": [],
        "eligible_destination_countries": ["CN"],
        "degree_levels": ["bachelors"],
        "is_guaranteed_statutory": False,
        "source_name": "USTC International College — 2027 UG Admission & Fellowship",
        "source_url": "https://ic.ustc.edu.cn/?abroad=339",
        "source_type": "official_institutional",
        "source_version": "ustc-ug-2027-csca",
        "claim_provenance": _build_batch3_claim_provenance(
            source_url="https://ic.ustc.edu.cn/?abroad=339",
            source_type="official_institutional",
            deadline_expires_iso="2027-03-31T23:59:59+08:00",
            notes={
                "award_amount": "Full/partial CNY tuition waiver, insurance, dorm & monthly stipend confirmed on ic.ustc.edu.cn; numeric CNY table maintained null where omitted on UG call.",
                "deadlines": "2027 UG application window Oct 25, 2026 – Mar 31, 2027 (mandatory CSCA pre-requisite for international UG applicants).",
            },
        ),
        "rules": [
            ("excluded_citizenships", "not_in", {"countries": ["CN"]}, "Non-Chinese citizens holding valid foreign passport per PRC Nationality Law", True),
            ("destination_country", "in", {"countries": ["CN"]}, "Full-time 4-year undergraduate degree at USTC (Hefei, China)", True),
            ("degree_level", "in", {"levels": ["bachelors"]}, "Undergraduate Bachelor's program", True),
            ("applicant_type", "in", {"types": ["first_year"]}, "First-time incoming undergraduate applicant", True),
            ("age_limit", "between", {"max_age": 24, "reference_date": "2027-09-01"}, "Under age 25 as of September 1, 2027", True),
            ("required_exams", "custom", {"exams": {"CSCA": None}}, "Mandatory China Scholastic Competency Assessment (CSCA: Professional Chinese, Math + Physics/Chemistry)", True),
            ("language_proficiency", "gte", {"language": "zh", "accepted_formats": ["hsk", "official_test", "certified_diploma"], "min_scores": {"HSK": 5}}, "Chinese HSK Level 5 (>= 180)", True),
        ],
    },
    # 3. India — DST INSPIRE Scholarship for Higher Education (SHE)
    {
        "country_code": "IN",
        "title": "DST INSPIRE Scholarship for Higher Education (SHE)",
        "sponsoring_institution": "Department of Science & Technology (DST), Ministry of Science & Technology, Government of India",
        "applicant_type": "first_year",
        "funding_type": "merit",
        "provider_type": "government",
        "award_type": "stipend_and_grant",
        "covers_international": False,
        "award_currency": "INR",
        "native_amount_min": 60000.00,
        "native_amount_max": 80000.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "₹5,000/month scholarship (₹60,000/yr for up to 5 yrs) + ₹20,000/yr Mentorship Grant in Years 3–4 (max ₹80,000/yr INR)",
        "eligibility_summary": "Flagship Indian government scholarship (12,000 awards/yr) for Indian nationals aged 17–22 in Class XII Top 1% or JEE/NEET Top 10,000 pursuing Basic & Natural Sciences (B.Sc./B.S./Int. M.Sc.). Excludes Engineering, Medicine, Computer Science, Economics, Psychology.",
        "covers_tuition": False,
        "covers_fees": False,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": False,
        "funding_duration_years": 5.0,
        "max_funding_periods": 5,
        "is_renewable": True,
        "renewal_conditions": "Annual aggregate >= 60% or >= 7.0/10.0 CGPA (no CGPA-to-% conversion allowed by DST) plus annual mentorship report.",
        "academic_year": "2026-2027",
        "application_deadline_date": None,
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": False,
        "eligible_citizenships": ["IN"],
        "eligible_destination_countries": ["IN"],
        "degree_levels": ["bachelors"],
        "is_guaranteed_statutory": False,
        "source_name": "DST INSPIRE Official Portal (Gov. of India)",
        "source_url": "https://www.online-inspire.gov.in/",
        "source_type": "government_portal",
        "source_version": "inspire-she-faq-official",
        "claim_provenance": _build_batch3_claim_provenance(
            source_url="https://www.online-inspire.gov.in/",
            source_type="government_portal",
            notes={
                "award_amount": "Verified directly in DST INSPIRE-SHE FAQ PDF: ₹5,000/month (₹60,000/yr) + ₹20,000/yr mentorship grant paid strictly in INR.",
                "citizenship_eligibility": "Requires Indian citizenship, Class XII Top 1% of Board OR JEE/NEET Top 10,000 OR NTSE/Olympiad; restricted strictly to 18 Basic & Natural Science subjects.",
            },
        ),
        "rules": [
            ("citizenship", "in", {"countries": ["IN"]}, "Indian citizen", True),
            ("destination_country", "in", {"countries": ["IN"]}, "Recognized Indian university or degree college (regular mode)", True),
            ("degree_level", "in", {"levels": ["bachelors"]}, "Undergraduate Basic/Natural Science (B.Sc., B.S., Int. M.Sc. / M.S.)", True),
            ("applicant_type", "in", {"types": ["first_year"]}, "Incoming 1st-year Basic & Natural Sciences undergraduate", True),
            ("age_limit", "between", {"min_age": 17, "max_age": 22, "reference_date": "2026-08-01"}, "Aged 17–22 in Class XII graduation year", True),
            ("field_of_study", "in", {
                "allowed_fields": [
                    "physics", "chemistry", "mathematics", "biology", "statistics",
                    "geology", "astrophysics", "astronomy", "electronics", "botany",
                    "zoology", "biochemistry", "microbiology", "anthropology",
                    "geophysics", "geochemistry", "atmospheric", "oceanic",
                    "basic science", "natural science", "physical science", "life science",
                ],
                "excluded_fields": [
                    "engineering", "medicine", "mbbs", "computer science",
                    "agriculture", "veterinary", "economics", "psychology",
                    "commerce", "management", "nursing", "pharmacy",
                ],
            }, "Strictly limited to DST-listed Basic & Natural Sciences (excludes Engineering, Medicine, CS, Agriculture, Economics)", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Must rank in Class XII Top 1% of Central/State Board OR Top 10,000 AIR in JEE Main/Advanced/NEET OR NTSE/JBNSTS/International Olympiad; renewal requires >=7.0/10 CGPA or >=60%."}, "Class XII Top 1% / JEE-NEET Top 10,000 & renewal standing", True),
        ],
    },
    # 4. South Korea — 2027 Global Korea Scholarship (GKS-U Undergraduate, NIIED)
    {
        "country_code": "KR",
        "title": "Global Korea Scholarship — Undergraduate Degrees (2027 GKS-U, NIIED)",
        "sponsoring_institution": "National Institute for International Education (NIIED), Ministry of Education, Republic of Korea",
        "applicant_type": "first_year",
        "funding_type": "full_funding",
        "provider_type": "government",
        "award_type": "full_ride",
        "covers_international": True,
        "award_currency": "KRW",
        "native_amount_min": 13560000.00,
        "native_amount_max": 14400000.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "13,560,000 KRW/yr (Korean language yr: 1,130,000 KRW/mo) to 14,400,000 KRW/yr (degree yrs: 1,200,000 KRW/mo) all-inclusive living allowance + up to 5M KRW/sem tuition + 5.2M KRW/yr language fee + economy airfare",
        "eligibility_summary": "Official 2027 NIIED Korean government undergraduate scholarship (up to 7 yrs) for foreign high school graduates (< 25 on Mar 1, 2027) with foreign GPA >= 80% / 2.64/4.0. Excludes Korean nationals, dual KR citizens, and Korean HS graduates (Embassy cycle closed Sep 30, 2026).",
        "covers_tuition": True,
        "covers_fees": True,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": True,
        "provides_living_stipend": True,
        "covers_travel": True,
        "funding_duration_years": 5.0,
        "max_funding_periods": 7,
        "is_renewable": True,
        "renewal_conditions": "TOPIK Level 3+ required after 1-year Korean language course to matriculate; TOPIK 5+ grants 100,000 KRW/mo merit bonus.",
        "academic_year": "2027",
        "application_deadline_date": date(2026, 9, 30),
        "is_deadline_rolling": False,
        "min_gpa_4": 2.64,
        "requires_financial_need": False,
        "eligible_citizenships": [],
        "eligible_destination_countries": ["KR"],
        "degree_levels": ["bachelors"],
        "is_guaranteed_statutory": False,
        "source_name": "Study in Korea / NIIED 2027 GKS-U Guidelines",
        "source_url": "https://www.studyinkorea.go.kr/en/plan/scholarship.do",
        "source_type": "government_portal",
        "source_version": "2027-gks-u-guidelines",
        "claim_provenance": _build_batch3_claim_provenance(
            source_url="https://www.studyinkorea.go.kr/en/plan/scholarship.do",
            source_type="government_portal",
            deadline_expires_iso="2026-09-30T23:59:59+09:00",
            notes={
                "award_amount": "Verified directly from Sept 2026 NIIED 2027 GKS-U Guidelines PDF (pp. 26–27): 1,130,000 KRW/mo (lang yr) / 1,200,000 KRW/mo (degree) + tuition up to 5M KRW/sem.",
                "deadlines": "2027 GKS-U Embassy track closed September 30, 2026.",
            },
        ),
        "rules": [
            ("excluded_citizenships", "not_in", {"countries": ["KR"]}, "Applicant and both parents must hold non-Korean citizenship", True),
            ("dual_citizenship", "in", {"policy": "restricted", "restricted_countries": ["KR"]}, "No Korean dual citizenship permitted (strictly verified by NIIED)", True),
            ("destination_country", "in", {"countries": ["KR"]}, "Designated Korean university (Associate or 4-year Bachelor's in ROK)", True),
            ("degree_level", "in", {"levels": ["bachelors"]}, "Undergraduate Associate or Bachelor's degree", True),
            ("age_limit", "between", {"max_age": 24, "reference_date": "2027-03-01"}, "Under 25 years old on March 1, 2027", True),
            ("minimum_gpa", "gte", {"min_gpa": 2.64}, "Minimum high school CGPA >= 2.64/4.0 or >= 80% percentile (foreign HS only; CSAT not required)", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Must graduate from high school outside South Korea (graduates of Korean high schools/international schools inside Korea excluded)."}, "Foreign high school graduation & non-KR residency track", True),
        ],
    },
    # 5. Singapore — A*STAR Graduate Scholarship (AGS — PhD)
    {
        "country_code": "SG",
        "title": "A*STAR Graduate Scholarship (AGS — PhD)",
        "sponsoring_institution": "Agency for Science, Technology and Research (A*STAR), Singapore",
        "applicant_type": "all",
        "funding_type": "full_funding",
        "provider_type": "government",
        "award_type": "full_ride",
        "covers_international": True,
        "award_currency": "SGD",
        "native_amount_min": 43200.00,
        "native_amount_max": 74400.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "S$3,600–S$5,000/mo International (S$43,200–S$60,000/yr) or S$4,500–S$6,200/mo Singapore Citizen (up to S$74,400/yr) + full PhD tuition + computer/book/conference/thesis grants + 12-mo overseas attachment",
        "eligibility_summary": "Singapore premier STEM PhD scholarship (Cycle 1 open Dec 15, 2026 – Feb 1, 2027) covering full tuition + monthly SGD stipend at NUS, NTU, SMU, or SUTD. Non-citizens/non-PRs must hold/complete a degree at a Singapore Autonomous University and serve a 3-yr Singapore RIE service bond.",
        "covers_tuition": True,
        "covers_fees": True,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": True,
        "funding_duration_years": 4.0,
        "max_funding_periods": 4,
        "is_renewable": True,
        "renewal_conditions": "Funded up to 4 years; international PhD graduates owe a 3-year RIE service commitment in an ACRA-registered Singapore entity.",
        "academic_year": "2027",
        "application_deadline_date": date(2027, 2, 1),
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": False,
        "eligible_citizenships": [],
        "eligible_destination_countries": ["SG"],
        "degree_levels": ["doctoral"],
        "is_guaranteed_statutory": False,
        "source_name": "A*STAR Singapore Graduate Scholarships",
        "source_url": "https://www.a-star.edu.sg/scholarships/home/scholarships/ags--scholarship",
        "source_type": "government_portal",
        "source_version": "ags-2027-cycle1",
        "claim_provenance": _build_batch3_claim_provenance(
            source_url="https://www.a-star.edu.sg/scholarships/home/scholarships/ags--scholarship",
            source_type="government_portal",
            deadline_expires_iso="2027-02-01T23:59:59+08:00",
            notes={
                "award_amount": "Verified directly from a-star.edu.sg: SGD 3,600–5,000/mo Intl, SGD 4,100–5,600/mo PR, SGD 4,500–6,200/mo Singapore Citizen + full tuition.",
                "deadlines": "2027 Cycle 1 window open Dec 15, 2026 – Feb 1, 2027 (Cycle 2 Jun 15 – Aug 1, 2027).",
            },
        ),
        "rules": [
            ("destination_country", "in", {"countries": ["SG"]}, "PhD admission at NUS, NTU, SMU, or SUTD (Singapore Autonomous Universities)", True),
            ("degree_level", "in", {"levels": ["doctoral"]}, "Full-time Doctoral PhD level", True),
            ("field_of_study", "in", {
                "allowed_fields": [
                    "computing", "information science", "computer science", "engineering",
                    "biomedical", "physical science", "chemistry", "physics", "mathematics",
                    "semiconductor", "quantum", "materials", "stem",
                ],
                "excluded_fields": ["law", "humanities", "fine arts", "business administration"],
            }, "Computing & Information Science, Biomedical, Physical Sciences & Engineering (incl. Quantum & Semiconductor)", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Second Class Upper Honours (or equiv.); non-Singapore Citizens/PRs must have completed or be completing a degree at a Singapore Autonomous University and execute a 3-yr ACRA Singapore RIE bond."}, "SG Autonomous University rule (for Intl) & Honours 2:1", True),
        ],
    },
    # 6. Malaysia — Malaysia International Scholarship (MIS, MOHE)
    {
        "country_code": "MY",
        "title": "Malaysia International Scholarship (MIS, MOHE)",
        "sponsoring_institution": "Ministry of Higher Education (MOHE), Malaysia",
        "applicant_type": "all",
        "funding_type": "full_funding",
        "provider_type": "government",
        "award_type": "tuition_plus_stipend",
        "covers_international": True,
        "award_currency": "MYR",
        "native_amount_min": 18000.00,
        "native_amount_max": 18000.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "RM 1,500.00/month living allowance (18,000 MYR/yr) + full academic tuition paid directly to any of 24 eligible Malaysian universities",
        "eligibility_summary": "Official MOHE Malaysia postgraduate scholarship for ASEAN, Commonwealth, and MOHE-designated non-Malaysian countries (CGPA >= 3.00, IELTS >= 6.0, Master's <= 40 / PhD <= 45; excludes Medicine, Nursing, Pharmacy). 2026/2027 cycle explicitly closed.",
        "covers_tuition": True,
        "covers_fees": True,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": False,
        "funding_duration_years": 3.0,
        "max_funding_periods": 3,
        "is_renewable": True,
        "renewal_conditions": "Full-time postgraduate progression at 24 listed Malaysian public/private universities (max 24 mo Master's; 36 mo PhD).",
        "academic_year": "2026-2027",
        "application_deadline_date": date(2026, 5, 15),
        "is_deadline_rolling": False,
        "min_gpa_4": 3.0,
        "requires_financial_need": False,
        "eligible_citizenships": MIS_ELIGIBLE_CITIZENSHIPS,
        "eligible_destination_countries": ["MY"],
        "degree_levels": ["masters", "doctoral"],
        "is_guaranteed_statutory": False,
        "source_name": "MOHE Malaysia International Scholarship (MIS)",
        "source_url": "https://biasiswa.mohe.gov.my/INTER/index.php",
        "source_type": "government_portal",
        "source_version": "mis-2026-2027-guidelines",
        "claim_provenance": _build_batch3_claim_provenance(
            source_url="https://biasiswa.mohe.gov.my/INTER/index.php",
            source_type="government_portal",
            deadline_expires_iso="2026-05-15T23:59:59+08:00",
            notes={
                "award_amount": "Verified in official MOHE MIS 2026/2027 Guidelines PDF: full tuition + RM 1,500.00/month living allowance (18,000 MYR/yr).",
                "deadlines": "2026/2027 cycle closed (Checking period Oct 8 – Dec 31, 2026 on biasiswa.mohe.gov.my).",
            },
        ),
        "rules": [
            ("geographic_region", "in", {"regions": ["asean", "commonwealth"], "countries": MIS_EXTRA_COUNTRIES, "scope": "citizenship"}, "Citizen of ASEAN, Commonwealth, or MOHE-designated MIS partner country", True),
            ("excluded_citizenships", "not_in", {"countries": ["MY"]}, "Excludes Malaysian citizens", True),
            ("destination_country", "in", {"countries": ["MY"]}, "Full-time study at one of 24 approved Malaysian universities", True),
            ("degree_level", "in", {"levels": ["masters", "doctoral"]}, "Postgraduate Master's or PhD (research/mixed mode/coursework)", True),
            ("age_limit", "between", {"max_age": 45, "reference_date": "2026-05-15"}, "Master's <= 40 years old; PhD <= 45 years old", True),
            ("minimum_gpa", "gte", {"min_gpa": 3.0}, "Minimum CGPA 3.00/4.00 (or 2nd Class Upper)", True),
            ("field_of_study", "in", {"excluded_fields": ["medicine", "nursing", "pharmacy"]}, "Priority areas only (Medicine, Nursing & Pharmacy excluded by MIS)", True),
            ("language_proficiency", "gte", {"language": "en", "accepted_formats": ["ielts", "toefl", "toefl_pbt", "toefl_ibt", "official_test", "certified_diploma"], "min_scores": {"IELTS": 6.0}}, "IELTS >= 6.0, TOEFL PBT >= 550, or prior degree taught in English", True),
        ],
    },
    # 7. Indonesia — Beasiswa KNB (Kemdiktisaintek RI)
    {
        "country_code": "ID",
        "title": "Beasiswa Kemitraan Negara Berkembang (KNB Scholarship, Kemdiktisaintek RI)",
        "sponsoring_institution": "Ministry of Higher Education, Science, and Technology (Kemdiktisaintek), Republic of Indonesia",
        "applicant_type": "all",
        "funding_type": "full_funding",
        "provider_type": "government",
        "award_type": "full_ride",
        "covers_international": True,
        "award_currency": "IDR",
        "native_amount_min": None,
        "native_amount_max": None,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "Full BIPA language + degree tuition waiver + monthly IDR living, book & research allowances + publication fee + medical insurance + roundtrip economy airfare (exact IDR figures omitted from published PDF)",
        "eligibility_summary": "Indonesian government development scholarship (136 partner countries, 47 Indonesian host universities) for non-Indonesian nationals from developing/partner states (UG <= 21, Master's <= 35, PhD <= 40; GPA >= 2.75; IELTS >= 5.5 / TOEFL iBT >= 53 / EMI; excludes refugees/stateless). 2026 cycle closed.",
        "covers_tuition": True,
        "covers_fees": True,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": True,
        "provides_living_stipend": True,
        "covers_travel": True,
        "funding_duration_years": 4.0,
        "max_funding_periods": 4,
        "is_renewable": True,
        "renewal_conditions": "1 year compulsory BIPA Indonesian language training plus up to 3–4 yrs degree duration subject to annual GPA compliance.",
        "academic_year": "2026",
        "application_deadline_date": date(2026, 3, 31),
        "is_deadline_rolling": False,
        "min_gpa_4": 2.75,
        "requires_financial_need": False,
        "eligible_citizenships": [],
        "eligible_destination_countries": ["ID"],
        "degree_levels": ["bachelors", "masters", "doctoral"],
        "is_guaranteed_statutory": False,
        "source_name": "Kemdiktisaintek KNB Official Portal & Guidelines",
        "source_url": "https://knb.kemdiktisaintek.go.id/",
        "source_type": "government_portal",
        "source_version": "knb-2026-official",
        "claim_provenance": _build_batch3_claim_provenance(
            source_url="https://knb.kemdiktisaintek.go.id/",
            source_type="government_portal",
            deadline_expires_iso="2026-03-31T23:59:59+07:00",
            notes={
                "award_amount": "Comprehensive tuition + BIPA + living/book/research/insurance/airfare confirmed in official KNB 2026 PDF; numeric IDR cap omitted from published guidelines so maintained null.",
                "deadlines": "2026 KNB selection Batch I–IV concluded in Sept 2026.",
            },
        ),
        "rules": [
            ("excluded_citizenships", "not_in", {"countries": ["ID"]}, "Foreign nationals from KNB developing/partner countries only (Indonesian nationals excluded)", True),
            ("destination_country", "in", {"countries": ["ID"]}, "Full-time study at 47 designated Indonesian universities", True),
            ("degree_level", "in", {"levels": ["bachelors", "masters", "doctoral"]}, "Bachelor's, Master's, or Doctoral degree following BIPA", True),
            ("age_limit", "between", {"max_age": 40, "reference_date": "2026-03-31"}, "UG <= 21, Master's <= 35, Doctoral <= 40 years old", True),
            ("minimum_gpa", "gte", {"min_gpa": 2.75}, "Minimum CGPA 2.75/4.00 (UG/Master's) or 3.00/4.00 (PhD)", True),
            ("language_proficiency", "gte", {"language": "en", "accepted_formats": ["ielts", "toefl_ibt", "toefl_pbt", "toefl", "official_test", "certified_diploma"], "min_scores": {"IELTS": 5.5, "TOEFL_IBT": 53}}, "IELTS >= 5.5, TOEFL iBT >= 53, or prior English-medium degree certificate", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Requires official Indonesian Embassy recommendation letter; strictly excludes applicants holding refugee/stateless status."}, "Embassy recommendation & non-refugee status", True),
        ],
    },
    # 8. Pakistan — HEC / BISP Undergraduate Scholarship (Ehsaas / Benazir Undergraduate)
    {
        "country_code": "PK",
        "title": "HEC / BISP Undergraduate Scholarship (Ehsaas / Benazir Undergraduate Scholarship)",
        "sponsoring_institution": "Higher Education Commission (HEC) Pakistan & Benazir Income Support Programme (BISP)",
        "applicant_type": "first_year",
        "funding_type": "full_funding",
        "provider_type": "government",
        "award_type": "tuition_plus_stipend",
        "covers_international": False,
        "award_currency": "PKR",
        "native_amount_min": 40000.00,
        "native_amount_max": 40000.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "Rs. 40,000 PKR/year living stipend + actual 100% public-sector university semester tuition fee",
        "eligibility_summary": "Pakistani federal need-cum-merit undergraduate scholarship covering actual public university tuition plus Rs. 40,000/yr stipend for Pakistani citizens newly admitted on merit (50% seats reserved for women; excludes evening, distance, self-finance, and 5th-sem lateral tracks).",
        "covers_tuition": True,
        "covers_fees": True,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": False,
        "funding_duration_years": 4.0,
        "max_funding_periods": 8,
        "is_renewable": True,
        "renewal_conditions": "Sustained satisfactory semester progression across 4–5 year public university BS degree.",
        "academic_year": "2026-2027",
        "application_deadline_date": None,
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": True,
        "eligible_citizenships": ["PK"],
        "eligible_destination_countries": ["PK"],
        "degree_levels": ["bachelors"],
        "is_guaranteed_statutory": False,
        "source_name": "HEC Pakistan — Benazir / Ehsaas Undergraduate Scholarship",
        "source_url": "https://www.hec.gov.pk/english/scholarshipsgrants/Ehsaas/Pages/default.aspx",
        "source_type": "government_portal",
        "source_version": "hec-bisp-ug-official",
        "claim_provenance": _build_batch3_claim_provenance(
            source_url="https://www.hec.gov.pk/english/scholarshipsgrants/Ehsaas/Pages/default.aspx",
            source_type="government_portal",
            notes={
                "award_amount": "Verified on official hec.gov.pk Financial-Support page: Rs. 40,000/yr PKR stipend + actual public university tuition fee.",
            },
        ),
        "rules": [
            ("citizenship", "in", {"countries": ["PK"]}, "Pakistani citizen", True),
            ("destination_country", "in", {"countries": ["PK"]}, "Regular morning merit program at a public-sector HEC-recognized Pakistani university", True),
            ("degree_level", "in", {"levels": ["bachelors"]}, "4-year or 5-year Undergraduate BS program", True),
            ("applicant_type", "in", {"types": ["first_year"]}, "Newly admitted 1st-year merit student (self-finance/evening/distance/5th-sem transfers excluded)", True),
            ("financial_need_level", "in", {"levels": ["high", "moderate"]}, "Verified household financial need (HEC/BISP threshold; 50% reserved for female students)", True),
        ],
    },
    # 9. Bangladesh — UGC PhD Scholarship (2026–2027, University Grants Commission)
    {
        "country_code": "BD",
        "title": "UGC PhD Scholarship (2026–2027, University Grants Commission of Bangladesh)",
        "sponsoring_institution": "University Grants Commission of Bangladesh (UGC)",
        "applicant_type": "all",
        "funding_type": "living_stipend",
        "provider_type": "government",
        "award_type": "fellowship",
        "covers_international": False,
        "award_currency": "BDT",
        "native_amount_min": None,
        "native_amount_max": None,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "National UGC doctoral fellowship disbursed in BDT under UGC Bangladesh rules (exact 2026–2027 Taka schedule unpublished in Oct 31 extension circular)",
        "eligibility_summary": "Statutory Bangladeshi national doctoral fellowship for full-time university teachers and UGC-approved PhD researchers enrolled in Bangladeshi universities (2026–2027 call extended to Nov 15, 2026 — now closed).",
        "covers_tuition": False,
        "covers_fees": False,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": False,
        "funding_duration_years": 3.0,
        "max_funding_periods": 3,
        "is_renewable": True,
        "renewal_conditions": "Annual doctoral progress certification submitted through host Bangladeshi public university Registrar to UGC Research Support & Publication Division.",
        "academic_year": "2026-2027",
        "application_deadline_date": date(2026, 11, 15),
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": False,
        "eligible_citizenships": ["BD"],
        "eligible_destination_countries": ["BD"],
        "degree_levels": ["doctoral"],
        "is_guaranteed_statutory": False,
        "source_name": "University Grants Commission of Bangladesh (UGC) Circular",
        "source_url": "https://ugc.gov.bd/storage/news/202610/20261031_WT7qwIGaGd30VlHEuuc9.pdf",
        "source_type": "government_portal",
        "source_version": "ugc-phd-2026-2027-ext",
        "claim_provenance": _build_batch3_claim_provenance(
            source_url="https://ugc.gov.bd/storage/news/202610/20261031_WT7qwIGaGd30VlHEuuc9.pdf",
            source_type="government_portal",
            deadline_expires_iso="2026-11-15T23:59:59+06:00",
            notes={
                "award_amount": "National BDT doctoral fellowship confirmed; numeric Taka table unpublished in Oct 31, 2026 circular so kept null.",
                "deadlines": "Extended deadline November 15, 2026 confirmed in UGC notice #37.01.0000.072.25.002.26.208 (now closed).",
            },
        ),
        "rules": [
            ("citizenship", "in", {"countries": ["BD"]}, "Bangladeshi citizen", True),
            ("destination_country", "in", {"countries": ["BD"]}, "Recognized Bangladeshi university PhD program", True),
            ("degree_level", "in", {"levels": ["doctoral"]}, "Full-time Doctoral (PhD) research degree", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Eligible applicant serving as Bangladeshi university teacher or approved full-time doctoral researcher with departmental forwarding."}, "Bangladeshi university teacher / PhD forwarding", True),
        ],
    },
    # 10. Vietnam — VNU Hanoi Institutional & Partner Scholarships (Vingroup / KBSV / Nguyễn Trường Tộ)
    {
        "country_code": "VN",
        "title": "VNU Hanoi Institutional & Partner Scholarships (Vingroup / KBSV / Nguyễn Trường Tộ — ĐHQGHN)",
        "sponsoring_institution": "Vietnam National University, Hanoi (VNU / ĐHQGHN) & Partner Foundations",
        "applicant_type": "all",
        "funding_type": "merit",
        "provider_type": "university",
        "award_type": "fixed_range",
        "covers_international": False,
        "award_currency": "VND",
        "native_amount_min": 7500000.00,
        "native_amount_max": 25000000.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "7,500,000 VND (Nguyễn Trường Tộ Need & Talent) to 25,000,000 VND/year (Vingroup-ĐHQGHN / KBSV-ĐHQGHN excellence scholarships)",
        "eligibility_summary": "Official Vietnam National University, Hanoi institutional & corporate partner scholarship portfolio awarding 7.5M–25M VND/yr to meritorious and high-need Vietnamese students across VNU member universities.",
        "covers_tuition": True,
        "covers_fees": True,
        "covers_housing": False,
        "covers_meals": False,
        "covers_health_insurance": False,
        "provides_living_stipend": False,
        "covers_travel": False,
        "funding_duration_years": 1.0,
        "max_funding_periods": 4,
        "is_renewable": True,
        "renewal_conditions": "Annual or semester selection via VNU Hanoi Student Affairs and Training Department across member colleges.",
        "academic_year": "2026-2027",
        "application_deadline_date": None,
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": False,
        "eligible_citizenships": ["VN"],
        "eligible_destination_countries": ["VN"],
        "degree_levels": ["bachelors", "masters", "doctoral"],
        "is_guaranteed_statutory": False,
        "source_name": "Vietnam National University, Hanoi (VNU Official)",
        "source_url": "https://vnu.edu.vn/dhqghn-tang-cuong-chinh-sach-hoc-bong-vua-nang-buoc-tai-nang-vua-chap-canh-uoc-mo-post38536.html",
        "source_type": "official_institutional",
        "source_version": "vnu-hanoi-2026-cohorts",
        "claim_provenance": _build_batch3_claim_provenance(
            source_url="https://vnu.edu.vn/dhqghn-tang-cuong-chinh-sach-hoc-bong-vua-nang-buoc-tai-nang-vua-chap-canh-uoc-mo-post38536.html",
            source_type="official_institutional",
            notes={
                "award_amount": "Verified directly across VNU Hanoi announcements: 7,500,000 VND (Nguyễn Trường Tộ) – 25,000,000 VND (Vingroup / KBSV) per academic year.",
            },
        ),
        "rules": [
            ("citizenship", "in", {"countries": ["VN"]}, "Vietnamese national enrolled at a VNU Hanoi member university", True),
            ("destination_country", "in", {"countries": ["VN"]}, "Study at Vietnam National University, Hanoi (ĐHQGHN)", True),
            ("degree_level", "in", {"levels": ["bachelors", "masters", "doctoral"]}, "Undergraduate or Postgraduate degree at VNU Hanoi", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Official enrollment and academic/financial-need nomination by VNU Hanoi Student Affairs Office (Ban Chính trị và Công tác Học sinh Sinh viên)."}, "VNU Hanoi enrollment & nomination", True),
        ],
    },
    # 11. Philippines — CHED-UniFAST Tertiary Education Subsidy (TES — RA 10931)
    {
        "country_code": "PH",
        "title": "CHED-UniFAST Tertiary Education Subsidy (TES — Republic Act 10931)",
        "sponsoring_institution": "Unified Student Financial Assistance System for Tertiary Education (UniFAST) / CHED, Philippines",
        "applicant_type": "all",
        "funding_type": "need_based",
        "provider_type": "government",
        "award_type": "grant",
        "covers_international": False,
        "award_currency": "PHP",
        "native_amount_min": 20000.00,
        "native_amount_max": 27000.00,
        "award_amount_min_usd": None,
        "award_amount_max_usd": None,
        "max_award_info": "₱20,000 PHP/academic year (SUCs & LUCs) or ₱27,000 PHP/academic year (CHED-recognized Private HEIs; +₱10,000/yr TES-3A allowance for Persons with Disabilities)",
        "eligibility_summary": "Statutory Philippine national higher-education subsidy under Republic Act 10931 granting ₱20,000/yr (public SUCs/LUCs) or ₱27,000/yr (private HEIs) to financially needy Filipino undergraduates (Listahanan / 4Ps priority) without a prior Bachelor's degree.",
        "covers_tuition": True,
        "covers_fees": True,
        "covers_housing": True,
        "covers_meals": True,
        "covers_health_insurance": False,
        "provides_living_stipend": True,
        "covers_travel": False,
        "funding_duration_years": 4.0,
        "max_funding_periods": 4,
        "is_renewable": True,
        "renewal_conditions": "Continued enrollment without exceeding statutory Maximum Residency Rule under RA 10931 & verified TES-1/TES-2 roster validation.",
        "academic_year": "2026-2027",
        "application_deadline_date": None,
        "is_deadline_rolling": False,
        "min_gpa_4": None,
        "requires_financial_need": True,
        "eligible_citizenships": ["PH"],
        "eligible_destination_countries": ["PH"],
        "degree_levels": ["bachelors"],
        "is_guaranteed_statutory": False,
        "source_name": "CHED-UniFAST Official TES Portal (RA 10931)",
        "source_url": "https://unifast.gov.ph/tes.html",
        "source_type": "government_portal",
        "source_version": "ra10931-tes-fy2025-2026",
        "claim_provenance": _build_batch3_claim_provenance(
            source_url="https://unifast.gov.ph/tes.html",
            source_type="government_portal",
            notes={
                "award_amount": "Verified directly in CHED-UniFAST TES Portal & JMC 2025 PDF: ₱20,000/yr SUC/LUC & ₱27,000/yr Private HEI (+ ₱10,000/yr TES-3A PWD supplement).",
            },
        ),
        "rules": [
            ("citizenship", "in", {"countries": ["PH"]}, "Filipino citizen", True),
            ("destination_country", "in", {"countries": ["PH"]}, "CHED-recognized SUC, LUC, or Private HEI in the Philippines", True),
            ("degree_level", "in", {"levels": ["bachelors"]}, "First undergraduate Bachelor's / Tech-Voc tertiary degree", True),
            ("financial_need_level", "in", {"levels": ["high", "moderate"]}, "DSWD Listahanan / 4Ps household or qualifying low-income TES-2 threshold", True),
            ("enrollment_context", "custom", {"is_future_condition": True, "condition_text": "Must have no prior Bachelor's degree and be endorsed by host Philippine HEI TES focal person within statutory residency limits."}, "No prior Bachelor's degree & HEI TES endorsement", True),
        ],
    },
]


def seed_phase4_batch3_asia_pacific(db: Session) -> Dict[str, int]:
    """
    Idempotently seed all 11 Batch 3 Asia & Southeast Asia verified scholarship programs
    and ensure all referenced Asian country codes (incl. ID = Indonesia) exist.
    """
    _ensure_batch3_countries(db)

    created = 0
    updated = 0
    rules_created = 0

    for item in BATCH3_ASIA_PACIFIC_SCHOLARSHIPS:
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
            "verified_at": BATCH3_VERIFIED_AT,
            "verification_expires_at": BATCH3_ELIG_EXPIRES_AT,
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
        "batch3_created": created,
        "batch3_updated": updated,
        "batch3_rules_created": rules_created,
    }
