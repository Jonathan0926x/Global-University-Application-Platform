"""
Routing Data Quality Verification Service (Phase 3 Milestone 7.1).

Evaluates `needs_verification` routes using deterministic provenance, HTTPS,
domain-matching against verified institutional domains, and curated public
centralized/statewide system allowlists — while preserving non-matching or
third-party CRM URLs for explicit human verifier review with immutable audits.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.ingestion.routing_seed import validate_routing_url
from app.models.institution import Institution
from app.models.routing import ApplicationRoute, ApplicationRouteAudit

VERIFICATION_VALIDITY_DAYS = 180


def compute_verification_expiration(
    verified_at: Optional[datetime], days: int = VERIFICATION_VALIDITY_DAYS
) -> Optional[datetime]:
    """Compute expiration date from a verified_at timestamp."""
    if not verified_at:
        return None
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=timezone.utc)
    return verified_at + timedelta(days=days)


ROUTE_REJECTION_REASONS: List[Dict[str, str]] = [
    {
        "code": "broken_or_404",
        "label": "Broken URL / 404 Not Found",
        "description": "The destination URL returned an HTTP 404/5xx error or failed to load.",
    },
    {
        "code": "insecure_http",
        "label": "Insecure HTTP Without TLS",
        "description": "Portal URL lacks valid HTTPS encryption for personal/financial data.",
    },
    {
        "code": "wrong_institution_domain",
        "label": "Unverified Cross-Domain / Wrong Institution",
        "description": "URL domain does not match the official institution or recognized admissions system.",
    },
    {
        "code": "placeholder_or_aggregator",
        "label": "Third-Party Lead / Non-Official Aggregator",
        "description": "Link routes to a marketing aggregator rather than an official application portal.",
    },
    {
        "code": "deprecated_term_portal",
        "label": "Deprecated or Superseded Portal",
        "description": "Institution has migrated applications to a newer official platform.",
    },
    {
        "code": "other",
        "label": "Other (See Verifier Notes)",
        "description": "Custom issue documented in verifier notes.",
    },
]
ROUTE_REJECTION_CODES = {r["code"]: r for r in ROUTE_REJECTION_REASONS}

OFFICIAL_SYSTEM_ALLOWLIST: Dict[str, str] = {
    "commonapp.org": "Common App Centralized System",
    "coalitionforcollegeaccess.org": "Coalition App / Scoir Centralized System",
    "calstate.edu": "Cal State Apply Official System",
    "universityofcalifornia.edu": "UC Application Official System",
    "applytexas.org": "ApplyTexas Statewide Portal",
    "opencccapply.net": "California Community Colleges OpenCCCApply",
    "laccd.edu": "Los Angeles Community College District Apply",
    "wisconsin.edu": "Universities of Wisconsin Apply Portal",
    "cuny.edu": "CUNY Centralized Undergraduate Portal",
    "cfnc.org": "College Foundation of North Carolina (CFNC)",
    "gafutures.xap.com": "GAfutures Official Georgia Application Portal",
    "suny.edu": "SUNY Application Services",
    "ucas.com": "UCAS UK Centralized Admissions",
    "ouac.on.ca": "Ontario Universities' Application Centre",
    "campusfrance.org": "Études en France (Campus France)",
    "uni-assist.de": "uni-assist e.V. German Portal",
    "uac.edu.au": "NSW/ACT Universities Admissions Centre",
    "vtac.edu.au": "Victorian Tertiary Admissions Centre",
    "qtac.edu.au": "Queensland Tertiary Admissions Centre",
}

THIRD_PARTY_CRM_HOSTS = {"elluciancrmrecruit.com", "force.com", "targetx.com", "slate.org"}


def _registrable_domain(host: Optional[str]) -> str:
    if not host:
        return ""
    clean = host.lower().strip().removeprefix("www.")
    parts = [p for p in clean.split(".") if p]
    if len(parts) <= 2:
        return clean
    # Preserve standard 2-level ccTLD suffixes such as .ac.uk, .edu.au, .on.ca
    if parts[-2] in ("ac", "edu", "gov", "on", "co", "gc") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def evaluate_route_trust(route: ApplicationRoute, inst: Optional[Institution]) -> Dict[str, Any]:
    """
    Runs deterministic provenance & structural trust evaluation on an ApplicationRoute.
    Never makes blind external guesses; promotes only strict HTTPS + institutional-domain
    or allowlisted public state/centralized system matches backed by NCES IPEDS provenance.
    """
    url_check = validate_routing_url(route.official_url)
    parsed = urlparse(route.official_url or "")
    host = (parsed.hostname or "").lower().removeprefix("www.")
    reg_domain = _registrable_domain(host)
    has_tracking_fragment = bool(parsed.fragment and "_ga=" in parsed.fragment)

    inst_domains = set()
    if inst:
        for candidate in (inst.official_website, inst.admissions_website):
            if candidate:
                c_host = (urlparse(candidate).hostname or "").lower().removeprefix("www.")
                c_dom = _registrable_domain(c_host)
                if c_dom:
                    inst_domains.add(c_dom)

    domain_matches_inst = bool(reg_domain and reg_domain in inst_domains)
    allowlisted_system = OFFICIAL_SYSTEM_ALLOWLIST.get(host) or OFFICIAL_SYSTEM_ALLOWLIST.get(reg_domain)
    is_third_party_crm = reg_domain in THIRD_PARTY_CRM_HOSTS
    has_ipeds_provenance = bool(
        (route.source_name and "IPEDS" in route.source_name.upper())
        or (inst and inst.ipeds_unit_id)
    )

    warnings: List[str] = []
    if not url_check["valid"]:
        warnings.append(f"Invalid URL structure: {url_check['reason']}")
    if not url_check.get("scheme_secure"):
        warnings.append("URL does not use HTTPS.")
    if is_third_party_crm:
        warnings.append("Uses third-party CRM subdomain; confirm institutional tenant association.")
    if not domain_matches_inst and not allowlisted_system and not is_third_party_crm:
        warnings.append("Portal domain differs from verified institutional website; requires verifier check.")
    if has_tracking_fragment:
        warnings.append("Contains analytics fragment (#_ga=...); clean base URL recommended.")

    # Expiration, link-health, redirect, and pathway warnings
    now = datetime.now(timezone.utc)
    is_expired = False
    expiring_soon = False
    if route.verification_status == "verified" and route.verification_expires_at:
        exp = route.verification_expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= now:
            is_expired = True
            warnings.append(f"Verification expired on {exp.strftime('%Y-%m-%d')}; needs reverification.")
        elif exp <= now + timedelta(days=30):
            expiring_soon = True
            warnings.append(f"Verification expires soon ({exp.strftime('%Y-%m-%d')}).")

    redirect_cross_domain = False
    if route.final_redirect_url:
        redir_dom = _registrable_domain(urlparse(route.final_redirect_url).hostname)
        if redir_dom and reg_domain and redir_dom != reg_domain:
            redirect_cross_domain = True
            warnings.append(f"Portal redirects cross-domain to {redir_dom}; confirm final destination.")

    if route.last_health_check_status in ("unreachable", "error"):
        warnings.append(
            f"Last link-health check reported '{route.last_health_check_status}' (HTTP {route.last_health_check_http_code or 'N/A'})."
        )

    if route.verification_status == "verified" and route.pathway_verified is not True:
        warnings.append(
            f"Pathway '{route.applicant_type}' applicability not independently verified (first-year vs. transfer)."
        )

    auto_verifiable = bool(
        url_check["valid"]
        and url_check.get("scheme_secure")
        and has_ipeds_provenance
        and not is_third_party_crm
        and (domain_matches_inst or allowlisted_system is not None)
    )

    method = None
    cleaned_url = route.official_url
    if has_tracking_fragment and auto_verifiable:
        cleaned_url = route.official_url.split("#", 1)[0]

    if domain_matches_inst and auto_verifiable:
        method = "ipeds_domain_match"
    elif allowlisted_system and auto_verifiable:
        method = "ipeds_state_system"

    return {
        "auto_verifiable": auto_verifiable,
        "recommended_method": method,
        "system_label": allowlisted_system,
        "cleaned_url": cleaned_url,
        "checks": {
            "url_structurally_valid": url_check["valid"],
            "https_secure": bool(url_check.get("scheme_secure")),
            "domain_matches_official_website": domain_matches_inst,
            "official_system_allowlist": allowlisted_system,
            "third_party_crm_host": is_third_party_crm,
            "has_ipeds_provenance": has_ipeds_provenance,
            "has_tracking_fragment": has_tracking_fragment,
            "portal_domain": reg_domain,
            "institution_domains": sorted(inst_domains),
            "verification_expired": is_expired,
            "verification_expiring_soon": expiring_soon,
            "pathway_verified": bool(route.pathway_verified),
            "last_health_check_status": route.last_health_check_status,
            "last_health_check_http_code": route.last_health_check_http_code,
            "final_redirect_url": route.final_redirect_url,
            "redirect_chain_length": route.redirect_chain_length,
            "redirect_cross_domain": redirect_cross_domain,
        },
        "warnings": warnings,
    }


def get_routing_quality_summary(db: Session) -> Dict[str, Any]:
    rows = (
        db.query(ApplicationRoute)
        .options(joinedload(ApplicationRoute.institution))
        .filter(ApplicationRoute.is_active == True)
        .all()
    )
    by_status = {"verified": 0, "needs_verification": 0, "unverified": 0}
    by_method: Dict[str, int] = {}
    auto_candidates = 0
    manual_remaining = 0

    manually_reviewed_count = 0
    for r in rows:
        by_status[r.verification_status] = by_status.get(r.verification_status, 0) + 1
        meth = r.verification_method or (
            "curated_official" if r.verification_status == "verified" else "pending_review"
        )
        by_method[meth] = by_method.get(meth, 0) + 1
        if r.verification_method in ("manual_verifier", "manual_rejected"):
            manually_reviewed_count += 1
        if r.verification_status == "needs_verification":
            ev = evaluate_route_trust(r, r.institution)
            if ev["auto_verifiable"]:
                auto_candidates += 1
            else:
                manual_remaining += 1

    from app.services.routing_health import get_route_health_summary

    return {
        "total_routes": len(rows),
        "verified": by_status.get("verified", 0),
        "needs_verification": by_status.get("needs_verification", 0),
        "unverified": by_status.get("unverified", 0),
        "by_method": by_method,
        "auto_verifiable_candidates": auto_candidates,
        "manual_review_remaining": manual_remaining,
        "manually_reviewed_count": manually_reviewed_count,
        "health": get_route_health_summary(db),
    }


def record_route_audit(
    db: Session,
    route: ApplicationRoute,
    from_status: Optional[str],
    to_status: str,
    action: str,
    actor_user_id: Optional[UUID],
    actor_role: str,
    actor_email: Optional[str] = None,
    rejection_reason_code: Optional[str] = None,
    notes: Optional[str] = None,
    checks_json: Optional[Dict[str, Any]] = None,
) -> ApplicationRouteAudit:
    audit = ApplicationRouteAudit(
        route_id=route.id,
        from_status=from_status,
        to_status=to_status,
        action=action,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        actor_email=actor_email,
        rejection_reason_code=rejection_reason_code,
        notes=notes,
        checks_json=checks_json or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    return audit


def reverify_ipeds_routes(
    db: Session,
    actor_user_id: Optional[UUID] = None,
    actor_role: str = "system",
    actor_email: Optional[str] = None,
    limit: int = 500,
) -> Dict[str, Any]:
    """
    Executes deterministic data-quality verification on all `needs_verification` routes.
    Promotes strictly verified HTTPS institutional-domain matches & official state/centralized
    system allowlist matches with full audit trails; preserves third-party CRM / cross-domain
    candidates in `needs_verification` for human verifier review.
    """
    candidates = (
        db.query(ApplicationRoute)
        .options(joinedload(ApplicationRoute.institution))
        .filter(
            ApplicationRoute.is_active == True,
            ApplicationRoute.verification_status == "needs_verification",
        )
        .limit(limit)
        .all()
    )

    now = datetime.now(timezone.utc)
    promoted = 0
    kept = 0
    flagged_unverified = 0
    method_counts: Dict[str, int] = {}

    for r in candidates:
        ev = evaluate_route_trust(r, r.institution)
        r.last_checked_at = now
        if not ev["checks"]["url_structurally_valid"]:
            prev = r.verification_status
            r.verification_status = "unverified"
            r.confidence_level = "low"
            r.verification_method = "auto_rejected"
            r.verification_notes = "; ".join(ev["warnings"])
            flagged_unverified += 1
            record_route_audit(
                db, r, prev, "unverified", "rejected_unverified",
                actor_user_id, actor_role, actor_email,
                rejection_reason_code="wrong_institution_domain",
                notes=r.verification_notes,
                checks_json=ev["checks"],
            )
        elif ev["auto_verifiable"]:
            prev = r.verification_status
            meth = ev["recommended_method"] or "ipeds_domain_match"
            if ev["cleaned_url"] != r.official_url:
                r.official_url = ev["cleaned_url"]
            r.verification_status = "verified"
            r.confidence_level = "high"
            r.verification_method = meth
            r.verified_at = now
            r.verification_expires_at = compute_verification_expiration(now)
            r.verified_by_user_id = actor_user_id
            r.verification_notes = (
                f"Verified via {meth}: HTTPS + NCES IPEDS HD2023 provenance + "
                + (
                    f"official system ({ev['system_label']})"
                    if ev["system_label"]
                    else f"exact domain match ({ev['checks']['portal_domain']})"
                )
            )
            promoted += 1
            method_counts[meth] = method_counts.get(meth, 0) + 1
            record_route_audit(
                db, r, prev, "verified", "auto_verified",
                actor_user_id, actor_role, actor_email,
                notes=r.verification_notes,
                checks_json=ev["checks"],
            )
        else:
            r.verification_notes = "; ".join(ev["warnings"]) or "Requires manual verifier review."
            kept += 1

    db.commit()
    return {
        "checked": len(candidates),
        "promoted_to_verified": promoted,
        "kept_needs_verification": kept,
        "flagged_unverified": flagged_unverified,
        "by_method": method_counts,
        "summary": get_routing_quality_summary(db),
    }


def review_single_route(
    db: Session,
    route: ApplicationRoute,
    decision: str,
    actor_user_id: Optional[UUID],
    actor_role: str,
    actor_email: Optional[str],
    rejection_reason_code: Optional[str] = None,
    notes: Optional[str] = None,
    corrected_url: Optional[str] = None,
    international_instructions: Optional[str] = None,
    pathway_verified: Optional[bool] = None,
    applicant_type: Optional[str] = None,
) -> ApplicationRoute:
    norm_decision = (decision or "").strip().lower()
    if norm_decision not in ("verified", "unverified", "needs_verification"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be 'verified', 'unverified', or 'needs_verification'.",
        )

    if norm_decision == "unverified":
        code = (rejection_reason_code or "").strip()
        if code not in ROUTE_REJECTION_CODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rejecting a route requires a valid rejection_reason_code: {sorted(ROUTE_REJECTION_CODES)}.",
            )
        if not (notes or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rejecting a route requires explanatory verifier notes.",
            )

    now = datetime.now(timezone.utc)
    if corrected_url and corrected_url.strip():
        chk = validate_routing_url(corrected_url.strip())
        if not chk["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrected URL invalid: {chk['reason']}",
            )
        route.official_url = chk["normalized_url"]

    if international_instructions is not None:
        route.international_instructions = international_instructions.strip() or None

    if applicant_type is not None and applicant_type.strip():
        norm_type = applicant_type.strip().lower()
        valid_types = {
            "first_year",
            "transfer",
            "international_first_year",
            "international_transfer",
            "all",
        }
        if norm_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid applicant_type '{applicant_type}'. Must be one of {sorted(valid_types)}.",
            )
        route.applicant_type = norm_type

    if pathway_verified is not None:
        route.pathway_verified = pathway_verified

    ev = evaluate_route_trust(route, route.institution)
    if norm_decision == "verified" and not ev["checks"]["url_structurally_valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot verify a structurally invalid portal URL.",
        )

    prev = route.verification_status
    route.verification_status = norm_decision
    route.last_checked_at = now
    route.verification_notes = (notes or "").strip() or route.verification_notes

    if norm_decision == "verified":
        route.confidence_level = "high"
        route.verification_method = "manual_verifier"
        route.verified_at = now
        route.verification_expires_at = compute_verification_expiration(now)
        route.verified_by_user_id = actor_user_id
        action = "verified"
    elif norm_decision == "unverified":
        route.confidence_level = "low"
        route.verification_method = "manual_rejected"
        action = "rejected_unverified"
    else:
        route.confidence_level = "medium"
        route.verification_method = "pending_review"
        action = "marked_needs_verification"

    record_route_audit(
        db=db,
        route=route,
        from_status=prev,
        to_status=norm_decision,
        action=action,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        actor_email=actor_email,
        rejection_reason_code=rejection_reason_code if norm_decision == "unverified" else None,
        notes=route.verification_notes,
        checks_json=ev["checks"],
    )
    db.commit()
    db.refresh(route)
    return route
