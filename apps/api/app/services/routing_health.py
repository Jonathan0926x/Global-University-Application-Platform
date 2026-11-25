"""
Routing Health Check & Lifecycle Governance Service (Phase 3 Milestone 7.2).

Provides:
- Periodic SSRF-safe HTTP HEAD/GET link-health checks
- Redirect destination & chain length tracking
- Verification expiration management (default 180 days)
- First-year vs. transfer pathway applicability verification
- Automatic reverification triggers when institutional websites change
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.ingestion.routing_seed import validate_routing_url
from app.models.routing import ApplicationRoute
from app.services.routing_verification import (
    VERIFICATION_VALIDITY_DAYS,
    _registrable_domain,
    compute_verification_expiration,
    record_route_audit,
)

# Health check status constants
HEALTH_STATUS_HEALTHY = "healthy"
HEALTH_STATUS_UNREACHABLE = "unreachable"
HEALTH_STATUS_REDIRECTED = "redirected"
HEALTH_STATUS_ERROR = "error"


def is_route_verification_expired(
    route: ApplicationRoute, as_of: Optional[datetime] = None
) -> bool:
    """Return True if a verified route has passed its verification_expires_at timestamp."""
    if route.verification_status != "verified" or not route.verification_expires_at:
        return False
    now = as_of or datetime.now(timezone.utc)
    exp = route.verification_expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp <= now


def get_expired_routes(
    db: Session, as_of: Optional[datetime] = None
) -> List[ApplicationRoute]:
    """Find all verified routes whose verification has expired."""
    now = as_of or datetime.now(timezone.utc)
    return (
        db.query(ApplicationRoute)
        .filter(
            ApplicationRoute.is_active == True,
            ApplicationRoute.verification_status == "verified",
            ApplicationRoute.verification_expires_at != None,
            ApplicationRoute.verification_expires_at <= now,
        )
        .all()
    )


def get_stale_routes(
    db: Session, stale_days: int = 90, limit: int = 100
) -> List[ApplicationRoute]:
    """Find active verified/pending routes that haven't been health-checked in `stale_days`."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
    return (
        db.query(ApplicationRoute)
        .filter(
            ApplicationRoute.is_active == True,
            ApplicationRoute.verification_status.in_(["verified", "needs_verification"]),
        )
        .filter(
            (ApplicationRoute.last_health_check_at == None)
            | (ApplicationRoute.last_health_check_at <= cutoff)
        )
        .order_by(ApplicationRoute.last_health_check_at.asc().nullsfirst())
        .limit(limit)
        .all()
    )


def _default_http_probe(url: str, timeout: float = 6.0) -> Dict[str, Any]:
    """
    Executes an SSRF-checked HTTP HEAD (with GET fallback on 403/405) request,
    following redirects safely and returning status, final URL, and chain length.
    """
    chk = validate_routing_url(url)
    if not chk["valid"]:
        return {
            "ok": False,
            "http_code": None,
            "final_url": None,
            "redirect_chain_length": 0,
            "error": chk["reason"] or "Invalid URL",
        }

    headers = {
        "User-Agent": "UniGlobe-LinkHealthBot/1.0 (+https://uniglobe.edu/ops)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
            resp = client.head(url)
            if resp.status_code in (403, 405, 501):
                resp = client.get(url)
            final_url = str(resp.url) if resp.url else url
            chain_len = len(resp.history)
            return {
                "ok": True,
                "http_code": resp.status_code,
                "final_url": final_url,
                "redirect_chain_length": chain_len,
                "error": None,
            }
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "http_code": None,
            "final_url": None,
            "redirect_chain_length": 0,
            "error": str(exc),
        }


def record_health_check(
    db: Session,
    route: ApplicationRoute,
    status: str,
    http_code: Optional[int] = None,
    final_redirect_url: Optional[str] = None,
    redirect_chain_length: Optional[int] = None,
) -> ApplicationRoute:
    """Record the result of a link-health check on a route."""
    now = datetime.now(timezone.utc)
    route.last_health_check_at = now
    route.last_health_check_status = status
    route.last_health_check_http_code = http_code

    if final_redirect_url is not None:
        route.final_redirect_url = final_redirect_url
    if redirect_chain_length is not None:
        route.redirect_chain_length = redirect_chain_length

    db.flush()
    return route


def perform_route_health_check(
    db: Session,
    route: ApplicationRoute,
    actor_user_id: Optional[UUID] = None,
    actor_role: str = "system",
    actor_email: Optional[str] = None,
    probe_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    commit: bool = True,
) -> Dict[str, Any]:
    """
    Runs a link-health check on `route`, tracking HTTP status, redirect chain length,
    and final redirect destination. Flags 404/410/unreachable or cross-domain redirects
    in audit logs for review.
    """
    probe = probe_fn or _default_http_probe
    url_chk = validate_routing_url(route.official_url)
    if not url_chk["valid"]:
        record_health_check(
            db, route, HEALTH_STATUS_ERROR, http_code=None, final_redirect_url=None, redirect_chain_length=0
        )
        if commit:
            db.commit()
            db.refresh(route)
        return {"route_id": str(route.id), "status": HEALTH_STATUS_ERROR, "http_code": None}

    res = probe(route.official_url)
    http_code = res.get("http_code")
    final_url = res.get("final_url") or route.official_url
    chain_len = int(res.get("redirect_chain_length") or 0)

    initial_dom = _registrable_domain(urlparse(route.official_url).hostname)
    final_dom = _registrable_domain(urlparse(final_url).hostname) if final_url else initial_dom
    cross_domain_redirect = bool(final_dom and initial_dom and final_dom != initial_dom)

    if not res.get("ok") or http_code is None:
        health_status = HEALTH_STATUS_UNREACHABLE
    elif http_code in (404, 410):
        health_status = HEALTH_STATUS_UNREACHABLE
    elif http_code >= 400:
        health_status = HEALTH_STATUS_ERROR
    elif cross_domain_redirect or chain_len > 0:
        health_status = HEALTH_STATUS_REDIRECTED
    else:
        health_status = HEALTH_STATUS_HEALTHY

    record_health_check(
        db=db,
        route=route,
        status=health_status,
        http_code=http_code,
        final_redirect_url=final_url if res.get("ok") else None,
        redirect_chain_length=chain_len,
    )

    if health_status == HEALTH_STATUS_UNREACHABLE or cross_domain_redirect:
        record_route_audit(
            db=db,
            route=route,
            from_status=route.verification_status,
            to_status=route.verification_status,
            action="health_check_warning",
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            actor_email=actor_email,
            notes=(
                f"Health check recorded status={health_status} (HTTP {http_code or 'N/A'})"
                + (
                    f"; redirected across domains {initial_dom} -> {final_dom}"
                    if cross_domain_redirect
                    else ""
                )
            ),
            checks_json={
                "health_status": health_status,
                "http_code": http_code,
                "final_redirect_url": final_url,
                "redirect_chain_length": chain_len,
                "cross_domain_redirect": cross_domain_redirect,
                "error": res.get("error"),
            },
        )

    if commit:
        db.commit()
        db.refresh(route)

    return {
        "route_id": str(route.id),
        "status": health_status,
        "http_code": http_code,
        "final_redirect_url": route.final_redirect_url,
        "redirect_chain_length": route.redirect_chain_length,
        "cross_domain_redirect": cross_domain_redirect,
    }


def run_batch_health_checks(
    db: Session,
    limit: int = 25,
    only_stale: bool = True,
    stale_days: int = 90,
    actor_user_id: Optional[UUID] = None,
    actor_role: str = "system",
    actor_email: Optional[str] = None,
    probe_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run health checks across stale or prioritized active routes."""
    if only_stale:
        candidates = get_stale_routes(db, stale_days=stale_days, limit=limit)
    else:
        candidates = (
            db.query(ApplicationRoute)
            .filter(ApplicationRoute.is_active == True)
            .order_by(ApplicationRoute.last_health_check_at.asc().nullsfirst())
            .limit(limit)
            .all()
        )

    counts: Dict[str, int] = {
        HEALTH_STATUS_HEALTHY: 0,
        HEALTH_STATUS_REDIRECTED: 0,
        HEALTH_STATUS_UNREACHABLE: 0,
        HEALTH_STATUS_ERROR: 0,
    }
    results: List[Dict[str, Any]] = []

    for r in candidates:
        out = perform_route_health_check(
            db=db,
            route=r,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            actor_email=actor_email,
            probe_fn=probe_fn,
            commit=False,
        )
        counts[out["status"]] = counts.get(out["status"], 0) + 1
        results.append(out)

    db.commit()
    return {
        "checked": len(candidates),
        "by_status": counts,
        "results": results,
    }


def flag_expired_routes_for_reverification(
    db: Session,
    actor_user_id: Optional[UUID] = None,
    actor_role: str = "system",
    actor_email: Optional[str] = None,
    as_of: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Find all expired verified routes and flag them back to needs_verification.
    Returns summary statistics.
    """
    expired = get_expired_routes(db, as_of=as_of)
    flagged = 0

    for route in expired:
        prev = route.verification_status
        route.verification_status = "needs_verification"
        route.confidence_level = "medium"
        route.verification_notes = (
            f"Verification expired on {route.verification_expires_at.strftime('%Y-%m-%d') if route.verification_expires_at else 'unknown'}. "
            f"Requires reverification."
        )
        flagged += 1

        record_route_audit(
            db=db,
            route=route,
            from_status=prev,
            to_status="needs_verification",
            action="verification_expired",
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            actor_email=actor_email,
            notes=route.verification_notes,
        )

    if flagged > 0:
        db.commit()

    return {
        "expired_checked": len(expired),
        "flagged_for_reverification": flagged,
    }


def flag_routes_for_institution_website_change(
    db: Session,
    institution_id: UUID,
    old_website: Optional[str],
    new_website: Optional[str],
    field_name: str = "official_website",
    actor_user_id: Optional[UUID] = None,
    actor_role: str = "system",
    actor_email: Optional[str] = None,
    commit: bool = True,
) -> Dict[str, Any]:
    """
    When an institution's official_website, admissions_website, or application_portal_url
    changes, flag all associated verified routes back to needs_verification.
    """
    if (old_website or "").strip() == (new_website or "").strip():
        return {"flagged": 0, "reason": "no_change"}

    routes = (
        db.query(ApplicationRoute)
        .filter(
            ApplicationRoute.institution_id == institution_id,
            ApplicationRoute.is_active == True,
            ApplicationRoute.verification_status == "verified",
        )
        .all()
    )

    flagged = 0
    for route in routes:
        prev = route.verification_status
        route.verification_status = "needs_verification"
        route.confidence_level = "medium"
        route.verification_notes = (
            f"Institution {field_name} changed from '{old_website}' to '{new_website}'. "
            f"Application portal URL requires reverification."
        )
        flagged += 1

        record_route_audit(
            db=db,
            route=route,
            from_status=prev,
            to_status="needs_verification",
            action="institution_website_changed",
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            actor_email=actor_email,
            notes=route.verification_notes,
            checks_json={
                "field_name": field_name,
                "old_website": old_website,
                "new_website": new_website,
            },
        )

    if flagged > 0 and commit:
        db.commit()

    return {
        "institution_id": str(institution_id),
        "field_name": field_name,
        "old_website": old_website,
        "new_website": new_website,
        "routes_checked": len(routes),
        "flagged": flagged,
    }


def set_pathway_verified(
    db: Session,
    route: ApplicationRoute,
    verified: bool,
    applicant_type: Optional[str] = None,
    actor_user_id: Optional[UUID] = None,
    actor_role: str = "system",
    actor_email: Optional[str] = None,
    notes: Optional[str] = None,
) -> ApplicationRoute:
    """Mark a route's applicant_type pathway applicability as verified or unverified."""
    valid_types = {
        "first_year",
        "transfer",
        "international_first_year",
        "international_transfer",
        "all",
    }
    prev_type = route.applicant_type
    if applicant_type is not None:
        norm = applicant_type.strip().lower()
        if norm not in valid_types:
            raise ValueError(f"Invalid applicant_type '{applicant_type}'. Must be one of {sorted(valid_types)}.")
        route.applicant_type = norm

    route.pathway_verified = verified
    route.last_checked_at = datetime.now(timezone.utc)

    record_route_audit(
        db=db,
        route=route,
        from_status=route.verification_status,
        to_status=route.verification_status,
        action="pathway_verification_updated",
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        actor_email=actor_email,
        notes=notes
        or f"Pathway verification set to {verified} (applicant_type: {prev_type} -> {route.applicant_type}).",
        checks_json={
            "pathway_verified": verified,
            "previous_applicant_type": prev_type,
            "applicant_type": route.applicant_type,
        },
    )

    db.commit()
    db.refresh(route)
    return route


def get_route_health_summary(db: Session) -> Dict[str, Any]:
    """Generate a summary of route health across all active routes."""
    routes = (
        db.query(ApplicationRoute)
        .filter(ApplicationRoute.is_active == True)
        .all()
    )

    now = datetime.now(timezone.utc)
    total = len(routes)
    health_counts: Dict[str, int] = {
        "healthy": 0,
        "unreachable": 0,
        "redirected": 0,
        "error": 0,
        "never_checked": 0,
    }
    expired = 0
    expiring_soon = 0
    pathway_verified_count = 0
    pathway_unverified_count = 0
    has_redirect_tracking = 0

    for r in routes:
        if r.last_health_check_status:
            health_counts[r.last_health_check_status] = (
                health_counts.get(r.last_health_check_status, 0) + 1
            )
        else:
            health_counts["never_checked"] += 1

        if r.verification_expires_at:
            exp = r.verification_expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp <= now:
                expired += 1
            elif exp <= now + timedelta(days=30):
                expiring_soon += 1

        if r.pathway_verified is True:
            pathway_verified_count += 1
        else:
            pathway_unverified_count += 1

        if r.final_redirect_url:
            has_redirect_tracking += 1

    return {
        "total_active_routes": total,
        "health_check_status": health_counts,
        "verification_expired": expired,
        "verification_expiring_soon_30d": expiring_soon,
        "pathway_verified": pathway_verified_count,
        "pathway_assumed": pathway_unverified_count,
        "routes_with_redirect_tracking": has_redirect_tracking,
    }
