from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.institution import Institution
from app.models.profile import StudentProfile
from app.models.requirements import CountryQualification, Deadline
from app.models.user import User
from app.schemas.requirements import (
    CountryQualificationSchema,
    DeadlineSchema,
    DynamicChecklistResponseSchema,
    InstitutionAdmissionsSummarySchema,
)
from app.services.requirements_engine import (
    _serialize_deadline,
    evaluate_dynamic_checklist,
    get_institution_admissions_summary,
)

router = APIRouter()


@router.get(
    "/institutions/{institution_id}/requirements",
    response_model=InstitutionAdmissionsSummarySchema,
    tags=["Admissions Requirements"],
)
def get_institution_requirements(
    institution_id: UUID,
    applicant_type: Optional[str] = Query(
        None,
        description="Filter by pathway: first_year, transfer, international_first_year, international_transfer, all",
    ),
    major: Optional[str] = Query(None, description="Optional intended major filter"),
    academic_year: str = Query("2026-2027", description="Target admissions cycle"),
    db: Session = Depends(get_db),
):
    """
    Public endpoint returning source-verified admission requirements, deadlines, and country
    qualifications for an institution. Never fabricates requirements when unverified.
    """
    institution = db.query(Institution).filter(Institution.id == institution_id).first()
    if not institution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

    return get_institution_admissions_summary(
        db=db,
        institution=institution,
        applicant_type=applicant_type,
        intended_major=major,
        academic_year=academic_year,
    )


@router.get(
    "/institutions/{institution_id}/checklist",
    response_model=DynamicChecklistResponseSchema,
    tags=["Admissions Requirements"],
)
def get_personalized_checklist(
    institution_id: UUID,
    applicant_type: Optional[str] = Query(None, description="Override pathway: first_year or transfer"),
    major: Optional[str] = Query(None, description="Override intended major"),
    academic_year: str = Query("2026-2027"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Authenticated endpoint evaluating the logged-in student's Universal Student Profile
    against an institution's verified admission requirements.
    """
    institution = db.query(Institution).filter(Institution.id == institution_id).first()
    if not institution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    return evaluate_dynamic_checklist(
        db=db,
        institution=institution,
        profile=profile,
        applicant_type=applicant_type,
        intended_major=major,
        academic_year=academic_year,
    )


@router.get(
    "/qualifications",
    response_model=List[CountryQualificationSchema],
    tags=["Admissions Requirements"],
)
def list_country_qualifications(
    country: Optional[str] = Query(None, description="ISO 3166-1 alpha-2 country code"),
    db: Session = Depends(get_db),
):
    """Lists verified national examinations, secondary diplomas, and international qualification systems."""
    query = db.query(CountryQualification)
    if country:
        query = query.filter(CountryQualification.country_code == country.strip().upper()[:2])
    return query.order_by(CountryQualification.country_code.asc(), CountryQualification.qualification_type.asc()).all()


@router.get(
    "/deadlines/upcoming",
    response_model=List[DeadlineSchema],
    tags=["Admissions Requirements"],
)
def list_upcoming_deadlines(
    country: Optional[str] = Query(None, description="ISO 3166-1 alpha-2 country code"),
    applicant_type: Optional[str] = Query(None),
    days: int = Query(180, ge=1, le=730),
    db: Session = Depends(get_db),
):
    """Lists upcoming verified institutional application deadlines ordered chronologically."""
    today = date.today()
    cutoff = today + timedelta(days=days)
    query = (
        db.query(Deadline)
        .join(Institution, Institution.id == Deadline.institution_id)
        .filter(
            Deadline.is_current == True,
            Deadline.deadline_date.isnot(None),
            Deadline.deadline_date >= today,
            Deadline.deadline_date <= cutoff,
        )
    )
    if country:
        query = query.filter(Institution.country_code == country.strip().upper()[:2])
    if applicant_type:
        query = query.filter(Deadline.applicant_type.in_([applicant_type, "all"]))
    rows = query.order_by(Deadline.deadline_date.asc()).limit(100).all()
    return [_serialize_deadline(d, today=today) for d in rows]
