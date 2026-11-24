from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.api.deps import require_admin_claims
from app.core.auth_provider import UserClaims
from app.models.country import Country
from app.models.institution import Institution, AcademicProgram
from app.models.provenance import DataProvenance, DataQualityFlag, IngestionRun
from app.schemas.institution import (
    CountrySchema,
    InstitutionDetailSchema,
    InstitutionSearchResponse,
    InstitutionSummaryV3Schema,
    DataProvenanceSchema,
    DataQualityFlagSchema,
    IngestionRunSchema,
)

router = APIRouter()


@router.get("/countries", response_model=List[CountrySchema], tags=["Global Infrastructure"])
def list_countries(
    region: Optional[str] = Query(None, description="Filter by geographic region"),
    db: Session = Depends(get_db),
):
    query = db.query(Country)
    if region:
        query = query.filter(Country.region.ilike(f"%{region}%"))
    return query.order_by(Country.name.asc()).all()


@router.get("/institutions/filters", tags=["Institutions"])
def get_institution_filter_options(db: Session = Depends(get_db)):
    """Returns distinct available filter values from published database records."""
    total_count = db.query(func.count(Institution.id)).filter(Institution.is_published == True).scalar() or 0
    us_count = (
        db.query(func.count(Institution.id))
        .filter(Institution.is_published == True, Institution.country_code == "US")
        .scalar()
        or 0
    )
    countries = (
        db.query(Institution.country_code, func.count(Institution.id))
        .filter(Institution.is_published == True)
        .group_by(Institution.country_code)
        .order_by(func.count(Institution.id).desc())
        .all()
    )
    states = (
        db.query(Institution.state_province)
        .filter(
            Institution.is_published == True,
            Institution.country_code == "US",
            Institution.state_province.isnot(None),
        )
        .distinct()
        .order_by(Institution.state_province.asc())
        .all()
    )
    types = (
        db.query(Institution.institution_type, func.count(Institution.id))
        .filter(Institution.is_published == True)
        .group_by(Institution.institution_type)
        .order_by(func.count(Institution.id).desc())
        .all()
    )
    return {
        "total_institutions": total_count,
        "us_institutions": us_count,
        "countries": [{"code": c, "count": n} for c, n in countries],
        "us_states": [s[0] for s in states if s[0] and len(s[0]) <= 10],
        "institution_types": [{"type": t, "count": n} for t, n in types],
    }


@router.get("/institutions/search", response_model=InstitutionSearchResponse, tags=["Institutions"])
def search_institutions(
    q: Optional[str] = Query(None, description="Full-text and fuzzy search query"),
    country: Optional[str] = Query(None, description="ISO 3166-1 alpha-2 country code"),
    state: Optional[str] = Query(None, description="State or province"),
    type: Optional[str] = Query(None, description="Institution type"),
    control: Optional[str] = Query(None, description="Control type: public, private_nonprofit, private_forprofit"),
    accepts_transfer: Optional[bool] = Query(None),
    accepts_first_year: Optional[bool] = Query(None),
    accepts_international: Optional[bool] = Query(None),
    tuition_max: Optional[float] = Query(None, ge=0),
    enrollment_min: Optional[int] = Query(None, ge=0),
    enrollment_max: Optional[int] = Query(None, ge=0),
    cip_code: Optional[str] = Query(None, description="Filter by AcademicProgram CIP code prefix"),
    sort: str = Query("relevance", description="Sort order: relevance, enrollment_desc, tuition_asc, name_asc"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Faceted global institutional search powered by PostgreSQL FTS + trigram similarity.
    Public endpoint: strictly institutional metadata only; zero student PII exposed.
    """
    query = db.query(Institution).filter(Institution.is_published == True)

    if country:
        query = query.filter(Institution.country_code == country.strip().upper()[:2])
    if state:
        st_clean = state.strip()
        if len(st_clean) == 2:
            query = query.filter(func.upper(Institution.state_province) == st_clean.upper())
        else:
            query = query.filter(Institution.state_province.ilike(f"%{st_clean}%"))
    if type:
        query = query.filter(Institution.institution_type == type.strip())
    if control:
        query = query.filter(Institution.control_type == control.strip())
    if accepts_transfer is not None:
        query = query.filter(Institution.accepts_transfer == accepts_transfer)
    if accepts_first_year is not None:
        query = query.filter(Institution.accepts_first_year == accepts_first_year)
    if accepts_international is not None:
        query = query.filter(Institution.accepts_international == accepts_international)
    if tuition_max is not None:
        query = query.filter(
            or_(
                Institution.tuition_in_state <= tuition_max,
                Institution.tuition_out_of_state <= tuition_max,
            )
        )
    if enrollment_min is not None:
        query = query.filter(Institution.total_enrollment >= enrollment_min)
    if enrollment_max is not None:
        query = query.filter(Institution.total_enrollment <= enrollment_max)
    if cip_code:
        query = query.join(AcademicProgram, AcademicProgram.institution_id == Institution.id).filter(
            AcademicProgram.cip_code.ilike(f"{cip_code.strip()}%")
        ).distinct()

    ts_query = None
    if q and q.strip():
        q_clean = q.strip()
        ts_query = func.plainto_tsquery("english", q_clean)
        ilike_pat = f"%{q_clean}%"
        query = query.filter(
            or_(
                Institution.search_vector.op("@@")(ts_query),
                Institution.official_name.ilike(ilike_pat),
                Institution.abbreviation.ilike(ilike_pat),
                Institution.city.ilike(ilike_pat),
                Institution.ipeds_unit_id == q_clean,
                Institution.ror_id == q_clean,
            )
        )

    if sort == "enrollment_desc":
        query = query.order_by(Institution.total_enrollment.desc().nullslast(), Institution.official_name.asc())
    elif sort == "tuition_asc":
        query = query.order_by(Institution.tuition_in_state.asc().nullslast(), Institution.official_name.asc())
    elif sort == "name_asc":
        query = query.order_by(Institution.official_name.asc())
    elif ts_query is not None:
        query = query.order_by(
            func.coalesce(func.ts_rank(Institution.search_vector, ts_query), 0.0).desc(),
            Institution.data_completeness_score.desc(),
            Institution.total_enrollment.desc().nullslast(),
            Institution.official_name.asc(),
        )
    else:
        query = query.order_by(
            Institution.data_completeness_score.desc(),
            Institution.total_enrollment.desc().nullslast(),
            Institution.official_name.asc(),
        )

    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()

    return InstitutionSearchResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/institutions/{institution_id}", response_model=InstitutionDetailSchema, tags=["Institutions"])
def get_institution_detail(
    institution_id: UUID,
    db: Session = Depends(get_db),
):
    inst = db.query(Institution).filter(
        Institution.id == institution_id,
        Institution.is_published == True,
    ).first()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

    provenance = (
        db.query(DataProvenance)
        .filter(
            DataProvenance.entity_type == "institution",
            DataProvenance.entity_id == inst.id,
            DataProvenance.is_current == True,
        )
        .order_by(DataProvenance.retrieved_at.desc())
        .all()
    )

    campuses = (
        db.query(Institution)
        .filter(Institution.parent_institution_id == inst.id, Institution.is_published == True)
        .all()
    )

    detail = InstitutionDetailSchema.model_validate(inst)
    detail.campuses = [InstitutionSummaryV3Schema.model_validate(c) for c in campuses]
    detail.provenance_summary = [DataProvenanceSchema.model_validate(p) for p in provenance]
    return detail


@router.get(
    "/institutions/{institution_id}/provenance",
    response_model=List[DataProvenanceSchema],
    tags=["Provenance & Data Quality"],
)
def get_institution_provenance_history(
    institution_id: UUID,
    db: Session = Depends(get_db),
):
    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

    return (
        db.query(DataProvenance)
        .filter(
            DataProvenance.entity_type == "institution",
            DataProvenance.entity_id == institution_id,
        )
        .order_by(DataProvenance.created_at.desc())
        .all()
    )


@router.get(
    "/admin/quality-flags",
    response_model=List[DataQualityFlagSchema],
    tags=["Provenance & Data Quality"],
)
def list_data_quality_flags(
    resolved: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    _: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    return (
        db.query(DataQualityFlag)
        .filter(DataQualityFlag.resolved == resolved)
        .order_by(DataQualityFlag.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get(
    "/admin/ingestion-runs",
    response_model=List[IngestionRunSchema],
    tags=["Provenance & Data Quality"],
)
def list_ingestion_runs(
    limit: int = Query(25, ge=1, le=100),
    _: UserClaims = Depends(require_admin_claims),
    db: Session = Depends(get_db),
):
    return (
        db.query(IngestionRun)
        .order_by(IngestionRun.started_at.desc())
        .limit(limit)
        .all()
    )
