from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.articulation import ArticulationAgreement, CourseCatalog
from app.models.course import Course
from app.models.document import Document
from app.models.enrollment import EnrollmentRecord
from app.models.institution import Institution
from app.models.profile import StudentProfile
from app.models.user import User
from app.schemas.articulation import (
    AdHocCourseEquivalencyRequest,
    AttachSyllabusRequest,
    CourseCatalogSchema,
    DegreeApplicabilitySummary,
    EvaluatedCourseResult,
)
from app.services.articulation_engine import (
    evaluate_course_against_target,
    evaluate_student_transfer_profile,
)

router = APIRouter()


@router.get("/transfer/catalog", response_model=List[CourseCatalogSchema], tags=["Transfer Articulation"])
def list_course_catalog(
    institution_id: Optional[UUID] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Lists normalized institution courses, descriptions, learning outcomes, and credit systems."""
    query = db.query(CourseCatalog)
    if institution_id:
        query = query.filter(CourseCatalog.institution_id == institution_id)
    if q and q.strip():
        pat = f"%{q.strip()}%"
        query = query.filter(
            or_(
                CourseCatalog.course_code.ilike(pat),
                CourseCatalog.course_name.ilike(pat),
                CourseCatalog.description.ilike(pat),
            )
        )
    return query.order_by(CourseCatalog.course_code.asc()).limit(limit).all()


@router.get("/transfer/agreements", tags=["Transfer Articulation"])
def list_articulation_agreements(
    source_institution_id: Optional[UUID] = Query(None),
    target_institution_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
):
    """Lists published inter-institutional transfer agreements with verified source URLs."""
    query = db.query(ArticulationAgreement)
    if source_institution_id:
        query = query.filter(ArticulationAgreement.source_institution_id == source_institution_id)
    if target_institution_id:
        query = query.filter(ArticulationAgreement.target_institution_id == target_institution_id)
    agreements = query.all()
    results = []
    for ag in agreements:
        results.append(
            {
                "id": ag.id,
                "source_institution_id": ag.source_institution_id,
                "source_institution_name": ag.source_institution.official_name if ag.source_institution else None,
                "target_institution_id": ag.target_institution_id,
                "target_institution_name": ag.target_institution.official_name if ag.target_institution else None,
                "agreement_type": ag.agreement_type,
                "program_name": ag.program_name,
                "academic_year": ag.academic_year,
                "notes": ag.notes,
                "source_name": ag.source_name,
                "source_url": ag.source_url,
                "verification_status": ag.verification_status,
            }
        )
    return results


@router.post(
    "/transfer/equivalencies/evaluate",
    response_model=EvaluatedCourseResult,
    tags=["Transfer Articulation"],
)
def evaluate_single_course(
    payload: AdHocCourseEquivalencyRequest,
    db: Session = Depends(get_db),
):
    """
    3-Tier Equivalency Lookup for any course against a target university:
    - Tier 1: Officially Verified (published articulation agreement)
    - Tier 2: Historically Observed
    - Tier 3: AI-Predicted (content, learning outcomes, credit/level similarity)
    - Unverified: when no agreement and insufficient course description/syllabus exist
    """
    target_inst = db.query(Institution).filter(Institution.id == payload.target_institution_id).first()
    if not target_inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target institution not found.")

    src_inst = None
    if payload.source_institution_id:
        src_inst = db.query(Institution).filter(Institution.id == payload.source_institution_id).first()

    return evaluate_course_against_target(
        db=db,
        target_inst=target_inst,
        source_inst=src_inst,
        source_inst_name=src_inst.official_name if src_inst else None,
        course_code=payload.source_course_code,
        course_name=payload.source_course_name,
        description=payload.source_description,
        learning_outcomes=payload.source_learning_outcomes,
        original_credits=payload.source_credits,
        original_credit_system=payload.source_credit_system,
        course_level=payload.course_level,
        department=payload.department,
        intended_major=payload.intended_major,
    )


@router.get(
    "/transfer/profile-summary",
    response_model=DegreeApplicabilitySummary,
    tags=["Transfer Articulation"],
)
def get_student_transfer_summary(
    target_institution_id: UUID = Query(..., description="Receiving institution UUID"),
    intended_major: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluates the authenticated student's Universal Profile coursework against a target receiving
    university, separating accepted units, major applicability, GE applicability, electives, and unverified courses.
    """
    target_inst = db.query(Institution).filter(Institution.id == target_institution_id).first()
    if not target_inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target institution not found.")

    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    return evaluate_student_transfer_profile(
        db=db,
        profile=profile,
        target_inst=target_inst,
        intended_major=intended_major,
    )


@router.post("/transfer/courses/{course_id}/attach-syllabus", tags=["Transfer Articulation"])
def attach_course_syllabus(
    course_id: UUID,
    payload: AttachSyllabusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Links an uploaded Document Vault syllabus to a student's course record while preserving
    original immutable files and flagging extracted data for human verification.
    """
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")

    course = (
        db.query(Course)
        .join(EnrollmentRecord, EnrollmentRecord.id == Course.enrollment_id)
        .filter(Course.id == course_id, EnrollmentRecord.profile_id == profile.id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found on student profile.")

    doc = (
        db.query(Document)
        .filter(Document.id == payload.document_id, Document.profile_id == profile.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Syllabus document not found in Document Vault.")
    from app.services.document_vault import DocumentVaultService
    DocumentVaultService.assert_document_accessible(doc)

    course.syllabus_document_id = doc.id
    if payload.description:
        course.description = payload.description
    elif doc.extraction and not course.description:
        course.description = doc.extraction.extracted_text[:1200]

    if payload.learning_outcomes:
        course.learning_outcomes = payload.learning_outcomes
    elif doc.extraction and not course.learning_outcomes:
        ext_json = doc.extraction.extracted_data_json or {}
        if isinstance(ext_json.get("learning_outcomes"), list):
            course.learning_outcomes = ext_json["learning_outcomes"]

    db.commit()
    db.refresh(course)
    return {
        "course_id": str(course.id),
        "syllabus_document_id": str(course.syllabus_document_id),
        "learning_outcomes": course.learning_outcomes or [],
        "description": course.description,
        "requires_human_verification": True,
        "notice": "Original syllabus preserved in Document Vault; extracted metadata is subject to receiving institution review.",
    }
