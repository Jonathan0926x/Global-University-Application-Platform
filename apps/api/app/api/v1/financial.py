from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_profile, get_db
from app.models.institution import Institution
from app.models.profile import StudentProfile
from app.models.rag import ScholarshipProgram
from app.schemas.phase4 import (
    CatalogCoverageAuditResponse,
    NetPriceCalculateRequest,
    NetPriceCalculationResponse,
    ScholarshipEligibilityResultSchema,
    ScholarshipMatchRequest,
    ScholarshipMatchResponse,
    StudentCoverageReportResponse,
)
from app.services.coverage_analytics import analyze_student_coverage, generate_global_coverage_audit
from app.services.financial_engine import (
    calculate_net_price,
    ensure_phase4_seeded,
    evaluate_single_scholarship,
    match_scholarships_deterministic,
)

router = APIRouter()


@router.get(
    "/financial/scholarships",
    response_model=List[ScholarshipEligibilityResultSchema],
    tags=["Financial & Scholarships"],
)
def list_verified_scholarships(
    country: Optional[str] = Query(None),
    funding_type: Optional[str] = Query(None),
    covers_international: Optional[bool] = Query(None),
    degree_level: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    ensure_phase4_seeded(db)
    qry = (
        db.query(ScholarshipProgram)
        .options(joinedload(ScholarshipProgram.institution), joinedload(ScholarshipProgram.rules))
        .filter(ScholarshipProgram.is_verified == True, ScholarshipProgram.is_current == True)
    )
    if country:
        qry = qry.filter(ScholarshipProgram.country_code == country.strip().upper()[:2])
    if funding_type:
        qry = qry.filter(ScholarshipProgram.funding_type == funding_type.strip().lower())
    if covers_international is not None:
        qry = qry.filter(ScholarshipProgram.covers_international == covers_international)
    if q:
        pat = f"%{q.strip()}%"
        qry = qry.filter(
            or_(
                ScholarshipProgram.title.ilike(pat),
                ScholarshipProgram.eligibility_summary.ilike(pat),
                ScholarshipProgram.source_name.ilike(pat),
            )
        )

    rows = qry.order_by(ScholarshipProgram.is_guaranteed_statutory.desc(), ScholarshipProgram.title.asc()).limit(limit).all()
    if degree_level:
        dl = degree_level.strip().lower()
        rows = [r for r in rows if dl in [str(x).lower() for x in (r.degree_levels or [])]]
    neutral_ctx = {
        "citizenships": [],
        "primary_citizenship": None,
        "dual_citizenship": None,
        "country_of_residence": None,
        "residency_state": None,
        "residency_status": None,
        "applicant_type": None,
        "degree_level": degree_level.strip().lower() if degree_level else None,
        "date_of_birth": None,
        "field_of_study": None,
        "qualifications": [],
        "exam_scores": {},
        "language_proficiencies": {},
        "has_us_community_college": False,
        "has_enrollment_history": False,
        "currently_enrolled": None,
        "final_year_undergraduate": None,
        "is_full_time": None,
        "gpa_4": None,
        "gpa_display": "Not Reported",
        "financial_need_level": None,
        "household_income_usd": None,
        "destination_country": None,
        "institution_id": None,
    }
    return [ScholarshipEligibilityResultSchema(**evaluate_single_scholarship(r, neutral_ctx)) for r in rows]


@router.post(
    "/financial/scholarships/match",
    response_model=ScholarshipMatchResponse,
    tags=["Financial & Scholarships"],
)
def match_scholarships_for_student(
    payload: ScholarshipMatchRequest,
    profile: Optional[StudentProfile] = Depends(get_current_profile),
    db: Session = Depends(get_db),
):
    res = match_scholarships_deterministic(
        db=db,
        profile=profile,
        overrides=payload.model_dump(),
        include_ineligible=payload.include_ineligible,
    )
    return ScholarshipMatchResponse(**res)


@router.post(
    "/financial/net-price",
    response_model=NetPriceCalculationResponse,
    tags=["Financial & Scholarships"],
)
def run_net_price_calculator(
    payload: NetPriceCalculateRequest,
    profile: Optional[StudentProfile] = Depends(get_current_profile),
    db: Session = Depends(get_db),
):
    inst = db.query(Institution).filter(Institution.id == payload.institution_id).first()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

    res = calculate_net_price(
        db=db,
        institution=inst,
        profile=profile,
        params=payload.model_dump(),
    )
    return NetPriceCalculationResponse(**res)


@router.get(
    "/financial/coverage-audit",
    response_model=CatalogCoverageAuditResponse,
    tags=["Financial & Scholarships"],
)
def get_catalog_coverage_audit(db: Session = Depends(get_db)):
    """
    Returns live Workstream E–G & Phase 4.1 global catalog verification metrics, pathway coverage,
    student archetype matrix, prioritized coverage gaps, and deferred research queue.
    """
    return CatalogCoverageAuditResponse(**generate_global_coverage_audit(db))


@router.post(
    "/financial/student-coverage",
    response_model=StudentCoverageReportResponse,
    tags=["Financial & Scholarships"],
)
def evaluate_student_scholarship_coverage(
    payload: ScholarshipMatchRequest,
    profile: Optional[StudentProfile] = Depends(get_current_profile),
    db: Session = Depends(get_db),
):
    """
    Evaluates student-level scholarship accessibility across separated non-blended counters
    (matched, verified eligibility, verified funding, open cycle, actionable open verified,
    insufficient info, and manual review) plus actionable coverage gaps.
    """
    return StudentCoverageReportResponse(**analyze_student_coverage(db, profile, payload.model_dump()))
