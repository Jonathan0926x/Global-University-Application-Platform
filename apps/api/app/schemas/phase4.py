from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class StructuredReasonItemSchema(BaseModel):
    reason_code: str
    params: Dict[str, Any] = {}
    fallback_detail: str


class ScholarshipRuleEvaluationSchema(BaseModel):
    dimension: str
    human_label: str
    status: str  # eligible | conditionally_eligible | ineligible | insufficient_information | requires_manual_review (plus legacy pass/fail alias in category note)
    outcome: str = "eligible"
    category: str = "eligibility"  # eligibility | renewal
    detail: str
    reason_code: Optional[str] = None
    params: Dict[str, Any] = {}
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
    degree_levels: List[str] = []
    eligibility_status: str  # eligible | conditionally_eligible | ineligible | insufficient_information | requires_manual_review
    funding_bucket: str = "review_required"  # verified_applicable | conditional | potential_insufficient_info | review_required | ineligible
    match_score: int
    rule_evaluations: List[ScholarshipRuleEvaluationSchema] = []
    renewal_evaluations: List[ScholarshipRuleEvaluationSchema] = []
    satisfied_reasons: List[str] = []
    missing_requirements: List[str] = []
    conditional_requirements: List[str] = []
    manual_review_reasons: List[str] = []
    failed_reasons: List[str] = []
    satisfied_items: List[StructuredReasonItemSchema] = []
    failed_items: List[StructuredReasonItemSchema] = []
    missing_items: List[StructuredReasonItemSchema] = []
    conditional_items: List[StructuredReasonItemSchema] = []
    manual_review_items: List[StructuredReasonItemSchema] = []
    freshness_warning_items: List[StructuredReasonItemSchema] = []
    student_evidence_used: Dict[str, Any] = {}
    official_supporting_sources: List[Dict[str, Any]] = []
    funding_scope: List[str] = []
    duration_renewal_summary: Optional[str] = None
    freshness_warnings: List[str] = []
    source_name: str
    source_url: str
    official_source_language: str = "en"
    verified_at: datetime
    award_currency: str = "USD"
    award_fixed_usd: Optional[float] = None
    native_amount_min: Optional[float] = None
    native_amount_max: Optional[float] = None
    covers_travel: bool = False
    funding_duration_years: Optional[float] = None
    max_funding_periods: Optional[int] = None
    renewal_conditions: Optional[str] = None
    sponsoring_institution: Optional[str] = None
    source_type: str = "unknown"
    source_version: Optional[str] = None
    academic_year: Optional[str] = None
    verification_method: str = "unknown"
    verified_by: Optional[str] = None
    verification_expires_at: Optional[datetime] = None
    freshness_status: str = "requires_manual_review"
    application_cycle_status: str = "unspecified"  # open | closed | rolling | cyclical_check_official | unspecified
    cycle_verification_state: str = "next_cycle_unannounced"
    cycle_reason_code: Optional[str] = None
    cycle_params: Dict[str, Any] = {}
    cycle_status_detail: Optional[str] = None
    is_cycle_open: bool = False
    is_amount_verified: bool = False
    is_actionable_for_student: bool = False
    aid_classification: Optional[str] = None
    is_variable_aid: bool = False
    transfer_pathway_classification: Optional[str] = None
    transfer_eligibility_detail: Optional[str] = None
    claim_freshness: Dict[str, str] = {}
    requires_manual_review: bool = False
    claim_provenance: Dict[str, Any] = {}
    conflict_notes: Optional[str] = None
    amount_classification: Optional[str] = None
    transfer_supported: Optional[bool] = None


class ScholarshipMatchRequest(BaseModel):
    citizenship_country: Optional[str] = None
    citizenships: Optional[List[str]] = None
    dual_citizenship: Optional[bool] = None
    country_of_residence: Optional[str] = None
    residency_state: Optional[str] = None
    applicant_type: Optional[str] = None  # first_year | transfer | both
    degree_level: Optional[str] = "bachelors"  # bachelors | masters | doctoral | research | exchange
    date_of_birth: Optional[date] = None
    field_of_study: Optional[str] = None
    qualifications: Optional[List[str]] = None
    exam_scores: Optional[Dict[str, Any]] = None
    language_proficiencies: Optional[Dict[str, Any]] = None
    gpa_4: Optional[float] = Field(default=None, ge=0.0, le=4.0)
    financial_need_level: Optional[str] = None  # high | moderate | low
    household_income_usd: Optional[float] = Field(default=None, ge=0.0)
    destination_country: Optional[str] = None
    institution_id: Optional[UUID] = None
    us_community_college_enrolled: Optional[bool] = None
    currently_enrolled: Optional[bool] = None
    final_year_undergraduate: Optional[bool] = None
    is_full_time: Optional[bool] = None
    include_ineligible: bool = True


class ScholarshipMatchResponse(BaseModel):
    evaluated_profile: Dict[str, Any]
    total_scholarships: int
    eligible_count: int
    conditionally_eligible_count: int
    insufficient_information_count: int = 0
    requires_manual_review_count: int = 0
    ineligible_count: int
    total_active_programs: int = 0
    verified_funding_programs: int = 0
    verified_funding_coverage: float = 0.0
    student_coverage_summary: Dict[str, Any] = {}
    aggregation_precedence: List[str] = [
        "ineligible",
        "requires_manual_review",
        "insufficient_information",
        "conditionally_eligible",
        "eligible",
    ]
    results: List[ScholarshipEligibilityResultSchema]
    disclaimer: str


class StudentCoverageReportResponse(BaseModel):
    evaluated_profile: Dict[str, Any]
    programs_evaluated: int
    programs_matched: int
    programs_verified_eligibility: int
    programs_verified_funding: int
    programs_open_cycle: int
    programs_actionable_open_verified: int
    programs_insufficient_info: int
    programs_manual_review: int
    programs_variable_aid_matched: int
    programs_expired_cycle_matched: int
    programs_transfer_unconfirmed: int
    aid_classification_breakdown: Dict[str, int] = {}
    transfer_pathway_breakdown: Dict[str, int] = {}
    gap_codes: List[str] = []
    profile_coverage_gaps: List[Dict[str, str]] = []
    next_steps_for_student: List[str] = []
    disclaimer: str


class CatalogCoverageAuditResponse(BaseModel):
    audited_at: str
    total_catalog_programs: int
    total_active_programs: int
    programs_reviewed: int
    legacy_reviewed_count: int
    legacy_total_count: int
    batch1_4_reverified_count: int
    complete_provenance_count: int
    complete_provenance_ratio: float
    verified_eligibility_count: int
    verified_funding_programs: int
    verified_funding_coverage: float
    actionable_coverage_count: int
    actionable_coverage_ratio: float
    confirmed_open_verified_programs: int = 0
    unknown_eligibility_count: int
    requires_manual_review_count: int
    expired_claim_count: int
    source_unavailable_count: int
    conflicting_count: int
    dual_citizenship_restricted_programs: int
    citizenship_residency_separated_programs: int
    multi_destination_programs: int
    citizenships_with_verified_funding_count: int
    by_pathway: Dict[str, int]
    transfer_pathway_breakdown: Dict[str, int] = {}
    aid_classification_breakdown: Dict[str, int] = {}
    cycle_verification_breakdown: Dict[str, int] = {}
    by_degree_level: Dict[str, Dict[str, int]]
    by_citizenship: List[Dict[str, Any]]
    by_destination: List[Dict[str, Any]]
    intersections: List[Dict[str, Any]]
    student_archetype_matrix: List[Dict[str, Any]] = []
    coverage_gaps: List[Dict[str, Any]] = []
    deferred_research_queue: List[Dict[str, Any]] = []
    manual_review_programs: List[Dict[str, Any]]
    unavailable_source_programs: List[Dict[str, Any]]


class CostLineItemSchema(BaseModel):
    key: str
    label: str
    category: str  # direct_billable | indirect_living
    amount_usd: Optional[float] = None
    currency: str = "USD"
    is_published: bool = True
    notes: Optional[str] = None


class CategoryAllocationRowSchema(BaseModel):
    category_key: str
    label: str
    cost_group: str  # direct_billable | indirect_living
    original_cost_usd: Optional[float] = None
    applied_verified_min_usd: float = 0.0
    applied_verified_max_usd: float = 0.0
    applied_conditional_max_usd: float = 0.0
    remaining_cost_min_usd: Optional[float] = None
    remaining_cost_max_usd: Optional[float] = None


class AidOffsetItemSchema(BaseModel):
    scholarship_id: UUID
    title: str
    provider_type: str
    award_type: str = "fixed_amount"
    eligibility_status: str
    funding_bucket: str = "verified_applicable"  # verified_applicable | conditional | potential | review_required
    freshness_status: str = "requires_manual_review"
    is_guaranteed_statutory: bool
    award_currency: str = "USD"
    native_amount_min: Optional[float] = None
    native_amount_max: Optional[float] = None
    funding_scope: List[str] = []
    allocated_categories: Dict[str, float] = {}
    estimated_min_usd: float = 0.0
    estimated_max_usd: float = 0.0
    funding_duration_years: Optional[float] = None
    is_renewable: bool = False
    renewal_conditions: Optional[str] = None
    reason: Optional[str] = None
    source_url: str


class NetPriceCalculateRequest(BaseModel):
    institution_id: UUID
    residency_classification: str = "international"  # in_state | out_of_state | international
    housing_preference: str = "on_campus"  # on_campus | off_campus | with_family
    applicant_type: str = "first_year"  # first_year | transfer
    degree_level: Optional[str] = "bachelors"  # bachelors | masters | doctoral
    citizenship_country: Optional[str] = None
    country_of_residence: Optional[str] = None
    dual_citizenship: Optional[bool] = None
    residency_state: Optional[str] = None
    date_of_birth: Optional[date] = None
    field_of_study: Optional[str] = None
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
    degree_level: str = "bachelors"
    academic_year: Optional[str] = None
    currency: str = "USD"
    direct_billable_items: List[CostLineItemSchema] = []
    indirect_living_items: List[CostLineItemSchema] = []
    category_breakdown: List[CategoryAllocationRowSchema] = []
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
    verified_applicable_aid: List[AidOffsetItemSchema] = []
    conditional_aid: List[AidOffsetItemSchema] = []
    insufficient_info_aid: List[AidOffsetItemSchema] = []
    review_required_aid: List[AidOffsetItemSchema] = []
    unallocated_potential_aid: List[AidOffsetItemSchema] = []
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
    issuing_authority: Optional[str] = None
    education_level: str = "secondary"
    exam_structure: Optional[str] = None
    framework_version: Optional[str] = None
    equivalency_classification: str = "official_equivalency"
    verified_by: Optional[str] = None
    verification_expires_at: Optional[datetime] = None
    freshness_status: str = "requires_manual_review"

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
