from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.profile import StudentProfile
from app.models.enrollment import EnrollmentRecord
from app.models.course import Course
from app.schemas.profile import (
    StudentProfileCreate,
    StudentProfileUpdate,
    StudentProfileResponse,
    EnrollmentSchema,
    CourseSchema
)
from app.api.deps import get_current_user

router = APIRouter()


def calculate_profile_completion(profile: StudentProfile) -> int:
    score = 0
    # Basic Demographics: 25%
    if profile.first_name and profile.last_name:
        score += 15
    if profile.date_of_birth and profile.country_code:
        score += 10
    
    # Pathway Intent: 25%
    if profile.applicant_type and profile.applicant_type != "undecided":
        score += 15
    if profile.intended_major:
        score += 10

    # Academic History: 35%
    if profile.enrollments and len(profile.enrollments) > 0:
        score += 20
        # If any enrollment has courses
        has_courses = any(len(e.courses) > 0 for e in profile.enrollments)
        if has_courses:
            score += 15

    # Citizenship/Residency: 15%
    if profile.country_of_residence:
        score += 15

    return min(100, score)


@router.get("/profile", response_model=StudentProfileResponse, tags=["Profile"])
def get_student_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found. Please initialize your profile."
        )
    return profile


@router.post("/profile", response_model=StudentProfileResponse, status_code=status.HTTP_201_CREATED, tags=["Profile"])
def create_student_profile(
    profile_in: StudentProfileCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile already exists for this user."
        )

    profile = StudentProfile(
        user_id=current_user.id,
        first_name=profile_in.first_name,
        last_name=profile_in.last_name,
        preferred_first_name=profile_in.preferred_first_name,
        preferred_last_name=profile_in.preferred_last_name,
        name_format=profile_in.name_format,
        full_name_native_script=profile_in.full_name_native_script,
        date_of_birth=profile_in.date_of_birth,
        country_code=profile_in.country_code,
        country_of_residence=profile_in.country_of_residence,
        residency_status=profile_in.residency_status,
        applicant_type=profile_in.applicant_type,
        intended_major=profile_in.intended_major,
        intended_enrollment_term=profile_in.intended_enrollment_term,
        intended_enrollment_year=profile_in.intended_enrollment_year,
    )
    profile.profile_completion_pct = calculate_profile_completion(profile)

    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.patch("/profile", response_model=StudentProfileResponse, tags=["Profile"])
def update_student_profile(
    profile_update: StudentProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found."
        )

    update_data = profile_update.model_dump(exclude_unset=True, exclude={"profile_completion_pct"})
    for field, value in update_data.items():
        setattr(profile, field, value)

    profile.profile_completion_pct = calculate_profile_completion(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/profile/enrollments", response_model=EnrollmentSchema, status_code=status.HTTP_201_CREATED, tags=["Profile"])
def add_enrollment_record(
    enrollment_in: EnrollmentSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile must exist before adding enrollment history."
        )

    enrollment = EnrollmentRecord(
        profile_id=profile.id,
        institution_name_manual=enrollment_in.institution_name_manual,
        institution_country=enrollment_in.institution_country,
        institution_city=enrollment_in.institution_city,
        enrollment_type=enrollment_in.enrollment_type,
        enrollment_status=enrollment_in.enrollment_status,
        start_date=enrollment_in.start_date,
        end_date=enrollment_in.end_date,
        expected_graduation=enrollment_in.expected_graduation,
        degree_type=enrollment_in.degree_type,
        major=enrollment_in.major,
        cumulative_gpa=enrollment_in.cumulative_gpa,
        gpa_scale=enrollment_in.gpa_scale,
        total_credits_earned=enrollment_in.total_credits_earned,
        is_current_institution=enrollment_in.is_current_institution
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    # Recalculate profile completion
    profile.profile_completion_pct = calculate_profile_completion(profile)
    db.commit()

    return enrollment


@router.post("/profile/enrollments/{enrollment_id}/courses", response_model=CourseSchema, status_code=status.HTTP_201_CREATED, tags=["Profile"])
def add_course_record(
    enrollment_id: UUID,
    course_in: CourseSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    enrollment = (
        db.query(EnrollmentRecord)
        .filter(
            EnrollmentRecord.id == enrollment_id,
            EnrollmentRecord.profile_id == profile.id,
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment record not found")

    course = Course(
        enrollment_id=enrollment.id,
        course_code=course_in.course_code,
        course_name=course_in.course_name,
        department=course_in.department,
        credit_hours=course_in.credit_hours,
        credit_type=course_in.credit_type,
        grade=course_in.grade,
        grade_points=course_in.grade_points,
        status=course_in.status,
        academic_term=course_in.academic_term,
        academic_year=course_in.academic_year,
        is_transferable=course_in.is_transferable
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course
