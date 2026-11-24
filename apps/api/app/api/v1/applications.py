from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.profile import StudentProfile
from app.models.institution import Institution
from app.models.application import Application, ApplicationRequirementStatus
from app.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    InstitutionSummarySchema
)
from app.api.deps import get_current_user
from app.ingestion.countries_seed import ensure_country_exists

router = APIRouter()


def seed_sample_institutions_if_empty(db: Session):
    count = db.query(Institution).count()
    if count == 0:
        ensure_country_exists(db, "US", "United States")
        samples = [
            Institution(
                official_name="University of California, Berkeley",
                alternative_names=["UC Berkeley", "Cal"],
                abbreviation="UCB",
                country_code="US",
                state_province="CA",
                city="Berkeley",
                institution_type="university",
                control_type="public",
                official_website="https://www.berkeley.edu",
                admissions_website="https://admissions.berkeley.edu",
                tuition_in_state=14226.0,
                tuition_out_of_state=44008.0,
                accepts_transfer=True,
                accepts_first_year=True
            ),
            Institution(
                official_name="University of California, Los Angeles",
                alternative_names=["UCLA"],
                abbreviation="UCLA",
                country_code="US",
                state_province="CA",
                city="Los Angeles",
                institution_type="university",
                control_type="public",
                official_website="https://www.ucla.edu",
                admissions_website="https://admission.ucla.edu",
                tuition_in_state=13746.0,
                tuition_out_of_state=43528.0,
                accepts_transfer=True,
                accepts_first_year=True
            ),
            Institution(
                official_name="San Francisco State University",
                alternative_names=["SFSU", "San Francisco State"],
                abbreviation="SFSU",
                country_code="US",
                state_province="CA",
                city="San Francisco",
                institution_type="university",
                control_type="public",
                official_website="https://www.sfsu.edu",
                admissions_website="https://future.sfsu.edu",
                tuition_in_state=7484.0,
                tuition_out_of_state=19364.0,
                accepts_transfer=True,
                accepts_first_year=True
            ),
            Institution(
                official_name="De Anza College",
                alternative_names=["De Anza"],
                abbreviation="DAC",
                country_code="US",
                state_province="CA",
                city="Cupertino",
                institution_type="community_college",
                control_type="public",
                official_website="https://www.deanza.edu",
                tuition_in_state=1560.0,
                tuition_out_of_state=9120.0,
                accepts_transfer=False,
                accepts_first_year=True
            )
        ]
        db.add_all(samples)
        db.commit()


@router.get("/institutions", response_model=List[InstitutionSummarySchema], tags=["Institutions"])
def list_institutions(
    type: Optional[str] = None,
    accepts_transfer: Optional[bool] = None,
    accepts_first_year: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    seed_sample_institutions_if_empty(db)
    query = db.query(Institution).filter(Institution.is_published == True)
    if type:
        query = query.filter(Institution.institution_type == type)
    if accepts_transfer is not None:
        query = query.filter(Institution.accepts_transfer == accepts_transfer)
    if accepts_first_year is not None:
        query = query.filter(Institution.accepts_first_year == accepts_first_year)
    return query.all()


@router.get("/applications", response_model=List[ApplicationResponse], tags=["Applications"])
def list_applications(
    applicant_type: Optional[str] = Query(None, description="Filter by 'first_year' or 'transfer'"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        return []

    query = db.query(Application).filter(Application.profile_id == profile.id)
    if applicant_type:
        query = query.filter(Application.applicant_type == applicant_type)
    return query.order_by(Application.created_at.desc()).all()


@router.post("/applications", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED, tags=["Applications"])
def create_application_workspace(
    app_in: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile required to create an application workspace."
        )

    institution = db.query(Institution).filter(Institution.id == app_in.institution_id).first()
    if not institution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target institution not found."
        )

    # Validate pathway support
    if app_in.applicant_type == "transfer" and not institution.accepts_transfer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{institution.official_name} does not currently accept transfer applications."
        )
    if app_in.applicant_type == "first_year" and not institution.accepts_first_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{institution.official_name} does not accept first-year applications."
        )

    application = Application(
        profile_id=profile.id,
        institution_id=institution.id,
        applicant_type=app_in.applicant_type,
        status="planning",
        intended_major=app_in.intended_major or profile.intended_major,
        intended_term=app_in.intended_term or profile.intended_enrollment_term or "Fall 2027",
        academic_year=app_in.academic_year or "2026-2027",
        readiness_pct=25
    )
    db.add(application)
    db.flush()

    # Generate initial dynamic checklist based on applicant pathway
    checklist_items = []
    if app_in.applicant_type == "transfer":
        checklist_items = [
            ApplicationRequirementStatus(application_id=application.id, title="Official College Transcript(s)", category="document", importance="required", status="pending"),
            ApplicationRequirementStatus(application_id=application.id, title="Transfer Personal Statement / Statement of Purpose", category="document", importance="required", status="pending"),
            ApplicationRequirementStatus(application_id=application.id, title="Major Prerequisites Audit (60 transferable units minimum)", category="academic", importance="required", status="pending"),
            ApplicationRequirementStatus(application_id=application.id, title="Professor Recommendation Letter", category="document", importance="optional", status="pending"),
            ApplicationRequirementStatus(application_id=application.id, title="Application Fee or Approved Fee Waiver", category="administrative", importance="required", status="pending")
        ]
    else: # first_year
        checklist_items = [
            ApplicationRequirementStatus(application_id=application.id, title="Official High School Secondary Transcript", category="document", importance="required", status="pending"),
            ApplicationRequirementStatus(application_id=application.id, title="Personal Essay / Statement", category="document", importance="required", status="pending"),
            ApplicationRequirementStatus(application_id=application.id, title="Standardized Exam Scores (SAT/ACT or International Bac)", category="academic", importance="recommended", status="pending"),
            ApplicationRequirementStatus(application_id=application.id, title="High School Counselor Recommendation", category="document", importance="required", status="pending"),
            ApplicationRequirementStatus(application_id=application.id, title="Application Fee or Fee Waiver Code", category="administrative", importance="required", status="pending")
        ]

    db.add_all(checklist_items)
    db.commit()
    db.refresh(application)
    return application


@router.get("/applications/{application_id}", response_model=ApplicationResponse, tags=["Applications"])
def get_application(
    application_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    app = db.query(Application).filter(
        Application.id == application_id,
        Application.profile_id == profile.id
    ).first()

    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application workspace not found")
    return app
