from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID


class CitizenshipSchema(BaseModel):
    country_code: str
    citizenship_type: str = "citizen"
    is_primary: str = "Y"

    model_config = ConfigDict(from_attributes=True)


class CourseSchema(BaseModel):
    id: Optional[UUID] = None
    course_code: Optional[str] = None
    course_name: str
    department: Optional[str] = None
    credit_hours: Optional[float] = None
    credit_type: str = "semester_hour"
    grade: Optional[str] = None
    grade_points: Optional[float] = None
    status: str = "completed"
    academic_term: Optional[str] = None
    academic_year: Optional[str] = None
    is_transferable: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class EnrollmentSchema(BaseModel):
    id: Optional[UUID] = None
    institution_name_manual: Optional[str] = None
    institution_country: Optional[str] = "US"
    institution_city: Optional[str] = None
    enrollment_type: str  # secondary, community_college, undergraduate
    enrollment_status: str = "current"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    expected_graduation: Optional[date] = None
    degree_type: Optional[str] = None
    major: Optional[str] = None
    cumulative_gpa: Optional[float] = None
    gpa_scale: Optional[float] = 4.0
    total_credits_earned: Optional[float] = None
    is_current_institution: bool = False
    courses: List[CourseSchema] = []

    model_config = ConfigDict(from_attributes=True)


class StudentProfileCreate(BaseModel):
    first_name: str
    last_name: str
    preferred_first_name: Optional[str] = None
    preferred_last_name: Optional[str] = None
    name_format: str = "western"
    full_name_native_script: Optional[str] = None
    date_of_birth: Optional[date] = None
    country_code: Optional[str] = "US"
    country_of_residence: Optional[str] = "US"
    residency_status: Optional[str] = "citizen"
    applicant_type: str = "undecided"  # first_year, transfer, both
    intended_major: Optional[str] = None
    intended_enrollment_term: Optional[str] = None
    intended_enrollment_year: Optional[int] = None


class StudentProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    preferred_first_name: Optional[str] = None
    preferred_last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    country_code: Optional[str] = None
    country_of_residence: Optional[str] = None
    residency_status: Optional[str] = None
    applicant_type: Optional[str] = None
    intended_major: Optional[str] = None
    intended_enrollment_term: Optional[str] = None
    intended_enrollment_year: Optional[int] = None
    profile_completion_pct: Optional[int] = None


class StudentProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    preferred_first_name: Optional[str] = None
    preferred_last_name: Optional[str] = None
    name_format: str
    full_name_native_script: Optional[str] = None
    date_of_birth: Optional[date] = None
    country_code: Optional[str] = None
    country_of_residence: Optional[str] = None
    residency_status: Optional[str] = None
    applicant_type: str
    intended_major: Optional[str] = None
    intended_enrollment_term: Optional[str] = None
    intended_enrollment_year: Optional[int] = None
    profile_completion_pct: int
    created_at: datetime
    updated_at: datetime
    citizenships: List[CitizenshipSchema] = []
    enrollments: List[EnrollmentSchema] = []

    model_config = ConfigDict(from_attributes=True)
