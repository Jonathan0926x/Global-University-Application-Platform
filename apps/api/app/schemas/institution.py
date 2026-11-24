from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class CountrySchema(BaseModel):
    code: str
    name: str
    name_local: Optional[str] = None
    region: Optional[str] = None
    subregion: Optional[str] = None
    currency_code: Optional[str] = None
    primary_languages: List[str] = []
    higher_ed_ministry: Optional[str] = None
    higher_ed_ministry_url: Optional[str] = None
    accreditation_body: Optional[str] = None
    education_system_notes: Optional[str] = None

    @field_validator("primary_languages", mode="before")
    @classmethod
    def coerce_langs(cls, v):
        return v if v is not None else []

    model_config = ConfigDict(from_attributes=True)


class AcademicProgramSchema(BaseModel):
    id: UUID
    institution_id: UUID
    program_name: str
    degree_level: str
    degree_type: Optional[str] = None
    department: Optional[str] = None
    cip_code: Optional[str] = None
    isced_code: Optional[str] = None
    duration_years: Optional[float] = None
    credit_requirements: Optional[int] = None
    language_of_instruction: str = "en"
    delivery_mode: str = "in_person"
    program_url: Optional[str] = None
    is_accepting_applications: bool = True
    accepts_transfer_students: Optional[bool] = None
    academic_year: Optional[str] = None
    source_url: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InstitutionCostSchema(BaseModel):
    id: UUID
    institution_id: UUID
    academic_year: str
    student_type: str
    degree_level: Optional[str] = None
    tuition: Optional[float] = None
    mandatory_fees: Optional[float] = None
    room_board: Optional[float] = None
    books_supplies: Optional[float] = None
    personal_expenses: Optional[float] = None
    transportation: Optional[float] = None
    health_insurance: Optional[float] = None
    total_estimated_cost: Optional[float] = None
    currency: Optional[str] = "USD"
    is_current: bool = True
    source_url: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    verification_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DataProvenanceSchema(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    field_name: Optional[str] = None
    source_type: str
    source_url: Optional[str] = None
    source_name: str
    collection_method: str
    retrieved_at: datetime
    verified_at: Optional[datetime] = None
    academic_year: Optional[str] = None
    confidence_level: str
    data_hash: Optional[str] = None
    previous_value: Optional[Dict[str, Any]] = None
    is_current: bool

    model_config = ConfigDict(from_attributes=True)


class InstitutionSummaryV3Schema(BaseModel):
    id: UUID
    official_name: str
    alternative_names: List[str] = []
    abbreviation: Optional[str] = None
    campus_name: Optional[str] = None
    is_main_campus: bool = True
    parent_institution_id: Optional[UUID] = None
    country_code: str
    state_province: Optional[str] = None
    city: Optional[str] = None
    institution_type: str
    control_type: Optional[str] = None
    carnegie_classification: Optional[str] = None
    official_website: Optional[str] = None
    admissions_website: Optional[str] = None
    total_enrollment: Optional[int] = None
    undergraduate_enrollment: Optional[int] = None
    acceptance_rate: Optional[float] = None
    tuition_in_state: Optional[float] = None
    tuition_out_of_state: Optional[float] = None
    avg_net_price: Optional[float] = None
    cost_of_attendance: Optional[float] = None
    currency: Optional[str] = "USD"
    ipeds_unit_id: Optional[str] = None
    ope_id: Optional[str] = None
    ope6_id: Optional[str] = None
    ror_id: Optional[str] = None
    openalex_id: Optional[str] = None
    accepts_transfer: bool = True
    accepts_first_year: bool = True
    accepts_international: bool = True
    data_completeness_score: Optional[float] = 0.0
    data_reporting_year: Optional[str] = None
    primary_source: Optional[str] = None
    is_verified: bool = True
    last_verified_at: Optional[datetime] = None

    @field_validator("alternative_names", mode="before")
    @classmethod
    def coerce_alt_names(cls, v):
        return v if v is not None else []

    @field_validator("data_completeness_score", mode="before")
    @classmethod
    def coerce_score(cls, v):
        return float(v) if v is not None else 0.0

    model_config = ConfigDict(from_attributes=True)


class InstitutionDetailSchema(InstitutionSummaryV3Schema):
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    financial_aid_website: Optional[str] = None
    international_admissions_website: Optional[str] = None
    net_price_calculator_url: Optional[str] = None
    application_portal_url: Optional[str] = None
    accreditation_status: Optional[str] = None
    accrediting_body: Optional[str] = None
    open_admissions: Optional[bool] = None
    calendar_system: Optional[str] = None
    undergrad_application_fee: Optional[float] = None
    graduate_enrollment: Optional[int] = None
    student_faculty_ratio: Optional[str] = None
    sat_math_25: Optional[int] = None
    sat_math_75: Optional[int] = None
    sat_ebrw_25: Optional[int] = None
    sat_ebrw_75: Optional[int] = None
    act_composite_25: Optional[int] = None
    act_composite_75: Optional[int] = None
    gpa_25: Optional[float] = None
    gpa_75: Optional[float] = None
    completion_rate_4yr: Optional[float] = None
    completion_rate_less_4yr: Optional[float] = None
    retention_rate: Optional[float] = None
    median_earnings_10yr: Optional[float] = None
    median_debt: Optional[float] = None
    pct_international: Optional[float] = None
    pct_pell: Optional[float] = None
    student_demographics: Dict[str, Any] = {}
    ucas_code: Optional[str] = None
    external_ids: Dict[str, Any] = {}
    programs: List[AcademicProgramSchema] = []
    costs: List[InstitutionCostSchema] = []
    campuses: List[InstitutionSummaryV3Schema] = []
    provenance_summary: List[DataProvenanceSchema] = []

    @field_validator("external_ids", "student_demographics", mode="before")
    @classmethod
    def coerce_dicts(cls, v):
        return v if v is not None else {}


class InstitutionSearchResponse(BaseModel):
    items: List[InstitutionSummaryV3Schema]
    total: int
    page: int
    limit: int


class DataQualityFlagSchema(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    flag_type: str
    severity: str
    description: Optional[str] = None
    auto_detected: bool
    resolved: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IngestionRunSchema(BaseModel):
    id: UUID
    source_name: str
    source_type: str
    license_type: Optional[str] = None
    status: str
    records_fetched: int
    records_created: int
    records_updated: int
    records_flagged: int
    error_summary: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
