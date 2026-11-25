"""
Phase 4 International Credential & Grade Evaluation Engine.

Core Principles (`docs/09_INTERNATIONAL_EDUCATION_INTELLIGENCE.md`):
1. Never flatten international grades blindly to 4.0; always display a Dual-View Record:
   Native Record + Informational Approximate Benchmark.
2. Uses percentile/distribution brackets (`GradeConversionRule`) and the Modified
   Bavarian Formula where applicable, citing exact methodology.
3. Pairs grade interpretation with `CredentialRecognitionRule` (NACES/WES/ECE/uni-assist/ENIC,
   translation, apostille/legalization, and English-waiver guidance) plus `CountryQualification`.
4. Explicitly discloses that results are informational preparation intelligence, NOT
   a legally binding credential evaluation.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.ingestion.phase4_seed import seed_phase4_financial_and_credentials
from app.models.credentials import CredentialRecognitionRule, GradeConversionRule
from app.models.profile import StudentProfile
from app.models.requirements import CountryQualification

CREDENTIAL_ADVISORY_DISCLAIMER = (
    "Informational grade equivalency and credential recognition guidance only — NOT an official or "
    "legally binding credential evaluation. Regulated NACES/AICE agencies (e.g., WES, ECE), uni-assist, "
    "UK ENIC, or the admitting university hold sole authority over final academic conversion."
)

SAMPLE_VALUES_BY_SYSTEM: Dict[str, List[str]] = {
    "fr_20": ["16.5", "14.5", "12.5", "10.5"],
    "ht_20": ["16.0", "14.2", "12.0", "10.0"],
    "de_abitur": ["1.2", "1.8", "2.6", "3.8"],
    "uk_alevel": ["A*", "A", "B", "C"],
    "in_pct": ["92", "78", "64", "48"],
    "in_cgpa10": ["9.2", "8.3", "7.1", "5.5"],
    "ib_45": ["41", "37", "32", "26"],
    "ca_pct": ["93", "84", "74", "58"],
    "ng_waec": ["A1", "B2", "C4", "C6"],
    "br_10": ["9.2", "8.4", "7.3", "6.2"],
    "au_atar": ["97.5", "89.0", "76.0", "62.0"],
}


def ensure_credentials_seeded(db: Session) -> None:
    if db.query(GradeConversionRule.id).limit(1).first() is None:
        seed_phase4_financial_and_credentials(db)


def list_grading_systems(db: Session) -> List[Dict[str, Any]]:
    ensure_credentials_seeded(db)
    rows = (
        db.query(GradeConversionRule)
        .order_by(GradeConversionRule.source_country_code.asc(), GradeConversionRule.grading_system_key.asc())
        .all()
    )
    seen = set()
    systems: List[Dict[str, Any]] = []
    for r in rows:
        if r.grading_system_key in seen:
            continue
        seen.add(r.grading_system_key)
        systems.append(
            {
                "source_country_code": r.source_country_code,
                "grading_system_key": r.grading_system_key,
                "scale_name": r.scale_name,
                "academic_level": r.academic_level,
                "is_inverted_scale": r.is_inverted_scale,
                "methodology": r.methodology,
                "sample_values": SAMPLE_VALUES_BY_SYSTEM.get(r.grading_system_key, []),
            }
        )
    return systems


def _interpolated_us_point(
    raw_num: float,
    bracket: GradeConversionRule,
) -> float:
    b_min = float(bracket.min_numeric) if bracket.min_numeric is not None else None
    b_max = float(bracket.max_numeric) if bracket.max_numeric is not None else None
    g_low = float(bracket.target_gpa_low)
    g_high = float(bracket.target_gpa_high)

    if b_min is None or b_max is None or b_max <= b_min:
        return round(float(bracket.target_gpa_point), 2)

    ratio = max(0.0, min(1.0, (raw_num - b_min) / (b_max - b_min)))
    if bracket.is_inverted_scale:
        # In German Abitur 1.0 (min numeric) -> highest US GPA (g_high)
        val = g_high - ratio * (g_high - g_low)
    else:
        val = g_low + ratio * (g_high - g_low)
    return round(val, 2)


def _modified_bavarian_score(raw_num: float, n_max: float = 1.0, n_min: float = 4.0) -> Optional[float]:
    """Computes Modified Bavarian Grade mapping when converting into German 1.0–4.0 reference."""
    if n_max == n_min:
        return None
    if raw_num > n_min and n_min > n_max:
        # Inverted failing Abitur (> 4.0)
        return round(min(6.0, raw_num), 2)
    return round(1.0 + 3.0 * ((n_max - raw_num) / (n_max - n_min)), 2)


def evaluate_credential(
    db: Session,
    *,
    source_country_code: str,
    grading_system_key: str,
    raw_grade: str,
    destination_country_code: str = "US",
    academic_level: str = "secondary",
) -> Dict[str, Any]:
    ensure_credentials_seeded(db)

    src_cc = source_country_code.strip().upper()[:2]
    dest_cc = destination_country_code.strip().upper()[:2]
    sys_key = grading_system_key.strip().lower()
    raw_clean = (raw_grade or "").strip()

    brackets = (
        db.query(GradeConversionRule)
        .filter(GradeConversionRule.grading_system_key == sys_key)
        .order_by(GradeConversionRule.band_order.asc())
        .all()
    )
    if not brackets:
        brackets = (
            db.query(GradeConversionRule)
            .filter(GradeConversionRule.source_country_code == src_cc)
            .order_by(GradeConversionRule.band_order.asc())
            .all()
        )

    matched_bracket: Optional[GradeConversionRule] = None
    numeric_val: Optional[float] = None
    try:
        numeric_val = float(raw_clean.replace("%", "").replace(",", ".").strip())
    except ValueError:
        numeric_val = None

    if numeric_val is not None:
        for b in brackets:
            if b.min_numeric is not None and b.max_numeric is not None:
                if float(b.min_numeric) <= numeric_val <= float(b.max_numeric):
                    matched_bracket = b
                    break
    else:
        raw_upper = raw_clean.upper()
        for b in brackets:
            if b.raw_grade_label and b.raw_grade_label.upper() == raw_upper:
                matched_bracket = b
                break

    scale_name = brackets[0].scale_name if brackets else f"{src_cc} Native Scale"
    if matched_bracket:
        us_point = (
            _interpolated_us_point(numeric_val, matched_bracket)
            if numeric_val is not None
            else round(float(matched_bracket.target_gpa_point), 2)
        )
        german_equiv = None
        if numeric_val is not None and not matched_bracket.is_inverted_scale and brackets:
            # Compute Modified Bavarian German equivalent when upper & lower passing thresholds exist
            passing_bands = [b for b in brackets if b.is_passing and b.min_numeric is not None and b.max_numeric is not None]
            if passing_bands:
                n_max = max(float(b.max_numeric) for b in passing_bands)
                n_min = min(float(b.min_numeric) for b in passing_bands)
                if n_max > n_min and numeric_val >= n_min:
                    german_equiv = _modified_bavarian_score(numeric_val, n_max=n_max, n_min=n_min)
        elif matched_bracket.is_inverted_scale and numeric_val is not None:
            german_equiv = round(numeric_val, 2)

        native_record = {
            "country_code": matched_bracket.source_country_code,
            "grading_system_key": matched_bracket.grading_system_key,
            "scale_name": matched_bracket.scale_name,
            "raw_input": raw_clean,
            "classification": matched_bracket.classification_label,
            "is_passing": matched_bracket.is_passing,
            "is_inverted_scale": matched_bracket.is_inverted_scale,
            "academic_level": academic_level or matched_bracket.academic_level,
        }
        info_equiv = {
            "us_4_0_point": us_point,
            "us_4_0_low": float(matched_bracket.target_gpa_low),
            "us_4_0_high": float(matched_bracket.target_gpa_high),
            "us_letter_equivalent": matched_bracket.target_letter_equivalent,
            "german_bavarian_equivalent": german_equiv,
            "methodology": matched_bracket.methodology,
            "methodology_citation": matched_bracket.methodology_citation,
            "percentile_note": matched_bracket.percentile_note,
            "equivalency_classification": matched_bracket.equivalency_classification or "reference_benchmark",
            "framework_version": matched_bracket.framework_version,
            "freshness_status": matched_bracket.freshness_status or "requires_manual_review",
            "confidence_level": matched_bracket.confidence_level,
        }
    else:
        native_record = {
            "country_code": src_cc,
            "grading_system_key": sys_key,
            "scale_name": scale_name,
            "raw_input": raw_clean,
            "classification": "Unmatched / Out-of-Range Input",
            "is_passing": None,
            "is_inverted_scale": brackets[0].is_inverted_scale if brackets else False,
            "academic_level": academic_level,
        }
        info_equiv = {
            "us_4_0_point": None,
            "us_4_0_low": None,
            "us_4_0_high": None,
            "us_letter_equivalent": "Unavailable",
            "german_bavarian_equivalent": None,
            "methodology": "unmatched",
            "methodology_citation": "Input value fell outside verified grading bracket boundaries.",
            "percentile_note": None,
            "confidence_level": "insufficient_data",
        }

    rec_rules = (
        db.query(CredentialRecognitionRule)
        .filter(
            CredentialRecognitionRule.source_country_code == src_cc,
            CredentialRecognitionRule.destination_country_code == dest_cc,
        )
        .all()
    )

    quals = (
        db.query(CountryQualification)
        .filter(CountryQualification.country_code.in_([src_cc, dest_cc]))
        .order_by(CountryQualification.country_code.asc())
        .all()
    )

    return {
        "conversion": {
            "native_record": native_record,
            "informational_equivalency": info_equiv,
        },
        "recognition_rules": rec_rules,
        "country_qualifications": [
            {
                "country_code": q.country_code,
                "qualification_name": q.qualification_name,
                "qualification_type": q.qualification_type,
                "education_level": q.education_level,
                "issuing_authority": q.issuing_authority,
                "grading_scale": q.grading_scale,
                "highest_grade": q.highest_grade,
                "passing_threshold": q.passing_threshold,
                "subject_structure": q.subject_structure,
                "exam_structure": q.exam_structure,
                "academic_duration": q.academic_duration,
                "framework_version": q.framework_version,
                "equivalency_classification": q.equivalency_classification,
                "equivalency_notes": q.equivalency_notes,
                "source_name": q.source_name,
                "source_url": q.source_url,
                "verified_at": q.verified_at.isoformat() if q.verified_at else None,
                "verification_expires_at": q.verification_expires_at.isoformat() if q.verification_expires_at else None,
                "freshness_status": q.freshness_status,
            }
            for q in quals
        ],
        "advisory_disclaimer": CREDENTIAL_ADVISORY_DISCLAIMER,
    }


def _infer_grading_system_for_enrollment(
    country_code: str,
    gpa_scale: Optional[float],
    enrollment_type: str,
) -> str:
    cc = (country_code or "US").strip().upper()[:2]
    sc = float(gpa_scale) if gpa_scale else 4.0

    if abs(sc - 20.0) < 0.01:
        return "ht_20" if cc == "HT" else "fr_20"
    if cc == "DE" or (abs(sc - 6.0) < 0.01) or (abs(sc - 5.0) < 0.01):
        return "de_abitur"
    if abs(sc - 45.0) < 0.01:
        return "ib_45"
    if abs(sc - 10.0) < 0.01:
        return "in_cgpa10" if cc == "IN" else "br_10"
    if abs(sc - 100.0) < 0.01:
        if cc == "IN":
            return "in_pct"
        if cc == "AU":
            return "au_atar"
        return "ca_pct"

    defaults_by_country = {
        "FR": "fr_20",
        "HT": "ht_20",
        "DE": "de_abitur",
        "GB": "uk_alevel",
        "IN": "in_cgpa10" if enrollment_type == "undergraduate" else "in_pct",
        "CA": "ca_pct",
        "NG": "ng_waec",
        "BR": "br_10",
        "AU": "au_atar",
        "IB": "ib_45",
    }
    return defaults_by_country.get(cc, "us_4")


def evaluate_profile_credentials(
    db: Session,
    profile: Optional[StudentProfile],
    destination_country_code: str = "US",
) -> Dict[str, Any]:
    """
    Evaluates all academic enrollments stored on a student's Universal Profile,
    inferring their native grading systems while preserving dual-view records.
    """
    ensure_credentials_seeded(db)
    dest_cc = (destination_country_code or "US").strip().upper()[:2]
    if profile is None:
        return {
            "has_profile": False,
            "destination_country_code": dest_cc,
            "enrollments_evaluated": [],
            "advisory_disclaimer": CREDENTIAL_ADVISORY_DISCLAIMER,
        }

    evaluated: List[Dict[str, Any]] = []
    for enr in list(profile.enrollments or []):
        if enr.cumulative_gpa is None:
            continue
        inst_cc = (
            enr.institution_country
            or (enr.institution.country_code if enr.institution else None)
            or profile.country_of_residence
            or profile.country_code
            or "US"
        ).strip().upper()[:2]
        inst_name = (
            enr.institution.official_name
            if enr.institution
            else (enr.institution_name_manual or f"{inst_cc} Institution")
        )
        scale = float(enr.gpa_scale) if enr.gpa_scale else 4.0
        sys_key = _infer_grading_system_for_enrollment(inst_cc, scale, enr.enrollment_type)
        gpa_val = float(enr.cumulative_gpa)
        acad_lvl = "secondary" if enr.enrollment_type == "secondary" else "undergraduate"

        if sys_key == "us_4":
            rec_rules = (
                db.query(CredentialRecognitionRule)
                .filter(
                    CredentialRecognitionRule.source_country_code == inst_cc,
                    CredentialRecognitionRule.destination_country_code == dest_cc,
                )
                .all()
            )
            quals = (
                db.query(CountryQualification)
                .filter(CountryQualification.country_code.in_([inst_cc, dest_cc]))
                .all()
            )
            eval_out = {
                "conversion": {
                    "native_record": {
                        "country_code": inst_cc,
                        "grading_system_key": "us_4",
                        "scale_name": f"0.0–{scale:g} Scale",
                        "raw_input": f"{gpa_val:.2f}",
                        "classification": "Direct Domestic / 4.0 Scale Record",
                        "is_passing": gpa_val >= 2.0,
                        "is_inverted_scale": False,
                        "academic_level": acad_lvl,
                    },
                    "informational_equivalency": {
                        "us_4_0_point": round(min(4.0, (gpa_val / scale) * 4.0) if scale > 0 else gpa_val, 2),
                        "us_4_0_low": round(min(4.0, (gpa_val / scale) * 4.0) if scale > 0 else gpa_val, 2),
                        "us_4_0_high": round(min(4.0, (gpa_val / scale) * 4.0) if scale > 0 else gpa_val, 2),
                        "us_letter_equivalent": "A" if gpa_val >= 3.7 else "B+" if gpa_val >= 3.3 else "B" if gpa_val >= 3.0 else "C+",
                        "german_bavarian_equivalent": None,
                        "methodology": "direct_scale",
                        "methodology_citation": "Normalized directly from institutional 4.0-compatible GPA record.",
                        "percentile_note": None,
                        "confidence_level": "high",
                    },
                },
                "recognition_rules": rec_rules,
                "country_qualifications": [
                    {
                        "country_code": q.country_code,
                        "qualification_name": q.qualification_name,
                        "qualification_type": q.qualification_type,
                        "grading_scale": q.grading_scale,
                        "passing_threshold": q.passing_threshold,
                        "equivalency_notes": q.equivalency_notes,
                        "source_name": q.source_name,
                        "source_url": q.source_url,
                    }
                    for q in quals
                ],
                "advisory_disclaimer": CREDENTIAL_ADVISORY_DISCLAIMER,
            }
        else:
            eval_out = evaluate_credential(
                db,
                source_country_code=inst_cc,
                grading_system_key=sys_key,
                raw_grade=f"{gpa_val:g}",
                destination_country_code=dest_cc,
                academic_level=acad_lvl,
            )

        evaluated.append(
            {
                "enrollment_id": enr.id,
                "institution_name": inst_name,
                "institution_country": inst_cc,
                "enrollment_type": enr.enrollment_type,
                "cumulative_gpa": gpa_val,
                "gpa_scale": scale,
                "inferred_system_key": sys_key,
                "evaluation": eval_out,
            }
        )

    return {
        "has_profile": True,
        "destination_country_code": dest_cc,
        "enrollments_evaluated": evaluated,
        "advisory_disclaimer": CREDENTIAL_ADVISORY_DISCLAIMER,
    }
