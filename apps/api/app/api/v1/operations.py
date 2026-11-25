import os
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_admin_claims
from app.core.auth_provider import UserClaims
from app.database import get_db
from app.models.application import Application
from app.models.document import Document
from app.models.institution import Institution
from app.models.profile import StudentProfile
from app.models.routing import ApplicationRoute, ApplicationSubmissionEvidence
from app.models.user import User
from app.schemas.routing import (
    ApplicationRouteAuditSchema,
    BatchHealthCheckResponse,
    BatchRouteVerifyResponse,
    EvidenceQueueItemSchema,
    EvidenceReviewRequest,
    ExpireRoutesResponse,
    RejectionReasonOptionSchema,
    RouteHealthSummarySchema,
    RoutePathwayVerifyRequest,
    RouteReviewRequest,
    RoutingQualitySummarySchema,
    RoutingQueueItemSchema,
)
from app.services.evidence_ops import (
    EVIDENCE_REJECTION_REASONS,
    execute_evidence_review,
    serialize_evidence,
)
from app.services.routing_health import (
    flag_expired_routes_for_reverification,
    get_route_health_summary,
    perform_route_health_check,
    run_batch_health_checks,
    set_pathway_verified,
)
from app.services.routing_verification import (
    ROUTE_REJECTION_REASONS,
    evaluate_route_trust,
    get_routing_quality_summary,
    reverify_ipeds_routes,
    review_single_route,
)

router = APIRouter()


def _serialize_routing_queue_item(route: ApplicationRoute) -> RoutingQueueItemSchema:
    inst = route.institution
    trust = evaluate_route_trust(route, inst)
    item = RoutingQueueItemSchema.model_validate(route)
    item.institution_name = inst.official_name if inst else "Centralized Platform"
    item.institution_website = inst.official_website if inst else None
    item.trust_checks = {**trust["checks"], "warnings": trust["warnings"], "auto_verifiable": trust["auto_verifiable"]}
    item.audits = [ApplicationRouteAuditSchema.model_validate(a) for a in (route.audits or [])]
    return item


def _serialize_evidence_queue_item(db: Session, ev: ApplicationSubmissionEvidence) -> EvidenceQueueItemSchema:
    base = serialize_evidence(ev, include_actor_email=True)
    app = ev.application or db.query(Application).filter(Application.id == ev.application_id).first()
    inst = app.institution if app else None
    profile = db.query(StudentProfile).filter(StudentProfile.id == ev.profile_id).first()
    user = db.query(User).filter(User.id == profile.user_id).first() if profile else None

    return EvidenceQueueItemSchema(
        **base.model_dump(),
        institution_id=app.institution_id if app else ev.application_id,
        institution_name=inst.official_name if inst else "Institution",
        applicant_type=app.applicant_type if app else "first_year",
        application_status=app.status if app else "unknown",
        student_email=user.email if user else None,
        student_name=(
            f"{profile.first_name} {profile.last_name}".strip()
            if profile and (profile.first_name or profile.last_name)
            else None
        ),
        file_size_bytes=ev.document.file_size_bytes if ev.document else None,
        file_type=ev.document.file_type if ev.document else None,
    )


@router.get("/admin/verification/taxonomies", tags=["Verification Operations"])
def get_verification_taxonomies(
    claims: UserClaims = Depends(require_admin_claims),
) -> Dict[str, List[RejectionReasonOptionSchema]]:
    return {
        "evidence_rejection_reasons": [RejectionReasonOptionSchema(**r) for r in EVIDENCE_REJECTION_REASONS],
        "route_rejection_reasons": [RejectionReasonOptionSchema(**r) for r in ROUTE_REJECTION_REASONS],
    }


@router.get("/admin/routing/summary", response_model=RoutingQualitySummarySchema, tags=["Verification Operations"])
def get_admin_routing_summary(
    claims: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    return RoutingQualitySummarySchema(**get_routing_quality_summary(db))


@router.get("/admin/routing/queue", response_model=List[RoutingQueueItemSchema], tags=["Verification Operations"])
def list_routing_verification_queue(
    verification_status: str = Query(
        "needs_verification",
        description="needs_verification | manual_review | verified | unverified | expired | all",
    ),
    q: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    claims: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    qry = (
        db.query(ApplicationRoute)
        .options(joinedload(ApplicationRoute.institution), joinedload(ApplicationRoute.audits))
        .filter(ApplicationRoute.is_active == True)
    )
    if verification_status == "manual_review":
        # Always surface both pending manual review routes (needs_verification)
        # AND routes previously reviewed by a human verifier/admin.
        qry = qry.filter(
            or_(
                ApplicationRoute.verification_status == "needs_verification",
                ApplicationRoute.verification_method.in_(["manual_verifier", "manual_rejected"]),
            )
        )
    elif verification_status == "expired":
        now = datetime.now(timezone.utc)
        qry = qry.filter(
            ApplicationRoute.verification_status == "verified",
            ApplicationRoute.verification_expires_at != None,
            ApplicationRoute.verification_expires_at <= now,
        )
    elif verification_status and verification_status != "all":
        qry = qry.filter(ApplicationRoute.verification_status == verification_status)
    if q:
        pat = f"%{q.strip()}%"
        qry = qry.outerjoin(ApplicationRoute.institution).filter(
            ApplicationRoute.platform_name.ilike(pat)
            | ApplicationRoute.official_url.ilike(pat)
            | Institution.official_name.ilike(pat)
        )

    rows = (
        qry.order_by(
            (ApplicationRoute.verification_status == "needs_verification").desc(),
            ApplicationRoute.verification_method.in_(["manual_verifier", "manual_rejected"]).desc(),
            ApplicationRoute.last_checked_at.desc(),
        )
        .limit(limit)
        .all()
    )
    return [_serialize_routing_queue_item(r) for r in rows]


@router.post("/admin/routing/verify-batch", response_model=BatchRouteVerifyResponse, tags=["Verification Operations"])
def run_batch_routing_verification(
    limit: int = Query(500, ge=1, le=1000),
    claims: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    actor = db.query(User).filter(User.external_auth_id == claims.user_id).first()
    res = reverify_ipeds_routes(
        db=db,
        actor_user_id=actor.id if actor else None,
        actor_role=claims.role,
        actor_email=claims.email,
        limit=limit,
    )
    return BatchRouteVerifyResponse(
        checked=res["checked"],
        promoted_to_verified=res["promoted_to_verified"],
        kept_needs_verification=res["kept_needs_verification"],
        flagged_unverified=res["flagged_unverified"],
        by_method=res["by_method"],
        summary=RoutingQualitySummarySchema(**res["summary"]),
    )


@router.post("/admin/routing/health-check", response_model=BatchHealthCheckResponse, tags=["Verification Operations"])
def run_batch_route_health_checks(
    limit: int = Query(15, ge=1, le=100),
    only_stale: bool = Query(True),
    claims: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    actor = db.query(User).filter(User.external_auth_id == claims.user_id).first()
    res = run_batch_health_checks(
        db=db,
        limit=limit,
        only_stale=only_stale,
        actor_user_id=actor.id if actor else None,
        actor_role=claims.role,
        actor_email=claims.email,
    )
    return BatchHealthCheckResponse(
        checked=res["checked"],
        by_status=res["by_status"],
        results=res["results"],
        summary=RoutingQualitySummarySchema(**get_routing_quality_summary(db)),
    )


@router.post("/admin/routing/expire-stale", response_model=ExpireRoutesResponse, tags=["Verification Operations"])
def expire_stale_verified_routes(
    claims: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    actor = db.query(User).filter(User.external_auth_id == claims.user_id).first()
    res = flag_expired_routes_for_reverification(
        db=db,
        actor_user_id=actor.id if actor else None,
        actor_role=claims.role,
        actor_email=claims.email,
    )
    return ExpireRoutesResponse(
        expired_checked=res["expired_checked"],
        flagged_for_reverification=res["flagged_for_reverification"],
        summary=RoutingQualitySummarySchema(**get_routing_quality_summary(db)),
    )


@router.post("/admin/routing/{route_id}/health-check", response_model=RoutingQueueItemSchema, tags=["Verification Operations"])
def check_single_route_health(
    route_id: UUID,
    claims: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    route = (
        db.query(ApplicationRoute)
        .options(joinedload(ApplicationRoute.institution), joinedload(ApplicationRoute.audits))
        .filter(ApplicationRoute.id == route_id)
        .first()
    )
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application route not found.")

    actor = db.query(User).filter(User.external_auth_id == claims.user_id).first()
    perform_route_health_check(
        db=db,
        route=route,
        actor_user_id=actor.id if actor else None,
        actor_role=claims.role,
        actor_email=claims.email,
        commit=True,
    )
    return _serialize_routing_queue_item(route)


@router.post("/admin/routing/{route_id}/pathway", response_model=RoutingQueueItemSchema, tags=["Verification Operations"])
def verify_route_pathway(
    route_id: UUID,
    payload: RoutePathwayVerifyRequest,
    claims: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    route = (
        db.query(ApplicationRoute)
        .options(joinedload(ApplicationRoute.institution), joinedload(ApplicationRoute.audits))
        .filter(ApplicationRoute.id == route_id)
        .first()
    )
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application route not found.")

    actor = db.query(User).filter(User.external_auth_id == claims.user_id).first()
    try:
        updated = set_pathway_verified(
            db=db,
            route=route,
            verified=payload.pathway_verified,
            applicant_type=payload.applicant_type,
            actor_user_id=actor.id if actor else None,
            actor_role=claims.role,
            actor_email=claims.email,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _serialize_routing_queue_item(updated)


@router.post("/admin/routing/{route_id}/review", response_model=RoutingQueueItemSchema, tags=["Verification Operations"])
def review_application_route(
    route_id: UUID,
    payload: RouteReviewRequest,
    claims: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    route = (
        db.query(ApplicationRoute)
        .options(joinedload(ApplicationRoute.institution), joinedload(ApplicationRoute.audits))
        .filter(ApplicationRoute.id == route_id)
        .first()
    )
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application route not found.")

    actor = db.query(User).filter(User.external_auth_id == claims.user_id).first()
    updated = review_single_route(
        db=db,
        route=route,
        decision=payload.decision,
        actor_user_id=actor.id if actor else None,
        actor_role=claims.role,
        actor_email=claims.email,
        rejection_reason_code=payload.rejection_reason_code,
        notes=payload.notes,
        corrected_url=payload.corrected_url,
        international_instructions=payload.international_instructions,
        pathway_verified=payload.pathway_verified,
        applicant_type=payload.applicant_type,
    )
    return _serialize_routing_queue_item(updated)


@router.get("/admin/evidence/queue", response_model=List[EvidenceQueueItemSchema], tags=["Verification Operations"])
def list_evidence_verification_queue(
    review_status: str = Query("pending", description="pending | accepted | rejected | all"),
    limit: int = Query(100, ge=1, le=250),
    claims: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    qry = (
        db.query(ApplicationSubmissionEvidence)
        .options(
            joinedload(ApplicationSubmissionEvidence.document),
            joinedload(ApplicationSubmissionEvidence.audits),
            joinedload(ApplicationSubmissionEvidence.application).joinedload(Application.institution),
        )
    )
    if review_status and review_status != "all":
        qry = qry.filter(ApplicationSubmissionEvidence.review_status == review_status)

    rows = (
        qry.order_by(
            (ApplicationSubmissionEvidence.review_status == "pending").desc(),
            ApplicationSubmissionEvidence.submitted_at.desc(),
        )
        .limit(limit)
        .all()
    )
    return [_serialize_evidence_queue_item(db, ev) for ev in rows]


@router.get("/admin/evidence/{evidence_id}/document", tags=["Verification Operations"])
def inspect_evidence_vault_document(
    evidence_id: UUID,
    download: bool = Query(False),
    claims: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    ev = (
        db.query(ApplicationSubmissionEvidence)
        .options(joinedload(ApplicationSubmissionEvidence.document))
        .filter(ApplicationSubmissionEvidence.id == evidence_id)
        .first()
    )
    if not ev or not ev.document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence Document Vault artifact not found.")

    doc = ev.document
    if download:
        if not os.path.exists(doc.storage_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored vault file missing on disk.")
        return FileResponse(path=doc.storage_path, filename=doc.original_filename)

    return {
        "document_id": str(doc.id),
        "original_filename": doc.original_filename,
        "file_type": doc.file_type,
        "file_size_bytes": doc.file_size_bytes,
        "file_sha256": doc.file_sha256,
        "document_category": doc.document_category,
        "extracted_text": doc.extraction.extracted_text if doc.extraction else None,
        "detected_language": doc.detected_language,
        "reviewed_by_role": claims.role,
    }


@router.post("/admin/evidence/{evidence_id}/review", response_model=EvidenceQueueItemSchema, tags=["Verification Operations"])
def admin_review_submission_evidence(
    evidence_id: UUID,
    payload: EvidenceReviewRequest,
    claims: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    ev = (
        db.query(ApplicationSubmissionEvidence)
        .options(
            joinedload(ApplicationSubmissionEvidence.document),
            joinedload(ApplicationSubmissionEvidence.audits),
            joinedload(ApplicationSubmissionEvidence.application).joinedload(Application.institution),
        )
        .filter(ApplicationSubmissionEvidence.id == evidence_id)
        .first()
    )
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission evidence not found.")

    updated = execute_evidence_review(
        db=db,
        ev=ev,
        decision=payload.decision,
        claims=claims,
        rejection_reason_code=payload.rejection_reason_code,
        reviewer_notes=payload.reviewer_notes,
    )
    return _serialize_evidence_queue_item(db, updated)
