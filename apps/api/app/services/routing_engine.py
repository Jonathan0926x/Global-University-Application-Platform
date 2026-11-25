"""
Application Routing & External Lifecycle Engine (Milestone 7).

Honesty & Verification Guarantees:
1. Never invents application portal URLs when unverified or missing.
2. Unverified routes are clearly labeled (`needs_verification` / `unverified`) and excluded
   from verified routing recommendations.
3. Redirecting to an external portal ONLY records `redirected_to_external_portal` + timestamp;
   never auto-marks submitted.
4. Self-reported submission moves to `student_reported_submitted` (not verified).
5. `submission_confirmed` requires explicit `admin` / `data_verifier` acceptance backed by
   supporting confirmation evidence (Document Vault artifact or confirmation reference).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.ingestion.routing_seed import seed_verified_application_routes, validate_routing_url
from app.models.application import Application
from app.models.institution import Institution
from app.models.requirements import Deadline
from app.models.routing import ApplicationRoute, ApplicationStatusHistory


CANONICAL_LIFECYCLE_STATES = (
    "not_started",
    "preparing",
    "ready_to_apply",
    "redirected_to_external_portal",
    "student_reported_submitted",
    "submission_confirmed",
)

STUDENT_PREP_STATES = ("not_started", "preparing", "ready_to_apply")


def normalize_legacy_status(status: str) -> str:
    legacy_map = {
        "exploring": "not_started",
        "planning": "preparing",
        "in_progress": "preparing",
        "awaiting_documents": "preparing",
        "ready_to_submit": "ready_to_apply",
        "submitted": "student_reported_submitted",
    }
    return legacy_map.get(status, status if status in CANONICAL_LIFECYCLE_STATES else "preparing")


def ensure_routes_seeded(db: Session) -> None:
    if db.query(ApplicationRoute.id).limit(1).first() is None:
        seed_verified_application_routes(db)


def resolve_institution_routing(
    db: Session,
    institution: Institution,
    applicant_type: str = "first_year",
    include_unverified_notices: bool = True,
) -> Dict[str, Any]:
    """
    Resolves verified application destinations for an institution + applicant pathway.
    Excludes unverified/invalid links from `verified_routes` and never invents a URL.
    """
    ensure_routes_seeded(db)
    pathway = (applicant_type or "first_year").lower()

    # Fetch institution-specific routes (and country fallback centralized platforms if relevant)
    rows = (
        db.query(ApplicationRoute)
        .filter(
            ApplicationRoute.institution_id == institution.id,
            ApplicationRoute.is_active == True,
        )
        .order_by(ApplicationRoute.verified_at.desc().nullslast())
        .all()
    )

    verified_routes: List[ApplicationRoute] = []
    needs_verification_routes: List[ApplicationRoute] = []
    excluded_unverified: List[Dict[str, str]] = []

    for r in rows:
        if r.applicant_type not in (pathway, "all", f"international_{pathway}"):
            continue
        url_check = validate_routing_url(r.official_url)
        if not url_check["valid"]:
            excluded_unverified.append(
                {
                    "platform_name": r.platform_name,
                    "reason": url_check["reason"] or "Invalid URL",
                    "verification_status": "unverified",
                }
            )
            continue

        if r.verification_status == "verified":
            expires_at = r.verification_expires_at
            if expires_at is not None and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at is not None and expires_at <= datetime.now(timezone.utc):
                excluded_unverified.append(
                    {
                        "platform_name": r.platform_name,
                        "reason": "Route verification has expired and requires reverification.",
                        "verification_status": "expired",
                    }
                )
            elif r.pathway_verified is not True:
                excluded_unverified.append(
                    {
                        "platform_name": r.platform_name,
                        "reason": "Applicant pathway has not been verified.",
                        "verification_status": "pathway_unverified",
                    }
                )
            elif r.last_health_check_status in ("unreachable", "error", "redirected"):
                excluded_unverified.append(
                    {
                        "platform_name": r.platform_name,
                        "reason": "The latest link-health check requires review before this route can be recommended.",
                        "verification_status": "health_check_review_required",
                    }
                )
            else:
                verified_routes.append(r)
        elif r.verification_status == "needs_verification":
            needs_verification_routes.append(r)
        else:
            excluded_unverified.append(
                {
                    "platform_name": r.platform_name,
                    "reason": "Unverified link excluded from verified recommendations.",
                    "verification_status": r.verification_status,
                }
            )

    # Also surface institutional application_portal_url dynamically if valid and not yet seeded in ApplicationRoute
    if not verified_routes and not needs_verification_routes and institution.application_portal_url:
        chk = validate_routing_url(institution.application_portal_url)
        if chk["valid"]:
            needs_verification_routes.append(
                ApplicationRoute(
                    id=institution.id,  # synthetic read-only indicator; not persisted unless explicitly seeded
                    institution_id=institution.id,
                    platform_name=f"{institution.official_name} Portal (Unverified Registry Link)",
                    platform_type="direct_portal",
                    country_code=institution.country_code,
                    applicant_type="all",
                    official_url=chk["normalized_url"],
                    notes="Registry link present; verification pending.",
                    source_name=institution.primary_source or "Institutional Registry",
                    source_url=institution.admissions_website or chk["normalized_url"],
                    verification_status="needs_verification",
                    confidence_level="low",
                    verified_at=institution.last_verified_at,
                    last_checked_at=datetime.now(timezone.utc),
                    is_active=True,
                )
            )
        elif include_unverified_notices:
            excluded_unverified.append(
                {
                    "platform_name": "Institutional Registry Portal Field",
                    "reason": chk["reason"] or "Invalid URL",
                    "verification_status": "unverified",
                }
            )

    if verified_routes:
        routing_status = "verified_available"
        notice = None
    elif needs_verification_routes:
        routing_status = "needs_verification_only"
        notice = (
            f"No independently verified destination route is curated yet for {institution.official_name} ({pathway}). "
            "Verify the candidate portal directly before submitting personal data."
        )
    else:
        routing_status = "no_verified_destination"
        notice = (
            f"No verified application portal URL is recorded for {institution.official_name}. "
            "UniGlobe never fabricates application URLs; check the university's official admissions office."
        )

    return {
        "institution_id": institution.id,
        "institution_name": institution.official_name,
        "applicant_type": pathway,
        "routing_status": routing_status,
        "has_verified_destination": len(verified_routes) > 0,
        "verified_routes": verified_routes,
        "needs_verification_routes": needs_verification_routes,
        "excluded_unverified": excluded_unverified,
        "notice": notice,
    }


def compute_deadline_countdowns(
    db: Session,
    institution_id: UUID,
    applicant_type: str,
) -> List[Dict[str, Any]]:
    today = datetime.now(timezone.utc).date()
    dls = (
        db.query(Deadline)
        .filter(
            Deadline.institution_id == institution_id,
            Deadline.is_current == True,
            Deadline.applicant_type.in_([applicant_type, "all", f"international_{applicant_type}"]),
        )
        .order_by(Deadline.deadline_date.asc().nullslast())
        .all()
    )
    out = []
    for d in dls:
        days_rem = (d.deadline_date - today).days if d.deadline_date else None
        out.append(
            {
                "id": str(d.id),
                "intake_term": d.intake_term,
                "deadline_type": d.deadline_type,
                "deadline_date": d.deadline_date.isoformat() if d.deadline_date else None,
                "days_remaining": days_rem,
                "is_passed": bool(days_rem is not None and days_rem < 0),
                "is_urgent": bool(days_rem is not None and 0 <= days_rem <= 14),
                "verification_status": d.verification_status,
                "source_name": d.source_name,
                "source_url": d.source_url,
                "notes": d.notes,
            }
        )
    return out


def record_status_transition(
    db: Session,
    app: Application,
    to_status: str,
    actor_user_id: Optional[UUID],
    actor_role: str = "student",
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ApplicationStatusHistory:
    prev = app.status
    app.status = to_status
    app.updated_at = datetime.now(timezone.utc)
    hist = ApplicationStatusHistory(
        application_id=app.id,
        from_status=prev,
        to_status=to_status,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        reason=reason,
        metadata_json=metadata or {},
        changed_at=datetime.now(timezone.utc),
    )
    db.add(hist)
    return hist
