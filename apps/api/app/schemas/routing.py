from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class ApplicationRouteSchema(BaseModel):
    id: UUID
    institution_id: Optional[UUID] = None
    institution_name: Optional[str] = None
    platform_name: str
    platform_type: str
    country_code: str
    applicant_type: str
    official_url: str
    international_instructions: Optional[str] = None
    notes: Optional[str] = None
    source_name: str
    source_url: Optional[str] = None
    verification_status: str
    confidence_level: str
    verified_at: Optional[datetime] = None
    last_checked_at: datetime
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class InstitutionRoutingResolutionSchema(BaseModel):
    institution_id: UUID
    institution_name: str
    applicant_type: str
    routing_status: str  # verified_available | needs_verification_only | no_verified_destination
    has_verified_destination: bool
    verified_routes: List[ApplicationRouteSchema] = []
    needs_verification_routes: List[ApplicationRouteSchema] = []
    excluded_unverified: List[Dict[str, str]] = []
    notice: Optional[str] = None


class DeadlineCountdownSchema(BaseModel):
    id: str
    intake_term: str
    deadline_type: str
    deadline_date: Optional[str] = None
    days_remaining: Optional[int] = None
    is_passed: bool = False
    is_urgent: bool = False
    verification_status: str
    source_name: str
    source_url: Optional[str] = None
    notes: Optional[str] = None


class StatusHistoryItemSchema(BaseModel):
    id: UUID
    from_status: Optional[str] = None
    to_status: str
    actor_role: str
    reason: Optional[str] = None
    metadata_json: Dict[str, Any] = {}
    changed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmissionEvidenceSchema(BaseModel):
    id: UUID
    application_id: UUID
    document_id: Optional[UUID] = None
    original_filename: Optional[str] = None
    evidence_type: str
    external_confirmation_number: Optional[str] = None
    submitted_note: Optional[str] = None
    review_status: str  # pending | accepted | rejected
    reviewer_notes: Optional[str] = None
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ApplicationStatusUpdateRequest(BaseModel):
    status: str
    reason: Optional[str] = None


class ApplicationRedirectRequest(BaseModel):
    route_id: Optional[UUID] = None
    target_url: Optional[str] = None
    acknowledge_unverified: bool = False


class ApplicationReportSubmissionRequest(BaseModel):
    external_confirmation_number: Optional[str] = None
    submitted_via: Optional[str] = None
    note: Optional[str] = None


class EvidenceReviewRequest(BaseModel):
    decision: str  # accepted | rejected
    reviewer_notes: Optional[str] = None


class UrlValidationRequest(BaseModel):
    url: str


class UrlValidationResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None
    normalized_url: Optional[str] = None
    scheme_secure: bool = False
