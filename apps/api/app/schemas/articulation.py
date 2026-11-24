from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class CourseCatalogSchema(BaseModel):
    id: UUID
    institution_id: UUID
    course_code: str
    course_name: str
    department: Optional[str] = None
    subject_area: Optional[str] = None
    description: Optional[str] = None
    learning_outcomes: List[str] = []
    prerequisites: Optional[str] = None
    credit_hours: Optional[float] = None
    credit_system: str
    course_level: Optional[str] = None
    is_lab: bool = False
    catalog_year: str
    source_name: str
    source_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AdHocCourseEquivalencyRequest(BaseModel):
    source_institution_id: Optional[UUID] = None
    source_course_code: str
    source_course_name: str
    source_description: Optional[str] = None
    source_learning_outcomes: List[str] = []
    source_credits: Optional[float] = None
    source_credit_system: str = "us_semester"
    course_level: Optional[str] = None
    department: Optional[str] = None
    target_institution_id: UUID
    intended_major: Optional[str] = None


class EvaluatedCourseResult(BaseModel):
    student_course_id: Optional[UUID] = None
    source_institution_name: Optional[str] = None
    source_course_code: str
    source_course_name: str
    original_credits: Optional[float] = None
    original_credit_system: str = "us_semester"
    normalized_semester_credits: Optional[float] = None
    credits_transferable: float = 0.0

    # 3-Tier Classification
    equivalency_tier: Optional[int] = None  # 1=Official, 2=Historical, 3=AI-Predicted, None=Unverified
    tier_label: str  # Officially Verified | Historically Observed | AI-Predicted (Unverified) | Unverified
    equivalency_type: str  # direct | partial | combined | elective_only | no_equivalent | unverified
    confidence_score: float = 0.0

    target_course_code: Optional[str] = None
    target_course_name: Optional[str] = None

    # Degree Applicability Distinction
    applicability_bucket: str  # major_and_ge | major | ge | elective_only | non_applicable | unverified
    satisfies_major_requirement: bool = False
    satisfies_ge_requirement: bool = False
    ge_category: Optional[str] = None
    satisfies_prerequisite: bool = False
    elective_only: bool = False

    # Metadata & Guards
    is_duplicate: bool = False
    requires_syllabus: bool = False
    syllabus_document_id: Optional[UUID] = None
    supporting_evidence: str
    disclaimer: str
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    verified_at: Optional[datetime] = None


class DegreeApplicabilitySummary(BaseModel):
    target_institution_id: UUID
    target_institution_name: str
    intended_major: Optional[str] = None

    # Course & Credit Counters (never equating accepted units w/ degree-applicable units!)
    total_courses_evaluated: int = 0
    officially_verified_count: int = 0
    historically_observed_count: int = 0
    ai_predicted_count: int = 0
    unverified_course_count: int = 0
    missing_syllabus_count: int = 0
    duplicate_course_count: int = 0

    total_original_credits_by_system: Dict[str, float] = {}
    normalized_semester_credits_attempted: float = 0.0
    officially_transferable_credits: float = 0.0
    potentially_transferable_credits: float = 0.0
    unverified_credits: float = 0.0

    # Degree Applicability Breakdown
    major_applicable_credits: float = 0.0
    ge_applicable_credits: float = 0.0
    elective_only_credits: float = 0.0
    non_applicable_or_duplicate_credits: float = 0.0

    ge_areas_satisfied: List[str] = []
    major_prerequisites_satisfied: List[str] = []
    major_prerequisites_remaining: List[str] = []
    warnings: List[str] = []
    disclaimer: str
    evaluated_courses: List[EvaluatedCourseResult] = []


class AttachSyllabusRequest(BaseModel):
    document_id: UUID
    learning_outcomes: Optional[List[str]] = None
    description: Optional[str] = None
