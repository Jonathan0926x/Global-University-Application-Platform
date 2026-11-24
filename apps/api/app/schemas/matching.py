from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class MatchingPreferenceUpdate(BaseModel):
    max_annual_budget: Optional[float] = Field(None, ge=0)
    currency: str = "USD"
    requires_full_aid: bool = False
    requires_merit_scholarships: bool = False
    preferred_countries: List[str] = ["US"]
    preferred_states_provinces: List[str] = []
    preferred_institution_types: List[str] = []
    preferred_languages: List[str] = ["en"]
    weight_academic: float = Field(0.30, ge=0.0, le=1.0)
    weight_financial: float = Field(0.25, ge=0.0, le=1.0)
    weight_readiness: float = Field(0.25, ge=0.0, le=1.0)
    weight_transfer: float = Field(0.20, ge=0.0, le=1.0)


class MatchingPreferenceResponse(MatchingPreferenceUpdate):
    id: UUID
    profile_id: UUID
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatchFactorSchema(BaseModel):
    name: str
    status: str  # verified_match | partial_match | potential_concern | insufficient_information | not_applicable
    score_impact: Optional[float] = None
    detail: str
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    verified_at: Optional[str] = None


class DimensionEvaluationSchema(BaseModel):
    key: str  # academic | financial | readiness | transfer
    label: str
    score: float
    weight_configured: float
    weight_applied: float
    status: str  # verified_match | partial_match | potential_concern | insufficient_information | not_applicable
    summary: str
    factors: List[MatchFactorSchema] = []


class InstitutionMatchSummaryInfo(BaseModel):
    id: UUID
    official_name: str
    country_code: str
    state_province: Optional[str] = None
    city: Optional[str] = None
    institution_type: str
    control_type: Optional[str] = None
    acceptance_rate: Optional[float] = None
    tuition_in_state: Optional[float] = None
    tuition_out_of_state: Optional[float] = None
    avg_net_price: Optional[float] = None
    cost_of_attendance: Optional[float] = None
    currency: Optional[str] = "USD"
    total_enrollment: Optional[int] = None
    official_website: Optional[str] = None
    admissions_website: Optional[str] = None
    application_portal_url: Optional[str] = None
    primary_source: Optional[str] = None
    last_verified_at: Optional[datetime] = None


class UniversityMatchRecommendationSchema(BaseModel):
    id: UUID
    institution_id: UUID
    institution: InstitutionMatchSummaryInfo
    applicant_type: str
    intended_major: Optional[str] = None
    match_category: str  # reach | target | likely | insufficient_data
    composite_score: float
    score_academic: float
    score_financial: float
    score_readiness: float
    score_transfer: float
    data_confidence_score: float

    calculation_formula: str
    dimensions: List[DimensionEvaluationSchema] = []
    positive_factors: List[str] = []
    missing_information: List[str] = []
    unsatisfied_requirements: List[str] = []
    financial_concerns: List[str] = []
    transfer_uncertainties: List[str] = []
    upcoming_deadlines: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []

    estimated_net_cost: Optional[float] = None
    published_tuition: Optional[float] = None
    estimated_living_expenses: Optional[float] = None
    cost_basis: Optional[str] = None
    cost_is_estimated: bool = True

    is_saved_by_student: bool = False
    is_dismissed: bool = False
    computed_at: datetime
    disclaimer: str


class MatchingRunRequest(BaseModel):
    applicant_type: Optional[str] = None
    intended_major: Optional[str] = None
    countries: Optional[List[str]] = None
    states: Optional[List[str]] = None
    institution_types: Optional[List[str]] = None
    max_annual_budget: Optional[float] = Field(None, ge=0)
    weight_academic: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_financial: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_readiness: Optional[float] = Field(None, ge=0.0, le=1.0)
    weight_transfer: Optional[float] = Field(None, ge=0.0, le=1.0)
    limit: int = Field(24, ge=1, le=50)
    persist: bool = True


class MatchingRunResponse(BaseModel):
    applicant_type: str
    intended_major: Optional[str] = None
    total_evaluated: int
    counts_by_category: Dict[str, int]
    weights_used: Dict[str, float]
    recommendations: List[UniversityMatchRecommendationSchema]
    disclaimer: str


class CompareInstitutionsRequest(BaseModel):
    institution_ids: List[UUID] = Field(..., min_length=1, max_length=4)
    applicant_type: Optional[str] = None
    intended_major: Optional[str] = None
