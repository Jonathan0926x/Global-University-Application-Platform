from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.ingestion.routing_seed import validate_routing_url
from app.models.institution import Institution
from app.models.routing import ApplicationRoute
from app.schemas.routing import (
    ApplicationRouteSchema,
    InstitutionRoutingResolutionSchema,
    UrlValidationRequest,
    UrlValidationResponse,
)
from app.services.routing_engine import ensure_routes_seeded, resolve_institution_routing

router = APIRouter()


@router.get("/routing/directory", response_model=List[ApplicationRouteSchema], tags=["Application Routing"])
def list_application_routing_directory(
    q: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    applicant_type: Optional[str] = Query(None),
    platform_type: Optional[str] = Query(None),
    verification_status: Optional[str] = Query(None),
    verified_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=250),
    db: Session = Depends(get_db),
):
    ensure_routes_seeded(db)
    qry = db.query(ApplicationRoute).options(joinedload(ApplicationRoute.institution)).filter(ApplicationRoute.is_active == True)

    if country:
        qry = qry.filter(ApplicationRoute.country_code == country.upper()[:2])
    if applicant_type and applicant_type != "all":
        qry = qry.filter(ApplicationRoute.applicant_type.in_([applicant_type, "all", f"international_{applicant_type}"]))
    if platform_type:
        qry = qry.filter(ApplicationRoute.platform_type == platform_type)
    if verified_only:
        qry = qry.filter(ApplicationRoute.verification_status == "verified")
    elif verification_status:
        qry = qry.filter(ApplicationRoute.verification_status == verification_status)
    if q:
        pat = f"%{q.strip()}%"
        qry = qry.outerjoin(ApplicationRoute.institution).filter(
            or_(
                ApplicationRoute.platform_name.ilike(pat),
                ApplicationRoute.official_url.ilike(pat),
                ApplicationRoute.international_instructions.ilike(pat),
                Institution.official_name.ilike(pat),
            )
        )

    rows = (
        qry.order_by(
            (ApplicationRoute.verification_status == "verified").desc(),
            ApplicationRoute.institution_id.is_(None).desc(),
            ApplicationRoute.verified_at.desc().nullslast(),
        )
        .limit(limit)
        .all()
    )

    out: List[ApplicationRouteSchema] = []
    for r in rows:
        item = ApplicationRouteSchema.model_validate(r)
        item.institution_name = r.institution.official_name if r.institution else "Centralized Platform"
        out.append(item)
    return out


@router.get(
    "/routing/institutions/{institution_id}",
    response_model=InstitutionRoutingResolutionSchema,
    tags=["Application Routing"],
)
def resolve_routes_for_institution(
    institution_id: UUID,
    applicant_type: str = Query("first_year"),
    db: Session = Depends(get_db),
):
    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

    resolved = resolve_institution_routing(db, inst, applicant_type=applicant_type)

    def _map_routes(items: List[ApplicationRoute]) -> List[ApplicationRouteSchema]:
        res = []
        for r in items:
            s = ApplicationRouteSchema.model_validate(r)
            s.institution_name = inst.official_name
            res.append(s)
        return res

    return InstitutionRoutingResolutionSchema(
        institution_id=inst.id,
        institution_name=inst.official_name,
        applicant_type=resolved["applicant_type"],
        routing_status=resolved["routing_status"],
        has_verified_destination=resolved["has_verified_destination"],
        verified_routes=_map_routes(resolved["verified_routes"]),
        needs_verification_routes=_map_routes(resolved["needs_verification_routes"]),
        excluded_unverified=resolved["excluded_unverified"],
        notice=resolved["notice"],
    )


@router.post("/routing/validate-url", response_model=UrlValidationResponse, tags=["Application Routing"])
def validate_portal_url(payload: UrlValidationRequest):
    return UrlValidationResponse(**validate_routing_url(payload.url))
