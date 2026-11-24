from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class RequirementStatusSchema(BaseModel):
    id: UUID
    title: str
    category: str
    importance: str
    status: str
    notes: Optional[str] = None

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

