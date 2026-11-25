from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ScholarshipRuleEvaluationSchema(BaseModel):
    dimension: str
    human_label: str
    status: str  # pass | fail | missing_data
    detail: str
    is_mandatory: bool = True


class ScholarshipEligibilityResultSchema(BaseModel):
    id: UUID
    institution_id: Optional[UUID] = None
    institution_name: Optional[str] = None
    country_code: str
    title: str
    provider_type: str
    award_type: str
    applicant_type: str
    funding_type: str
    covers_international: bool
    award_amount_min_usd: Optional[float] = None
    award_amount_max_usd: Optional[float] = None
    max_award_info: Optional[str] = None
    eligibility_summary: str
    covers_tuition: bool
    covers_fees: bool
    covers_housing: bool
    covers_meals: bool
    covers_health_insurance: bool
    provides_living_stipend: bool
    is_renewable: bool
    is_guaranteed_statutory: bool
    application_deadline_date: Optional[date] = None
    is_deadline_rolling: bool
    min_gpa_4: Optional[float] = None
    requires_financial_need: bool
    eligible_citizenships: List[str] = []
    eligible_residency_states: List[str] = []
    eligible_destination_countries: List[str] = []
    eligibility_status: str  # eligible | conditionally_eligible | ineligible
    match_score: int
    rule_evaluations: List[ScholarshipRuleEvaluationSchema] = []
    missing_requirements: List[str] = []
    failed_reasons: List[str] = []
    source_name: str
    source_url: str
    verified_at: datetime


class ScholarshipMatchRequest(BaseModel):
    citizenship_country: Optional[str] = None
    residency_state: Optional[str] = None
    applicant_type: Optional[str] = None  # first_year | transfer | both
    degree_level: str = "bachelors"  # bachelors | masters | doctoral
    gpa_4: Optional[float] = Field(default=None, ge=0.0, le=4.0)
    financial_need_level: Optional[str] = None  # high | moderate | low
    household_income_usd: Optional[float] = Field(default=None, ge=0.0)
    destination_country: Optional[str] = None
    institution_id: Optional[UUID] = None
    us_community_college_enrolled: Optional[bool] = None
    include_ineligible: bool = True


class ScholarshipMatchResponse(BaseModel):
    evaluated_profile: Dict[str, Any]
    total_scholarships: int
    eligible_count: int
    conditionally_eligible_count: int
    ineligible_count: int
    results: List[ScholarshipEligibilityResultSchema]
    disclaimer: str


class CostLineItemSchema(BaseModel):
    key: str
    label: str
    category: str  # direct_billable | indirect_living
    amount_usd: Optional[float] = None
    is_published: bool = True
    notes: Optional[str] = None


class AidOffsetItemSchema(BaseModel):
    scholarship_id: UUID
    title: str
    provider_type: str
    eligibility_status: str
    is_guaranteed_statutory: bool
    estimated_min_usd: float
    estimated_max_usd: float
    source_url: str


class NetPriceCalculateRequest(BaseModel):
    institution_id: UUID
    residency_classification: str = "international"  # in_state | out_of_state | international
    housing_preference: str = "on_campus"  # on_campus | off_campus | with_family
    applicant_type: str = "first_year"  # first_year | transfer
    citizenship_country: Optional[str] = None
    residency_state: Optional[str] = None
    gpa_4: Optional[float] = Field(default=None, ge=0.0, le=4.0)
    financial_need_level: Optional[str] = None  # high | moderate | low
    household_income_usd: Optional[float] = Field(default=None, ge=0.0)
    annual_budget_usd: Optional[float] = Field(default=None, ge=0.0)
    program_years: int = Field(default=4, ge=1, le=6)
    include_competitive_aid: bool = True


class NetPriceCalculationResponse(BaseModel):
    institution_id: UUID
    institution_name: str
    country_code: str
    residency_classification: str
    housing_preference: str
    applicant_type: str
    academic_year: Optional[str] = None
    currency: str = "USD"
    direct_billable_items: List[CostLineItemSchema] = []
    indirect_living_items: List[CostLineItemSchema] = []
    gross_direct_cost_usd: Optional[float] = None
    gross_indirect_cost_usd: Optional[float] = None
    total_coa_usd: Optional[float] = None
    guaranteed_aid_min_usd: float = 0.0
    guaranteed_aid_max_usd: float = 0.0
    competitive_aid_min_usd: float = 0.0
    competitive_aid_max_usd: float = 0.0
    eligible_aid_min_usd: float = 0.0
    eligible_aid_max_usd: float = 0.0
    estimated_net_price_min_usd: Optional[float] = None
    estimated_net_price_max_usd: Optional[float] = None
    multi_year_net_min_usd: Optional[float] = None
    multi_year_net_max_usd: Optional[float] = None
    annual_budget_usd: Optional[float] = None
    budget_gap_min_usd: Optional[float] = None
    budget_gap_max_usd: Optional[float] = None
    affordability_status: str  # within_budget | reachable_with_competitive_aid | exceeds_budget | missing_cost_data
    aid_offsets: List[AidOffsetItemSchema] = []
    data_confidence: str
    warnings: List[str] = []
    sources: List[Dict[str, Optional[str]]] = []
    disclaimer: str


class GradingSystemOptionSchema(BaseModel):
    source_country_code: str
    grading_system_key: str
    scale_name: str
    academic_level: str
    is_inverted_scale: bool
    methodology: str
    sample_values: List[str] = []


class CredentialEvaluateRequest(BaseModel):
    source_country_code: str
    grading_system_key: str
    raw_grade: str
    destination_country_code: str = "US"
    academic_level: str = "secondary"


class GradeConversionOutcomeSchema(BaseModel):
    native_record: Dict[str, Any]
    informational_equivalency: Dict[str, Any]


class CredentialRecognitionRuleSchema(BaseModel):
    id: UUID
    source_country_code: str
    destination_country_code: str
    source_credential_name: str
    is_directly_recognized: bool
    requires_external_evaluation: bool
    accepted_evaluation_agencies: List[str] = []
    requires_official_translation: bool
    translation_requirements: Optional[str] = None
    requires_apostille_or_legalization: bool
    requires_direct_institutional_dispatch: bool
    english_waiver_policy: Optional[str] = None
    pathway_notes: str
    source_name: str
    source_url: str
    verified_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CredentialEvaluationResponse(BaseModel):
    conversion: GradeConversionOutcomeSchema
    recognition_rules: List[CredentialRecognitionRuleSchema] = []
    country_qualifications: List[Dict[str, Any]] = []
    advisory_disclaimer: str


class ProfileEnrollmentCredentialItemSchema(BaseModel):
    enrollment_id: UUID
    institution_name: str
    institution_country: str
    enrollment_type: str
    cumulative_gpa: Optional[float] = None
    gpa_scale: Optional[float] = None
    inferred_system_key: str
    evaluation: CredentialEvaluationResponse


class ProfileCredentialEvaluationResponse(BaseModel):
    has_profile: bool
    destination_country_code: str
    enrollments_evaluated: List[ProfileEnrollmentCredentialItemSchema] = []
    advisory_disclaimer: str
