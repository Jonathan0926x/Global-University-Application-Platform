"""
Phase 4 Global Scholarship Matching & Net Price Affordability Engine.

Guarantees:
1. Evaluates 18 deterministic eligibility dimensions with strict evidence boundaries
   (never infers citizenship from residence, residence from citizenship, degree level
   from age, transfer status from institution name, or absent test scores as 0).
2. Produces 5 explicit outcomes with documented precedence:
   ineligible > requires_manual_review > insufficient_information > conditionally_eligible > eligible.
3. Enforces degree-level isolation before including awards in matching or net-price calculations.
4. Enforces component-aware Net Price accounting:
   - Tuition-only awards reduce tuition/fees only (never housing/living costs).
   - Living stipends/travel allowances reduce living/transportation costs (never tuition).
   - Unknown scope, unknown currency, missing amounts, one-time vs unknown duration,
     expired records, and unverified/manual-review awards never reduce verified net price.
   - No category or total net cost can ever be over-credited or negative.
"""

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.ingestion.phase4_seed import seed_phase4_financial_and_credentials
from app.models.institution import Institution, InstitutionCost
from app.models.profile import CitizenshipRecord, StudentProfile
from app.models.rag import ScholarshipEligibilityRule, ScholarshipProgram
from app.services.freshness_governance import (
    _has_verified_funding_coverage,
    _utcnow,
    compute_verified_funding_coverage,
    evaluate_scholarship_claim_breakdown,
    evaluate_scholarship_freshness,
)
from app.services.matching_engine import _normalize_student_gpa_to_4

FINANCIAL_DISCLAIMER = (
    "Informational affordability and scholarship eligibility estimate only based on published institutional "
    "cost schedules and verified aid policies. Actual billed charges and aid packages are determined solely "
    "by official university financial aid offers. Neither net-price figures nor scholarship matches are guaranteed offers."
)

AGGREGATION_PRECEDENCE: Tuple[str, ...] = (
    "ineligible",
    "requires_manual_review",
    "insufficient_information",
    "conditionally_eligible",
    "eligible",
)

SUPPORTED_DEGREE_LEVELS = {
    "bachelors",
    "masters",
    "doctoral",
    "associate",
    "research",
    "exchange",
    "certificate",
}

REGION_COUNTRIES: Dict[str, set] = {
    "africa": {
        "NG", "GH", "KE", "ZA", "ET", "RW", "SN", "CI", "EG", "MA", "MR",
        "TN", "UG", "TZ", "CM", "ZM", "ZW", "DZ", "LY", "SD", "LR",
    },
    "sub_saharan_africa": {"NG", "GH", "KE", "ZA", "ET", "RW", "SN", "CI", "UG", "TZ", "CM", "ZM", "ZW"},
    "caribbean": {"HT", "JM", "TT", "BB", "BS", "DO", "CU", "LC", "GD", "VC", "AG", "DM", "KN"},
    "caricom": {"JM", "BB", "TT", "BS", "BZ", "DM", "GD", "LC", "VC", "AG", "KN", "GY", "HT", "SR"},
    "latam": {"BR", "MX", "CO", "CL", "AR", "PE", "EC", "BO", "PY", "UY", "VE", "CR", "PA", "GT"},
    "latin_america": {"BR", "MX", "CO", "CL", "AR", "PE", "EC", "BO", "PY", "UY", "VE", "CR", "PA", "GT"},
    "iberoamerica": {"BR", "MX", "CO", "CL", "AR", "PE", "EC", "BO", "PY", "UY", "VE", "CR", "PA", "GT", "HN", "NI", "SV", "DO", "CU"},
    "pacific_alliance": {"CL", "CO", "MX", "PE"},
    "americas": {"US", "CA", "MX", "HT", "JM", "TT", "BB", "BS", "DO", "BR", "CO", "CL", "AR", "PE"},
    "eu": {
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
        "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
        "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    },
    "eea": {
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
        "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
        "PL", "PT", "RO", "SK", "SI", "ES", "SE", "NO", "IS", "LI",
    },
    "europe": {
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
        "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
        "PL", "PT", "RO", "SK", "SI", "ES", "SE", "NO", "IS", "LI",
        "CH", "GB", "UA", "TR", "MD", "BY", "RS", "AL", "MK", "ME", "BA", "XK",
    },
    "asia": {"IN", "CN", "JP", "KR", "SG", "MY", "ID", "PH", "VN", "PK", "BD", "TH"},
    "asean": {"SG", "MY", "ID", "PH", "VN", "TH", "KH", "LA", "MM", "BN"},
    "commonwealth": {"GB", "CA", "AU", "NZ", "IN", "NG", "GH", "KE", "ZA", "JM", "TT", "BB", "BS", "MY", "SG", "PK", "BD"},
}

CERTIFIED_LANGUAGE_TESTS = {
    "TOEFL": ("en", "toefl"),
    "IELTS": ("en", "ielts"),
    "DUOLINGO": ("en", "duolingo"),
    "DET": ("en", "duolingo"),
    "DELF": ("fr", "delf"),
    "DALF": ("fr", "dalf"),
    "TESTDAF": ("de", "testdaf"),
    "JLPT": ("ja", "jlpt"),
}

DEFAULT_ACCEPTED_LANGUAGE_FORMATS = {"toefl", "ielts", "duolingo", "delf", "dalf", "testdaf", "jlpt", "cefr", "official_test", "certified_diploma"}


def ensure_phase4_seeded(db: Session) -> None:
    """Seed verified Phase 4 scholarships, rules, and credential tables if empty or un-synced."""
    has_rule = db.query(ScholarshipEligibilityRule.id).limit(1).first()
    has_yale = (
        db.query(ScholarshipProgram.id)
        .filter(ScholarshipProgram.title == "Yale Need-Blind Worldwide & Full-Need Financial Aid")
        .limit(1)
        .first()
    )
    has_batch1 = (
        db.query(ScholarshipProgram.id)
        .filter(ScholarshipProgram.title == "Commonwealth Master's Scholarships (CSC UK / FCDO)")
        .limit(1)
        .first()
    )
    has_batch2 = (
        db.query(ScholarshipProgram.id)
        .filter(ScholarshipProgram.title == "ICETEX Programa de Reciprocidad para Extranjeros en Colombia (Beca Colombia 2026-2)")
        .limit(1)
        .first()
    )
    has_batch3 = (
        db.query(ScholarshipProgram.id)
        .filter(ScholarshipProgram.title == "CAS-ANSO Scholarship (2027 Call — USTC / UCAS / CAS)")
        .limit(1)
        .first()
    )
    has_batch4 = (
        db.query(ScholarshipProgram.id)
        .filter(ScholarshipProgram.title == "NL Scholarship (Incoming Non-EEA Bachelor's & Master's — Study in NL / OCW)")
        .limit(1)
        .first()
    )
    has_audit_remediated = (
        db.query(ScholarshipProgram.id)
        .filter(
            ScholarshipProgram.title == "Imperial College President's Undergraduate Scholarships",
            ScholarshipProgram.award_currency == "GBP",
        )
        .limit(1)
        .first()
    )
    if (
        has_rule is None
        or has_yale is None
        or has_batch1 is None
        or has_batch2 is None
        or has_batch3 is None
        or has_batch4 is None
        or has_audit_remediated is None
    ):
        seed_phase4_financial_and_credentials(db)


def _parse_optional_date(val: Any) -> Optional[date]:
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str) and val.strip():
        try:
            return date.fromisoformat(val.strip()[:10])
        except ValueError:
            return None
    return None


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str) and val.strip():
        try:
            return float(val.strip())
        except ValueError:
            return None
    return None


def _derive_student_context(
    db: Session,
    profile: Optional[StudentProfile],
    overrides: Dict[str, Any],
) -> Dict[str, Any]:
    citizenships: List[str] = []
    dual_citizenship: Optional[bool] = None
    country_of_residence: Optional[str] = None
    residency_state: Optional[str] = None
    residency_status: Optional[str] = None
    applicant_type: Optional[str] = None
    date_of_birth: Optional[date] = None
    field_of_study: Optional[str] = None
    gpa_4: Optional[float] = None
    gpa_display: str = "Not Reported"
    has_us_cc = False
    has_enrollment_history = False
    currently_enrolled: Optional[bool] = None
    qualifications: List[str] = []
    exam_scores: Dict[str, Any] = {}
    language_proficiencies: Dict[str, Any] = {}

    if profile is not None:
        cit_rows = (
            db.query(CitizenshipRecord)
            .filter(CitizenshipRecord.profile_id == profile.id)
            .all()
        )
        citizenships = list(dict.fromkeys(c.country_code.strip().upper()[:2] for c in cit_rows if c.country_code))
        if any(c.citizenship_type == "dual_citizen" for c in cit_rows) or len(citizenships) > 1:
            dual_citizenship = True
        elif cit_rows:
            dual_citizenship = False
        if not citizenships and profile.country_code:
            citizenships = [profile.country_code.strip().upper()[:2]]
            dual_citizenship = False

        if any(c.citizenship_type == "permanent_resident" for c in cit_rows):
            residency_status = "permanent_resident"
        elif profile.residency_status:
            residency_status = profile.residency_status.strip().lower()

        country_of_residence = profile.country_of_residence.strip().upper()[:2] if profile.country_of_residence else None
        residency_state = profile.state_province.strip().upper() if profile.state_province else None
        applicant_type = profile.applicant_type if profile.applicant_type and profile.applicant_type != "undecided" else None
        date_of_birth = profile.date_of_birth
        field_of_study = profile.intended_major.strip() if profile.intended_major else None

        enrollments = sorted(
            list(profile.enrollments or []),
            key=lambda e: (
                1 if e.enrollment_status == "attending" else 0,
                1 if (e.enrollment_type or "") != "high_school" else 0,
                1 if (e.gpa_scale or 0) == 4.0 else 0,
                str(e.start_date or ""),
                str(e.id),
            ),
        )
        has_enrollment_history = len(enrollments) > 0
        if enrollments:
            currently_enrolled = any(e.enrollment_status == "attending" for e in enrollments)
        for enr in enrollments:
            enr_cc = (enr.institution_country or "").strip().upper()[:2]
            if enr.enrollment_type == "community_college" and enr_cc == "US":
                has_us_cc = True
            if enr.degree_type and enr.enrollment_status == "graduated":
                qualifications.append(enr.degree_type.strip().lower())
            elif enr.enrollment_status == "graduated" and enr.enrollment_type:
                qualifications.append(enr.enrollment_type.strip().lower())

        for enr in reversed(enrollments):
            if enr.cumulative_gpa is not None:
                scale_val = float(enr.gpa_scale) if getattr(enr, "gpa_scale", None) else 4.0
                gpa_4, gpa_display = _normalize_student_gpa_to_4(
                    float(enr.cumulative_gpa),
                    scale_val,
                    country_of_residence or (citizenships[0] if citizenships else None),
                )
                break

        for t in list(profile.standardized_tests or []):
            t_key = (t.test_type or "").strip().upper()
            if not t_key:
                continue
            parsed_score = _safe_float(t.total_score)
            exam_scores[t_key] = parsed_score if parsed_score is not None else t.total_score
            if t_key in CERTIFIED_LANGUAGE_TESTS:
                lang_code, fmt_name = CERTIFIED_LANGUAGE_TESTS[t_key]
                language_proficiencies[lang_code] = {
                    "format": fmt_name,
                    "score": parsed_score if parsed_score is not None else t.total_score,
                    "test_type": t_key,
                }

    # Explicit request overrides (never cross-infer unrelated domains)
    if overrides.get("citizenships"):
        explicit_cits = [str(c).strip().upper()[:2] for c in overrides["citizenships"] if str(c).strip()]
        if explicit_cits:
            citizenships = list(dict.fromkeys(explicit_cits))
            if overrides.get("dual_citizenship") is None:
                dual_citizenship = len(citizenships) > 1
    elif overrides.get("citizenship_country"):
        cc = str(overrides["citizenship_country"]).strip().upper()[:2]
        if cc:
            citizenships = [cc]
            if cc != "US" and overrides.get("residency_state") is None:
                residency_state = None
            if overrides.get("dual_citizenship") is None:
                dual_citizenship = False

    if overrides.get("dual_citizenship") is not None:
        dual_citizenship = bool(overrides["dual_citizenship"])

    if overrides.get("country_of_residence") is not None:
        cor = str(overrides["country_of_residence"]).strip().upper()[:2]
        country_of_residence = cor or None

    if overrides.get("residency_state") is not None:
        st = str(overrides["residency_state"]).strip().upper()
        residency_state = st or None

    if overrides.get("applicant_type") is not None:
        at = str(overrides["applicant_type"]).strip().lower()
        applicant_type = None if at in ("", "undecided") else at

    if "degree_level" in overrides:
        raw_dl = overrides.get("degree_level")
        degree_level = str(raw_dl).strip().lower() if raw_dl else None
    elif profile and profile.intended_degree_level:
        degree_level = profile.intended_degree_level.strip().lower()
    else:
        degree_level = None

    if overrides.get("date_of_birth") is not None:
        date_of_birth = _parse_optional_date(overrides.get("date_of_birth"))

    if overrides.get("field_of_study") is not None:
        fos = str(overrides.get("field_of_study")).strip()
        field_of_study = fos or None

    if overrides.get("qualifications"):
        qualifications = list(dict.fromkeys(qualifications + [str(q).strip().lower() for q in overrides["qualifications"] if str(q).strip()]))

    if isinstance(overrides.get("exam_scores"), dict):
        for k, v in overrides["exam_scores"].items():
            exam_scores[str(k).strip().upper()] = v

    if isinstance(overrides.get("language_proficiencies"), dict):
        for k, v in overrides["language_proficiencies"].items():
            language_proficiencies[str(k).strip().lower()] = v

    if overrides.get("gpa_4") is not None:
        gpa_4 = float(overrides["gpa_4"])
        gpa_display = f"{gpa_4:.2f}/4.0"

    need_level = (overrides.get("financial_need_level") or "").strip().lower() or None
    income_usd = overrides.get("household_income_usd")
    if not need_level and income_usd is not None:
        inc = float(income_usd)
        if inc <= 65000:
            need_level = "high"
        elif inc <= 125000:
            need_level = "moderate"
        else:
            need_level = "low"

    if overrides.get("us_community_college_enrolled") is True:
        has_us_cc = True
        has_enrollment_history = True
    elif overrides.get("us_community_college_enrolled") is False:
        has_us_cc = False
        has_enrollment_history = True

    if overrides.get("currently_enrolled") is not None:
        currently_enrolled = bool(overrides["currently_enrolled"])

    return {
        "citizenships": citizenships,
        "primary_citizenship": citizenships[0] if citizenships else None,
        "dual_citizenship": dual_citizenship,
        "country_of_residence": country_of_residence,
        "residency_state": residency_state,
        "residency_status": residency_status,
        "applicant_type": applicant_type,
        "degree_level": degree_level,
        "date_of_birth": date_of_birth.isoformat() if date_of_birth else None,
        "field_of_study": field_of_study,
        "qualifications": qualifications,
        "exam_scores": exam_scores,
        "language_proficiencies": language_proficiencies,
        "has_us_community_college": has_us_cc,
        "has_enrollment_history": has_enrollment_history,
        "currently_enrolled": currently_enrolled,
        "final_year_undergraduate": overrides.get("final_year_undergraduate"),
        "is_full_time": overrides.get("is_full_time"),
        "gpa_4": gpa_4,
        "gpa_display": gpa_display,
        "financial_need_level": need_level,
        "household_income_usd": float(income_usd) if income_usd is not None else None,
        "destination_country": (overrides.get("destination_country") or "").strip().upper()[:2] or None,
        "institution_id": str(overrides["institution_id"]) if overrides.get("institution_id") else None,
    }


def _outcome(
    status: str,
    detail: str,
    category: str = "eligibility",
    reason_code: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "outcome": status,
        "status": status,
        "detail": detail,
        "category": category,
        "reason_code": reason_code or f"rule.generic.{status}",
        "params": params or {},
    }


def _infer_official_source_language(sch: ScholarshipProgram) -> str:
    url = (sch.source_url or "").lower()
    cc = (sch.country_code or "US").strip().upper()
    if "/en/" in url or "/english/" in url:
        return "en"
    lang_map = {
        "AR": "es", "CL": "es", "CO": "es", "DO": "es", "ES": "es", "MX": "es", "PE": "es",
        "BR": "pt", "FR": "fr", "DE": "de", "IT": "it",
    }
    return lang_map.get(cc, "en")


def classify_cycle_verification_state(
    sch: ScholarshipProgram,
    claim_breakdown: Dict[str, Any],
    freshness: str,
    ref_now: Optional[datetime] = None,
) -> Tuple[str, str, bool, str, Dict[str, Any], str]:
    """
    Distinguishes 8 honest application cycle states without ever labeling unannounced
    cyclical deadlines or WAF-blocked portals as confirmed open:
      confirmed_open | confirmed_upcoming | rolling | previous_cycle_only |
      next_cycle_unannounced | deadline_expired | source_unavailable |
      requires_manual_verification
    Returns (cycle_state, app_cycle_status, is_open, reason_code, params, detail).
    """
    now_dt = ref_now or _utcnow(None)
    today_d = now_dt.date()
    audit_meta = (sch.claim_provenance or {}).get("audit_metadata") if isinstance(sch.claim_provenance, dict) else {}
    audit_meta = audit_meta if isinstance(audit_meta, dict) else {}
    http_status = audit_meta.get("http_status")
    next_cycle = str(audit_meta.get("next_cycle_status") or "").strip().lower()
    dl_str = sch.application_deadline_date.isoformat() if sch.application_deadline_date else ""

    if freshness == "conflicting_information" or next_cycle == "conflicting_information":
        return (
            "requires_manual_verification",
            "requires_manual_verification",
            False,
            "cycle.requires_manual_verification",
            {"date": dl_str} if dl_str else {},
            "Conflicting published application cycle metadata requires manual verification.",
        )

    if claim_breakdown.get("deadline_date_passed") and claim_breakdown["claims"].get("deadlines") != "expired":
        return (
            "previous_cycle_only",
            "closed",
            False,
            "cycle.previous_cycle_only",
            {"date": dl_str},
            f"Published cycle deadline ({dl_str}) has already passed; next cycle window is unannounced.",
        )

    if claim_breakdown.get("deadline_expired"):
        return (
            "deadline_expired",
            "closed",
            False,
            "cycle.deadline_expired",
            {"date": dl_str} if dl_str else {},
            (
                f"Cycle deadline ({dl_str}) has passed; confirm next cycle opening dates on official sponsor portal."
                if dl_str
                else "Recorded cycle deadline has expired; verify next application window on official sponsor portal."
            ),
        )

    if freshness == "source_unavailable" or http_status in (403, 0) or next_cycle in ("source_unavailable", "waf_blocked_manual_review"):
        return (
            "source_unavailable",
            "source_unavailable",
            False,
            "cycle.source_unavailable",
            {"http_status": str(http_status or "blocked"), "date": dl_str},
            "Official portal blocked automated verification (HTTP 403/timeout); check sponsor portal manually before relying on deadlines.",
        )

    if next_cycle == "upcoming":
        return (
            "confirmed_upcoming",
            "upcoming",
            False,
            "cycle.confirmed_upcoming",
            {"date": dl_str} if dl_str else {},
            "Verified upcoming application cycle (not yet open; check official opening date).",
        )

    if sch.application_deadline_date and sch.application_deadline_date >= today_d:
        return (
            "confirmed_open",
            "open",
            True,
            "cycle.confirmed_open",
            {"date": dl_str},
            f"Confirmed open cycle (published deadline: {dl_str}).",
        )

    if sch.is_deadline_rolling:
        return (
            "rolling",
            "rolling",
            True,
            "cycle.rolling",
            {},
            "Rolling application cycle accepted continuously per official policy.",
        )

    return (
        "next_cycle_unannounced",
        "cyclical_check_official",
        False,
        "cycle.next_cycle_unannounced",
        {},
        "Recurring annual program; next cycle opening and deadline dates are unannounced — do not assume open.",
    )


def _eval_rule(
    rule: ScholarshipEligibilityRule,
    sch: ScholarshipProgram,
    ctx: Dict[str, Any],
) -> Dict[str, Any]:
    dim = (rule.rule_dimension or "").strip().lower()
    val = rule.rule_value or {}

    if not isinstance(val, dict):
        return _outcome("requires_manual_review", f"Malformed rule payload for '{dim}'.", reason_code="rule.malformed", params={"dim": dim})

    if dim == "citizenship":
        allowed = [str(c).strip().upper()[:2] for c in val.get("countries", []) if str(c).strip()]
        excluded = [str(c).strip().upper()[:2] for c in val.get("excluded_countries", []) if str(c).strip()]
        if set(allowed) & set(excluded):
            return _outcome("requires_manual_review", "Conflicting allowed and excluded citizenship lists.", reason_code="rule.citizenship.conflict")
        stud_cits = ctx["citizenships"]
        cits_str = ", ".join(stud_cits)
        if not stud_cits:
            return _outcome("insufficient_information", "Citizenship country is required and has not been reported.", reason_code="rule.citizenship.missing")
        if any(c in excluded for c in stud_cits):
            return _outcome("ineligible", f"Citizenship {stud_cits[0]} is explicitly excluded by program rules.", reason_code="rule.citizenship.excluded", params={"citizenship": stud_cits[0]})
        if allowed and not any(c in allowed for c in stud_cits):
            return _outcome("ineligible", f"Citizenship {stud_cits} is outside eligible countries {allowed}.", reason_code="rule.citizenship.outside_allowed", params={"citizenships": cits_str, "allowed": ", ".join(allowed[:8])})
        return _outcome("eligible", f"Citizenship {stud_cits} satisfies eligibility criteria.", reason_code="rule.citizenship.eligible", params={"citizenships": cits_str})

    if dim == "excluded_citizenships":
        excluded = [str(c).strip().upper()[:2] for c in val.get("countries", []) if str(c).strip()]
        stud_cits = ctx["citizenships"]
        if not stud_cits:
            return _outcome("insufficient_information", "Citizenship country needed to check exclusion restrictions.", reason_code="rule.citizenship.missing")
        blocked = [c for c in stud_cits if c in excluded]
        if blocked:
            return _outcome("ineligible", f"Citizenship {blocked[0]} is explicitly excluded from this scholarship.", reason_code="rule.citizenship.excluded", params={"citizenship": blocked[0]})
        return _outcome("eligible", f"Citizenship {stud_cits} is not in excluded list.", reason_code="rule.excluded_citizenships.eligible", params={"citizenships": ", ".join(stud_cits)})

    if dim == "dual_citizenship":
        policy = str(val.get("policy", "")).strip().lower()
        dual = ctx.get("dual_citizenship")
        cits = set(ctx["citizenships"])
        if policy in ("prohibited", "restricted"):
            restricted_countries = {str(c).strip().upper()[:2] for c in val.get("restricted_countries", []) if str(c).strip()}
            if dual is None:
                return _outcome("insufficient_information", "Dual citizenship status must be reported for this restriction.", reason_code="rule.dual_citizenship.missing")
            if restricted_countries:
                if dual and (cits & restricted_countries):
                    return _outcome("ineligible", f"Holding dual citizenship with {sorted(cits & restricted_countries)} is restricted.", reason_code="rule.dual_citizenship.restricted_country", params={"countries": ", ".join(sorted(cits & restricted_countries))})
                return _outcome("eligible", "Dual citizenship restriction satisfied.", reason_code="rule.dual_citizenship.eligible")
            if dual:
                return _outcome("ineligible", "Applicants holding dual citizenship are restricted under program rules.", reason_code="rule.dual_citizenship.prohibited")
            return _outcome("eligible", "Single citizenship satisfies dual-citizenship restriction.", reason_code="rule.dual_citizenship.eligible")
        if policy == "required":
            req_countries = {str(c).strip().upper()[:2] for c in val.get("required_countries", []) if str(c).strip()}
            if dual is None:
                return _outcome("insufficient_information", "Dual citizenship records required.", reason_code="rule.dual_citizenship.missing")
            if not dual or (req_countries and not req_countries.issubset(cits)):
                return _outcome("ineligible", f"Requires dual citizenship including {sorted(req_countries)}.", reason_code="rule.dual_citizenship.required_failed", params={"countries": ", ".join(sorted(req_countries))})
            return _outcome("eligible", "Dual citizenship requirement satisfied.", reason_code="rule.dual_citizenship.eligible")
        if policy == "permitted":
            if not ctx["citizenships"]:
                return _outcome("insufficient_information", "Citizenship required to evaluate dual-citizenship allowance.", reason_code="rule.citizenship.missing")
            return _outcome("eligible", "Dual citizenship is explicitly permitted.", reason_code="rule.dual_citizenship.permitted")
        return _outcome("requires_manual_review", f"Unsupported dual_citizenship policy '{policy or 'unspecified'}'.", reason_code="rule.unsupported", params={"dim": dim})

    if dim == "country_of_residence":
        allowed = [str(c).strip().upper()[:2] for c in val.get("countries", []) if str(c).strip()]
        excluded = [str(c).strip().upper()[:2] for c in val.get("excluded_countries", []) if str(c).strip()]
        if set(allowed) & set(excluded):
            return _outcome("requires_manual_review", "Conflicting allowed and excluded countries of residence.", reason_code="rule.residence.conflict")
        res_cc = ctx.get("country_of_residence")
        if not res_cc:
            return _outcome("insufficient_information", "Actual country of residence is required (never inferred from citizenship).", reason_code="rule.residence.missing")
        if res_cc in excluded:
            return _outcome("ineligible", f"Country of residence '{res_cc}' is excluded.", reason_code="rule.residence.excluded", params={"country": res_cc})
        if allowed and res_cc not in allowed:
            return _outcome("ineligible", f"Country of residence '{res_cc}' is outside eligible list {allowed}.", reason_code="rule.residence.outside_allowed", params={"country": res_cc, "allowed": ", ".join(allowed[:8])})
        return _outcome("eligible", f"Country of residence '{res_cc}' satisfies criteria.", reason_code="rule.residence.eligible", params={"country": res_cc})

    if dim == "residency_state":
        allowed = [str(s).strip().upper() for s in val.get("states", []) if str(s).strip()]
        st = ctx.get("residency_state")
        if ctx["primary_citizenship"] and ctx["primary_citizenship"] != "US" and not sch.covers_international and ctx.get("residency_status") != "permanent_resident":
            return _outcome("ineligible", "International citizens are ineligible for state-resident need programs.", reason_code="rule.state.intl_ineligible")
        if not st:
            return _outcome("insufficient_information", f"State/province residency required ({'/'.join(allowed)}).", reason_code="rule.state.missing", params={"allowed": "/".join(allowed)})
        if st in allowed:
            return _outcome("eligible", f"State residency '{st}' matches {allowed}.", reason_code="rule.state.eligible", params={"state": st, "allowed": ", ".join(allowed)})
        return _outcome("ineligible", f"Residency '{st}' does not match required {allowed}.", reason_code="rule.state.outside_allowed", params={"state": st, "allowed": ", ".join(allowed)})

    if dim == "destination_country":
        allowed = [str(c).strip().upper()[:2] for c in val.get("countries", []) if str(c).strip()]
        dest = ctx.get("destination_country")
        if not dest:
            if val.get("strict"):
                return _outcome("insufficient_information", f"Destination study country must match {', '.join(allowed)}.", reason_code="rule.destination.missing", params={"allowed": ", ".join(allowed)})
            return _outcome("eligible", f"Applicable for destination {', '.join(allowed)}.", reason_code="rule.destination.open_target", params={"allowed": ", ".join(allowed)})
        if dest in allowed:
            return _outcome("eligible", f"Destination '{dest}' matches scholarship target.", reason_code="rule.destination.eligible", params={"destination": dest})
        return _outcome("ineligible", f"Scholarship applies to {', '.join(allowed)}, not '{dest}'.", reason_code="rule.destination.mismatch", params={"allowed": ", ".join(allowed), "destination": dest})

    if dim == "degree_level":
        allowed = [str(x).strip().lower() for x in val.get("levels", []) if str(x).strip()]
        if not allowed or any(x not in SUPPORTED_DEGREE_LEVELS for x in allowed):
            return _outcome("requires_manual_review", "Degree-level restriction contains unsupported or empty degree levels.", reason_code="rule.degree.unsupported")
        dl = ctx.get("degree_level")
        if not dl:
            return _outcome("insufficient_information", f"Intended degree level required ({', '.join(allowed)}).", reason_code="rule.degree.missing", params={"allowed": ", ".join(allowed)})
        if dl in allowed:
            return _outcome("eligible", f"Degree level '{dl}' matches allowed levels {allowed}.", reason_code="rule.degree.eligible", params={"degree": dl})
        return _outcome("ineligible", f"Restricted to degree levels {allowed} (applicant: '{dl}').", reason_code="rule.degree.mismatch", params={"allowed": ", ".join(allowed), "degree": dl})

    if dim == "applicant_type":
        allowed = [str(t).strip().lower() for t in val.get("types", []) if str(t).strip()]
        app_t = ctx.get("applicant_type")
        if not app_t:
            return _outcome("insufficient_information", f"Applicant pathway ({'/'.join(allowed)}) not reported.", reason_code="rule.pathway.missing", params={"allowed": "/".join(allowed)})
        if app_t in allowed:
            return _outcome("eligible", f"Applicant pathway '{app_t}' qualifies.", reason_code="rule.pathway.eligible", params={"pathway": app_t})
        if app_t == "both" and any(x in ("first_year", "transfer", "both") for x in allowed):
            return _outcome("eligible", "Applicant supports eligible undergraduate pathway.", reason_code="rule.pathway.eligible", params={"pathway": app_t})
        return _outcome("ineligible", f"Restricted to {', '.join(allowed)} applicants (student: '{app_t}').", reason_code="rule.pathway.mismatch", params={"allowed": ", ".join(allowed), "pathway": app_t})

    if dim == "minimum_gpa":
        req_gpa = _safe_float(val.get("min_gpa"))
        if req_gpa is None or req_gpa < 0 or req_gpa > 4.0:
            return _outcome("requires_manual_review", "Invalid or non-normalized GPA threshold requires manual review.", reason_code="rule.gpa.invalid")
        stud_gpa = ctx.get("gpa_4")
        if stud_gpa is None:
            return _outcome("insufficient_information", f"Academic GPA needed to verify {req_gpa:.2f} minimum.", reason_code="rule.gpa.missing", params={"min_gpa": f"{req_gpa:.2f}"})
        if stud_gpa >= req_gpa:
            return _outcome("eligible", f"GPA {stud_gpa:.2f} meets >= {req_gpa:.2f} requirement.", reason_code="rule.gpa.eligible", params={"gpa": f"{stud_gpa:.2f}", "min_gpa": f"{req_gpa:.2f}"})
        return _outcome("ineligible", f"GPA {stud_gpa:.2f} is below {req_gpa:.2f} minimum.", reason_code="rule.gpa.below", params={"gpa": f"{stud_gpa:.2f}", "min_gpa": f"{req_gpa:.2f}"})

    if dim == "financial_need_level":
        allowed_levels = [str(lvl).strip().lower() for lvl in val.get("levels", []) if str(lvl).strip()]
        max_inc = _safe_float(val.get("max_income_usd"))
        if val.get("max_income_usd") is not None and (max_inc is None or max_inc < 0):
            return _outcome("requires_manual_review", "Conflicting or invalid household income cap.", reason_code="rule.need.conflict")
        inc = ctx.get("household_income_usd")
        need = ctx.get("financial_need_level")
        if max_inc is not None:
            if inc is None:
                return _outcome("insufficient_information", f"Household income needed to verify ${max_inc:,.0f} threshold.", reason_code="rule.need.income_missing", params={"max_income": f"{max_inc:,.0f}"})
            if inc <= max_inc:
                return _outcome("eligible", f"Household income ${inc:,.0f} is within ${max_inc:,.0f} cap.", reason_code="rule.need.income_eligible", params={"income": f"{inc:,.0f}", "max_income": f"{max_inc:,.0f}"})
            return _outcome("ineligible", f"Household income ${inc:,.0f} exceeds ${max_inc:,.0f} cap.", reason_code="rule.need.income_exceeds", params={"income": f"{inc:,.0f}", "max_income": f"{max_inc:,.0f}"})
        if not need:
            return _outcome("insufficient_information", "Financial need level required to evaluate need-based criteria.", reason_code="rule.need.level_missing")
        if need in allowed_levels:
            return _outcome("eligible", f"Financial need level '{need}' aligns with program criteria.", reason_code="rule.need.level_eligible", params={"need": need})
        return _outcome("ineligible", f"Requires {'/'.join(allowed_levels)} financial need (reported '{need}').", reason_code="rule.need.level_mismatch", params={"allowed": "/".join(allowed_levels), "need": need})

    if dim == "enrollment_context":
        if val.get("is_future_condition"):
            desc = str(val.get("condition_text") or rule.human_label or "Future enrollment verification required upon matriculation.")
            return _outcome("conditionally_eligible", desc, reason_code="rule.enrollment.future_condition", params={"condition": desc})
        if val.get("requires_us_community_college"):
            if ctx.get("has_us_community_college"):
                return _outcome("eligible", "Active U.S. community college enrollment verified on student profile.", reason_code="rule.enrollment.cc_verified")
            if ctx.get("has_enrollment_history"):
                return _outcome("ineligible", "Requires current enrollment at an accredited U.S. 2-year community college.", reason_code="rule.enrollment.cc_failed")
            return _outcome("insufficient_information", "Enrollment records required to confirm U.S. 2-year community college status.", reason_code="rule.enrollment.cc_missing")
        req_contexts = [str(c).strip().lower() for c in val.get("required_contexts", []) if str(c).strip()]
        for rc in req_contexts:
            if rc == "currently_enrolled":
                if ctx.get("currently_enrolled") is None:
                    return _outcome("insufficient_information", "Current enrollment status has not been reported.", reason_code="rule.enrollment.current_missing")
                if not ctx["currently_enrolled"]:
                    return _outcome("ineligible", "Requires currently active institutional enrollment.", reason_code="rule.enrollment.current_failed")
            elif rc == "final_year_undergraduate":
                if ctx.get("final_year_undergraduate") is None:
                    return _outcome("insufficient_information", "Final-year undergraduate status is not yet confirmed.", reason_code="rule.enrollment.final_ug_missing")
                if not ctx["final_year_undergraduate"]:
                    return _outcome("ineligible", "Restricted to final-year undergraduate applicants.", reason_code="rule.enrollment.final_ug_failed")
            elif rc == "full_time":
                if ctx.get("is_full_time") is None:
                    return _outcome("insufficient_information", "Full-time enrollment commitment is not confirmed.", reason_code="rule.enrollment.full_time_missing")
                if not ctx["is_full_time"]:
                    return _outcome("ineligible", "Requires full-time student enrollment.", reason_code="rule.enrollment.full_time_failed")
            elif rc in ("first_year", "transfer"):
                at = ctx.get("applicant_type")
                if not at:
                    return _outcome("insufficient_information", f"Enrollment pathway '{rc}' not reported.", reason_code="rule.pathway.missing", params={"allowed": rc})
                if at != rc and at != "both":
                    return _outcome("ineligible", f"Enrollment context requires '{rc}' (applicant: '{at}').", reason_code="rule.pathway.mismatch", params={"allowed": rc, "pathway": at})
            elif rc == "graduate":
                dl = ctx.get("degree_level")
                if not dl:
                    return _outcome("insufficient_information", "Graduate degree level not specified.", reason_code="rule.degree.missing", params={"allowed": "masters, doctoral"})
                if dl not in ("masters", "doctoral", "research"):
                    return _outcome("ineligible", f"Enrollment context restricted to graduate programs (applicant: '{dl}').", reason_code="rule.degree.mismatch", params={"allowed": "masters, doctoral", "degree": dl})
            else:
                return _outcome("requires_manual_review", f"Unsupported enrollment_context '{rc}'.", reason_code="rule.unsupported", params={"dim": rc})
        return _outcome("eligible", "Enrollment context criteria satisfied.", reason_code="rule.enrollment.eligible")

    if dim == "required_qualifications":
        req_quals = [str(q).strip().lower() for q in val.get("qualifications", []) if str(q).strip()]
        if not req_quals:
            return _outcome("requires_manual_review", "Qualification requirement list is empty or ambiguous.", reason_code="rule.unsupported", params={"dim": dim})
        stud_quals = ctx.get("qualifications", [])
        if not stud_quals:
            return _outcome("insufficient_information", f"Completed academic qualification record needed ({', '.join(req_quals)}).", reason_code="rule.qualifications.missing", params={"allowed": ", ".join(req_quals)})
        if any(q in req_quals for q in stud_quals):
            return _outcome("eligible", f"Completed qualification matches required {req_quals}.", reason_code="rule.qualifications.eligible", params={"allowed": ", ".join(req_quals)})
        return _outcome("ineligible", f"Requires one of {req_quals} (student holds {stud_quals}).", reason_code="rule.qualifications.mismatch", params={"allowed": ", ".join(req_quals)})

    if dim == "language_proficiency":
        lang = str(val.get("language", "en")).strip().lower()[:2]
        accepted = {str(f).strip().lower() for f in val.get("accepted_formats", DEFAULT_ACCEPTED_LANGUAGE_FORMATS)}
        tests_map = {str(k).strip().upper(): _safe_float(v) for k, v in (val.get("min_scores") or {}).items()}
        profs = ctx.get("language_proficiencies", {})
        ev = profs.get(lang)
        if not ev:
            return _outcome("insufficient_information", f"Certified {lang.upper()} language proficiency evidence required.", reason_code="rule.language.missing", params={"lang": lang.upper()})
        if isinstance(ev, dict):
            fmt = str(ev.get("format", "")).strip().lower()
            if not fmt or fmt not in accepted:
                return _outcome("requires_manual_review", f"Submitted language evidence format '{fmt or 'unknown'}' requires manual verification.", reason_code="rule.language.manual", params={"format": fmt or "unknown"})
            test_name = str(ev.get("test_type", fmt)).strip().upper()
            score = _safe_float(ev.get("score"))
            if test_name in tests_map and tests_map[test_name] is not None:
                if score is None:
                    return _outcome("insufficient_information", f"{test_name} numeric score required.", reason_code="rule.exam.missing", params={"exam": test_name})
                if score < tests_map[test_name]:
                    return _outcome("ineligible", f"{test_name} score {score} is below minimum {tests_map[test_name]}.", reason_code="rule.exam.below", params={"exam": test_name, "score": str(score), "min_score": str(tests_map[test_name])})
            return _outcome("eligible", f"Language proficiency in '{lang}' verified via {fmt}.", reason_code="rule.language.eligible", params={"lang": lang.upper(), "format": fmt})
        return _outcome("requires_manual_review", "Language evidence format is unstructured and requires manual review.", reason_code="rule.language.manual", params={"format": "unstructured"})

    if dim == "required_exams":
        exams_req = val.get("exams") or ({val["exam"]: val.get("min_score")} if val.get("exam") else {})
        if not exams_req:
            return _outcome("requires_manual_review", "Exam requirement has no specified examination.", reason_code="rule.unsupported", params={"dim": dim})
        stud_exams = ctx.get("exam_scores", {})
        for ex_name, min_sc_raw in exams_req.items():
            ex_key = str(ex_name).strip().upper()
            if ex_key not in stud_exams or stud_exams[ex_key] is None:
                return _outcome("insufficient_information", f"Required {ex_key} score is not yet submitted (absent score is never treated as zero).", reason_code="rule.exam.missing", params={"exam": ex_key})
            min_sc = _safe_float(min_sc_raw)
            actual = _safe_float(stud_exams[ex_key])
            if actual is None:
                return _outcome("requires_manual_review", f"Submitted {ex_key} score '{stud_exams[ex_key]}' requires manual evaluation.", reason_code="rule.exam.manual", params={"exam": ex_key})
            if min_sc is not None and actual < min_sc:
                return _outcome("ineligible", f"{ex_key} score {actual:g} is below minimum {min_sc:g}.", reason_code="rule.exam.below", params={"exam": ex_key, "score": f"{actual:g}", "min_score": f"{min_sc:g}"})
        return _outcome("eligible", "Required examination thresholds satisfied.", reason_code="rule.exam.eligible")

    if dim == "age_limit":
        min_age = val.get("min_age")
        max_age = val.get("max_age")
        if min_age is not None and max_age is not None and float(min_age) > float(max_age):
            return _outcome("requires_manual_review", "Conflicting age_limit rule: min_age exceeds max_age.", reason_code="rule.age.conflict")
        dob_str = ctx.get("date_of_birth")
        dob = _parse_optional_date(dob_str)
        if not dob:
            return _outcome("insufficient_information", "Date of birth required to verify age eligibility.", reason_code="rule.age.missing")
        ref_date = _parse_optional_date(val.get("reference_date")) or sch.application_deadline_date or date.today()
        age_years = ref_date.year - dob.year - ((ref_date.month, ref_date.day) < (dob.month, dob.day))
        if min_age is not None and age_years < int(min_age):
            return _outcome("ineligible", f"Applicant age ({age_years}) as of {ref_date.isoformat()} is below minimum {min_age}.", reason_code="rule.age.below", params={"age": str(age_years), "min_age": str(min_age), "date": ref_date.isoformat()})
        if max_age is not None and age_years > int(max_age):
            return _outcome("ineligible", f"Applicant age ({age_years}) as of {ref_date.isoformat()} exceeds maximum {max_age}.", reason_code="rule.age.exceeds", params={"age": str(age_years), "max_age": str(max_age), "date": ref_date.isoformat()})
        return _outcome("eligible", f"Applicant age ({age_years}) as of {ref_date.isoformat()} satisfies age limits.", reason_code="rule.age.eligible", params={"age": str(age_years), "date": ref_date.isoformat()})

    if dim == "field_of_study":
        allowed = [str(f).strip().lower() for f in val.get("allowed_fields", []) if str(f).strip()]
        excluded = [str(f).strip().lower() for f in val.get("excluded_fields", []) if str(f).strip()]
        if set(allowed) & set(excluded):
            return _outcome("requires_manual_review", "Conflicting allowed and excluded fields of study.", reason_code="rule.field.conflict")
        fos = (ctx.get("field_of_study") or "").strip().lower()
        if not fos:
            return _outcome("insufficient_information", "Intended field of study required.", reason_code="rule.field.missing")
        if any(ex in fos or fos == ex for ex in excluded):
            return _outcome("ineligible", f"Field of study '{ctx['field_of_study']}' is excluded by program terms.", reason_code="rule.field.excluded", params={"field": str(ctx["field_of_study"])})
        if allowed and not any(al in fos or fos in al for al in allowed):
            return _outcome("ineligible", f"Field of study '{ctx['field_of_study']}' is outside eligible disciplines {allowed}.", reason_code="rule.field.outside_allowed", params={"field": str(ctx["field_of_study"])})
        return _outcome("eligible", f"Field of study '{ctx['field_of_study']}' matches eligible disciplines.", reason_code="rule.field.eligible", params={"field": str(ctx["field_of_study"])})

    if dim == "geographic_region":
        regions = [str(r).strip().lower() for r in val.get("regions", []) if str(r).strip()]
        scope = str(val.get("scope", "citizenship")).strip().lower()
        allowed_codes = {str(c).strip().upper()[:2] for c in val.get("countries", []) if str(c).strip()}
        for reg in regions:
            if reg not in REGION_COUNTRIES:
                return _outcome("requires_manual_review", f"Unmapped geographic region '{reg}' requires manual verification.", reason_code="rule.unsupported", params={"dim": reg})
            allowed_codes |= REGION_COUNTRIES[reg]
        reg_str = ", ".join(regions)
        if scope == "residence":
            res_cc = ctx.get("country_of_residence")
            if not res_cc:
                return _outcome("insufficient_information", "Country of residence needed to check regional eligibility.", reason_code="rule.residence.missing")
            if res_cc in allowed_codes:
                return _outcome("eligible", f"Residence country '{res_cc}' belongs to eligible region {regions}.", reason_code="rule.region.residence_eligible", params={"country": res_cc, "regions": reg_str})
            return _outcome("ineligible", f"Residence country '{res_cc}' falls outside eligible regions {regions}.", reason_code="rule.region.residence_outside", params={"country": res_cc, "regions": reg_str})
        stud_cits = ctx["citizenships"]
        if not stud_cits:
            return _outcome("insufficient_information", "Citizenship country needed to check regional eligibility.", reason_code="rule.citizenship.missing")
        cits_str = ", ".join(stud_cits)
        if any(c in allowed_codes for c in stud_cits):
            return _outcome("eligible", f"Citizenship {stud_cits} falls within eligible region {regions}.", reason_code="rule.region.citizenship_eligible", params={"citizenships": cits_str, "regions": reg_str})
        return _outcome("ineligible", f"Citizenship {stud_cits} is outside eligible regions {regions}.", reason_code="rule.region.citizenship_outside", params={"citizenships": cits_str, "regions": reg_str})

    if dim == "renewal":
        # Evaluated separately from initial-award eligibility
        min_ren_gpa = _safe_float(val.get("min_renewal_gpa"))
        req_ft = val.get("requires_full_time")
        cond_text = str(val.get("condition_text") or rule.human_label or "Maintain satisfactory academic progress for renewal.")
        return _outcome("conditionally_eligible", f"Renewal criterion: {cond_text}" + (f" (min GPA {min_ren_gpa:.2f})" if min_ren_gpa else "") + (" [full-time required]" if req_ft else ""), category="renewal", reason_code="rule.renewal.condition", params={"condition": cond_text})

    # Never silently ignore unsupported rule dimensions
    return _outcome("requires_manual_review", f"Unsupported rule dimension '{dim}' requires human verification.", reason_code="rule.unsupported", params={"dim": dim})


def _derive_funding_scope(sch: ScholarshipProgram) -> List[str]:
    scope: List[str] = []
    if sch.covers_tuition:
        scope.append("tuition")
    if sch.covers_fees:
        scope.append("mandatory_fees")
    if sch.covers_housing:
        scope.append("housing")
    if sch.covers_meals:
        scope.append("meals")
    if sch.covers_health_insurance:
        scope.append("health_insurance")
    if getattr(sch, "covers_travel", False):
        scope.append("travel")
    if sch.provides_living_stipend:
        scope.append("living_stipend")
    return scope


def _format_duration_renewal(sch: ScholarshipProgram) -> str:
    parts: List[str] = []
    if sch.max_funding_periods == 1 and not sch.is_renewable:
        parts.append("One-time award (1 period)")
    elif sch.is_renewable:
        if getattr(sch, "funding_duration_years", None):
            parts.append(f"Renewable up to {float(sch.funding_duration_years):g} years")
        elif getattr(sch, "max_funding_periods", None):
            parts.append(f"Renewable up to {sch.max_funding_periods} periods")
        else:
            parts.append("Renewable (exact max duration unspecified)")
    else:
        parts.append("Non-renewable / duration unspecified")
    if getattr(sch, "renewal_conditions", None):
        parts.append(sch.renewal_conditions)
    return "; ".join(parts)


def classify_transfer_pathway(sch: ScholarshipProgram) -> Tuple[str, str]:
    """
    Classifies a scholarship into one of 7 explicit transfer-intelligence categories
    without ever inferring transfer eligibility from general undergraduate status:
      1. exchange_only
      2. graduate_only
      3. community_college_required
      4. transfer_restricted_by_institution_or_country
      5. explicitly_accepts_transfer
      6. first_year_only
      7. ug_transfer_unconfirmed
    """
    ftype = (sch.funding_type or "").strip().lower()
    if ftype == "exchange_mobility":
        return (
            "exchange_only",
            "Short-term exchange/mobility grant only (not a degree-seeking transfer or first-year award).",
        )

    degs = {str(d).strip().lower() for d in (sch.degree_levels or []) if str(d).strip()}
    if degs and degs <= {"masters", "doctoral", "research"}:
        return (
            "graduate_only",
            "Restricted to graduate/doctoral degree pathways (undergraduate transfer not applicable).",
        )

    rules = list(sch.rules or [])
    if any(
        (r.rule_dimension or "").strip().lower() == "enrollment_context"
        and isinstance(r.rule_value, dict)
        and r.rule_value.get("requires_us_community_college")
        for r in rules
    ):
        return (
            "community_college_required",
            "Requires current enrollment at an accredited U.S. 2-year community college before transferring.",
        )

    audit_meta = (sch.claim_provenance or {}).get("audit_metadata") if isinstance(sch.claim_provenance, dict) else {}
    explicit_tx = audit_meta.get("transfer_supported") if isinstance(audit_meta, dict) else None
    app_type = (sch.applicant_type or "all").strip().lower()
    title_l = (sch.title or "").lower()

    has_transfer_restriction = (
        sch.institution_id is not None and len(sch.eligible_residency_states or []) > 0
    ) or any(kw in title_l for kw in ("alianza del pacífico", "oas academic scholarship", "promise grant"))
    if has_transfer_restriction and (app_type == "transfer" or explicit_tx is True):
        return (
            "transfer_restricted_by_institution_or_country",
            "Transfer eligibility is verified only for designated participating institutions, states, or partner-country universities.",
        )

    if app_type == "transfer" or explicit_tx is True:
        return (
            "explicitly_accepts_transfer",
            "Explicitly accepts transfer applicants under published institutional or statutory rules.",
        )

    if app_type == "first_year" or explicit_tx is False:
        return (
            "first_year_only",
            "Restricted to incoming first-year applicants; transfer students are explicitly excluded.",
        )

    return (
        "ug_transfer_unconfirmed",
        "Accepts undergraduate applicants broadly, but transfer eligibility is not explicitly confirmed in official source documentation.",
    )


def classify_aid_type(
    sch: ScholarshipProgram,
    claim_breakdown: Dict[str, Any],
) -> Tuple[str, bool, bool]:
    """
    Distinguishes fixed verified funding from variable, formulaic, waiver, exchange-only,
    and unverified awards. Returns (aid_classification, is_variable_aid, is_amount_verified).
    """
    ftype = (sch.funding_type or "").strip().lower()
    atype = (sch.award_type or "").strip().lower()
    audit_meta = (sch.claim_provenance or {}).get("audit_metadata") if isinstance(sch.claim_provenance, dict) else {}
    amt_class = str((audit_meta or {}).get("amount_classification") or "").strip().lower()
    title_l = (sch.title or "").lower()

    is_amt_verified = _has_verified_funding_coverage(sch, _utcnow(None))

    if ftype == "exchange_mobility" or atype == "mobility_grant":
        return "exchange_only", True, False

    if "css" in amt_class or amt_class == "need_based_variable" or any(
        kw in title_l for kw in ("mit need-blind", "yale need-blind", "princeton financial aid", "stanford university need-based")
    ):
        return "css_profile_full_need", True, False

    if sch.is_guaranteed_statutory and amt_class in ("published_fixed", "published_range") and is_amt_verified:
        return "fixed_statutory", False, True

    if atype in ("tuition_waiver",) or ftype in ("tuition_waiver", "tuition_free") or "waiver" in amt_class or "tuition_free" in amt_class:
        return "tuition_waiver", not is_amt_verified, is_amt_verified

    if amt_class in (
        "conditional_sai_formula",
        "conditional_last_dollar_gift_aid",
        "conditional_per_unit",
        "destination_and_commission_dependent",
        "full_cost_program_dependent",
    ) or (ftype in ("need_based", "need_and_merit") and not is_amt_verified):
        return "variable_institutional_need", True, False

    if ftype == "merit" and not is_amt_verified:
        return "variable_merit", True, False

    if is_amt_verified and amt_class in ("published_fixed", "published_range", "published_mixed_fee_policy"):
        return "fixed_published", False, True

    if is_amt_verified:
        return "fixed_published", False, True

    return "unpublished_or_manual_review", True, False


def _aggregate_outcomes(outcomes: List[str]) -> str:
    """Applies documented deterministic precedence:
    ineligible > requires_manual_review > insufficient_information > conditionally_eligible > eligible.
    """
    for level in AGGREGATION_PRECEDENCE:
        if level in outcomes:
            return level
    return "eligible"


def evaluate_single_scholarship(
    sch: ScholarshipProgram,
    ctx: Dict[str, Any],
) -> Dict[str, Any]:
    evals: List[Dict[str, Any]] = []
    renewal_evals: List[Dict[str, Any]] = []
    satisfied_reasons: List[str] = []
    failed_reasons: List[str] = []
    missing_reqs: List[str] = []
    conditional_reqs: List[str] = []
    manual_reasons: List[str] = []
    freshness_warnings: List[str] = []

    satisfied_items: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []
    missing_items: List[Dict[str, Any]] = []
    conditional_items: List[Dict[str, Any]] = []
    manual_review_items: List[Dict[str, Any]] = []
    freshness_warning_items: List[Dict[str, Any]] = []

    def _record(dim: str, label: str, outcome_dict: Dict[str, Any], mandatory: bool = True) -> None:
        item = {
            "dimension": dim,
            "human_label": label,
            "status": outcome_dict["outcome"],
            "outcome": outcome_dict["outcome"],
            "category": outcome_dict["category"],
            "detail": outcome_dict["detail"],
            "reason_code": outcome_dict.get("reason_code") or f"rule.generic.{outcome_dict['outcome']}",
            "params": outcome_dict.get("params") or {},
            "is_mandatory": mandatory,
        }
        structured_entry = {
            "reason_code": item["reason_code"],
            "params": item["params"],
            "fallback_detail": outcome_dict["detail"],
        }
        if outcome_dict["category"] == "renewal":
            renewal_evals.append(item)
            return
        evals.append(item)
        if not mandatory:
            return
        st = outcome_dict["outcome"]
        if st == "eligible":
            satisfied_reasons.append(f"{label}: {outcome_dict['detail']}")
            satisfied_items.append(structured_entry)
        elif st == "ineligible":
            failed_reasons.append(outcome_dict["detail"])
            failed_items.append(structured_entry)
        elif st == "requires_manual_review":
            manual_reasons.append(outcome_dict["detail"])
            manual_review_items.append(structured_entry)
        elif st == "insufficient_information":
            missing_reqs.append(outcome_dict["detail"])
            missing_items.append(structured_entry)
        elif st == "conditionally_eligible":
            conditional_reqs.append(outcome_dict["detail"])
            conditional_items.append(structured_entry)

    freshness = evaluate_scholarship_freshness(sch)
    claim_breakdown = evaluate_scholarship_claim_breakdown(sch)
    (
        cycle_verification_state,
        app_cycle_status,
        is_cycle_open,
        cycle_reason_code,
        cycle_params,
        cycle_status_detail,
    ) = classify_cycle_verification_state(sch, claim_breakdown, freshness)

    if cycle_verification_state in ("previous_cycle_only", "deadline_expired"):
        freshness_warnings.append("Current cycle application deadline has passed; confirm next cycle opening dates on official sponsor site.")
        freshness_warning_items.append({"reason_code": cycle_reason_code, "params": cycle_params, "fallback_detail": cycle_status_detail})

    if freshness == "approaching_expiration":
        exp_str = sch.verification_expires_at.date().isoformat() if sch.verification_expires_at else "soon"
        msg = f"Verification approaching expiration ({exp_str}). Confirm latest terms on official site."
        freshness_warnings.append(msg)
        freshness_warning_items.append({"reason_code": "fresh.approaching_expiration", "params": {"date": exp_str}, "fallback_detail": msg})
    elif freshness == "expired":
        if claim_breakdown["amount_expired"]:
            msg = "Award amount claim expired; excluded from verified dollar discounts."
            freshness_warnings.append(msg)
            freshness_warning_items.append({"reason_code": "fresh.amount_expired", "params": {}, "fallback_detail": msg})
        elif claim_breakdown["existence_current"] and claim_breakdown["deadline_expired"]:
            # Existence & amount are verified; only application deadline is closed
            freshness = claim_breakdown["record_state"]
        else:
            msg = "Source verification expired; excluded from verified funding."
            freshness_warnings.append(msg)
            freshness_warning_items.append({"reason_code": "fresh.record_expired", "params": {}, "fallback_detail": msg})
    elif freshness == "conflicting_information":
        msg = sch.conflict_notes or "Conflicting published scholarship terms require manual review."
        manual_reasons.append(msg)
        manual_review_items.append({"reason_code": "fresh.conflicting", "params": {}, "fallback_detail": msg})
        freshness_warnings.append("Conflicting award metadata detected.")
        freshness_warning_items.append({"reason_code": "fresh.conflicting", "params": {}, "fallback_detail": msg})
    elif freshness == "source_unavailable":
        msg = "Official source URL unavailable or blocked automated HTTP check (403/timeout)."
        manual_reasons.append(msg)
        manual_review_items.append({"reason_code": "fresh.source_unavailable", "params": {}, "fallback_detail": msg})
        freshness_warnings.append("Official verification source unavailable.")
        freshness_warning_items.append({"reason_code": "fresh.source_unavailable", "params": {}, "fallback_detail": msg})
    elif freshness == "requires_manual_review":
        msg = "Missing verified cycle expiry or award amount confirmation; excluded from guaranteed aid calculations."
        freshness_warnings.append(msg)
        freshness_warning_items.append({"reason_code": "fresh.requires_manual_review", "params": {}, "fallback_detail": msg})

    if bool(sch.requires_manual_review):
        msg = "Scholarship is explicitly flagged for manual verifier review."
        manual_reasons.append(msg)
        manual_review_items.append({"reason_code": "fresh.manual_flag", "params": {}, "fallback_detail": msg})
    if not sch.is_verified:
        msg = "Scholarship lacks primary-source verification."
        manual_reasons.append(msg)
        manual_review_items.append({"reason_code": "fresh.unverified", "params": {}, "fallback_detail": msg})

    tx_pathway_cls, tx_pathway_detail = classify_transfer_pathway(sch)
    aid_cls, is_variable_aid, is_amt_verified = classify_aid_type(sch, claim_breakdown)
    official_src_lang = _infer_official_source_language(sch)

    # Degree-level implicit check whenever no explicit degree_level rule is attached
    has_degree_rule = any(r.rule_dimension == "degree_level" for r in (sch.rules or []))
    if not has_degree_rule:
        allowed_dl = [str(d).strip().lower() for d in (sch.degree_levels or []) if str(d).strip()]
        if not allowed_dl or any(d not in SUPPORTED_DEGREE_LEVELS for d in allowed_dl):
            _record("degree_level", "Eligible degree levels", _outcome("requires_manual_review", "Unknown or unsupported scholarship degree_levels metadata.", reason_code="rule.degree.unsupported"), mandatory=True)
        elif not ctx.get("degree_level"):
            _record("degree_level", "Eligible degree levels", _outcome("insufficient_information", f"Intended degree level required ({', '.join(allowed_dl)}).", reason_code="rule.degree.missing", params={"allowed": ", ".join(allowed_dl)}), mandatory=True)
        elif ctx["degree_level"] not in allowed_dl:
            _record("degree_level", "Eligible degree levels", _outcome("ineligible", f"Restricted to degree levels {allowed_dl} (applicant: '{ctx['degree_level']}').", reason_code="rule.degree.mismatch", params={"allowed": ", ".join(allowed_dl), "degree": ctx["degree_level"]}), mandatory=True)
        else:
            _record("degree_level", "Eligible degree levels", _outcome("eligible", f"Degree level '{ctx['degree_level']}' qualifies.", reason_code="rule.degree.eligible", params={"degree": ctx["degree_level"]}), mandatory=True)

    # Destination-country implicit check whenever no explicit destination_country rule is attached
    has_dest_rule = any(r.rule_dimension == "destination_country" for r in (sch.rules or []))
    if not has_dest_rule and ctx.get("destination_country"):
        allowed_dests = [
            str(d).strip().upper()[:2]
            for d in (sch.eligible_destination_countries or ([sch.country_code] if sch.country_code else []))
            if str(d).strip()
        ]
        if allowed_dests and ctx["destination_country"] not in allowed_dests:
            _record(
                "destination_country",
                "Eligible study destination",
                _outcome(
                    "ineligible",
                    f"Scholarship applies to study in {', '.join(allowed_dests)} (selected destination: '{ctx['destination_country']}').",
                    reason_code="rule.destination.mismatch",
                    params={"allowed": ", ".join(allowed_dests), "destination": ctx["destination_country"]},
                ),
                mandatory=True,
            )

    # Applicant pathway baseline check + strict non-inference guard for unconfirmed UG transfer awards
    has_app_rule = any(r.rule_dimension == "applicant_type" for r in (sch.rules or []))
    if sch.applicant_type and sch.applicant_type != "all":
        if not has_app_rule:
            app_t = ctx.get("applicant_type")
            if not app_t:
                _record("applicant_type", f"Pathway: {sch.applicant_type}", _outcome("insufficient_information", f"Applicant pathway ({sch.applicant_type}) not selected.", reason_code="rule.pathway.missing", params={"allowed": sch.applicant_type}), mandatory=True)
            elif app_t not in (sch.applicant_type, "both"):
                _record("applicant_type", f"Pathway: {sch.applicant_type}", _outcome("ineligible", f"Restricted to {sch.applicant_type} applicants (student: '{app_t}').", reason_code="rule.pathway.mismatch", params={"allowed": sch.applicant_type, "pathway": app_t}), mandatory=True)
            else:
                _record("applicant_type", f"Pathway: {sch.applicant_type}", _outcome("eligible", f"Applicant pathway '{app_t}' matches.", reason_code="rule.pathway.eligible", params={"pathway": app_t}), mandatory=True)
    elif ctx.get("applicant_type") == "transfer" and tx_pathway_cls == "ug_transfer_unconfirmed":
        # Section 3 safeguard: NEVER infer transfer eligibility from general applicant_type='all' UG status!
        _record(
            "transfer_eligibility",
            "Transfer pathway verification",
            _outcome(
                "requires_manual_review",
                "Program covers undergraduates broadly ('all'), but transfer student eligibility is unconfirmed in official source documentation — manual verification required.",
                reason_code="rule.transfer.unconfirmed",
            ),
            mandatory=True,
        )

    # International citizenship baseline guard (with explicit LPR/permanent_resident exception for domestic US programs)
    stud_cits = ctx["citizenships"]
    is_us_lpr = ctx.get("residency_status") == "permanent_resident" and sch.country_code == "US"
    if not sch.covers_international:
        if not stud_cits:
            _record(
                "international_policy",
                "International student coverage",
                _outcome("insufficient_information", "Citizenship status is required to verify domestic/eligible non-citizen funding rules.", reason_code="rule.citizenship.missing"),
                mandatory=True,
            )
        elif not is_us_lpr:
            dom_allowed = [str(c).strip().upper()[:2] for c in (sch.eligible_citizenships or [sch.country_code]) if str(c).strip()]
            if not any(c in dom_allowed for c in stud_cits):
                _record(
                    "international_policy",
                    "International student coverage",
                    _outcome(
                        "ineligible",
                        f"Award is restricted to {', '.join(dom_allowed)} domestic/eligible non-citizen students (excludes temporary/international {stud_cits[0]} applicants).",
                        reason_code="rule.intl_policy.domestic_only",
                        params={"allowed": ", ".join(dom_allowed), "citizenship": stud_cits[0]},
                    ),
                    mandatory=True,
                )

    # Evaluate structured rules
    for rule in (sch.rules or []):
        res = _eval_rule(rule, sch, ctx)
        _record(rule.rule_dimension, rule.human_label, res, mandatory=bool(rule.is_mandatory))

    mandatory_outcomes = [e["outcome"] for e in evals if e["is_mandatory"]]
    if manual_reasons:
        mandatory_outcomes.append("requires_manual_review")
    elig_status = _aggregate_outcomes(mandatory_outcomes)

    if elig_status == "ineligible":
        score = 10
        bucket = "ineligible"
    elif elig_status == "requires_manual_review":
        score = 35
        bucket = "review_required"
    elif elig_status == "insufficient_information":
        score = 55
        bucket = "potential_insufficient_info"
    elif freshness in ("requires_manual_review", "conflicting_information", "source_unavailable", "expired") or not is_amt_verified:
        score = 65 if elig_status == "eligible" else 55
        bucket = "review_required"
    elif elig_status == "conditionally_eligible":
        score = 75
        bucket = "conditional"
    else:
        score = 100 if sch.is_guaranteed_statutory else 90
        bucket = "verified_applicable"

    is_actionable_student = bool(
        elig_status in ("eligible", "conditionally_eligible")
        and is_amt_verified
        and is_cycle_open
        and (sch.funding_type or "").strip().lower() != "exchange_mobility"
    )

    official_sources = [
        {
            "source_name": sch.source_name,
            "source_url": sch.source_url,
            "sponsoring_institution": sch.sponsoring_institution,
            "source_type": sch.source_type or "unknown",
            "verified_at": sch.verified_at.isoformat() if sch.verified_at else None,
            "claim_domains_supported": list((sch.claim_provenance or {}).keys())[:15] if isinstance(sch.claim_provenance, dict) else [],
        }
    ]

    evidence_used = {
        "citizenships": ctx["citizenships"],
        "dual_citizenship": ctx.get("dual_citizenship"),
        "country_of_residence": ctx.get("country_of_residence"),
        "residency_state": ctx.get("residency_state"),
        "residency_status": ctx.get("residency_status"),
        "applicant_type": ctx.get("applicant_type"),
        "degree_level": ctx.get("degree_level"),
        "gpa_4": ctx.get("gpa_4"),
        "household_income_usd": ctx.get("household_income_usd"),
        "financial_need_level": ctx.get("financial_need_level"),
        "field_of_study": ctx.get("field_of_study"),
        "has_us_community_college": ctx.get("has_us_community_college"),
    }

    return {
        "id": sch.id,
        "institution_id": sch.institution_id,
        "institution_name": sch.institution.official_name if sch.institution else None,
        "country_code": sch.country_code,
        "title": sch.title,
        "provider_type": sch.provider_type,
        "award_type": sch.award_type,
        "applicant_type": sch.applicant_type,
        "funding_type": sch.funding_type,
        "covers_international": sch.covers_international,
        "award_amount_min_usd": float(sch.award_amount_min_usd) if sch.award_amount_min_usd is not None else None,
        "award_amount_max_usd": float(sch.award_amount_max_usd) if sch.award_amount_max_usd is not None else None,
        "max_award_info": sch.max_award_info,
        "eligibility_summary": sch.eligibility_summary,
        "covers_tuition": sch.covers_tuition,
        "covers_fees": sch.covers_fees,
        "covers_housing": sch.covers_housing,
        "covers_meals": sch.covers_meals,
        "covers_health_insurance": sch.covers_health_insurance,
        "provides_living_stipend": sch.provides_living_stipend,
        "is_renewable": sch.is_renewable,
        "is_guaranteed_statutory": sch.is_guaranteed_statutory,
        "application_deadline_date": sch.application_deadline_date,
        "is_deadline_rolling": sch.is_deadline_rolling,
        "min_gpa_4": float(sch.min_gpa_4) if sch.min_gpa_4 is not None else None,
        "requires_financial_need": sch.requires_financial_need,
        "eligible_citizenships": sch.eligible_citizenships or [],
        "eligible_residency_states": sch.eligible_residency_states or [],
        "eligible_destination_countries": sch.eligible_destination_countries or [],
        "degree_levels": sch.degree_levels or ["bachelors"],
        "eligibility_status": elig_status,
        "funding_bucket": bucket,
        "match_score": score,
        "rule_evaluations": evals,
        "renewal_evaluations": renewal_evals,
        "satisfied_reasons": satisfied_reasons,
        "missing_requirements": missing_reqs,
        "conditional_requirements": conditional_reqs,
        "manual_review_reasons": manual_reasons,
        "failed_reasons": failed_reasons,
        "satisfied_items": satisfied_items,
        "failed_items": failed_items,
        "missing_items": missing_items,
        "conditional_items": conditional_items,
        "manual_review_items": manual_review_items,
        "freshness_warning_items": freshness_warning_items,
        "student_evidence_used": evidence_used,
        "funding_scope": _derive_funding_scope(sch),
        "duration_renewal_summary": _format_duration_renewal(sch),
        "freshness_warnings": freshness_warnings,
        "source_name": sch.source_name,
        "source_url": sch.source_url,
        "official_source_language": official_src_lang,
        "verified_at": sch.verified_at,
        "award_currency": str(sch.award_currency or "USD").strip().upper(),
        "award_fixed_usd": float(sch.award_fixed_usd) if sch.award_fixed_usd is not None else None,
        "native_amount_min": float(sch.native_amount_min) if sch.native_amount_min is not None else None,
        "native_amount_max": float(sch.native_amount_max) if sch.native_amount_max is not None else None,
        "covers_travel": bool(sch.covers_travel),
        "funding_duration_years": float(sch.funding_duration_years) if sch.funding_duration_years is not None else None,
        "max_funding_periods": sch.max_funding_periods,
        "renewal_conditions": sch.renewal_conditions,
        "sponsoring_institution": sch.sponsoring_institution,
        "source_type": sch.source_type or "unknown",
        "source_version": sch.source_version,
        "academic_year": sch.academic_year,
        "verification_method": sch.verification_method or "unknown",
        "verified_by": sch.verified_by,
        "verification_expires_at": sch.verification_expires_at,
        "freshness_status": freshness,
        "application_cycle_status": app_cycle_status,
        "cycle_verification_state": cycle_verification_state,
        "cycle_reason_code": cycle_reason_code,
        "cycle_params": cycle_params,
        "cycle_status_detail": cycle_status_detail,
        "is_cycle_open": is_cycle_open,
        "is_amount_verified": is_amt_verified,
        "is_actionable_for_student": is_actionable_student,
        "aid_classification": aid_cls,
        "is_variable_aid": is_variable_aid,
        "transfer_pathway_classification": tx_pathway_cls,
        "transfer_eligibility_detail": tx_pathway_detail,
        "official_supporting_sources": official_sources,
        "claim_freshness": claim_breakdown["claims"],
        "requires_manual_review": bool(sch.requires_manual_review),
        "claim_provenance": sch.claim_provenance or {},
        "conflict_notes": sch.conflict_notes,
        "amount_classification": ((sch.claim_provenance or {}).get("audit_metadata") or {}).get("amount_classification"),
        "transfer_supported": ((sch.claim_provenance or {}).get("audit_metadata") or {}).get("transfer_supported"),
    }


def compute_student_coverage_metrics(
    evaluated_results: List[Dict[str, Any]],
    ctx: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Computes separated, non-blended student-level scholarship coverage denominators
    and detects student-specific funding/pathway gaps cleanly.
    """
    total_evaluated = len(evaluated_results)
    matched = [r for r in evaluated_results if r["eligibility_status"] in ("eligible", "conditionally_eligible")]
    verified_elig = [r for r in evaluated_results if r["eligibility_status"] == "eligible"]
    verified_funding = [r for r in matched if r.get("is_amount_verified")]
    open_cycle = [r for r in matched if r.get("is_cycle_open")]
    actionable = [r for r in matched if r.get("is_actionable_for_student")]
    insufficient_info = [r for r in evaluated_results if r["eligibility_status"] == "insufficient_information"]
    manual_review = [r for r in evaluated_results if r["eligibility_status"] == "requires_manual_review"]
    variable_matched = [r for r in matched if r.get("is_variable_aid")]
    closed_cycle_matched = [r for r in matched if not r.get("is_cycle_open")]
    unconfirmed_transfer_flagged = [
        r for r in evaluated_results
        if r.get("transfer_pathway_classification") == "ug_transfer_unconfirmed"
        and r["eligibility_status"] == "requires_manual_review"
    ]

    aid_breakdown: Dict[str, int] = {}
    tx_breakdown: Dict[str, int] = {}
    for r in evaluated_results:
        ac = r.get("aid_classification") or "unpublished_or_manual_review"
        aid_breakdown[ac] = aid_breakdown.get(ac, 0) + 1
        tp = r.get("transfer_pathway_classification") or "ug_transfer_unconfirmed"
        tx_breakdown[tp] = tx_breakdown.get(tp, 0) + 1

    gaps: List[str] = []
    gap_details: List[Dict[str, str]] = []
    if len(verified_funding) == 0:
        gaps.append("no_verified_funding")
        gap_details.append(
            {
                "gap_code": "no_verified_funding",
                "title": "No Fixed Verified Funding Matched",
                "detail": "None of the matched scholarships currently publish a verified fixed or bounded award amount in this profile; variable or manual-review programs cannot guarantee exact dollar discounts.",
            }
        )
    if len(actionable) == 0:
        gaps.append("no_actionable_opportunities")
        gap_details.append(
            {
                "gap_code": "no_actionable_opportunities",
                "title": "No Actionable Open Verified Funding",
                "detail": "0 matched scholarships currently satisfy BOTH verified published funding amounts AND an open/rolling application deadline.",
            }
        )
    if matched and len(verified_funding) == 0 and len(variable_matched) == len(matched):
        gaps.append("only_variable_institutional_aid")
        gap_details.append(
            {
                "gap_code": "only_variable_institutional_aid",
                "title": "Only Variable / Formulaic Aid Matched",
                "detail": "Available matches rely on institutional CSS Profile / financial-aid office calculations or unpublished award amounts.",
            }
        )
    if matched and len(open_cycle) == 0 and len(closed_cycle_matched) > 0:
        gaps.append("only_expired_cycles")
        gap_details.append(
            {
                "gap_code": "only_expired_cycles",
                "title": "All Matched Programs Have Closed or Unverified Deadlines",
                "detail": "Matched programs exist in the catalog, but current application deadlines have closed or require checking next cycle dates.",
            }
        )
    if ctx.get("applicant_type") == "transfer" and len(matched) == 0 and len(unconfirmed_transfer_flagged) > 0:
        gaps.append("only_unconfirmed_transfer")
        gap_details.append(
            {
                "gap_code": "only_unconfirmed_transfer",
                "title": "Only Unconfirmed Transfer Scholarships",
                "detail": "Undergraduate matches lack confirmed transfer eligibility and require official verification before relying on them.",
            }
        )

    next_steps: List[str] = []
    if insufficient_info:
        next_steps.append(
            f"Complete missing profile evidence (e.g., exam scores, language tests, enrollment history, or DOB) to resolve {len(insufficient_info)} 'Insufficient Info' scholarships."
        )
    if unconfirmed_transfer_flagged:
        next_steps.append(
            f"Confirm transfer student eligibility directly with sponsors for {len(unconfirmed_transfer_flagged)} general undergraduate programs currently flagged for manual transfer review."
        )
    if closed_cycle_matched:
        next_steps.append(
            f"Track next-cycle opening dates on official sponsor sites for {len(closed_cycle_matched)} currently closed matched programs."
        )

    return {
        "programs_evaluated": total_evaluated,
        "programs_matched": len(matched),
        "programs_verified_eligibility": len(verified_elig),
        "programs_verified_funding": len(verified_funding),
        "programs_open_cycle": len(open_cycle),
        "programs_actionable_open_verified": len(actionable),
        "programs_insufficient_info": len(insufficient_info),
        "programs_manual_review": len(manual_review),
        "programs_variable_aid_matched": len(variable_matched),
        "programs_expired_cycle_matched": len(closed_cycle_matched),
        "programs_transfer_unconfirmed": len(unconfirmed_transfer_flagged),
        "aid_classification_breakdown": aid_breakdown,
        "transfer_pathway_breakdown": tx_breakdown,
        "gap_codes": gaps,
        "profile_coverage_gaps": gap_details,
        "next_steps_for_student": next_steps,
    }


def match_scholarships_deterministic(
    db: Session,
    profile: Optional[StudentProfile],
    overrides: Dict[str, Any],
    include_ineligible: bool = True,
) -> Dict[str, Any]:
    ensure_phase4_seeded(db)
    ctx = _derive_student_context(db, profile, overrides)

    qry = (
        db.query(ScholarshipProgram)
        .options(joinedload(ScholarshipProgram.institution), joinedload(ScholarshipProgram.rules))
        .filter(ScholarshipProgram.is_verified == True, ScholarshipProgram.is_current == True)
    )
    if ctx["institution_id"]:
        inst_uuid = UUID(str(ctx["institution_id"]))
        qry = qry.filter((ScholarshipProgram.institution_id == inst_uuid) | (ScholarshipProgram.institution_id.is_(None)))

    active_programs = []
    for p in qry.all():
        cb = evaluate_scholarship_claim_breakdown(p)
        freshness = evaluate_scholarship_freshness(p)
        # Exclude expired records while retaining active source_unavailable/conflicting programs under
        # funding_bucket='review_required' so students/reviewers see transparent warnings (Net Price still excludes them).
        if cb["record_expired"]:
            continue
        if freshness == "expired" and not cb["existence_current"]:
            continue
        allowed_levels = [str(d).strip().lower() for d in (p.degree_levels or []) if str(d).strip()]
        if ctx["degree_level"] and allowed_levels and ctx["degree_level"] not in allowed_levels:
            continue
        active_programs.append(p)

    evaluated = [evaluate_single_scholarship(p, ctx) for p in active_programs]

    rank_order = {
        "eligible": 0,
        "conditionally_eligible": 1,
        "insufficient_information": 2,
        "requires_manual_review": 3,
        "ineligible": 4,
    }
    evaluated.sort(
        key=lambda r: (
            rank_order.get(r["eligibility_status"], 5),
            0 if r["funding_bucket"] == "verified_applicable" else 1,
            not r["is_guaranteed_statutory"],
            -(r["award_amount_max_usd"] or 0.0),
            r["title"],
        )
    )

    counts = {k: 0 for k in AGGREGATION_PRECEDENCE}
    for r in evaluated:
        counts[r["eligibility_status"]] = counts.get(r["eligibility_status"], 0) + 1

    filtered = evaluated if include_ineligible else [r for r in evaluated if r["eligibility_status"] != "ineligible"]

    coverage_metrics = compute_verified_funding_coverage(db)
    student_metrics = compute_student_coverage_metrics(evaluated, ctx)

    return {
        "evaluated_profile": ctx,
        "total_scholarships": len(evaluated),
        "eligible_count": counts["eligible"],
        "conditionally_eligible_count": counts["conditionally_eligible"],
        "insufficient_information_count": counts["insufficient_information"],
        "requires_manual_review_count": counts["requires_manual_review"],
        "ineligible_count": counts["ineligible"],
        **coverage_metrics,
        "student_coverage_summary": student_metrics,
        "aggregation_precedence": list(AGGREGATION_PRECEDENCE),
        "results": filtered,
        "disclaimer": FINANCIAL_DISCLAIMER,
    }


def _permitted_cost_keys(sch_dict: Dict[str, Any]) -> Tuple[List[str], bool]:
    """
    Maps a scholarship's verified coverage flags strictly to permitted cost keys.
    Returns (permitted_keys, has_defined_scope).
    - Tuition-only -> ["tuition"] (+ "mandatory_fees" only if covers_fees)
    - Living stipend -> ["room_board", "books_supplies", "transportation", "personal_expenses"] (NEVER tuition/fees)
    - Travel allowance -> ["transportation"] ONLY
    - Unknown scope -> ([], False)
    """
    keys: List[str] = []
    if sch_dict["covers_tuition"]:
        keys.append("tuition")
    if sch_dict["covers_fees"]:
        keys.append("mandatory_fees")
    if sch_dict["covers_housing"] or sch_dict["covers_meals"]:
        if "room_board" not in keys:
            keys.append("room_board")
    if sch_dict["covers_health_insurance"]:
        keys.append("health_insurance")
    if sch_dict["covers_travel"]:
        keys.append("transportation")
    if sch_dict["provides_living_stipend"]:
        for living_k in ("room_board", "books_supplies", "transportation", "personal_expenses"):
            if living_k not in keys:
                keys.append(living_k)
    return keys, len(keys) > 0


def calculate_net_price(
    db: Session,
    institution: Institution,
    profile: Optional[StudentProfile],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    ensure_phase4_seeded(db)

    residency = (params.get("residency_classification") or "international").strip().lower()
    housing = (params.get("housing_preference") or "on_campus").strip().lower()
    applicant_type = (params.get("applicant_type") or "first_year").strip().lower()
    degree_level = (
        (params.get("degree_level") or (profile.intended_degree_level if profile else None) or "bachelors")
        .strip()
        .lower()
    )
    program_years = int(params.get("program_years") or (2 if applicant_type == "transfer" else 4))
    include_competitive = bool(params.get("include_competitive_aid", True))
    annual_budget = params.get("annual_budget_usd")

    cost_rows = (
        db.query(InstitutionCost)
        .filter(InstitutionCost.institution_id == institution.id, InstitutionCost.is_current == True)
        .all()
    )
    degree_cost_rows = [c for c in cost_rows if (c.degree_level or "bachelors").strip().lower() == degree_level]
    active_cost_rows = degree_cost_rows or cost_rows
    cost_by_type = {c.student_type: c for c in active_cost_rows}
    chosen_cost = (
        cost_by_type.get(residency)
        or (cost_by_type.get("out_of_state") if residency == "international" else None)
        or next(iter(active_cost_rows), None)
    )

    warnings: List[str] = []
    if not degree_cost_rows and cost_rows:
        warnings.append(f"Cost schedule reflects general/undergraduate figures; dedicated {degree_level} tuition schedule not separately published.")

    tuition_val: Optional[float] = None
    if chosen_cost and chosen_cost.tuition is not None:
        tuition_val = float(chosen_cost.tuition)
    elif residency == "in_state" and institution.tuition_in_state is not None:
        tuition_val = float(institution.tuition_in_state)
    elif institution.tuition_out_of_state is not None:
        tuition_val = float(institution.tuition_out_of_state)

    fees_val = float(chosen_cost.mandatory_fees) if chosen_cost and chosen_cost.mandatory_fees is not None else None
    room_board_val = float(chosen_cost.room_board) if chosen_cost and chosen_cost.room_board is not None else None

    if tuition_val is None and institution.avg_net_price is None and institution.cost_of_attendance is None:
        warnings.append("Official tuition schedule not yet reported for this institution.")

    if housing == "on_campus":
        housing_amt = room_board_val
        housing_note = None if room_board_val is not None else "On-campus housing & dining not itemized separately."
    elif housing == "with_family":
        housing_amt = 0.0
        housing_note = "Student selected living with family ($0 institutional housing)."
    else:
        housing_amt = room_board_val
        housing_note = "Uses campus COA living allowance benchmark for off-campus housing estimate."

    books_val = float(chosen_cost.books_supplies) if chosen_cost and chosen_cost.books_supplies is not None else None
    trans_val = float(chosen_cost.transportation) if chosen_cost and chosen_cost.transportation is not None else None
    pers_val = float(chosen_cost.personal_expenses) if chosen_cost and chosen_cost.personal_expenses is not None else None
    ins_val = float(chosen_cost.health_insurance) if chosen_cost and chosen_cost.health_insurance is not None else None

    if (
        chosen_cost is None
        and institution.cost_of_attendance is not None
        and tuition_val is not None
        and float(institution.cost_of_attendance) > tuition_val
    ):
        residual = round(float(institution.cost_of_attendance) - tuition_val - (room_board_val or 0.0), 2)
        if residual > 0:
            pers_val = residual
            warnings.append("Books, housing, and indirect living expenses derived from IPEDS/Scorecard total COA minus tuition.")

    if residency == "international" and ins_val is None:
        warnings.append("Mandatory international student health insurance is not itemized in federal COA data; budget ~$2,500–$4,500/yr extra.")

    target_currency = str((chosen_cost.currency if chosen_cost else None) or institution.currency or "USD").strip().upper()

    direct_items: List[Dict[str, Any]] = [
        {
            "key": "tuition",
            "label": f"Published Tuition ({residency.replace('_', ' ')})",
            "category": "direct_billable",
            "amount_usd": tuition_val,
            "currency": target_currency,
            "is_published": tuition_val is not None,
            "notes": None if tuition_val is not None else "Missing published tuition record.",
        },
        {
            "key": "mandatory_fees",
            "label": "Mandatory Institutional Fees",
            "category": "direct_billable",
            "amount_usd": fees_val,
            "currency": target_currency,
            "is_published": fees_val is not None,
            "notes": "Included in IPEDS combined tuition & fees when not broken out." if fees_val is None else None,
        },
        {
            "key": "room_board",
            "label": "Housing & Meals",
            "category": "direct_billable" if housing == "on_campus" else "indirect_living",
            "amount_usd": housing_amt,
            "currency": target_currency,
            "is_published": room_board_val is not None or housing == "with_family",
            "notes": housing_note,
        },
    ]

    indirect_items: List[Dict[str, Any]] = [
        {
            "key": "books_supplies",
            "label": "Books & Course Materials",
            "category": "indirect_living",
            "amount_usd": books_val,
            "currency": target_currency,
            "is_published": books_val is not None,
            "notes": None if books_val is not None else "Not published separately.",
        },
        {
            "key": "transportation",
            "label": "Transportation & Travel",
            "category": "indirect_living",
            "amount_usd": trans_val,
            "currency": target_currency,
            "is_published": trans_val is not None,
            "notes": None if trans_val is not None else "Not published separately (international flights extra).",
        },
        {
            "key": "personal_expenses",
            "label": "Personal Living Expenses",
            "category": "indirect_living",
            "amount_usd": pers_val,
            "currency": target_currency,
            "is_published": pers_val is not None,
            "notes": None if pers_val is not None else "Not published separately.",
        },
        {
            "key": "health_insurance",
            "label": "Student Health Insurance",
            "category": "indirect_living",
            "amount_usd": ins_val,
            "currency": target_currency,
            "is_published": ins_val is not None,
            "notes": (
                "Mandatory for F-1/J-1 international students if not waived (typically $2,000–$4,500/yr at US universities)."
                if residency == "international" and ins_val is None
                else None
            ),
        },
    ]

    all_cost_items = direct_items + [i for i in indirect_items]
    direct_sum = round(
        sum(i["amount_usd"] for i in all_cost_items if i["category"] == "direct_billable" and i["amount_usd"] is not None),
        2,
    ) if any(i["category"] == "direct_billable" and i["amount_usd"] is not None for i in all_cost_items) else None
    indirect_sum = round(
        sum(i["amount_usd"] for i in all_cost_items if i["category"] == "indirect_living" and i["amount_usd"] is not None),
        2,
    ) if any(i["category"] == "indirect_living" and i["amount_usd"] is not None for i in all_cost_items) else 0.0

    total_coa: Optional[float] = None
    if direct_sum is not None:
        total_coa = round(direct_sum + (indirect_sum or 0.0), 2)
    elif institution.cost_of_attendance is not None:
        total_coa = float(institution.cost_of_attendance)

    # Propagate FULL student context including degree_level to scholarship matching
    overrides = {
        "citizenship_country": params.get("citizenship_country") or ("US" if residency != "international" else None),
        "country_of_residence": params.get("country_of_residence"),
        "dual_citizenship": params.get("dual_citizenship"),
        "residency_state": params.get("residency_state") or (institution.state_province if residency == "in_state" else None),
        "applicant_type": applicant_type,
        "degree_level": degree_level,
        "date_of_birth": params.get("date_of_birth"),
        "field_of_study": params.get("field_of_study"),
        "gpa_4": params.get("gpa_4"),
        "financial_need_level": params.get("financial_need_level"),
        "household_income_usd": params.get("household_income_usd"),
        "destination_country": institution.country_code,
        "institution_id": institution.id,
    }
    sch_match = match_scholarships_deterministic(db, profile, overrides, include_ineligible=False)

    # Track exact remaining cost ceilings per category to prevent over-crediting or negative category nets
    orig_by_key: Dict[str, float] = {i["key"]: float(i["amount_usd"]) for i in all_cost_items if i["amount_usd"] is not None}
    rem_min_by_key: Dict[str, float] = dict(orig_by_key)
    rem_max_by_key: Dict[str, float] = dict(orig_by_key)
    applied_guar_min_by_key: Dict[str, float] = {i["key"]: 0.0 for i in all_cost_items}
    applied_guar_max_by_key: Dict[str, float] = {i["key"]: 0.0 for i in all_cost_items}
    applied_comp_min_by_key: Dict[str, float] = {i["key"]: 0.0 for i in all_cost_items}
    applied_comp_max_by_key: Dict[str, float] = {i["key"]: 0.0 for i in all_cost_items}
    applied_cond_max_by_key: Dict[str, float] = {i["key"]: 0.0 for i in all_cost_items}

    inc_val = params.get("household_income_usd")
    need_lvl = (params.get("financial_need_level") or "").strip().lower()
    coa_cap = total_coa if total_coa is not None else 0.0

    verified_applicable_aid: List[Dict[str, Any]] = []
    conditional_aid: List[Dict[str, Any]] = []
    insufficient_info_aid: List[Dict[str, Any]] = []
    review_required_aid: List[Dict[str, Any]] = []
    unallocated_potential_aid: List[Dict[str, Any]] = []
    aid_offsets: List[Dict[str, Any]] = []

    guar_min = 0.0
    guar_max = 0.0
    comp_min = 0.0
    comp_max = 0.0
    guar_recurring_min = 0.0
    guar_recurring_max = 0.0
    comp_recurring_min = 0.0
    comp_recurring_max = 0.0
    multi_year_unknown_warned = False

    def _raw_award_range(s: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        if s.get("award_fixed_usd") is not None:
            fv = float(s["award_fixed_usd"])
            return fv, fv
        amin = float(s["award_amount_min_usd"]) if s.get("award_amount_min_usd") is not None else None
        amax = float(s["award_amount_max_usd"]) if s.get("award_amount_max_usd") is not None else amin
        return amin, amax

    def _make_aid_entry(s: Dict[str, Any], bucket: str, alloc_cats: Dict[str, float], est_min: float, est_max: float, reason: Optional[str] = None) -> Dict[str, Any]:
        return {
            "scholarship_id": s["id"],
            "title": s["title"],
            "provider_type": s["provider_type"],
            "award_type": s["award_type"],
            "eligibility_status": s["eligibility_status"],
            "funding_bucket": bucket,
            "freshness_status": s["freshness_status"],
            "is_guaranteed_statutory": s["is_guaranteed_statutory"],
            "award_currency": s.get("award_currency") or "USD",
            "native_amount_min": s.get("native_amount_min"),
            "native_amount_max": s.get("native_amount_max"),
            "funding_scope": s.get("funding_scope", []),
            "allocated_categories": alloc_cats,
            "estimated_min_usd": round(est_min, 2),
            "estimated_max_usd": round(est_max, 2),
            "funding_duration_years": s.get("funding_duration_years"),
            "is_renewable": bool(s.get("is_renewable")),
            "renewal_conditions": s.get("renewal_conditions"),
            "reason": reason,
            "source_url": s["source_url"],
        }

    for s in sch_match["results"]:
        freshness = s["freshness_status"]
        amt_freshness = (s.get("claim_freshness") or {}).get("award_amounts")
        elig_st = s["eligibility_status"]
        cur = str(s.get("award_currency") or "").strip().upper()
        permitted_keys, has_scope = _permitted_cost_keys(s)
        amin_raw, amax_raw = _raw_award_range(s)

        # 1. Segregate unverified / variable formulaic / manual-review / conflicting freshness first
        if (
            elig_st == "requires_manual_review"
            or freshness in ("requires_manual_review", "conflicting_information", "source_unavailable", "expired")
            or amt_freshness in ("requires_manual_review", "conflicting_information", "source_unavailable", "expired")
            or (
                s.get("aid_classification") in ("css_profile_full_need", "variable_institutional_need", "variable_merit")
                and amin_raw is not None
            )
        ):
            reason = (
                "; ".join(s.get("manual_review_reasons") or [])
                or (
                    f"Award amount claim status '{amt_freshness}' excludes award from guaranteed/verified net-price deductions."
                    if amt_freshness in ("requires_manual_review", "conflicting_information", "source_unavailable", "expired")
                    else f"Freshness state '{freshness}' excludes award from guaranteed/verified net-price deductions."
                )
            )
            review_required_aid.append(_make_aid_entry(s, "review_required", {}, 0.0, 0.0, reason=reason))
            continue

        # 2. Insufficient profile information
        if elig_st == "insufficient_information":
            reason = "; ".join(s.get("missing_requirements") or []) or "Missing student information."
            insufficient_info_aid.append(_make_aid_entry(s, "potential", {}, 0.0, 0.0, reason=reason))
            continue

        # 3. Unknown scope, exchange-only mobility, unknown/non-matching currency, or missing dollar amount -> unallocated potential aid
        if (s.get("funding_type") or "").strip().lower() == "exchange_mobility":
            reason = "Exchange / short-term mobility grant is excluded from full-degree net-price cost calculations."
            unallocated_potential_aid.append(_make_aid_entry(s, "potential", {}, 0.0, 0.0, reason=reason))
            continue
        if not has_scope:
            reason = "Funding scope (tuition/housing/stipend) is unspecified; excluded from category net-price discounts."
            unallocated_potential_aid.append(_make_aid_entry(s, "potential", {}, 0.0, 0.0, reason=reason))
            continue
        if not cur or cur == "UNK" or cur != target_currency:
            reason = f"Award currency '{cur or 'UNKNOWN'}' does not match cost schedule '{target_currency}' (never converted with invented rates)."
            unallocated_potential_aid.append(_make_aid_entry(s, "potential", {}, 0.0, 0.0, reason=reason))
            continue
        if amin_raw is None or amax_raw is None or amax_raw <= 0.0:
            reason = "Published award amount missing; cannot compute deterministic dollar discount."
            unallocated_potential_aid.append(_make_aid_entry(s, "potential", {}, 0.0, 0.0, reason=reason))
            continue

        amin = float(amin_raw)
        amax = float(amax_raw)
        if s["award_type"] == "full_ride" and s["requires_financial_need"] and s["provider_type"] == "university":
            if inc_val is not None and coa_cap > 0:
                est_efc = max(0.0, (float(inc_val) - 75000.0) * 0.28)
                need_cap = max(0.0, coa_cap - est_efc)
                amax = min(amax, round(need_cap, 2))
                amin = min(amin, amax)
            elif need_lvl == "moderate" and coa_cap > 0:
                amax = min(amax, round(coa_cap * 0.65, 2))
                amin = min(amin, amax)

        if elig_st == "conditionally_eligible":
            # Conditional awards track category potential separately without inflating guaranteed aid
            cap_cond = min(amax, sum(max(0.0, rem_max_by_key.get(k, 0.0) - applied_cond_max_by_key.get(k, 0.0)) for k in permitted_keys))
            cond_cats: Dict[str, float] = {}
            rem = cap_cond
            for k in permitted_keys:
                avail = max(0.0, rem_max_by_key.get(k, 0.0) - applied_cond_max_by_key.get(k, 0.0))
                take = min(rem, avail)
                if take > 0:
                    applied_cond_max_by_key[k] += take
                    cond_cats[k] = round(take, 2)
                    rem -= take
            conditional_aid.append(
                _make_aid_entry(
                    s,
                    "conditional",
                    cond_cats,
                    0.0,
                    cap_cond,
                    reason="; ".join(s.get("conditional_requirements") or ["Pending future condition fulfillment."]),
                )
            )
            continue

        # 4. Eligible + verified current/approaching award -> allocate strictly against remaining permitted category balances
        if not s["is_guaranteed_statutory"] and not include_competitive:
            unallocated_potential_aid.append(
                _make_aid_entry(s, "potential", {}, 0.0, 0.0, reason="Competitive award excluded per user toggle.")
            )
            continue

        alloc_cats: Dict[str, float] = {}
        rem_to_alloc_max = amax
        total_alloc_max = 0.0
        for k in permitted_keys:
            if k not in rem_max_by_key or rem_to_alloc_max <= 0:
                continue
            avail = rem_max_by_key[k]
            take = min(rem_to_alloc_max, avail)
            if take > 0:
                rem_max_by_key[k] = round(avail - take, 2)
                alloc_cats[k] = round(take, 2)
                total_alloc_max += take
                rem_to_alloc_max -= take

        rem_to_alloc_min = min(amin, total_alloc_max)
        total_alloc_min = 0.0
        for k in permitted_keys:
            if k not in rem_min_by_key or rem_to_alloc_min <= 0:
                continue
            avail_min = rem_min_by_key[k]
            take_min = min(rem_to_alloc_min, avail_min)
            if take_min > 0:
                rem_min_by_key[k] = round(avail_min - take_min, 2)
                total_alloc_min += take_min
                rem_to_alloc_min -= take_min

        if total_alloc_max <= 0.0:
            unallocated_potential_aid.append(
                _make_aid_entry(
                    s,
                    "potential",
                    {},
                    0.0,
                    0.0,
                    reason=f"Permitted expense categories ({', '.join(permitted_keys)}) already fully covered or $0 at institution.",
                )
            )
            continue

        for k, val_taken in alloc_cats.items():
            if s["is_guaranteed_statutory"]:
                applied_guar_max_by_key[k] = round(applied_guar_max_by_key.get(k, 0.0) + val_taken, 2)
            else:
                applied_comp_max_by_key[k] = round(applied_comp_max_by_key.get(k, 0.0) + val_taken, 2)

        # Conservative min proportional tracking per key
        rem_track_min = total_alloc_min
        for k in alloc_cats:
            take_k = min(rem_track_min, alloc_cats[k])
            if take_k > 0:
                if s["is_guaranteed_statutory"]:
                    applied_guar_min_by_key[k] = round(applied_guar_min_by_key.get(k, 0.0) + take_k, 2)
                else:
                    applied_comp_min_by_key[k] = round(applied_comp_min_by_key.get(k, 0.0) + take_k, 2)
                rem_track_min -= take_k

        entry = _make_aid_entry(s, "verified_applicable", alloc_cats, total_alloc_min, total_alloc_max)
        verified_applicable_aid.append(entry)
        aid_offsets.append(entry)

        if s["is_guaranteed_statutory"]:
            guar_min += total_alloc_min
            guar_max += total_alloc_max
        else:
            comp_min += total_alloc_min
            comp_max += total_alloc_max

        # Duration/renewal check for multi-year projections (Years 2..program_years)
        dur_yrs = s.get("funding_duration_years")
        max_p = s.get("max_funding_periods")
        extra_years_eligible = 0
        if s.get("is_renewable"):
            if dur_yrs is not None and dur_yrs > 1:
                extra_years_eligible = max(0, min(program_years - 1, int(dur_yrs) - 1))
            elif max_p is not None and max_p > 1:
                extra_years_eligible = max(0, min(program_years - 1, int(max_p) - 1))
            else:
                if not multi_year_unknown_warned:
                    warnings.append("Awards without explicit multi-year duration/periods are applied to Year 1 only rather than projected across all years.")
                    multi_year_unknown_warned = True

        if extra_years_eligible > 0:
            if s["is_guaranteed_statutory"]:
                guar_recurring_min += total_alloc_min * extra_years_eligible
                guar_recurring_max += total_alloc_max * extra_years_eligible
            else:
                comp_recurring_min += total_alloc_min * extra_years_eligible
                comp_recurring_max += total_alloc_max * extra_years_eligible

    guar_min = round(min(coa_cap, guar_min), 2) if total_coa else 0.0
    guar_max = round(min(coa_cap, guar_max), 2) if total_coa else 0.0
    comp_min = round(min(max(0.0, coa_cap - guar_min), comp_min), 2) if total_coa else 0.0
    comp_max = round(min(max(0.0, coa_cap - guar_min), comp_max), 2) if total_coa else 0.0

    eligible_min = round(min(coa_cap, guar_min + (comp_min if include_competitive else 0.0)), 2) if total_coa else 0.0
    eligible_max = round(min(coa_cap, guar_max + (comp_max if include_competitive else 0.0)), 2) if total_coa else 0.0

    net_min = round(max(0.0, total_coa - eligible_max), 2) if total_coa is not None else None
    net_max = round(max(0.0, total_coa - eligible_min), 2) if total_coa is not None else None

    if net_min is not None and net_max is not None and program_years > 1 and total_coa is not None:
        subsequent_gross = round(total_coa * (program_years - 1), 2)
        subsequent_aid_min = round(min(subsequent_gross, guar_recurring_min + (comp_recurring_min if include_competitive else 0.0)), 2)
        subsequent_aid_max = round(min(subsequent_gross, guar_recurring_max + (comp_recurring_max if include_competitive else 0.0)), 2)
        multi_min = round(max(0.0, net_min + (subsequent_gross - subsequent_aid_max)), 2)
        multi_max = round(max(0.0, net_max + (subsequent_gross - subsequent_aid_min)), 2)
    else:
        multi_min = net_min
        multi_max = net_max

    category_breakdown: List[Dict[str, Any]] = []
    for item in all_cost_items:
        k = item["key"]
        orig = item["amount_usd"]
        v_min = round(applied_guar_min_by_key.get(k, 0.0) + (applied_comp_min_by_key.get(k, 0.0) if include_competitive else 0.0), 2)
        v_max = round(applied_guar_max_by_key.get(k, 0.0) + (applied_comp_max_by_key.get(k, 0.0) if include_competitive else 0.0), 2)
        if orig is not None:
            v_max = min(orig, v_max)
            v_min = min(orig, v_min)
            rem_min = round(max(0.0, orig - v_max), 2)
            rem_max = round(max(0.0, orig - v_min), 2)
        else:
            rem_min = None
            rem_max = None
        category_breakdown.append(
            {
                "category_key": k,
                "label": item["label"],
                "cost_group": item["category"],
                "original_cost_usd": orig,
                "applied_verified_min_usd": v_min,
                "applied_verified_max_usd": v_max,
                "applied_conditional_max_usd": round(applied_cond_max_by_key.get(k, 0.0), 2),
                "remaining_cost_min_usd": rem_min,
                "remaining_cost_max_usd": rem_max,
            }
        )

    gap_min = round(net_min - float(annual_budget), 2) if (net_min is not None and annual_budget is not None) else None
    gap_max = round(net_max - float(annual_budget), 2) if (net_max is not None and annual_budget is not None) else None

    if total_coa is None:
        affordability = "missing_cost_data"
    elif annual_budget is None:
        affordability = "within_budget" if (net_max or 0) <= 0 else "reachable_with_competitive_aid" if eligible_max > 0 else "exceeds_budget"
    else:
        b = float(annual_budget)
        if net_max is not None and net_max <= b:
            affordability = "within_budget"
        elif net_min is not None and net_min <= b:
            affordability = "reachable_with_competitive_aid"
        else:
            affordability = "exceeds_budget"

    confidence = "high" if chosen_cost is not None else ("medium" if total_coa is not None else "low")
    sources = [
        {
            "name": institution.primary_source or "NCES IPEDS / Institutional Cost Schedule",
            "url": (chosen_cost.source_url if chosen_cost and chosen_cost.source_url else None)
            or institution.financial_aid_website
            or institution.official_website,
        }
    ]

    return {
        "institution_id": institution.id,
        "institution_name": institution.official_name,
        "country_code": institution.country_code,
        "residency_classification": residency,
        "housing_preference": housing,
        "applicant_type": applicant_type,
        "degree_level": degree_level,
        "academic_year": chosen_cost.academic_year if chosen_cost else institution.data_reporting_year,
        "currency": target_currency,
        "direct_billable_items": direct_items,
        "indirect_living_items": [i for i in indirect_items if i["category"] == "indirect_living"],
        "category_breakdown": category_breakdown,
        "gross_direct_cost_usd": direct_sum,
        "gross_indirect_cost_usd": indirect_sum,
        "total_coa_usd": total_coa,
        "guaranteed_aid_min_usd": guar_min,
        "guaranteed_aid_max_usd": guar_max,
        "competitive_aid_min_usd": comp_min,
        "competitive_aid_max_usd": comp_max,
        "eligible_aid_min_usd": eligible_min,
        "eligible_aid_max_usd": eligible_max,
        "estimated_net_price_min_usd": net_min,
        "estimated_net_price_max_usd": net_max,
        "multi_year_net_min_usd": multi_min,
        "multi_year_net_max_usd": multi_max,
        "annual_budget_usd": float(annual_budget) if annual_budget is not None else None,
        "budget_gap_min_usd": gap_min,
        "budget_gap_max_usd": gap_max,
        "affordability_status": affordability,
        "aid_offsets": aid_offsets,
        "verified_applicable_aid": verified_applicable_aid,
        "conditional_aid": conditional_aid,
        "insufficient_info_aid": insufficient_info_aid,
        "review_required_aid": review_required_aid,
        "unallocated_potential_aid": unallocated_potential_aid,
        "data_confidence": confidence,
        "warnings": warnings,
        "sources": sources,
        "disclaimer": FINANCIAL_DISCLAIMER,
    }
