"""
Phase 4 Data Provenance, Differentiated Expiration & Freshness Governance Service.

Enforces:
1. Canonical freshness classifications:
   - current
   - approaching_expiration
   - expired
   - source_unavailable
   - conflicting_information
   - requires_manual_review
2. Differentiated verification-expiration policies by volatility domain:
   - scholarship_deadlines: 90 days (approaching window: 14 days)
   - scholarship_amounts: 120 days (approaching window: 21 days)
   - scholarship_eligibility: 180 days (approaching window: 30 days)
   - qualification_frameworks: 365 days (approaching window: 45 days)
   - credential_recognition: 365 days (approaching window: 45 days)
   - grade_conversion_rules: 730 days (approaching window: 60 days)
3. Non-destructive preservation of historical/expired records.
4. Independent validation auditing for official primary URLs, duplicates,
   provenance completeness, expired entries, and conflicting rules/values.
"""

from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from sqlalchemy.orm import Session, joinedload

from app.models.credentials import CredentialRecognitionRule, GradeConversionRule
from app.models.rag import ScholarshipProgram
from app.models.requirements import CountryQualification

FRESHNESS_STATES = (
    "current",
    "approaching_expiration",
    "expired",
    "source_unavailable",
    "conflicting_information",
    "requires_manual_review",
)

VERIFICATION_POLICY_INTERVALS: Dict[str, Dict[str, int]] = {
    "scholarship_deadlines": {"max_age_days": 90, "approaching_window_days": 14},
    "scholarship_amounts": {"max_age_days": 120, "approaching_window_days": 21},
    "scholarship_eligibility": {"max_age_days": 180, "approaching_window_days": 30},
    "qualification_frameworks": {"max_age_days": 365, "approaching_window_days": 45},
    "credential_recognition": {"max_age_days": 365, "approaching_window_days": 45},
    "grade_conversion_rules": {"max_age_days": 730, "approaching_window_days": 60},
}

UNOFFICIAL_AGGREGATOR_HOSTS = {
    "scholarships.com",
    "www.scholarships.com",
    "fastweb.com",
    "www.fastweb.com",
    "niche.com",
    "www.niche.com",
    "cappex.com",
    "www.cappex.com",
    "bold.org",
    "www.bold.org",
    "scholarshipowl.com",
    "www.scholarshipowl.com",
    "scholars4dev.com",
    "www.scholars4dev.com",
    "afterschoolafrica.com",
    "www.afterschoolafrica.com",
    "opportunitydesk.org",
    "www.opportunitydesk.org",
    "opportunitiesforafricans.com",
    "www.opportunitiesforafricans.com",
    "iefa.org",
    "www.iefa.org",
}


def _utcnow(now: Optional[datetime] = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def compute_verification_expiry(
    verified_at: Optional[datetime],
    policy_kind: str,
) -> Optional[datetime]:
    """
    Computes an expiration timestamp strictly from an observed verified_at timestamp
    and a differentiated domain policy. Returns None if verified_at was never recorded.
    """
    if verified_at is None:
        return None
    base = verified_at if verified_at.tzinfo else verified_at.replace(tzinfo=timezone.utc)
    policy = VERIFICATION_POLICY_INTERVALS.get(policy_kind, VERIFICATION_POLICY_INTERVALS["scholarship_eligibility"])
    return base + timedelta(days=policy["max_age_days"])


def is_valid_official_url(url: Optional[str], *, require_https: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validates that a source URL uses an official web scheme, valid public hostname,
    and is not a localhost/private IP literal or blocked secondary aggregator.
    """
    if not url or not str(url).strip():
        return False, "Missing official source URL."
    parsed = urlparse(str(url).strip())
    scheme = (parsed.scheme or "").lower()
    if require_https and scheme != "https":
        return False, f"Source URL must use HTTPS (found '{scheme or 'none'}')."
    if not require_https and scheme not in ("https", "http"):
        return False, f"Invalid URL scheme '{scheme or 'none'}'."
    host = (parsed.hostname or "").lower()
    if not host or "." not in host:
        return False, "Source URL lacks a valid public domain."
    if host in ("localhost", "localhost.localdomain") or host.endswith(".local"):
        return False, f"Local hostname '{host}' is not a valid institutional URL."
    try:
        ip_address(host)
        return False, f"Raw IP address '{host}' is not allowed as an official institutional URL."
    except ValueError:
        pass
    if host in UNOFFICIAL_AGGREGATOR_HOSTS:
        return False, f"Secondary aggregator host '{host}' cannot verify official eligibility or award amounts."
    return True, None


def classify_freshness(
    *,
    verified_at: Optional[datetime],
    verification_expires_at: Optional[datetime],
    policy_kind: str,
    source_url: Optional[str] = None,
    require_source_url: bool = True,
    has_conflict: bool = False,
    source_unavailable: bool = False,
    requires_manual_review: bool = False,
    now: Optional[datetime] = None,
) -> str:
    """Determines canonical freshness classification without modifying historical data."""
    ref_now = _utcnow(now)

    if has_conflict:
        return "conflicting_information"
    if source_unavailable:
        return "source_unavailable"
    if require_source_url:
        ok, _ = is_valid_official_url(source_url)
        if not ok:
            return "source_unavailable"

    if verification_expires_at is not None:
        exp = (
            verification_expires_at
            if verification_expires_at.tzinfo
            else verification_expires_at.replace(tzinfo=timezone.utc)
        )
        if exp <= ref_now:
            return "expired"
        if requires_manual_review or verified_at is None:
            return "requires_manual_review"
        window_days = VERIFICATION_POLICY_INTERVALS.get(
            policy_kind, VERIFICATION_POLICY_INTERVALS["scholarship_eligibility"]
        )["approaching_window_days"]
        if (exp - ref_now) <= timedelta(days=window_days):
            return "approaching_expiration"
        return "current"

    # Never fabricate missing expiry/verification dates; mark unreviewed / unknown as requires_manual_review
    return "requires_manual_review"


def evaluate_scholarship_claim_breakdown(
    sch: ScholarshipProgram,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Returns independent freshness classifications per provenance claim domain
    (`program_existence`, `award_amounts`, `eligibility_rules`, `deadlines`) so
    an expired deadline claim flags the cycle closed without erasing verified
    program existence or conflating deadlines with amount expiration.
    """
    ref_now = _utcnow(now)
    record_conflict = bool(sch.conflict_notes)
    if sch.award_amount_min_usd is not None and sch.award_amount_max_usd is not None:
        if float(sch.award_amount_min_usd) > float(sch.award_amount_max_usd):
            record_conflict = True
    if sch.native_amount_min is not None and sch.native_amount_max is not None:
        if float(sch.native_amount_min) > float(sch.native_amount_max):
            record_conflict = True

    record_exp = _parse_iso_dt(sch.verification_expires_at)
    record_state = classify_freshness(
        verified_at=sch.verified_at,
        verification_expires_at=record_exp,
        policy_kind="scholarship_eligibility",
        source_url=sch.source_url,
        has_conflict=record_conflict,
        requires_manual_review=bool(sch.requires_manual_review) or not sch.is_verified,
        now=ref_now,
    )

    claims = sch.claim_provenance if isinstance(sch.claim_provenance, dict) else {}
    policy_for_key = {
        "program_existence": "scholarship_eligibility",
        "eligibility_rules": "scholarship_eligibility",
        "award_amounts": "scholarship_amounts",
        "deadlines": "scholarship_deadlines",
    }
    claim_states: Dict[str, str] = {}
    for key, policy_kind in policy_for_key.items():
        c = claims.get(key)
        if not isinstance(c, dict):
            claim_states[key] = record_state
            continue
        c_ver = _parse_iso_dt(c.get("verified_at")) or sch.verified_at
        c_exp = _parse_iso_dt(c.get("expires_at")) or compute_verification_expiry(c_ver, policy_kind)
        claim_states[key] = classify_freshness(
            verified_at=c_ver,
            verification_expires_at=c_exp,
            policy_kind=policy_kind,
            source_url=c.get("source_url") or sch.source_url,
            has_conflict=bool(c.get("has_conflict")) or record_conflict,
            source_unavailable=bool(c.get("source_unavailable")),
            requires_manual_review=bool(c.get("requires_manual_review")),
            now=ref_now,
        )

    deadline_expired = claim_states["deadlines"] == "expired"
    amount_expired = claim_states["award_amounts"] == "expired"
    record_expired = record_exp is not None and record_exp <= ref_now
    existence_current = (
        not record_expired
        and not record_conflict
        and claim_states["program_existence"] in ("current", "approaching_expiration")
    )

    return {
        "record_state": record_state,
        "claims": claim_states,
        "record_expired": record_expired,
        "existence_current": existence_current,
        "amount_expired": amount_expired,
        "deadline_expired": deadline_expired,
    }


def evaluate_scholarship_freshness(
    sch: ScholarshipProgram,
    now: Optional[datetime] = None,
) -> str:
    """
    Evaluates overall scholarship freshness across record metadata and
    per-claim provenance (deadlines 90d, amounts 120d, eligibility 180d).
    """
    ref_now = _utcnow(now)
    has_conflict = bool(sch.conflict_notes)
    if sch.award_amount_min_usd is not None and sch.award_amount_max_usd is not None:
        if float(sch.award_amount_min_usd) > float(sch.award_amount_max_usd):
            has_conflict = True

    claims = sch.claim_provenance or {}
    claim_states: List[str] = []
    claim_policy_map = {
        "deadlines": "scholarship_deadlines",
        "award_amounts": "scholarship_amounts",
        "eligibility_rules": "scholarship_eligibility",
    }
    if isinstance(claims, dict):
        for key, policy_kind in claim_policy_map.items():
            c = claims.get(key)
            if not isinstance(c, dict):
                continue
            c_ver_raw = c.get("verified_at")
            c_exp_raw = c.get("expires_at")
            c_ver = _parse_iso_dt(c_ver_raw)
            c_exp = _parse_iso_dt(c_exp_raw) or compute_verification_expiry(c_ver, policy_kind)
            c_state = classify_freshness(
                verified_at=c_ver,
                verification_expires_at=c_exp,
                policy_kind=policy_kind,
                source_url=c.get("source_url") or sch.source_url,
                has_conflict=bool(c.get("has_conflict")),
                source_unavailable=bool(c.get("source_unavailable")),
                requires_manual_review=bool(c.get("requires_manual_review")),
                now=ref_now,
            )
            claim_states.append(c_state)

    record_state = classify_freshness(
        verified_at=sch.verified_at,
        verification_expires_at=sch.verification_expires_at,
        policy_kind="scholarship_eligibility",
        source_url=sch.source_url,
        has_conflict=has_conflict,
        source_unavailable=False,
        requires_manual_review=bool(sch.requires_manual_review) or not sch.is_verified,
        now=ref_now,
    )

    all_states = [record_state] + claim_states
    for priority in (
        "conflicting_information",
        "source_unavailable",
        "expired",
        "requires_manual_review",
        "approaching_expiration",
    ):
        if priority in all_states:
            return priority
    return "current"


def evaluate_scholarship_claim_breakdown(
    sch: ScholarshipProgram,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Returns independent freshness classifications per provenance claim domain
    (`program_existence`, `award_amounts`, `eligibility_rules`, `deadlines`) so
    an expired deadline claim flags the cycle closed without erasing verified
    program existence or conflating deadlines with amount expiration.
    """
    ref_now = _utcnow(now)
    record_conflict = bool(sch.conflict_notes)
    if sch.award_amount_min_usd is not None and sch.award_amount_max_usd is not None:
        if float(sch.award_amount_min_usd) > float(sch.award_amount_max_usd):
            record_conflict = True
    if sch.native_amount_min is not None and sch.native_amount_max is not None:
        if float(sch.native_amount_min) > float(sch.native_amount_max):
            record_conflict = True

    record_exp = _parse_iso_dt(sch.verification_expires_at)
    record_state = classify_freshness(
        verified_at=sch.verified_at,
        verification_expires_at=record_exp,
        policy_kind="scholarship_eligibility",
        source_url=sch.source_url,
        has_conflict=record_conflict,
        requires_manual_review=bool(sch.requires_manual_review) or not sch.is_verified,
        now=ref_now,
    )

    claims = sch.claim_provenance if isinstance(sch.claim_provenance, dict) else {}
    policy_for_key = {
        "program_existence": "scholarship_eligibility",
        "eligibility_rules": "scholarship_eligibility",
        "award_amounts": "scholarship_amounts",
        "deadlines": "scholarship_deadlines",
    }
    claim_states: Dict[str, str] = {}
    for key, policy_kind in policy_for_key.items():
        c = claims.get(key)
        if not isinstance(c, dict):
            claim_states[key] = record_state
            continue
        c_ver = _parse_iso_dt(c.get("verified_at")) or sch.verified_at
        c_exp = _parse_iso_dt(c.get("expires_at")) or compute_verification_expiry(c_ver, policy_kind)
        claim_states[key] = classify_freshness(
            verified_at=c_ver,
            verification_expires_at=c_exp,
            policy_kind=policy_kind,
            source_url=c.get("source_url") or sch.source_url,
            has_conflict=bool(c.get("has_conflict")) or record_conflict,
            source_unavailable=bool(c.get("source_unavailable")),
            requires_manual_review=bool(c.get("requires_manual_review")),
            now=ref_now,
        )

    deadline_expired = claim_states["deadlines"] == "expired"
    amount_expired = claim_states["award_amounts"] == "expired"
    record_expired = record_exp is not None and record_exp <= ref_now
    existence_current = (
        not record_expired
        and not record_conflict
        and claim_states["program_existence"] in ("current", "approaching_expiration")
    )

    return {
        "record_state": record_state,
        "claims": claim_states,
        "record_expired": record_expired,
        "existence_current": existence_current,
        "amount_expired": amount_expired,
        "deadline_expired": deadline_expired,
    }


def _parse_iso_dt(val: Any) -> Optional[datetime]:
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str) and val.strip():
        try:
            dt = datetime.fromisoformat(val.strip().replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def sweep_phase4_freshness(
    db: Session,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Recomputes freshness classifications across scholarships and credential/qualification tables.
    NEVER deletes expired records; preserves all historical records in PostgreSQL.
    """
    ref_now = _utcnow(now)
    counts: Dict[str, int] = {k: 0 for k in FRESHNESS_STATES}

    for sch in db.query(ScholarshipProgram).all():
        status = evaluate_scholarship_freshness(sch, now=ref_now)
        sch.freshness_status = status
        if status in ("expired", "source_unavailable", "conflicting_information"):
            sch.is_current = False
        counts[status] += 1

    for gr in db.query(GradeConversionRule).all():
        status = classify_freshness(
            verified_at=gr.verified_at,
            verification_expires_at=gr.verification_expires_at,
            policy_kind="grade_conversion_rules",
            source_url=gr.source_url,
            require_source_url=bool(gr.source_url),
            now=ref_now,
        )
        gr.freshness_status = status
        counts[status] += 1

    for rr in db.query(CredentialRecognitionRule).all():
        status = classify_freshness(
            verified_at=rr.verified_at,
            verification_expires_at=rr.verification_expires_at,
            policy_kind="credential_recognition",
            source_url=rr.source_url,
            requires_manual_review=(rr.verification_status != "verified"),
            now=ref_now,
        )
        rr.freshness_status = status
        counts[status] += 1

    for cq in db.query(CountryQualification).all():
        status = classify_freshness(
            verified_at=cq.verified_at,
            verification_expires_at=cq.verification_expires_at,
            policy_kind="qualification_frameworks",
            source_url=cq.source_url,
            requires_manual_review=(cq.verification_status != "verified"),
            now=ref_now,
        )
        cq.freshness_status = status
        counts[status] += 1

    db.commit()
    return {"checked_at": ref_now.isoformat(), "counts": counts}


def validate_scholarship_catalog(
    db: Session,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Independent governance audit over scholarship records:
    detects invalid URLs, duplicate titles, missing provenance, expired records,
    and conflicting rules/amounts.
    """
    ref_now = _utcnow(now)
    programs = (
        db.query(ScholarshipProgram)
        .options(joinedload(ScholarshipProgram.rules))
        .order_by(ScholarshipProgram.title.asc())
        .all()
    )

    invalid_urls: List[Dict[str, str]] = []
    duplicates: List[Dict[str, str]] = []
    missing_provenance: List[Dict[str, Any]] = []
    expired_records: List[Dict[str, str]] = []
    conflicting_records: List[Dict[str, Any]] = []

    seen_title_inst: Dict[Tuple[str, str], str] = {}
    seen_sponsor_url_cycle: Dict[Tuple[str, str, str, str], str] = {}

    for p in programs:
        url_ok, url_reason = is_valid_official_url(p.source_url)
        if not url_ok:
            invalid_urls.append({"id": str(p.id), "title": p.title, "reason": url_reason or "Invalid URL"})

        dup_key = (p.title.strip().lower(), str(p.institution_id or "global"))
        if dup_key in seen_title_inst:
            duplicates.append(
                {
                    "id": str(p.id),
                    "title": p.title,
                    "duplicate_of": seen_title_inst[dup_key],
                }
            )
        else:
            seen_title_inst[dup_key] = str(p.id)

        sponsor_key = (
            (p.sponsoring_institution or p.source_name or "").strip().lower(),
            (p.source_url or "").strip().lower().rstrip("/"),
            (p.academic_year or "unspecified").strip().lower(),
            ",".join(sorted(str(d).lower() for d in (p.degree_levels or []))),
        )
        if sponsor_key[0] and sponsor_key[1]:
            if sponsor_key in seen_sponsor_url_cycle:
                # Distinct named awards may share a directory page ONLY if titles differ meaningfully
                prev_id, prev_title = seen_sponsor_url_cycle[sponsor_key].split("|", 1)
                if prev_title == p.title.strip().lower():
                    duplicates.append(
                        {
                            "id": str(p.id),
                            "title": p.title,
                            "duplicate_of": prev_id,
                        }
                    )
            else:
                seen_sponsor_url_cycle[sponsor_key] = f"{p.id}|{p.title.strip().lower()}"

        cur_val = str(p.award_currency or "").strip().upper()
        if (p.native_amount_min is not None or p.native_amount_max is not None) and (not cur_val or len(cur_val) != 3 or not cur_val.isalpha()):
            conflicting_records.append(
                {"id": str(p.id), "title": p.title, "conflicts": [f"Invalid native currency code '{cur_val}'"]}
            )

        missing_fields: List[str] = []
        if not p.source_name or not p.source_name.strip():
            missing_fields.append("source_name")
        if not p.verified_at:
            missing_fields.append("verified_at")
        if p.verification_expires_at is None:
            missing_fields.append("verification_expires_at")
        if (p.source_type or "unknown") == "unknown":
            missing_fields.append("source_type")
        if not p.academic_year:
            missing_fields.append("academic_year")
        if not p.claim_provenance:
            missing_fields.append("claim_provenance")
        if missing_fields:
            missing_provenance.append({"id": str(p.id), "title": p.title, "missing_fields": missing_fields})

        cb = evaluate_scholarship_claim_breakdown(p, now=ref_now)
        freshness = evaluate_scholarship_freshness(p, now=ref_now)
        p_exp = _parse_iso_dt(p.verification_expires_at)
        if (
            cb["record_expired"]
            or cb["amount_expired"]
            or (freshness == "expired" and not cb["existence_current"])
            or (p_exp is not None and p_exp <= ref_now)
        ):
            expired_records.append(
                {
                    "id": str(p.id),
                    "title": p.title,
                    "verification_expires_at": p.verification_expires_at.isoformat() if p.verification_expires_at else "unknown",
                }
            )

        conflicts: List[str] = []
        if p.conflict_notes:
            conflicts.append(p.conflict_notes)
        if p.award_amount_min_usd is not None and p.award_amount_max_usd is not None:
            if float(p.award_amount_min_usd) > float(p.award_amount_max_usd):
                conflicts.append("award_amount_min_usd exceeds award_amount_max_usd")
        if p.award_amount_min_usd is not None and float(p.award_amount_min_usd) < 0:
            conflicts.append("negative award_amount_min_usd")
        if not p.covers_international:
            for r in (p.rules or []):
                if r.rule_dimension == "citizenship":
                    allowed = [str(c).upper() for c in (r.rule_value or {}).get("countries", [])]
                    if any(c != (p.country_code or "").upper() for c in allowed):
                        conflicts.append(
                            f"covers_international=False conflicts with citizenship rule allowing {allowed}"
                        )
        if conflicts:
            conflicting_records.append({"id": str(p.id), "title": p.title, "conflicts": conflicts})

    coverage_metrics = _compute_coverage_from_programs(programs, ref_now)
    return {
        "total_checked": len(programs),
        "invalid_urls": invalid_urls,
        "duplicates": duplicates,
        "missing_provenance": missing_provenance,
        "expired_records": expired_records,
        "conflicting_records": conflicting_records,
        **coverage_metrics,
    }


def _has_verified_funding_coverage(p: ScholarshipProgram, ref_now: datetime) -> bool:
    """
    Returns True only when an active scholarship has verified, current (non-expired,
    non-manual-review) eligibility and award-amount claims with a concrete published
    numeric amount in a known currency.
    """
    if not p.is_current or not p.is_verified or p.requires_manual_review:
        return False
    if (p.funding_type or "").strip().lower() == "exchange_mobility":
        return False
    currency = (p.award_currency or "").strip().upper()
    if not currency or currency == "UNK":
        return False
    has_concrete_amount = any(
        val is not None
        for val in (
            p.award_amount_min_usd,
            p.award_amount_max_usd,
            p.award_fixed_usd,
            p.native_amount_min,
            p.native_amount_max,
        )
    )
    if not has_concrete_amount:
        return False
    breakdown = evaluate_scholarship_claim_breakdown(p, now=ref_now)
    if not breakdown["existence_current"] or breakdown["record_expired"]:
        return False
    claims = breakdown["claims"]
    return (
        claims.get("program_existence") in ("current", "approaching_expiration")
        and claims.get("eligibility_rules") in ("current", "approaching_expiration")
        and claims.get("award_amounts") in ("current", "approaching_expiration")
    )


def _compute_coverage_from_programs(
    programs: List[ScholarshipProgram],
    ref_now: datetime,
) -> Dict[str, Any]:
    active_programs = [p for p in programs if p.is_current]
    total_active = len(active_programs)
    verified_funding = sum(
        1 for p in active_programs if _has_verified_funding_coverage(p, ref_now)
    )
    ratio = round(verified_funding / total_active, 4) if total_active > 0 else 0.0
    return {
        "total_active_programs": total_active,
        "verified_funding_programs": verified_funding,
        "verified_funding_coverage": ratio,
    }


def compute_verified_funding_coverage(
    db: Session,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Computes verified funding coverage across all active scholarship programs:
    count of active programs with current verified award-amount & eligibility claims
    divided by total active scholarship programs.
    """
    ref_now = _utcnow(now)
    active_programs = (
        db.query(ScholarshipProgram)
        .filter(ScholarshipProgram.is_current.is_(True))
        .all()
    )
    return _compute_coverage_from_programs(active_programs, ref_now)


def validate_credential_catalog(
    db: Session,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Validates grade conversion rules, recognition rules, and qualification frameworks."""
    ref_now = _utcnow(now)
    invalid_urls: List[Dict[str, str]] = []
    expired_records: List[Dict[str, str]] = []
    conflicting_records: List[Dict[str, str]] = []

    for rr in db.query(CredentialRecognitionRule).all():
        ok, reason = is_valid_official_url(rr.source_url)
        if not ok:
            invalid_urls.append({"table": "credential_recognition_rules", "id": str(rr.id), "reason": reason or "Invalid URL"})
        rr_exp = _parse_iso_dt(rr.verification_expires_at)
        if (
            classify_freshness(
                verified_at=rr.verified_at,
                verification_expires_at=rr.verification_expires_at,
                policy_kind="credential_recognition",
                source_url=rr.source_url,
                now=ref_now,
            )
            == "expired"
            or (rr_exp is not None and rr_exp <= ref_now)
        ):
            expired_records.append({"table": "credential_recognition_rules", "id": str(rr.id)})

    for cq in db.query(CountryQualification).all():
        ok, reason = is_valid_official_url(cq.source_url)
        if not ok:
            invalid_urls.append({"table": "country_qualifications", "id": str(cq.id), "reason": reason or "Invalid URL"})
        cq_exp = _parse_iso_dt(cq.verification_expires_at)
        if (
            classify_freshness(
                verified_at=cq.verified_at,
                verification_expires_at=cq.verification_expires_at,
                policy_kind="qualification_frameworks",
                source_url=cq.source_url,
                now=ref_now,
            )
            == "expired"
            or (cq_exp is not None and cq_exp <= ref_now)
        ):
            expired_records.append({"table": "country_qualifications", "id": str(cq.id)})

    for gr in db.query(GradeConversionRule).all():
        if gr.min_numeric is not None and gr.max_numeric is not None and float(gr.min_numeric) > float(gr.max_numeric):
            conflicting_records.append(
                {
                    "table": "grade_conversion_rules",
                    "id": str(gr.id),
                    "reason": "min_numeric exceeds max_numeric",
                }
            )
        if float(gr.target_gpa_low) > float(gr.target_gpa_high):
            conflicting_records.append(
                {
                    "table": "grade_conversion_rules",
                    "id": str(gr.id),
                    "reason": "target_gpa_low exceeds target_gpa_high",
                }
            )

    return {
        "invalid_urls": invalid_urls,
        "expired_records": expired_records,
        "conflicting_records": conflicting_records,
    }
