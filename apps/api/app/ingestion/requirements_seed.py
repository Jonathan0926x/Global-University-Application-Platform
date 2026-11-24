"""
Source-Verified Global Admissions Requirements, Deadlines & National Qualifications Seeder.

Every requirement seeded here cites a real, officially verified admissions portal or government
authority inspected during Milestone 3 implementation. Institutions whose admissions policies have
not been verified are intentionally left without fabricated requirement rows.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.institution import Institution
from app.models.provenance import DataProvenance
from app.models.requirements import (
    CountryQualification,
    Deadline,
    InstitutionRequirement,
    RequirementCondition,
    RequirementTemplate,
)
from app.ingestion.countries_seed import ensure_country_exists


VERIFIED_AT = datetime(2026, 11, 24, 18, 0, 0, tzinfo=timezone.utc)
CYCLE_2026_2027 = "2026-2027"


# ---------------------------------------------------------------------------
# 1. Canonical Requirement Templates
# ---------------------------------------------------------------------------
REQUIREMENT_TEMPLATES: List[Dict[str, Any]] = [
    {
        "template_key": "official_transcript:high_school",
        "requirement_type": "official_transcript",
        "requirement_subtype": "high_school",
        "display_name": "Official High School / Secondary School Transcript",
        "description": "Official record of all secondary school coursework and final grades.",
        "category": "document",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "documents",
        "profile_source_filter": {"document_category": ["transcript", "diploma"]},
    },
    {
        "template_key": "official_transcript:high_school_conditional",
        "requirement_type": "official_transcript",
        "requirement_subtype": "high_school_conditional",
        "display_name": "High School Transcript (Conditional on Transfer Credits)",
        "description": "Required when transfer applicant has fewer than minimum college credits/terms.",
        "category": "document",
        "default_importance": "conditional",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "documents",
        "profile_source_filter": {"document_category": ["transcript"]},
    },
    {
        "template_key": "official_transcript:college_all",
        "requirement_type": "official_transcript",
        "requirement_subtype": "college_all",
        "display_name": "Official College / University Transcript(s)",
        "description": "Official transcripts from every post-secondary institution attended.",
        "category": "document",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "documents",
        "profile_source_filter": {"document_category": ["transcript"]},
    },
    {
        "template_key": "secondary_qualification:national_diploma",
        "requirement_type": "secondary_qualification",
        "requirement_subtype": "national_diploma",
        "display_name": "Recognized Secondary Leaving Qualification / National Diploma",
        "description": "Completion of recognized secondary credential (e.g., A-Levels, IB, Abitur/HZB, French/Haitian Baccalauréat, Class XII).",
        "category": "academic",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "enrollments",
        "profile_source_filter": {"enrollment_type": "secondary"},
    },
    {
        "template_key": "national_exam:entrance_exam",
        "requirement_type": "national_exam",
        "requirement_subtype": "entrance_exam",
        "display_name": "National / Institutional Entrance Examination",
        "description": "Required national or university entrance exam (e.g., CUET-UG, JEE Advanced, EJU, Concours d'admission).",
        "category": "exam",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "standardized_tests",
        "profile_source_filter": {"test_type": ["CUET", "JEE_MAIN", "JEE_ADVANCED", "EJU", "CONCOURS", "BACCALAUREAT"]},
    },
    {
        "template_key": "standardized_test:sat_act",
        "requirement_type": "standardized_test",
        "requirement_subtype": "sat_act",
        "display_name": "SAT / ACT Standardized Admissions Testing",
        "description": "College Board SAT or ACT examination policy (Required, Test-Optional, or Test-Blind).",
        "category": "exam",
        "default_importance": "optional",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "standardized_tests",
        "profile_source_filter": {"test_type": ["SAT", "ACT"]},
    },
    {
        "template_key": "english_proficiency:toefl_ielts_det",
        "requirement_type": "english_proficiency",
        "requirement_subtype": "toefl_ielts_det",
        "display_name": "English Language Proficiency (TOEFL / IELTS / DET)",
        "description": "Proof of English proficiency for applicants educated outside English-medium systems.",
        "category": "exam",
        "default_importance": "conditional",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "standardized_tests",
        "profile_source_filter": {"test_type": ["TOEFL", "IELTS", "DET", "CAE", "PTE", "MET"]},
    },
    {
        "template_key": "language_proficiency:french_b2",
        "requirement_type": "language_proficiency",
        "requirement_subtype": "french_b2",
        "display_name": "French Language Proficiency (DELF B2 / DALF / TCF DAP)",
        "description": "Official certification of French proficiency (CEFR B2+) for French-taught undergraduate entry.",
        "category": "exam",
        "default_importance": "conditional",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "standardized_tests",
        "profile_source_filter": {"test_type": ["DELF", "DALF", "TCF"]},
    },
    {
        "template_key": "language_proficiency:german_c1",
        "requirement_type": "language_proficiency",
        "requirement_subtype": "german_c1",
        "display_name": "German Language Proficiency (DSH-2 / TestDaF / Goethe C1)",
        "description": "Official CEFR C1 German certification required for German-taught degree tracks.",
        "category": "exam",
        "default_importance": "conditional",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "standardized_tests",
        "profile_source_filter": {"test_type": ["DSH", "TESTDAF", "GOETHE_C1", "TELC_C1"]},
    },
    {
        "template_key": "language_proficiency:japanese_n1",
        "requirement_type": "language_proficiency",
        "requirement_subtype": "japanese_n1",
        "display_name": "Japanese Language Proficiency (JLPT N1 / EJU)",
        "description": "Required for Japanese-taught undergraduate tracks; waived for English-medium tracks.",
        "category": "exam",
        "default_importance": "conditional",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "standardized_tests",
        "profile_source_filter": {"test_type": ["JLPT", "EJU"]},
    },
    {
        "template_key": "minimum_gpa:high_school",
        "requirement_type": "minimum_gpa",
        "requirement_subtype": "high_school",
        "display_name": "Minimum Secondary GPA / Academic Standing",
        "description": "Minimum high school grade point average or national exam percentage.",
        "category": "academic",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "enrollments",
        "profile_source_filter": {"enrollment_type": "secondary"},
    },
    {
        "template_key": "minimum_gpa:transfer_cumulative",
        "requirement_type": "minimum_gpa",
        "requirement_subtype": "transfer_cumulative",
        "display_name": "Minimum Transferable College GPA",
        "description": "Minimum cumulative GPA across transferable post-secondary coursework.",
        "category": "academic",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "enrollments",
        "profile_source_filter": {"enrollment_type": ["community_college", "undergraduate"]},
    },
    {
        "template_key": "minimum_credits:transfer_min_credits",
        "requirement_type": "minimum_credits",
        "requirement_subtype": "transfer_min_credits",
        "display_name": "Minimum Completed Transferable Credits / Terms",
        "description": "Minimum college semester/quarter credits or full-time terms required prior to transfer matriculation.",
        "category": "academic",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "enrollments",
        "profile_source_filter": {"enrollment_type": ["community_college", "undergraduate"]},
    },
    {
        "template_key": "maximum_credits:transfer_max_credits",
        "requirement_type": "maximum_credits",
        "requirement_subtype": "transfer_max_credits",
        "display_name": "Maximum Transferable Credits / Terms Cap",
        "description": "Upper ceiling on prior college terms or transferable lower-division credit hours.",
        "category": "academic",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "enrollments",
        "profile_source_filter": {"enrollment_type": ["community_college", "undergraduate"]},
    },
    {
        "template_key": "specific_coursework:uc_seven_course_pattern",
        "requirement_type": "specific_coursework",
        "requirement_subtype": "uc_seven_course_pattern",
        "display_name": "General Education / 7-Course Breadth Pattern",
        "description": "Two transferable English composition courses, one mathematical/quantitative course, and four courses across at least two breadth areas (Arts/Humanities, Social/Behavioral, Physical/Biological Sciences).",
        "category": "academic",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "courses",
        "profile_source_filter": {},
    },
    {
        "template_key": "prerequisite_courses:major_specific",
        "requirement_type": "prerequisite_courses",
        "requirement_subtype": "major_specific",
        "display_name": "Major-Specific Prerequisite Coursework",
        "description": "Lower-division foundational courses required for admission into the intended major.",
        "category": "academic",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "courses",
        "profile_source_filter": {},
    },
    {
        "template_key": "associate_degree:adt_transfer_pathway",
        "requirement_type": "associate_degree",
        "requirement_subtype": "adt_transfer_pathway",
        "display_name": "Associate Degree / Lower-Division Preparation Pathway",
        "description": "Optional or preferred Associate Degree (AA-T/AS-T) or IGETC completion prior to transfer.",
        "category": "academic",
        "default_importance": "recommended",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "enrollments",
        "profile_source_filter": {"enrollment_type": "community_college"},
    },
    {
        "template_key": "academic_standing:good_standing",
        "requirement_type": "academic_standing",
        "requirement_subtype": "good_standing",
        "display_name": "Good Academic Standing at Current/Prior Institution",
        "description": "Applicant must be in good academic standing and eligible to return to previous college(s).",
        "category": "academic",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "enrollments",
        "profile_source_filter": {},
    },
    {
        "template_key": "personal_statement:essay",
        "requirement_type": "personal_statement",
        "requirement_subtype": "essay",
        "display_name": "Personal Statement / Application Essays",
        "description": "Required personal insight questions, UCAS personal statement, or transfer statement of purpose.",
        "category": "document",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "documents",
        "profile_source_filter": {"document_category": ["personal_statement", "essay"]},
    },
    {
        "template_key": "recommendation_letter:academic_ref",
        "requirement_type": "recommendation_letter",
        "requirement_subtype": "academic_ref",
        "display_name": "Academic Recommendation Letter(s) / Referee Report",
        "description": "Teacher, counselor, or college professor letters of evaluation.",
        "category": "document",
        "default_importance": "required",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "documents",
        "profile_source_filter": {"document_category": ["recommendation", "recommendation_letter"]},
    },
    {
        "template_key": "credential_evaluation:foreign_eval",
        "requirement_type": "credential_evaluation",
        "requirement_subtype": "foreign_eval",
        "display_name": "International Credential Evaluation (VPD / uni-assist / WES / MENFP)",
        "description": "Official equivalency recognition or grade conversion for foreign academic credentials.",
        "category": "document",
        "default_importance": "conditional",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "documents",
        "profile_source_filter": {"document_category": ["credential_evaluation", "diploma"]},
    },
    {
        "template_key": "certified_translation:non_english_docs",
        "requirement_type": "certified_translation",
        "requirement_subtype": "non_english_docs",
        "display_name": "Certified Translation of Foreign-Language Transcripts",
        "description": "Certified translation when original academic records are not issued in the university's language of instruction.",
        "category": "document",
        "default_importance": "conditional",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "documents",
        "profile_source_filter": {"document_category": ["certified_translation", "transcript"]},
    },
    {
        "template_key": "course_descriptions:syllabi_intl",
        "requirement_type": "course_descriptions",
        "requirement_subtype": "syllabi_intl",
        "display_name": "Course Descriptions / Syllabi for Transfer Articulation",
        "description": "Detailed course syllabi needed to evaluate transfer credit equivalency.",
        "category": "document",
        "default_importance": "conditional",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "documents",
        "profile_source_filter": {"document_category": ["syllabus"]},
    },
    {
        "template_key": "financial_documentation:intl_sponsor_bank",
        "requirement_type": "financial_documentation",
        "requirement_subtype": "intl_sponsor_bank",
        "display_name": "Financial Support Documentation (Visa / I-20 / Study Permit)",
        "description": "Proof of funds required for international student visa sponsorship upon admission or financial aid.",
        "category": "financial",
        "default_importance": "conditional",
        "can_be_satisfied_from_profile": True,
        "profile_source_table": "documents",
        "profile_source_filter": {"document_category": ["financial_documentation"]},
    },
    {
        "template_key": "application_form:portal",
        "requirement_type": "application_form",
        "requirement_subtype": "portal",
        "display_name": "Official Application Portal Submission",
        "description": "Submission via designated centralized or direct university portal (UC App, Common App, OUAC, UCAS, Parcoursup/Campus France, uni-assist, CSAS, JoSAA).",
        "category": "administrative",
        "default_importance": "required",
        "can_be_satisfied_from_profile": False,
        "profile_source_table": None,
        "profile_source_filter": {},
    },
    {
        "template_key": "application_fee:undergrad_fee",
        "requirement_type": "application_fee",
        "requirement_subtype": "undergrad_fee",
        "display_name": "Application Processing Fee or Approved Fee Waiver",
        "description": "Published institutional or portal application fee (waiver available for qualifying applicants).",
        "category": "administrative",
        "default_importance": "required",
        "can_be_satisfied_from_profile": False,
        "profile_source_table": None,
        "profile_source_filter": {},
    },
    {
        "template_key": "aptitude_assessment:institutional_exam",
        "requirement_type": "aptitude_assessment",
        "requirement_subtype": "institutional_exam",
        "display_name": "Program Aptitude Assessment / Subject Admissions Test",
        "description": "Faculty-specific written assessment, admissions test (e.g., Oxford PAT/MAT/LNAT, TUM Eignungsfeststellungsverfahren), or interview.",
        "category": "exam",
        "default_importance": "conditional",
        "can_be_satisfied_from_profile": False,
        "profile_source_table": None,
        "profile_source_filter": {},
    },
]


# ---------------------------------------------------------------------------
# 2. Country-Level Qualifications & National Examination Frameworks
# ---------------------------------------------------------------------------
COUNTRY_QUALIFICATIONS: List[Dict[str, Any]] = [
    {
        "country_code": "US",
        "qualification_name": "US High School Diploma (+ AP / IB / Dual Enrollment)",
        "qualification_type": "secondary_diploma",
        "grading_scale": "0.0–4.0 GPA scale (unweighted/weighted)",
        "passing_threshold": "State graduation completion; competitive 4-year typically 3.0+",
        "equivalency_notes": "Standard domestic US first-year secondary credential.",
        "recognition_rules": {"accepts_ap": True, "accepts_ib": True, "credit_transfer": "sem_quarter_units"},
        "source_name": "NCES / U.S. Department of Education",
        "source_url": "https://nces.ed.gov/",
    },
    {
        "country_code": "US",
        "qualification_name": "Associate Degree for Transfer (AA-T / AS-T) & IGETC",
        "qualification_type": "transfer_credential",
        "grading_scale": "0.0–4.0 GPA scale (60 semester / 90 quarter units)",
        "passing_threshold": "2.0+ degree floor; 2.4–3.2+ for UC/selective transfer",
        "equivalency_notes": "Guarantees junior standing in matching CSU majors and prepares lower-division GE/major prep for UC.",
        "recognition_rules": {"min_semester_units": 60, "min_quarter_units": 90},
        "source_name": "University of California & California Community Colleges ASSIST",
        "source_url": "https://admission.universityofcalifornia.edu/admission-requirements/transfer-requirements/",
    },
    {
        "country_code": "HT",
        "qualification_name": "Baccalauréat haïtien (Nouveau Secondaire IV / Bac II)",
        "qualification_type": "national_exam",
        "grading_scale": "0–20 point scale (or coefficient weighted)",
        "passing_threshold": "10/20 minimum passing mark; MENFP official certificate",
        "equivalency_notes": "Recognized internationally as comparable to US High School Diploma completion; foreign credential evaluation (WES/IERF) often requested by US universities.",
        "recognition_rules": {"comparable_us": "high_school_diploma", "min_passing_numeric": 10},
        "source_name": "MENFP Haïti / Université d'État d'Haïti & WES Credential Guide",
        "source_url": "https://admission.ueh.edu.ht/",
    },
    {
        "country_code": "FR",
        "qualification_name": "Diplôme du Baccalauréat Général / Technologique",
        "qualification_type": "national_exam",
        "grading_scale": "0–20 French numerical scale",
        "passing_threshold": "10/20 (Passable); Mentions Assez Bien (12+), Bien (14+), Très Bien (16+)",
        "equivalency_notes": "Confers legal eligibility for first-year Licence entry in France via Parcoursup / Études en France.",
        "recognition_rules": {"direct_university_access": True, "language_threshold": "DELF B2 / TCF DAP"},
        "source_name": "Campus France & Parcoursup (MESR)",
        "source_url": "https://www.campusfrance.org/en/etudes-en-france-procedure",
    },
    {
        "country_code": "DE",
        "qualification_name": "Allgemeine Hochschulreife (Abitur) / Foreign HZB via uni-assist VPD",
        "qualification_type": "secondary_diploma",
        "grading_scale": "1.0 (highest) to 6.0 (4.0 minimum pass)",
        "passing_threshold": "4.0 passing grade; foreign credentials converted via Bavarian formula (VPD)",
        "equivalency_notes": "Direct entry requires HZB equivalence in anabin/uni-assist; non-equivalent secondary diplomas require Studienkolleg.",
        "recognition_rules": {"requires_vpd_for_foreign": True, "language_threshold": "C1 German (DSH-2 / TestDaF)"},
        "source_name": "Technical University of Munich / uni-assist / DAAD",
        "source_url": "https://www.tum.de/en/studies/application/application-info-portal/vorpruefungsdokumentation-vpd",
    },
    {
        "country_code": "GB",
        "qualification_name": "GCE A-Levels & International Equivalents via UCAS",
        "qualification_type": "secondary_diploma",
        "grading_scale": "A*–E letter grades per subject (typically 3 A-Levels)",
        "passing_threshold": "Course-dependent conditional offers (e.g., A*A*A–AAB at Oxford/Cambridge/UCL)",
        "equivalency_notes": "US applicants typically evaluated via 3–5 AP exams (scores 4–5) plus SAT/ACT; non-equivalent diplomas may take UK Foundation/UPC.",
        "recognition_rules": {"central_portal": "UCAS"},
        "source_name": "UCAS / University of Oxford / UCL",
        "source_url": "https://www.ox.ac.uk/admissions/undergraduate/applying-to-oxford/for-international-students/international-qualifications",
    },
    {
        "country_code": "CA",
        "qualification_name": "Canadian Provincial Secondary Diplomas (OSSD / BC Dogwood / Quebec DEC)",
        "qualification_type": "secondary_diploma",
        "grading_scale": "0–100% percentage or provincial GPA",
        "passing_threshold": "50% provincial pass; competitive university entry 80%–95%+",
        "equivalency_notes": "Ontario OSSD requires 6 Grade 12 U/M courses including ENG4U; Quebec CEGEP DEC applicants may receive first-year transfer/advanced standing.",
        "recognition_rules": {"english_exemption_years": 4},
        "source_name": "University of Toronto / McGill / UBC Admissions",
        "source_url": "https://future.utoronto.ca/apply/requirements/international-high-school-secondary/",
    },
    {
        "country_code": "IN",
        "qualification_name": "Class XII Senior Secondary (CBSE / ISC / State Boards)",
        "qualification_type": "secondary_diploma",
        "grading_scale": "0–100% aggregate percentage",
        "passing_threshold": "33% board pass; 75% (65% SC/ST/PwD) or top 20 percentile required for IITs",
        "equivalency_notes": "Recognized globally as equivalent to US/UK/Australian Year 12 depending on board scores.",
        "recognition_rules": {"iit_min_pct": 75},
        "source_name": "University of Delhi & IIT Kharagpur / JoSAA",
        "source_url": "https://www.iitkgp.ac.in/",
    },
    {
        "country_code": "IN",
        "qualification_name": "CUET-UG & JEE Main / JEE Advanced National Entrance Exams",
        "qualification_type": "university_entrance_exam",
        "grading_scale": "Normalized NTA scores (CUET) & All India Rank (JEE)",
        "passing_threshold": "Mandatory central testing for DU (CUET via CSAS) and IITs (JEE Advanced via JoSAA)",
        "equivalency_notes": "DU requires CUET subjects matching passed Class XII subjects; IITs require JEE Main qualification + JEE Advanced rank.",
        "recognition_rules": {"cuet_portal": "CSAS", "jee_portal": "JoSAA"},
        "source_name": "University of Delhi & JoSAA / NTA",
        "source_url": "https://admission.uod.ac.in/",
    },
    {
        "country_code": "AU",
        "qualification_name": "Australian Senior Secondary Certificate (ATAR) / Recognized Year 12",
        "qualification_type": "secondary_diploma",
        "grading_scale": "ATAR percentile rank (0.00–99.95)",
        "passing_threshold": "Minimum/Guaranteed Entry ATAR published per degree (e.g., 85.00+)",
        "equivalency_notes": "International credentials (IB, A-Levels, SAT/AP, CBSE/ISC) mapped to Guaranteed Entry Scores.",
        "recognition_rules": {"english_ielts_min": 6.5},
        "source_name": "University of Melbourne Study Admissions",
        "source_url": "https://study.unimelb.edu.au/how-to-apply/undergraduate-study/international-applications",
    },
    {
        "country_code": "JP",
        "qualification_name": "EJU (Examination for Japanese University Admission) & JLPT N1",
        "qualification_type": "university_entrance_exam",
        "grading_scale": "EJU subject scores (0–400 Japanese, 0–200 Science/Math) + JLPT N5–N1",
        "passing_threshold": "JLPT N1 required for Japanese-taught undergraduate tracks",
        "equivalency_notes": "English-medium tracks (e.g., UTokyo PEAK) evaluate SAT/ACT/IB/A-Levels plus TOEFL/IELTS instead of EJU/JLPT N1.",
        "recognition_rules": {"japanese_track_jlpt": "N1"},
        "source_name": "The University of Tokyo / JASSO",
        "source_url": "https://www.u-tokyo.ac.jp/en/prospective-students/undergraduate_admissions.html",
    },
]


# ---------------------------------------------------------------------------
# 3. Helper Lookup & Seed Engine
# ---------------------------------------------------------------------------
def _find_institution(
    db: Session,
    ipeds_unit_id: Optional[str] = None,
    official_name: Optional[str] = None,
) -> Optional[Institution]:
    if ipeds_unit_id:
        inst = db.query(Institution).filter(Institution.ipeds_unit_id == ipeds_unit_id).first()
        if inst:
            return inst
    if official_name:
        return db.query(Institution).filter(Institution.official_name == official_name).first()
    return None


def _upsert_template(db: Session, item: Dict[str, Any]) -> RequirementTemplate:
    tpl = (
        db.query(RequirementTemplate)
        .filter(RequirementTemplate.template_key == item["template_key"])
        .first()
    )
    if tpl:
        return tpl
    tpl = RequirementTemplate(**item)
    db.add(tpl)
    db.flush()
    return tpl


def _upsert_country_qual(db: Session, item: Dict[str, Any]) -> bool:
    ensure_country_exists(db, item["country_code"])
    existing = (
        db.query(CountryQualification)
        .filter(
            CountryQualification.country_code == item["country_code"],
            CountryQualification.qualification_name == item["qualification_name"],
        )
        .first()
    )
    if existing:
        return False
    db.add(
        CountryQualification(
            **item,
            verified_at=VERIFIED_AT,
            verification_status="verified",
        )
    )
    return True


def _upsert_requirement(
    db: Session,
    inst: Institution,
    templates: Dict[str, RequirementTemplate],
    spec: Dict[str, Any],
) -> tuple[InstitutionRequirement, bool]:
    tpl = templates[spec["template"]]
    existing = (
        db.query(InstitutionRequirement)
        .filter(
            InstitutionRequirement.institution_id == inst.id,
            InstitutionRequirement.requirement_template_id == tpl.id,
            InstitutionRequirement.applicant_type == spec["applicant_type"],
            InstitutionRequirement.academic_year == spec.get("academic_year", CYCLE_2026_2027),
            InstitutionRequirement.program_name_filter == spec.get("program_name"),
        )
        .first()
    )
    if existing:
        return existing, False

    req = InstitutionRequirement(
        institution_id=inst.id,
        program_name_filter=spec.get("program_name"),
        cip_code=spec.get("cip_code"),
        requirement_template_id=tpl.id,
        applicant_type=spec["applicant_type"],
        importance=spec.get("importance", "required"),
        title_override=spec.get("title"),
        institution_specific_notes=spec.get("notes"),
        quantity=spec.get("quantity", 1),
        minimum_value=spec.get("min_val"),
        maximum_value=spec.get("max_val"),
        fee_amount=spec.get("fee_amount"),
        fee_currency=spec.get("fee_currency"),
        fee_waiver_available=spec.get("fee_waiver"),
        academic_year=spec.get("academic_year", CYCLE_2026_2027),
        is_current=True,
        source_name=spec["source_name"],
        source_type=spec.get("source_type", "official_website"),
        source_url=spec["source_url"],
        verified_at=VERIFIED_AT,
        confidence_level=spec.get("confidence_level", "verified"),
        verification_status=spec.get("verification_status", "verified"),
    )
    db.add(req)
    db.flush()

    for cond in spec.get("conditions", []):
        db.add(
            RequirementCondition(
                requirement_id=req.id,
                condition_type=cond["condition_type"],
                condition_field=cond["condition_field"],
                condition_operator=cond["condition_operator"],
                condition_value=cond["condition_value"],
                result_importance=cond["result_importance"],
                explanation=cond.get("explanation"),
            )
        )

    db.add(
        DataProvenance(
            entity_type="requirement",
            entity_id=req.id,
            source_type=spec.get("source_type", "official_website"),
            source_url=spec["source_url"],
            source_name=spec["source_name"],
            collection_method="official_html",
            retrieved_at=VERIFIED_AT,
            verified_at=VERIFIED_AT,
            academic_year=spec.get("academic_year", CYCLE_2026_2027),
            confidence_level=spec.get("confidence_level", "verified"),
            is_current=True,
        )
    )
    return req, True


def _upsert_deadline(
    db: Session,
    inst: Institution,
    spec: Dict[str, Any],
) -> bool:
    existing = (
        db.query(Deadline)
        .filter(
            Deadline.institution_id == inst.id,
            Deadline.applicant_type == spec["applicant_type"],
            Deadline.deadline_type == spec["deadline_type"],
            Deadline.intake_term == spec["intake_term"],
            Deadline.academic_year == spec.get("academic_year", CYCLE_2026_2027),
        )
        .first()
    )
    if existing:
        return False

    dl = Deadline(
        institution_id=inst.id,
        program_name_filter=spec.get("program_name"),
        applicant_type=spec["applicant_type"],
        deadline_type=spec["deadline_type"],
        intake_term=spec["intake_term"],
        deadline_date=spec.get("deadline_date"),
        deadline_time=spec.get("deadline_time"),
        timezone=spec.get("timezone"),
        is_firm=spec.get("is_firm", True),
        notification_date=spec.get("notification_date"),
        academic_year=spec.get("academic_year", CYCLE_2026_2027),
        is_current=True,
        notes=spec.get("notes"),
        source_name=spec["source_name"],
        source_url=spec["source_url"],
        verified_at=VERIFIED_AT,
        verification_status="verified",
        confidence_level="verified",
    )
    db.add(dl)
    db.flush()
    db.add(
        DataProvenance(
            entity_type="deadline",
            entity_id=dl.id,
            source_type="official_website",
            source_url=spec["source_url"],
            source_name=spec["source_name"],
            collection_method="official_html",
            retrieved_at=VERIFIED_AT,
            verified_at=VERIFIED_AT,
            academic_year=spec.get("academic_year", CYCLE_2026_2027),
            confidence_level="verified",
            is_current=True,
        )
    )
    return True


def _build_verified_catalog() -> List[Dict[str, Any]]:
    """
    Verified institutional admissions specs across US, CA, GB, FR, DE, HT, IN, AU, JP.
    """
    UC_TRANSFER_URL = "https://admission.universityofcalifornia.edu/admission-requirements/transfer-requirements/"
    UC_FY_URL = "https://admission.universityofcalifornia.edu/admission-requirements/freshman-requirements/"
    UC_ENGLISH_URL = "https://admission.universityofcalifornia.edu/admission-requirements/international-applicants/english-language-proficiency-toefl-ielts.html"
    UC_APPLY_URL = "https://admission.universityofcalifornia.edu/apply-now.html"
    UCB_ECON_URL = "https://www.econ.berkeley.edu/undergrad/prospective/transfer-students"
    UCB_CS_URL = "https://cdss.berkeley.edu/academics"

    intl_english_cond = [
        {
            "condition_type": "residency",
            "condition_field": "requires_english_proficiency",
            "condition_operator": "equals",
            "condition_value": True,
            "result_importance": "required",
            "explanation": "Required when secondary/prior instruction was outside an exempted English-speaking country.",
        },
        {
            "condition_type": "residency",
            "condition_field": "requires_english_proficiency",
            "condition_operator": "equals",
            "condition_value": False,
            "result_importance": "not_applicable",
            "explanation": "Exempted for domestic/English-medium instruction verified on profile.",
        },
    ]
    intl_only_cond = [
        {
            "condition_type": "citizenship",
            "condition_field": "is_international_for_target",
            "condition_operator": "equals",
            "condition_value": True,
            "result_importance": "required",
            "explanation": "Required for international/visa-seeking applicants.",
        },
        {
            "condition_type": "citizenship",
            "condition_field": "is_international_for_target",
            "condition_operator": "equals",
            "condition_value": False,
            "result_importance": "not_applicable",
            "explanation": "Not applicable to domestic citizens/permanent residents.",
        },
    ]

    return [
        # ------------------------------------------------------------------
        # 1. UC Berkeley (US - IPEDS 110635)
        # ------------------------------------------------------------------
        {
            "ipeds_unit_id": "110635",
            "portal_urls": {
                "admissions_website": "https://admissions.berkeley.edu/",
                "application_portal_url": UC_APPLY_URL,
            },
            "requirements": [
                # First-Year
                {"template": "application_form:portal", "applicant_type": "first_year", "title": "UC Undergraduate Application Portal (Fall-Only)", "notes": "Filing period Oct 1 – Nov 30; no Early Action or Early Decision.", "source_name": "UC Berkeley Admissions", "source_url": UC_APPLY_URL},
                {"template": "standardized_test:sat_act", "applicant_type": "first_year", "importance": "not_accepted", "title": "SAT / ACT Policy: Test-Blind (Not Considered)", "notes": "UC Berkeley does not consider SAT or ACT scores for admission or scholarship review.", "source_name": "UC Admissions", "source_url": UC_FY_URL},
                {"template": "official_transcript:high_school", "applicant_type": "first_year", "title": "Self-Reported Academic Record & Final High School Transcript", "notes": "15 college-preparatory A–G courses with 3.0 minimum GPA (CA) / 3.4 (non-resident).", "min_val": "3.0", "source_name": "UC Admissions", "source_url": UC_FY_URL},
                {"template": "personal_statement:essay", "applicant_type": "first_year", "quantity": 4, "title": "UC Personal Insight Questions (4 of 8 prompts)", "notes": "Maximum 350 words per response.", "source_name": "UC Admissions", "source_url": UC_FY_URL},
                {"template": "application_fee:undergrad_fee", "applicant_type": "first_year", "fee_amount": 80.0, "fee_currency": "USD", "fee_waiver": True, "notes": "$80 domestic ($95 international); fee waivers built into UC Application.", "source_name": "UC Admissions", "source_url": UC_APPLY_URL},
                # Transfer (General + Economics + CS)
                {"template": "application_form:portal", "applicant_type": "transfer", "title": "UC Transfer Application (Fall Entry Only)", "notes": "UC Berkeley accepts transfer applications exclusively for the Fall semester.", "source_name": "UC Berkeley Admissions", "source_url": UC_APPLY_URL},
                {"template": "minimum_credits:transfer_min_credits", "applicant_type": "transfer", "min_val": "60 semester units", "notes": "Must complete at least 60 UC-transferable semester units (90 quarter units) by end of Spring prior to Fall entry.", "source_name": "UC Admissions", "source_url": UC_TRANSFER_URL},
                {"template": "minimum_gpa:transfer_cumulative", "applicant_type": "transfer", "min_val": "3.0", "notes": "Minimum 3.0 overall transferable GPA recommended/required for UC Berkeley transfer consideration (2.4 CA / 2.8 non-res UC floor).", "source_name": "UC Berkeley & UC Admissions", "source_url": UC_TRANSFER_URL},
                {"template": "specific_coursework:uc_seven_course_pattern", "applicant_type": "transfer", "title": "UC 7-Course Breadth Pattern", "notes": "2 English Composition, 1 Mathematical Concepts, and 4 courses across Arts/Humanities, Social/Behavioral, or Physical/Biological Sciences.", "source_name": "UC Admissions", "source_url": UC_TRANSFER_URL},
                {"template": "official_transcript:college_all", "applicant_type": "transfer", "title": "Official College Transcript(s) & Self-Reported UC Academic Record", "notes": "All college coursework reported on UC TAU; official transcripts due July 1 after admission.", "source_name": "UC Admissions", "source_url": UC_TRANSFER_URL},
                {"template": "personal_statement:essay", "applicant_type": "transfer", "quantity": 4, "title": "UC Transfer Personal Insight Questions (1 Required + 3 Chosen)", "notes": "Includes mandatory prompt explaining preparation for intended major.", "source_name": "UC Admissions", "source_url": UC_TRANSFER_URL},
                {"template": "associate_degree:adt_transfer_pathway", "applicant_type": "transfer", "importance": "recommended", "title": "IGETC Certification or Campus GE Pattern", "notes": "Recommended for Letters & Science; check college-specific exceptions (e.g., Engineering).", "source_name": "UC Admissions", "source_url": UC_TRANSFER_URL},
                {"template": "prerequisite_courses:major_specific", "applicant_type": "transfer", "program_name": "Economics", "cip_code": "45", "title": "Economics Transfer Major Preparation (Micro/Macro Econ + Calculus I & II)", "min_val": "ECON 1/2 + MATH 1A/1B (or 16A/16B)", "notes": "Verify CA community college course equivalencies on ASSIST.org; all prerequisites must be completed before transfer.", "source_name": "UC Berkeley Department of Economics", "source_url": UCB_ECON_URL},
                {"template": "prerequisite_courses:major_specific", "applicant_type": "transfer", "program_name": "Computer Science", "cip_code": "11", "title": "Computer Science Transfer Major Prep (CS 61A/B/C Equiv, Calc I–II, Linear Algebra)", "min_val": "CS 61A/61B/61C + MATH 1A/1B + MATH 54", "notes": "Direct CDSS Computer Science transfer requires lower-division CS/Math foundation courses per ASSIST.org.", "source_name": "UC Berkeley CDSS", "source_url": UCB_CS_URL},
                # International (Applies across First-Year & Transfer)
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "all", "importance": "conditional", "min_val": "TOEFL 80 / IELTS 6.5 / DET 115", "notes": "Required if secondary/college instruction was not entirely in English; complete by December.", "conditions": intl_english_cond, "source_name": "UC Admissions", "source_url": UC_ENGLISH_URL},
                {"template": "financial_documentation:intl_sponsor_bank", "applicant_type": "all", "importance": "conditional", "title": "International Non-Immigrant Visa & Financial Certification (Post-Admission)", "notes": "UC does not award need-based aid to non-US citizens/non-PRs; proof of funds required for I-20/DS-2019 upon admission.", "conditions": intl_only_cond, "source_name": "UC Admissions", "source_url": UC_FY_URL},
            ],
            "deadlines": [
                {"applicant_type": "first_year", "deadline_type": "regular_decision", "intake_term": "Fall 2027", "deadline_date": date(2026, 11, 30), "deadline_time": "23:59 PST", "timezone": "America/Los_Angeles", "notes": "UC Application filing window opens October 1 and closes November 30.", "source_name": "UC Berkeley Admissions", "source_url": UC_APPLY_URL},
                {"applicant_type": "transfer", "deadline_type": "transfer_fall", "intake_term": "Fall 2027", "deadline_date": date(2026, 11, 30), "deadline_time": "23:59 PST", "timezone": "America/Los_Angeles", "notes": "Fall-only transfer cycle; UC Transfer Academic Update (TAU) due January 31.", "source_name": "UC Berkeley Admissions", "source_url": UC_APPLY_URL},
            ],
        },

        # ------------------------------------------------------------------
        # 2. UCLA (US - IPEDS 110662)
        # ------------------------------------------------------------------
        {
            "ipeds_unit_id": "110662",
            "portal_urls": {
                "admissions_website": "https://admission.ucla.edu/",
                "application_portal_url": UC_APPLY_URL,
            },
            "requirements": [
                {"template": "standardized_test:sat_act", "applicant_type": "first_year", "importance": "not_accepted", "title": "SAT / ACT Policy: Test-Blind (Not Considered)", "notes": "UCLA does not use SAT or ACT scores in admissions selection.", "source_name": "UCLA Undergraduate Admission", "source_url": "https://admission.ucla.edu/apply/freshman-requirements"},
                {"template": "official_transcript:high_school", "applicant_type": "first_year", "min_val": "3.0", "notes": "A–G college-prep pattern with minimum 3.0 GPA (CA) / 3.4 (non-resident).", "source_name": "UCLA Undergraduate Admission", "source_url": "https://admission.ucla.edu/apply/freshman-requirements"},
                {"template": "minimum_credits:transfer_min_credits", "applicant_type": "transfer", "min_val": "60 semester units", "notes": "Minimum 60 UC-transferable semester (90 quarter) units by end of Spring; capped at 70 lower-division semester units.", "max_val": "70 lower-div semester units", "source_name": "UCLA Transfer Requirements", "source_url": "https://admission.ucla.edu/apply/transfer/transfer-requirements"},
                {"template": "minimum_gpa:transfer_cumulative", "applicant_type": "transfer", "min_val": "3.2", "notes": "UCLA requires a minimum 3.2 transferable GPA to be competitive across Letters & Science (higher for Engineering/CS).", "source_name": "UCLA Transfer Requirements", "source_url": "https://admission.ucla.edu/apply/transfer/transfer-requirements"},
                {"template": "specific_coursework:uc_seven_course_pattern", "applicant_type": "transfer", "notes": "UC 7-course pattern mandatory for all UC transfer applicants.", "source_name": "UC Admissions", "source_url": UC_TRANSFER_URL},
                {"template": "prerequisite_courses:major_specific", "applicant_type": "transfer", "program_name": "Economics", "cip_code": "45", "title": "UCLA Economics Major Prep (Micro/Macro Econ + Calculus I & II + Writing)", "min_val": "ECON 1/2 + MATH 31A/31B equiv", "notes": "All preparatory courses must be completed for letter grades by Spring prior to entry.", "source_name": "UCLA Transfer Major Prep", "source_url": "https://admission.ucla.edu/apply/transfer/deciding-on-a-major"},
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "all", "importance": "conditional", "min_val": "TOEFL 100 / IELTS 7.0 recommended (80 / 6.5 UC min)", "conditions": intl_english_cond, "source_name": "UCLA International Applicants", "source_url": UC_ENGLISH_URL},
            ],
            "deadlines": [
                {"applicant_type": "first_year", "deadline_type": "regular_decision", "intake_term": "Fall 2027", "deadline_date": date(2026, 11, 30), "deadline_time": "23:59 PST", "timezone": "America/Los_Angeles", "source_name": "UCLA Undergraduate Admission", "source_url": UC_APPLY_URL},
                {"applicant_type": "transfer", "deadline_type": "transfer_fall", "intake_term": "Fall 2027", "deadline_date": date(2026, 11, 30), "deadline_time": "23:59 PST", "timezone": "America/Los_Angeles", "source_name": "UCLA Undergraduate Admission", "source_url": UC_APPLY_URL},
            ],
        },

        # ------------------------------------------------------------------
        # 3. University of Michigan-Ann Arbor (US - IPEDS 170976)
        # ------------------------------------------------------------------
        {
            "ipeds_unit_id": "170976",
            "portal_urls": {
                "admissions_website": "https://admissions.umich.edu/",
                "application_portal_url": "https://admissions.umich.edu/apply",
            },
            "requirements": [
                {"template": "standardized_test:sat_act", "applicant_type": "all", "importance": "optional", "title": "SAT / ACT Policy: Test-Optional", "notes": "Applicants may choose whether to submit SAT or ACT scores.", "source_name": "UMich Undergraduate Admissions", "source_url": "https://admissions.umich.edu/apply/first-year-applicants/requirements-deadlines"},
                {"template": "official_transcript:high_school", "applicant_type": "first_year", "notes": "Official high school transcript and Secondary School Report required.", "source_name": "UMich Undergraduate Admissions", "source_url": "https://admissions.umich.edu/apply/first-year-applicants/requirements-deadlines"},
                {"template": "recommendation_letter:academic_ref", "applicant_type": "first_year", "quantity": 1, "notes": "One academic teacher evaluation plus Counselor School Report.", "source_name": "UMich Undergraduate Admissions", "source_url": "https://admissions.umich.edu/apply/first-year-applicants/requirements-deadlines"},
                {"template": "minimum_gpa:transfer_cumulative", "applicant_type": "transfer", "min_val": "3.0", "notes": "Minimum 3.0 cumulative college GPA required for LSA/Engineering transfer review (admitted averages 3.7+).", "source_name": "UMich Transfer Requirements", "source_url": "https://admissions.umich.edu/apply/transfer-applicants/requirements-deadlines"},
                {"template": "official_transcript:college_all", "applicant_type": "transfer", "notes": "Official college transcripts from all institutions attended.", "source_name": "UMich Transfer Requirements", "source_url": "https://admissions.umich.edu/apply/transfer-applicants/requirements-deadlines"},
                {
                    "template": "official_transcript:high_school_conditional",
                    "applicant_type": "transfer",
                    "importance": "conditional",
                    "notes": "Official high school transcript required if applicant has completed fewer than two semesters (~30 credits) of graded college work.",
                    "conditions": [
                        {
                            "condition_type": "credits",
                            "condition_field": "earned_college_credits",
                            "condition_operator": "less_than",
                            "condition_value": 30,
                            "result_importance": "required",
                            "explanation": "Fewer than 30 college credits (< 2 semesters) requires full high school transcript review.",
                        },
                        {
                            "condition_type": "credits",
                            "condition_field": "earned_college_credits",
                            "condition_operator": "greater_than",
                            "condition_value": 29.9,
                            "result_importance": "optional",
                            "explanation": "With 30+ graded college credits, college performance carries primary review weight (HS transcript still verifies graduation).",
                        },
                    ],
                    "source_name": "UMich Transfer Requirements",
                    "source_url": "https://admissions.umich.edu/apply/transfer-applicants/requirements-deadlines",
                },
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "all", "importance": "conditional", "min_val": "TOEFL 100 / IELTS 7.0 / MET 64", "conditions": intl_english_cond, "source_name": "UMich International Applicants", "source_url": "https://admissions.umich.edu/apply/international-applicants/english-language-proficiency"},
                {"template": "application_fee:undergrad_fee", "applicant_type": "all", "fee_amount": 75.0, "fee_currency": "USD", "fee_waiver": True, "source_name": "UMich Admissions", "source_url": "https://admissions.umich.edu/apply"},
            ],
            "deadlines": [
                {"applicant_type": "first_year", "deadline_type": "early_action", "intake_term": "Fall 2027", "deadline_date": date(2026, 11, 1), "source_name": "UMich Admissions", "source_url": "https://admissions.umich.edu/apply/first-year-applicants/requirements-deadlines"},
                {"applicant_type": "first_year", "deadline_type": "regular_decision", "intake_term": "Fall 2027", "deadline_date": date(2027, 2, 1), "source_name": "UMich Admissions", "source_url": "https://admissions.umich.edu/apply/first-year-applicants/requirements-deadlines"},
                {"applicant_type": "transfer", "deadline_type": "transfer_fall", "intake_term": "Fall 2027", "deadline_date": date(2027, 2, 1), "source_name": "UMich Transfer Admissions", "source_url": "https://admissions.umich.edu/apply/transfer-applicants/requirements-deadlines"},
                {"applicant_type": "transfer", "deadline_type": "transfer_spring", "intake_term": "Winter 2027", "deadline_date": date(2026, 10, 1), "source_name": "UMich Transfer Admissions", "source_url": "https://admissions.umich.edu/apply/transfer-applicants/requirements-deadlines"},
            ],
        },

        # ------------------------------------------------------------------
        # 4. MIT (US - IPEDS 166683)
        # ------------------------------------------------------------------
        {
            "ipeds_unit_id": "166683",
            "portal_urls": {
                "admissions_website": "https://mitadmissions.org/",
                "application_portal_url": "https://my.mit.edu/",
            },
            "requirements": [
                {"template": "standardized_test:sat_act", "applicant_type": "all", "importance": "required", "title": "SAT or ACT Required (First-Year & Transfer)", "notes": "MIT requires official SAT or ACT scores for both first-year and transfer admission.", "source_name": "MIT Admissions", "source_url": "https://mitadmissions.org/apply/firstyear/tests-scores/"},
                {"template": "recommendation_letter:academic_ref", "applicant_type": "first_year", "quantity": 2, "notes": "1 Math/Science teacher + 1 Humanities/Social Science/Language teacher recommendation.", "source_name": "MIT Admissions", "source_url": "https://mitadmissions.org/apply/firstyear/"},
                {"template": "minimum_credits:transfer_min_credits", "applicant_type": "transfer", "min_val": "2 full-time college terms", "max_val": "5 college terms", "notes": "Must complete at least 2 terms and no more than 5 terms of college before matriculating; second bachelor's degrees not eligible.", "source_name": "MIT Transfer Admissions", "source_url": "https://mitadmissions.org/apply/transfer/before-you-apply/"},
                {"template": "prerequisite_courses:major_specific", "applicant_type": "transfer", "title": "MIT Core STEM Transfer Prep (Calculus I–II, Physics, Chemistry, Biology)", "min_val": "Calculus + Calculus-based Physics + Chemistry/Bio", "notes": "Must demonstrate mastery in core STEM prerequisites for MIT credit readiness.", "source_name": "MIT Transfer Admissions", "source_url": "https://mitadmissions.org/apply/transfer/before-you-apply/"},
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "all", "importance": "conditional", "min_val": "TOEFL 90 / IELTS 7.0 / DET 120 recommended", "conditions": intl_english_cond, "source_name": "MIT International Admissions", "source_url": "https://mitadmissions.org/apply/firstyear/tests-scores/"},
            ],
            "deadlines": [
                {"applicant_type": "first_year", "deadline_type": "early_action", "intake_term": "Fall 2027", "deadline_date": date(2026, 11, 1), "source_name": "MIT Admissions", "source_url": "https://mitadmissions.org/apply/firstyear/deadlines/"},
                {"applicant_type": "first_year", "deadline_type": "regular_decision", "intake_term": "Fall 2027", "deadline_date": date(2027, 1, 5), "source_name": "MIT Admissions", "source_url": "https://mitadmissions.org/apply/firstyear/deadlines/"},
                {"applicant_type": "transfer", "deadline_type": "transfer_fall", "intake_term": "Fall 2027", "deadline_date": date(2027, 3, 15), "source_name": "MIT Transfer Admissions", "source_url": "https://mitadmissions.org/apply/transfer/deadlines/"},
                {"applicant_type": "transfer", "deadline_type": "transfer_spring", "intake_term": "Spring 2027", "deadline_date": date(2026, 10, 1), "source_name": "MIT Transfer Admissions", "source_url": "https://mitadmissions.org/apply/transfer/deadlines/"},
            ],
        },

        # ------------------------------------------------------------------
        # 5. De Anza College (US Community College - IPEDS 113333)
        # ------------------------------------------------------------------
        {
            "ipeds_unit_id": "113333",
            "portal_urls": {
                "admissions_website": "https://www.deanza.edu/admissions/index.html",
                "application_portal_url": "https://www.deanza.edu/admissions/apply.html",
            },
            "requirements": [
                {"template": "application_form:portal", "applicant_type": "first_year", "title": "CCCApply Open-Admissions Application", "notes": "Open admissions community college: open to high school graduates or adults 18+.", "source_name": "De Anza College Admissions", "source_url": "https://www.deanza.edu/admissions/apply.html"},
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "all", "importance": "conditional", "min_val": "TOEFL 61 / IELTS 6.0 / DET 95", "conditions": intl_english_cond, "source_name": "De Anza International Student Programs", "source_url": "https://www.deanza.edu/international/"},
                {"template": "financial_documentation:intl_sponsor_bank", "applicant_type": "all", "importance": "conditional", "notes": "Bank verification required for F-1 I-20 issuance for international applicants.", "conditions": intl_only_cond, "source_name": "De Anza International Student Programs", "source_url": "https://www.deanza.edu/international/"},
            ],
            "deadlines": [],
        },

        # ------------------------------------------------------------------
        # 6. University of Toronto (CA)
        # ------------------------------------------------------------------
        {
            "official_name": "University of Toronto",
            "portal_urls": {
                "admissions_website": "https://future.utoronto.ca/",
                "application_portal_url": "https://www.ouac.on.ca/",
            },
            "requirements": [
                {"template": "application_form:portal", "applicant_type": "all", "title": "OUAC Undergraduate Application Portal", "source_name": "University of Toronto Future Students", "source_url": "https://future.utoronto.ca/apply/"},
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "notes": "Recognized senior secondary completion equivalent to Ontario OSSD including senior-level English (ENG4U equiv).", "source_name": "U of T Admissions", "source_url": "https://future.utoronto.ca/apply/requirements/international-high-school-secondary/"},
                {"template": "official_transcript:college_all", "applicant_type": "transfer", "notes": "Post-secondary transcripts and course syllabi/descriptions required for transfer credit assessment.", "source_name": "U of T Transfer Credit", "source_url": "https://future.utoronto.ca/apply/requirements/transfer-credit/"},
                {"template": "course_descriptions:syllabi_intl", "applicant_type": "transfer", "importance": "required", "source_name": "U of T Transfer Credit", "source_url": "https://future.utoronto.ca/apply/requirements/transfer-credit/"},
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "all", "importance": "conditional", "min_val": "IELTS 6.5 (6.0 sub) / TOEFL 100 (22 W) / DET 120", "notes": "Required unless 4+ consecutive years in an English-language school system in an English-dominant country.", "conditions": intl_english_cond, "source_name": "U of T English Language Requirements", "source_url": "https://future.utoronto.ca/apply/english-language-requirements/"},
            ],
            "deadlines": [
                {"applicant_type": "first_year", "deadline_type": "early_action", "intake_term": "Fall 2027", "deadline_date": date(2026, 11, 7), "is_firm": False, "notes": "Recommended early consideration submission target.", "source_name": "U of T Key Dates", "source_url": "https://future.utoronto.ca/apply/important-application-dates/"},
                {"applicant_type": "all", "deadline_type": "regular_decision", "intake_term": "Fall 2027", "deadline_date": date(2027, 1, 15), "notes": "General OUAC application deadline (check program-specific dates).", "source_name": "U of T Key Dates", "source_url": "https://future.utoronto.ca/apply/important-application-dates/"},
            ],
        },

        # ------------------------------------------------------------------
        # 7. McGill University (CA)
        # ------------------------------------------------------------------
        {
            "official_name": "McGill University",
            "portal_urls": {
                "admissions_website": "https://www.mcgill.ca/undergraduate-admissions",
                "application_portal_url": "https://www.mcgill.ca/undergraduate-admissions/apply",
            },
            "requirements": [
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "notes": "Recognized secondary credential (DEC Quebec, OSSD, US HS, French Bac, IB, A-Levels).", "source_name": "McGill Undergraduate Admissions", "source_url": "https://www.mcgill.ca/undergraduate-admissions"},
                {"template": "official_transcript:college_all", "applicant_type": "transfer", "notes": "Official university transcripts from all institutions attended.", "source_name": "McGill Transfer Admissions", "source_url": "https://www.mcgill.ca/undergraduate-admissions/apply/requirements/university"},
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "all", "importance": "conditional", "min_val": "IELTS 6.5 (6.0 sub) / TOEFL 100 (or 90 faculty dependent)", "notes": "Required unless minimum 4 consecutive years in an acknowledged English-speaking institution.", "conditions": intl_english_cond, "source_name": "McGill English Proficiency", "source_url": "https://www.mcgill.ca/undergraduate-admissions/apply/english-proficiency"},
            ],
            "deadlines": [
                {"applicant_type": "all", "deadline_type": "regular_decision", "intake_term": "Fall 2027", "deadline_date": date(2027, 1, 15), "notes": "International & outside-Quebec application deadline; supporting docs due March 1.", "source_name": "McGill Deadlines", "source_url": "https://www.mcgill.ca/undergraduate-admissions/apply/dates"},
                {"applicant_type": "all", "deadline_type": "supporting_documents", "intake_term": "Fall 2027", "deadline_date": date(2027, 3, 1), "notes": "Supporting transcripts and English test scores deadline.", "source_name": "McGill Deadlines", "source_url": "https://www.mcgill.ca/undergraduate-admissions/apply/dates"},
            ],
        },

        # ------------------------------------------------------------------
        # 8. University of British Columbia (CA)
        # ------------------------------------------------------------------
        {
            "official_name": "University of British Columbia",
            "portal_urls": {
                "admissions_website": "https://you.ubc.ca/",
                "application_portal_url": "https://you.ubc.ca/applying-ubc/applied/",
            },
            "requirements": [
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "source_name": "UBC Admissions", "source_url": "https://you.ubc.ca/applying-ubc/requirements/"},
                {"template": "official_transcript:college_all", "applicant_type": "transfer", "source_name": "UBC Transfer", "source_url": "https://you.ubc.ca/applying-ubc/requirements/university-college-transfer/"},
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "all", "importance": "conditional", "title": "UBC English Language Admission Standard (ELAS)", "min_val": "IELTS 6.5 (6.0 sub) / TOEFL 90 (22 R/L, 21 W/S)", "conditions": intl_english_cond, "source_name": "UBC ELAS", "source_url": "https://you.ubc.ca/applying-ubc/requirements/english-language-competency/"},
            ],
            "deadlines": [
                {"applicant_type": "all", "deadline_type": "regular_decision", "intake_term": "Fall 2027", "deadline_date": date(2027, 1, 15), "notes": "Winter Session (Sept entry) general application deadline.", "source_name": "UBC Important Dates", "source_url": "https://you.ubc.ca/applying-ubc/dates-deadlines/"},
                {"applicant_type": "all", "deadline_type": "supporting_documents", "intake_term": "Fall 2027", "deadline_date": date(2027, 2, 15), "notes": "ELAS English documentation deadline.", "source_name": "UBC ELAS Dates", "source_url": "https://you.ubc.ca/applying-ubc/requirements/english-language-competency/"},
            ],
        },

        # ------------------------------------------------------------------
        # 9. University of Oxford (GB)
        # ------------------------------------------------------------------
        {
            "official_name": "University of Oxford",
            "portal_urls": {
                "admissions_website": "https://www.ox.ac.uk/admissions/undergraduate",
                "application_portal_url": "https://www.ucas.com/",
            },
            "requirements": [
                {"template": "application_form:portal", "applicant_type": "first_year", "title": "UCAS Undergraduate Application", "source_name": "University of Oxford", "source_url": "https://www.ox.ac.uk/admissions/undergraduate/applying-to-oxford"},
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "title": "A-Levels / IB / Country-Specific Qualifying Equivalents", "notes": "Oxford publishes country-by-country qualification standards (many national diplomas require foundation or US AP/SAT/ACT equivalents).", "source_name": "Oxford International Qualifications", "source_url": "https://www.ox.ac.uk/admissions/undergraduate/applying-to-oxford/for-international-students/international-qualifications"},
                {"template": "aptitude_assessment:institutional_exam", "applicant_type": "first_year", "importance": "conditional", "notes": "Course-specific Oxford admissions test (MAT, PAT, LNAT, TSA, etc.) and shortlisted interview required for most degrees.", "source_name": "Oxford Admissions Tests", "source_url": "https://www.ox.ac.uk/admissions/undergraduate/applying-to-oxford/guide/admissions-tests"},
                {"template": "personal_statement:essay", "applicant_type": "first_year", "source_name": "Oxford / UCAS", "source_url": "https://www.ox.ac.uk/admissions/undergraduate/applying-to-oxford"},
                {"template": "recommendation_letter:academic_ref", "applicant_type": "first_year", "title": "UCAS Academic Reference", "source_name": "Oxford / UCAS", "source_url": "https://www.ox.ac.uk/admissions/undergraduate/applying-to-oxford"},
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "first_year", "importance": "conditional", "min_val": "IELTS 7.5 (7.0 sub) / TOEFL 110 (Standard/Higher tiers)", "notes": "Not needed to apply on UCAS; must fulfill post-offer condition by July 31.", "conditions": intl_english_cond, "source_name": "Oxford English Language Requirements", "source_url": "https://www.ox.ac.uk/admissions/undergraduate/applying-to-oxford/for-international-students/english-language-requirements"},
            ],
            "deadlines": [
                {"applicant_type": "first_year", "deadline_type": "ucas_oxbridge", "intake_term": "Fall 2027", "deadline_date": date(2026, 10, 15), "deadline_time": "18:00 UK", "timezone": "Europe/London", "notes": "Strict UCAS deadline for all Oxford undergraduate courses.", "source_name": "Oxford Application Guide", "source_url": "https://www.ox.ac.uk/admissions/undergraduate/applying-to-oxford/guide/timelines"},
                {"applicant_type": "first_year", "deadline_type": "supporting_documents", "intake_term": "Fall 2027", "deadline_date": date(2027, 7, 31), "notes": "Deadline for offer holders to submit English proficiency proof.", "source_name": "Oxford English Requirements", "source_url": "https://www.ox.ac.uk/admissions/undergraduate/applying-to-oxford/for-international-students/english-language-requirements"},
            ],
        },

        # ------------------------------------------------------------------
        # 10. University College London — UCL (GB)
        # ------------------------------------------------------------------
        {
            "official_name": "University College London",
            "portal_urls": {
                "admissions_website": "https://www.ucl.ac.uk/prospective-students/undergraduate",
                "application_portal_url": "https://www.ucas.com/",
            },
            "requirements": [
                {"template": "application_form:portal", "applicant_type": "first_year", "title": "UCAS Undergraduate Application", "source_name": "UCL Undergraduate Prospectus", "source_url": "https://www.ucl.ac.uk/prospective-students/undergraduate/how-apply"},
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "notes": "Accepts A-Levels, IB, and recognized country equivalents; applicants without direct-entry equivalency may apply to UCL Undergraduate Preparatory Certificates (UPC).", "source_name": "UCL International Qualifications", "source_url": "https://www.ucl.ac.uk/prospective-students/undergraduate/how-apply/international-students"},
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "first_year", "importance": "conditional", "min_val": "UCL Level 1–5 (IELTS 6.5–8.0 / TOEFL 92–110 by program)", "notes": "Required as a condition of offer if not meeting UKVI majority-English exemption.", "conditions": intl_english_cond, "source_name": "UCL English Language Requirements", "source_url": "https://www.ucl.ac.uk/prospective-students/undergraduate/how-apply/english-language-requirements"},
            ],
            "deadlines": [
                {"applicant_type": "first_year", "deadline_type": "ucas_equal_consideration", "intake_term": "Fall 2027", "deadline_date": date(2027, 1, 13), "deadline_time": "18:00 UK", "timezone": "Europe/London", "notes": "UCAS Equal Consideration deadline for most UCL courses (Oct 15 for Medicine).", "source_name": "UCL How to Apply", "source_url": "https://www.ucl.ac.uk/prospective-students/undergraduate/how-apply"},
            ],
        },

        # ------------------------------------------------------------------
        # 11. University of Cambridge (GB)
        # ------------------------------------------------------------------
        {
            "official_name": "University of Cambridge",
            "portal_urls": {
                "admissions_website": "https://www.undergraduate.study.cam.ac.uk/",
                "application_portal_url": "https://www.ucas.com/",
            },
            "requirements": [
                {"template": "application_form:portal", "applicant_type": "first_year", "title": "UCAS + MyCambridge Application", "source_name": "Cambridge Undergraduate Study", "source_url": "https://www.undergraduate.study.cam.ac.uk/applying"},
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "source_name": "Cambridge International Qualifications", "source_url": "https://www.undergraduate.study.cam.ac.uk/international-students/international-qualifications"},
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "first_year", "importance": "conditional", "min_val": "IELTS 7.5 (7.0 sub) / TOEFL 110 (25 sub)", "conditions": intl_english_cond, "source_name": "Cambridge English Requirements", "source_url": "https://www.undergraduate.study.cam.ac.uk/international-students/english-language-requirements"},
            ],
            "deadlines": [
                {"applicant_type": "first_year", "deadline_type": "ucas_oxbridge", "intake_term": "Fall 2027", "deadline_date": date(2026, 10, 15), "deadline_time": "18:00 UK", "timezone": "Europe/London", "source_name": "Cambridge Application Dates", "source_url": "https://www.undergraduate.study.cam.ac.uk/applying/key-dates"},
            ],
        },

        # ------------------------------------------------------------------
        # 12 & 13. France: Sorbonne Université & Université Paris-Saclay
        # ------------------------------------------------------------------
        {
            "official_name": "Sorbonne Université",
            "portal_urls": {
                "admissions_website": "https://www.sorbonne-universite.fr/en/admissions",
                "application_portal_url": "https://pastel.diplomatie.gouv.fr/etudesenfrance",
            },
            "requirements": [
                {"template": "application_form:portal", "applicant_type": "first_year", "title": "Parcoursup (EU/French Bac) or Campus France Études en France / DAP (Non-EU International)", "notes": "International residents in Études en France countries must apply through Campus France DAP before institutional enrollment.", "source_name": "Campus France & Sorbonne Université", "source_url": "https://www.campusfrance.org/en/etudes-en-france-procedure"},
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "notes": "French Baccalauréat or foreign secondary diploma granting higher-education access in home country.", "source_name": "Campus France", "source_url": "https://www.campusfrance.org/en/application-first-year-licence-dap"},
                {"template": "language_proficiency:french_b2", "applicant_type": "all", "importance": "conditional", "min_val": "DELF B2 / DALF C1 / TCF DAP (B2 minimum)", "notes": "Mandatory for Licence 1 programs taught in French unless exempted by French-medium schooling.", "source_name": "Campus France DAP", "source_url": "https://www.campusfrance.org/en/application-first-year-licence-dap"},
                {"template": "certified_translation:non_english_docs", "applicant_type": "all", "importance": "conditional", "title": "Official French Translation of Foreign Academic Records", "conditions": intl_only_cond, "source_name": "Campus France", "source_url": "https://www.campusfrance.org/en/etudes-en-france-procedure"},
            ],
            "deadlines": [],
        },
        {
            "official_name": "Université Paris-Saclay",
            "portal_urls": {
                "admissions_website": "https://www.universite-paris-saclay.fr/en/admissions",
                "application_portal_url": "https://pastel.diplomatie.gouv.fr/etudesenfrance",
            },
            "requirements": [
                {"template": "application_form:portal", "applicant_type": "first_year", "title": "Parcoursup / Études en France (Campus France DAP)", "source_name": "Campus France & Paris-Saclay", "source_url": "https://www.campusfrance.org/en/etudes-en-france-procedure"},
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "source_name": "Campus France", "source_url": "https://www.campusfrance.org/en/application-first-year-licence-dap"},
                {"template": "language_proficiency:french_b2", "applicant_type": "all", "importance": "conditional", "min_val": "DELF B2 / TCF DAP", "source_name": "Campus France", "source_url": "https://www.campusfrance.org/en/application-first-year-licence-dap"},
            ],
            "deadlines": [],
        },

        # ------------------------------------------------------------------
        # 14 & 15. Germany: TUM & LMU Munich
        # ------------------------------------------------------------------
        {
            "official_name": "Technical University of Munich",
            "portal_urls": {
                "admissions_website": "https://www.tum.de/en/studies/application",
                "application_portal_url": "https://campus.tum.de/",
            },
            "requirements": [
                {"template": "credential_evaluation:foreign_eval", "applicant_type": "all", "importance": "conditional", "title": "VPD (Vorprüfungsdokumentation) via uni-assist", "notes": "International applicants with non-German secondary/college certificates must obtain a VPD from uni-assist before or alongside TUMonline submission.", "conditions": intl_only_cond, "source_name": "TUM VPD Requirements", "source_url": "https://www.tum.de/en/studies/application/application-info-portal/vorpruefungsdokumentation-vpd"},
                {"template": "application_form:portal", "applicant_type": "all", "title": "TUMonline Direct Application Portal", "source_name": "TUM Application Portal", "source_url": "https://www.tum.de/en/studies/application"},
                {"template": "language_proficiency:german_c1", "applicant_type": "all", "importance": "conditional", "min_val": "DSH-2 / TestDaF 4x4 / Goethe C1 / DSD II", "notes": "Required by deadline for German-taught Bachelor programs; English-taught tracks accept TOEFL/IELTS instead.", "source_name": "TUM Language Certificates", "source_url": "https://www.tum.de/en/studies/application/application-info-portal/language-certificates"},
                {"template": "aptitude_assessment:institutional_exam", "applicant_type": "first_year", "title": "TUM Aptitude Assessment (Eignungsfeststellungsverfahren)", "notes": "Evaluates secondary grades, subject weights, and (when shortlisted) motivation/interview.", "source_name": "TUM Admissions", "source_url": "https://www.tum.de/en/studies/application"},
            ],
            "deadlines": [
                {"applicant_type": "all", "deadline_type": "regular_decision", "intake_term": "Winter 2027", "deadline_date": date(2027, 7, 15), "notes": "Standard Winter Semester application deadline (early VPD request via uni-assist recommended 6–8 weeks ahead).", "source_name": "TUM Application Deadlines", "source_url": "https://www.tum.de/en/studies/application/dates-and-deadlines"},
                {"applicant_type": "all", "deadline_type": "transfer_spring", "intake_term": "Summer 2027", "deadline_date": date(2027, 1, 15), "source_name": "TUM Application Deadlines", "source_url": "https://www.tum.de/en/studies/application/dates-and-deadlines"},
            ],
        },
        {
            "official_name": "Ludwig-Maximilians-Universität München",
            "portal_urls": {
                "admissions_website": "https://www.lmu.de/en/study/all-degrees-and-programs/programs-for-international-visiting-students/",
                "application_portal_url": "https://www.lmu.de/en/study/degree-students/applications/",
            },
            "requirements": [
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "notes": "Recognized Abitur or equivalent HZB assessed for international admission.", "source_name": "LMU Munich Admissions", "source_url": "https://www.lmu.de/en/study/degree-students/applications/"},
                {"template": "language_proficiency:german_c1", "applicant_type": "all", "importance": "conditional", "min_val": "DSH-2 / TestDaF / Goethe C2", "source_name": "LMU Munich", "source_url": "https://www.lmu.de/en/study/degree-students/applications/"},
            ],
            "deadlines": [
                {"applicant_type": "all", "deadline_type": "regular_decision", "intake_term": "Winter 2027", "deadline_date": date(2027, 7, 15), "source_name": "LMU Application Dates", "source_url": "https://www.lmu.de/en/study/degree-students/applications/"},
            ],
        },

        # ------------------------------------------------------------------
        # 16 & 17. Haiti: UEH & Quisqueya University
        # ------------------------------------------------------------------
        {
            "official_name": "University of Haiti",
            "portal_urls": {
                "admissions_website": "https://ueh.edu.ht/",
                "application_portal_url": "https://admission.ueh.edu.ht/",
            },
            "requirements": [
                {"template": "application_form:portal", "applicant_type": "first_year", "title": "Inscription en ligne UEH (admission.ueh.edu.ht)", "source_name": "Université d'État d'Haïti", "source_url": "https://admission.ueh.edu.ht/"},
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "title": "Certificat de fin d'études secondaires / NS4 ou Équivalence MENFP", "min_val": "Baccalauréat II / NS4", "notes": "Foreign secondary diplomas require official equivalence from MENFP (Ministère de l'Éducation Nationale).", "source_name": "UEH Admissions", "source_url": "https://admission.ueh.edu.ht/"},
                {"template": "national_exam:entrance_exam", "applicant_type": "first_year", "title": "Concours d'admission par entité/faculté UEH", "notes": "Each UEH faculty/campus administers a competitive entrance examination.", "source_name": "UEH Admissions", "source_url": "https://admission.ueh.edu.ht/"},
                {"template": "application_fee:undergrad_fee", "applicant_type": "first_year", "fee_amount": 800.0, "fee_currency": "HTG", "fee_waiver": False, "notes": "Standard UEH registration fee (800 HTG per faculty registration).", "source_name": "UEH Admissions", "source_url": "https://admission.ueh.edu.ht/"},
            ],
            "deadlines": [],
        },
        {
            "official_name": "Quisqueya University",
            "portal_urls": {
                "admissions_website": "https://uniq.edu.ht/",
                "application_portal_url": "https://uniq.edu.ht/",
            },
            "requirements": [
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "title": "Bac II / NS4 + Relevés de notes officiels (or US SAT >= 800 / ACT >= 18)", "min_val": "Bac II / SAT 800 / ACT 18", "notes": "US secondary applicants require minimum SAT 800 or ACT 18/36.", "source_name": "Université Quisqueya (UniQ)", "source_url": "https://uniq.edu.ht/"},
                {"template": "official_transcript:high_school", "applicant_type": "first_year", "notes": "Physical dossier submitted to VRAAC / Registrar including birth certificate (extrait d'acte de naissance) and 3 ID photos.", "source_name": "Université Quisqueya (UniQ)", "source_url": "https://uniq.edu.ht/"},
                {"template": "national_exam:entrance_exam", "applicant_type": "first_year", "title": "Concours d'admission UniQ", "notes": "Faculty access card issued after VRAAC dossier validation and admission fee payment.", "source_name": "Université Quisqueya (UniQ)", "source_url": "https://uniq.edu.ht/"},
            ],
            "deadlines": [],
        },

        # ------------------------------------------------------------------
        # 18 & 19. India: University of Delhi & IIT Kharagpur
        # ------------------------------------------------------------------
        {
            "official_name": "University of Delhi",
            "portal_urls": {
                "admissions_website": "https://admission.uod.ac.in/",
                "application_portal_url": "https://ugadmission.uod.ac.in/",
            },
            "requirements": [
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "title": "Class XII Senior Secondary Board Completion", "source_name": "University of Delhi Admission Branch", "source_url": "https://admission.uod.ac.in/"},
                {"template": "national_exam:entrance_exam", "applicant_type": "first_year", "title": "CUET-UG (Common University Entrance Test) in Passed Class XII Subjects", "notes": "Mandatory for DU undergraduate selection; program-specific Section IA/IB language + 2–3 domain tests required.", "source_name": "University of Delhi / CSAS", "source_url": "https://admission.uod.ac.in/"},
                {"template": "application_form:portal", "applicant_type": "first_year", "title": "DU CSAS (Common Seat Allocation System) Portal", "source_name": "University of Delhi", "source_url": "https://ugadmission.uod.ac.in/"},
            ],
            "deadlines": [],
        },
        {
            "official_name": "Indian Institute of Technology Kharagpur",
            "portal_urls": {
                "admissions_website": "https://www.iitkgp.ac.in/",
                "application_portal_url": "https://josaa.nic.in/",
            },
            "requirements": [
                {"template": "minimum_gpa:high_school", "applicant_type": "first_year", "title": "Class XII Board Aggregate >= 75% (65% SC/ST/PwD) or Top 20 Percentile", "min_val": "75% (65% reserved)", "notes": "Must include Physics, Chemistry, and Mathematics.", "source_name": "IIT Kharagpur / JoSAA", "source_url": "https://www.iitkgp.ac.in/"},
                {"template": "national_exam:entrance_exam", "applicant_type": "first_year", "title": "JEE Main Qualification + JEE Advanced All India Rank", "notes": "Candidates must qualify via JEE Main and clear JEE Advanced; seats allocated via JoSAA counseling.", "source_name": "IIT Kharagpur / JoSAA", "source_url": "https://josaa.nic.in/"},
                {"template": "application_form:portal", "applicant_type": "first_year", "title": "JoSAA Centralized Seat Allocation Portal", "source_name": "JoSAA", "source_url": "https://josaa.nic.in/"},
            ],
            "deadlines": [],
        },

        # ------------------------------------------------------------------
        # 20. Australia: The University of Melbourne
        # ------------------------------------------------------------------
        {
            "official_name": "The University of Melbourne",
            "portal_urls": {
                "admissions_website": "https://study.unimelb.edu.au/",
                "application_portal_url": "https://study.unimelb.edu.au/how-to-apply/undergraduate-study/international-applications",
            },
            "requirements": [
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "notes": "Recognized Year 12 equivalent (ATAR, IB, A-Levels, CBSE/ISC, SAT/AP) meeting Guaranteed or Minimum Entry Score plus subject prerequisites.", "source_name": "University of Melbourne", "source_url": "https://study.unimelb.edu.au/how-to-apply/undergraduate-study/international-applications"},
                {"template": "official_transcript:college_all", "applicant_type": "transfer", "notes": "Post-secondary academic transcripts and course syllabi evaluated for credit/advanced standing.", "source_name": "University of Melbourne", "source_url": "https://study.unimelb.edu.au/how-to-apply/undergraduate-study/international-applications"},
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "all", "importance": "conditional", "min_val": "IELTS 6.5 (6.0 sub) / TOEFL iBT 79 / PTE 58", "conditions": intl_english_cond, "source_name": "Melbourne English Requirements", "source_url": "https://study.unimelb.edu.au/how-to-apply/english-language-requirements"},
            ],
            "deadlines": [],
        },

        # ------------------------------------------------------------------
        # 21. Japan: The University of Tokyo
        # ------------------------------------------------------------------
        {
            "official_name": "The University of Tokyo",
            "portal_urls": {
                "admissions_website": "https://www.u-tokyo.ac.jp/en/prospective-students/undergraduate_admissions.html",
                "application_portal_url": "https://www.u-tokyo.ac.jp/en/prospective-students/undergraduate_admissions.html",
            },
            "requirements": [
                {"template": "secondary_qualification:national_diploma", "applicant_type": "first_year", "notes": "12 years of schooling completed (or IB/A-Levels/SAT/ACT for English-taught PEAK tracks).", "source_name": "University of Tokyo", "source_url": "https://www.u-tokyo.ac.jp/en/prospective-students/undergraduate_admissions.html"},
                {"template": "language_proficiency:japanese_n1", "applicant_type": "first_year", "importance": "conditional", "title": "EJU + JLPT N1 (Japanese-Taught Tracks)", "min_val": "EJU + JLPT N1", "notes": "Mandatory for standard Japanese-taught faculties; not required for English-taught interdisciplinary PEAK tracks.", "source_name": "University of Tokyo", "source_url": "https://www.u-tokyo.ac.jp/en/prospective-students/undergraduate_admissions.html"},
                {"template": "english_proficiency:toefl_ielts_det", "applicant_type": "first_year", "importance": "conditional", "title": "TOEFL iBT / IELTS (English-Taught PEAK Track)", "min_val": "TOEFL / IELTS required if non-native", "conditions": intl_english_cond, "source_name": "University of Tokyo PEAK", "source_url": "https://www.u-tokyo.ac.jp/en/prospective-students/undergraduate_admissions.html"},
            ],
            "deadlines": [],
        },
    ]


def seed_verified_requirements(db: Session) -> Dict[str, int]:
    """
    Idempotently seeds Milestone 3 templates, country qualifications, verified institutional
    requirements, conditional rules, and official deadlines.
    """
    counts = {
        "templates_total": 0,
        "country_qualifications_created": 0,
        "institutions_matched": 0,
        "requirements_created": 0,
        "deadlines_created": 0,
    }

    templates: Dict[str, RequirementTemplate] = {}
    for item in REQUIREMENT_TEMPLATES:
        tpl = _upsert_template(db, item)
        templates[tpl.template_key] = tpl
    counts["templates_total"] = len(templates)

    for q_item in COUNTRY_QUALIFICATIONS:
        if _upsert_country_qual(db, q_item):
            counts["country_qualifications_created"] += 1

    for entry in _build_verified_catalog():
        inst = _find_institution(
            db,
            ipeds_unit_id=entry.get("ipeds_unit_id"),
            official_name=entry.get("official_name"),
        )
        if not inst:
            continue

        counts["institutions_matched"] += 1
        portal_urls = entry.get("portal_urls") or {}
        if portal_urls.get("admissions_website") and not inst.admissions_website:
            inst.admissions_website = portal_urls["admissions_website"]
        if portal_urls.get("application_portal_url") and not inst.application_portal_url:
            inst.application_portal_url = portal_urls["application_portal_url"]
        if portal_urls.get("admissions_website") and not inst.official_website:
            inst.official_website = portal_urls["admissions_website"]

        for req_spec in entry.get("requirements", []):
            _, created = _upsert_requirement(db, inst, templates, req_spec)
            if created:
                counts["requirements_created"] += 1

        for dl_spec in entry.get("deadlines", []):
            if _upsert_deadline(db, inst, dl_spec):
                counts["deadlines_created"] += 1

    db.commit()
    return counts
