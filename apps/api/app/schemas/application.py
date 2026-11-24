from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


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

    model_config = ConfigDict(from_attributes=True)


class ApplicationCreate(BaseModel):
    institution_id: UUID
    applicant_type: str  # first_year or transfer
    intended_major: Optional[str] = None
    intended_term: Optional[str] = None
    academic_year: Optional[str] = None


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
    created_at: datetime
    updated_at: datetime
    institution: Optional[InstitutionSummarySchema] = None
    requirements_status: List[RequirementStatusSchema] = []

    model_config = ConfigDict(from_attributes=True)

