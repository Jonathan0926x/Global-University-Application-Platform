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
    verified_by_user_id: Optional[UUID] = None
    verification_method: Optional[str] = None
    verification_notes: Optional[str] = None
    verification_expires_at: Optional[datetime] = None
    last_health_check_at: Optional[datetime] = None
    last_health_check_status: Optional[str] = None
    last_health_check_http_code: Optional[int] = None
    pathway_verified: Optional[bool] = None
    final_redirect_url: Optional[str] = None
    redirect_chain_length: Optional[int] = None
    last_checked_at: datetime
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class RejectionReasonOptionSchema(BaseModel):
    code: str
    label: str
    description: str


class ApplicationRouteAuditSchema(BaseModel):
    id: UUID
    route_id: UUID
    from_status: Optional[str] = None
    to_status: str
    action: str
    actor_role: str
    actor_email: Optional[str] = None
    rejection_reason_code: Optional[str] = None
    notes: Optional[str] = None
    checks_json: Dict[str, Any] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoutingQueueItemSchema(ApplicationRouteSchema):
    institution_website: Optional[str] = None
    trust_checks: Dict[str, Any] = {}
    audits: List[ApplicationRouteAuditSchema] = []


class RouteHealthSummarySchema(BaseModel):
    total_active_routes: int = 0
    health_check_status: Dict[str, int] = {}
    verification_expired: int = 0
    verification_expiring_soon_30d: int = 0
    pathway_verified: int = 0
    pathway_assumed: int = 0
    routes_with_redirect_tracking: int = 0


class RoutingQualitySummarySchema(BaseModel):
    total_routes: int
    verified: int
    needs_verification: int
    unverified: int
    by_method: Dict[str, int] = {}
    auto_verifiable_candidates: int = 0
    manual_review_remaining: int = 0
    manually_reviewed_count: int = 0
    health: Optional[RouteHealthSummarySchema] = None


class RouteReviewRequest(BaseModel):
    decision: str  # verified | unverified | needs_verification
    rejection_reason_code: Optional[str] = None
    notes: Optional[str] = None
    corrected_url: Optional[str] = None
    international_instructions: Optional[str] = None
    pathway_verified: Optional[bool] = None
    applicant_type: Optional[str] = None


class RoutePathwayVerifyRequest(BaseModel):
    pathway_verified: bool
    applicant_type: Optional[str] = None
    notes: Optional[str] = None


class RouteHealthCheckItemSchema(BaseModel):
    route_id: str
    status: str
    http_code: Optional[int] = None
    final_redirect_url: Optional[str] = None
    redirect_chain_length: Optional[int] = None
    cross_domain_redirect: bool = False


class BatchHealthCheckResponse(BaseModel):
    checked: int
    by_status: Dict[str, int] = {}
    results: List[RouteHealthCheckItemSchema] = []
    summary: RoutingQualitySummarySchema


class ExpireRoutesResponse(BaseModel):
    expired_checked: int
    flagged_for_reverification: int
    summary: RoutingQualitySummarySchema


class BatchRouteVerifyResponse(BaseModel):
    checked: int
    promoted_to_verified: int
    kept_needs_verification: int
    flagged_unverified: int
    by_method: Dict[str, int] = {}
    summary: RoutingQualitySummarySchema


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


class EvidenceReviewAuditSchema(BaseModel):
    id: UUID
    evidence_id: UUID
    application_id: UUID
    from_review_status: Optional[str] = None
    to_review_status: str
    action: str
    actor_role: str
    actor_email: Optional[str] = None
    rejection_reason_code: Optional[str] = None
    rejection_reason_label: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmissionEvidenceSchema(BaseModel):
    id: UUID
    application_id: UUID
    document_id: Optional[UUID] = None
    original_filename: Optional[str] = None
    document_sha256: Optional[str] = None
    evidence_type: str
    external_confirmation_number: Optional[str] = None
    submitted_note: Optional[str] = None
    review_status: str  # pending | accepted | rejected
    rejection_reason_code: Optional[str] = None
    rejection_reason_label: Optional[str] = None
    reviewer_notes: Optional[str] = None
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None
    audit_history: List[EvidenceReviewAuditSchema] = []

    model_config = ConfigDict(from_attributes=True)


class EvidenceQueueItemSchema(SubmissionEvidenceSchema):
    institution_id: UUID
    institution_name: str
    applicant_type: str
    application_status: str
    student_email: Optional[str] = None
    student_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    file_type: Optional[str] = None


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
    rejection_reason_code: Optional[str] = None
    reviewer_notes: Optional[str] = None


class UrlValidationRequest(BaseModel):
    url: str


class UrlValidationResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None
    normalized_url: Optional[str] = None
    scheme_secure: bool = False
