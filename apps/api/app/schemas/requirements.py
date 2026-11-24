from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from uuid import UUID


class RequirementConditionSchema(BaseModel):
    id: UUID
    condition_type: str
    condition_field: str
    condition_operator: str
    condition_value: Any
    result_importance: str
    explanation: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InstitutionRequirementSchema(BaseModel):
    id: UUID
    institution_id: UUID
    program_id: Optional[UUID] = None
    program_name_filter: Optional[str] = None
    cip_code: Optional[str] = None
    applicant_type: str
    importance: str
    requirement_type: str
    requirement_subtype: Optional[str] = None
    category: str
    title: str
    description: Optional[str] = None
    institution_specific_notes: Optional[str] = None
    quantity: Optional[int] = 1
    minimum_value: Optional[str] = None
    maximum_value: Optional[str] = None
    fee_amount: Optional[float] = None
    fee_currency: Optional[str] = None
    fee_waiver_available: Optional[bool] = None
    academic_year: str
    source_name: str
    source_type: str
    source_url: str
    verified_at: Optional[datetime] = None
    confidence_level: str
    verification_status: str
    conditions: List[RequirementConditionSchema] = []


class DeadlineSchema(BaseModel):
    id: UUID
    institution_id: UUID
    program_name_filter: Optional[str] = None
    applicant_type: str
    deadline_type: str
    intake_term: str
    deadline_date: Optional[date] = None
    deadline_time: Optional[str] = None
    timezone: Optional[str] = None
    is_firm: bool
    notification_date: Optional[date] = None
    academic_year: str
    notes: Optional[str] = None
    days_remaining: Optional[int] = None
    is_past: Optional[bool] = None
    source_name: str
    source_url: str
    verified_at: Optional[datetime] = None
    verification_status: str
    confidence_level: str

    model_config = ConfigDict(from_attributes=True)


class CountryQualificationSchema(BaseModel):
    id: UUID
    country_code: str
    qualification_name: str
    qualification_type: str
    grading_scale: Optional[str] = None
    passing_threshold: Optional[str] = None
    equivalency_notes: Optional[str] = None
    recognition_rules: Dict[str, Any] = {}
    source_name: str
    source_url: str
    verified_at: Optional[datetime] = None
    verification_status: str

    model_config = ConfigDict(from_attributes=True)


class InstitutionAdmissionsSummarySchema(BaseModel):
    institution_id: UUID
    official_name: str
    country_code: str
    academic_year: str
    has_verified_requirements: bool
    coverage_notice: Optional[str] = None
    admissions_website: Optional[str] = None
    application_portal_url: Optional[str] = None
    net_price_calculator_url: Optional[str] = None
    open_admissions: Optional[bool] = None
    undergrad_application_fee: Optional[float] = None
    requirements: List[InstitutionRequirementSchema] = []
    deadlines: List[DeadlineSchema] = []
    country_qualifications: List[CountryQualificationSchema] = []


class ChecklistItemEvaluationSchema(BaseModel):
    requirement_id: UUID
    title: str
    category: str
    requirement_type: str
    program_name_filter: Optional[str] = None
    original_importance: str
    effective_importance: str
    status: str  # completed, in_progress, pending, not_applicable, waived, needs_verification, missing
    explanation: Optional[str] = None
    minimum_value: Optional[str] = None
    maximum_value: Optional[str] = None
    satisfied_by_document_id: Optional[UUID] = None
    satisfied_by_profile_field: Optional[str] = None
    matched_evidence: List[str] = []
    missing_items: List[str] = []
    auto_matched: bool = False
    source_name: str
    source_url: str
    verified_at: Optional[datetime] = None
    verification_status: str


class DynamicChecklistResponseSchema(BaseModel):
    institution_id: UUID
    official_name: str
    country_code: str
    applicant_type: str
    is_international_for_target: Optional[bool] = None
    intended_major: Optional[str] = None
    academic_year: str
    has_verified_requirements: bool
    eligibility_status: str  # eligible_preliminary, in_progress, needs_information, concerns_identified, requirements_unverified
    readiness_pct: int
    summary_notice: Optional[str] = None
    completed_requirements: List[ChecklistItemEvaluationSchema] = []
    missing_documents: List[ChecklistItemEvaluationSchema] = []
    outstanding_prerequisites: List[ChecklistItemEvaluationSchema] = []
    other_requirements: List[ChecklistItemEvaluationSchema] = []
    not_applicable_requirements: List[ChecklistItemEvaluationSchema] = []
    eligibility_concerns: List[str] = []
    upcoming_deadlines: List[DeadlineSchema] = []
    next_actions: List[str] = []
    applicable_qualifications: List[CountryQualificationSchema] = []
