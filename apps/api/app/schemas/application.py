from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.schemas.routing import (
    ApplicationRouteSchema,
    DeadlineCountdownSchema,
    StatusHistoryItemSchema,
    SubmissionEvidenceSchema,
)


class RequirementStatusSchema(BaseModel):
    id: UUID
    institution_requirement_id: Optional[UUID] = None
    title: str
    category: str
    importance: str
    status: str
    notes: Optional[str] = None
    satisfied_by_document_id: Optional[UUID] = None
    satisfied_by_profile_field: Optional[str] = None
    auto_matched: bool = False
    verification_status: Optional[str] = None
    source_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InstitutionSummarySchema(BaseModel):
    id: UUID
    official_name: str
    abbreviation: Optional[str] = None
    country_code: str
    state_province: Optional[str] = None
    city: Optional[str] = None
    institution_type: str
    admissions_website: Optional[str] = None
    application_portal_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ApplicationCreate(BaseModel):
    institution_id: UUID
    applicant_type: str  # first_year or transfer
    intended_major: Optional[str] = None
    intended_term: Optional[str] = None
    academic_year: Optional[str] = None
    route_id: Optional[UUID] = None


class ApplicationResponse(BaseModel):
    id: UUID
    profile_id: UUID
    institution_id: UUID
    applicant_type: str
    status: str
    intended_major: Optional[str] = None
    intended_term: Optional[str] = None
    academic_year: Optional[str] = None
    readiness_pct: int
    notes: Optional[str] = None

    selected_route_id: Optional[UUID] = None
    external_portal_url: Optional[str] = None
    external_platform_name: Optional[str] = None
    redirected_at: Optional[datetime] = None
    student_reported_submitted_at: Optional[datetime] = None
    submission_confirmed_at: Optional[datetime] = None
    external_confirmation_number: Optional[str] = None
    submitted_via: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    institution: Optional[InstitutionSummarySchema] = None
    requirements_status: List[RequirementStatusSchema] = []
    status_history: List[StatusHistoryItemSchema] = []
    submission_evidence: List[SubmissionEvidenceSchema] = []
    verified_routes: List[ApplicationRouteSchema] = []
    needs_verification_routes: List[ApplicationRouteSchema] = []
    routing_notice: Optional[str] = None
    deadlines: List[DeadlineCountdownSchema] = []

    model_config = ConfigDict(from_attributes=True)
