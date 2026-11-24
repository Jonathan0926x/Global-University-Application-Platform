import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, CHAR, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database import Base


class Institution(Base):
    __tablename__ = "institutions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    official_name = Column(String(500), nullable=False, index=True)
    alternative_names = Column(JSONB, default=list)  # e.g. ["UC Berkeley", "Cal"]
    abbreviation = Column(String(50), nullable=True)

    # Multi-campus support
    parent_institution_id = Column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True)
    campus_name = Column(String(200), nullable=True)
    is_main_campus = Column(Boolean, default=True, nullable=False)

    # Geography
    country_code = Column(CHAR(2), ForeignKey("countries.code"), nullable=False, default="US", index=True)
    state_province = Column(String(100), nullable=True, index=True)
    city = Column(String(200), nullable=True)
    postal_code = Column(String(20), nullable=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)

    # Classification
    institution_type = Column(String(50), nullable=False, index=True)
    # university, liberal_arts_college, community_college, technical_college, vocational, specialized, online, branch_campus, other
    control_type = Column(String(30), nullable=True)  # public, private_nonprofit, private_forprofit
    carnegie_classification = Column(String(150), nullable=True)

    # Official presence
    official_website = Column(Text, nullable=True)
    admissions_website = Column(Text, nullable=True)
    financial_aid_website = Column(Text, nullable=True)
    international_admissions_website = Column(Text, nullable=True)

    # Accreditation
    accreditation_status = Column(String(50), nullable=True)
    accrediting_body = Column(String(300), nullable=True)
    accreditation_details = Column(JSONB, default=dict)

    # Size & published admission benchmarks (only populated from authoritative sources)
    total_enrollment = Column(Integer, nullable=True)
    undergraduate_enrollment = Column(Integer, nullable=True)
    graduate_enrollment = Column(Integer, nullable=True)
    acceptance_rate = Column(Numeric(5, 2), nullable=True)
    student_faculty_ratio = Column(String(20), nullable=True)
    sat_math_25 = Column(Integer, nullable=True)
    sat_math_75 = Column(Integer, nullable=True)
    sat_ebrw_25 = Column(Integer, nullable=True)
    sat_ebrw_75 = Column(Integer, nullable=True)
    act_composite_25 = Column(Integer, nullable=True)
    act_composite_75 = Column(Integer, nullable=True)
    gpa_25 = Column(Numeric(4, 2), nullable=True)
    gpa_75 = Column(Numeric(4, 2), nullable=True)

    # Costs (summary in-state and out-of-state/international; versioned details in institution_costs)
    tuition_in_state = Column(Numeric(10, 2), nullable=True)
    tuition_out_of_state = Column(Numeric(10, 2), nullable=True)
    currency = Column(CHAR(3), default="USD")

    # External canonical identifiers
    ipeds_unit_id = Column(String(20), nullable=True, unique=True, index=True)
    ope_id = Column(String(20), nullable=True, index=True)
    ucas_code = Column(String(20), nullable=True, index=True)
    ror_id = Column(String(100), nullable=True, unique=True, index=True)
    openalex_id = Column(String(100), nullable=True, unique=True, index=True)
    external_ids = Column(JSONB, default=dict)  # Country-specific IDs e.g. fr_uai, in_aishe, ca_dli, ht_menfp

    # Transfer & First-year specifics
    accepts_transfer = Column(Boolean, default=True)
    accepts_first_year = Column(Boolean, default=True)
    accepts_international = Column(Boolean, default=True)

    # Vector embedding & Full-Text Search
    embedding = Column(Vector(1536), nullable=True)
    search_vector = Column(TSVECTOR, nullable=True)

    # Data quality & verification
    data_completeness_score = Column(Numeric(3, 2), default=0.0)
    last_verified_at = Column(DateTime(timezone=True), nullable=True)
    is_verified = Column(Boolean, default=True)
    is_published = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    country = relationship("Country", back_populates="institutions")
    parent_institution = relationship("Institution", remote_side=[id], backref="campuses")
    applications = relationship("Application", back_populates="institution")
    programs = relationship("AcademicProgram", back_populates="institution", cascade="all, delete-orphan")
    costs = relationship("InstitutionCost", back_populates="institution", cascade="all, delete-orphan")


class AcademicProgram(Base):
    __tablename__ = "academic_programs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)

    program_name = Column(String(500), nullable=False, index=True)
    degree_level = Column(String(50), nullable=False, index=True)  # certificate, associate, bachelors, masters, doctoral, professional, other
    degree_type = Column(String(100), nullable=True)  # Bachelor of Science, Associate of Science for Transfer
    department = Column(String(300), nullable=True)

    cip_code = Column(String(20), nullable=True, index=True)  # US CIP
    isced_code = Column(String(20), nullable=True, index=True)  # UNESCO ISCED international field code
    duration_years = Column(Numeric(3, 1), nullable=True)
    credit_requirements = Column(Integer, nullable=True)

    language_of_instruction = Column(String(20), default="en")
    delivery_mode = Column(String(30), default="in_person")  # in_person, online, hybrid
    program_url = Column(Text, nullable=True)
    is_accepting_applications = Column(Boolean, default=True)
    accepts_transfer_students = Column(Boolean, nullable=True)

    academic_year = Column(String(9), nullable=True, index=True)
    source_url = Column(Text, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_status = Column(String(20), default="unverified")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    institution = relationship("Institution", back_populates="programs")


class InstitutionCost(Base):
    __tablename__ = "institution_costs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)

    academic_year = Column(String(9), nullable=False, index=True)  # e.g., "2026-2027"
    student_type = Column(String(30), nullable=False, index=True)  # in_state, out_of_state, international, domestic
    degree_level = Column(String(50), default="bachelors")

    tuition = Column(Numeric(10, 2), nullable=True)
    mandatory_fees = Column(Numeric(10, 2), nullable=True)
    room_board = Column(Numeric(10, 2), nullable=True)
    books_supplies = Column(Numeric(10, 2), nullable=True)
    personal_expenses = Column(Numeric(10, 2), nullable=True)
    transportation = Column(Numeric(10, 2), nullable=True)
    health_insurance = Column(Numeric(10, 2), nullable=True)
    total_estimated_cost = Column(Numeric(10, 2), nullable=True)
    currency = Column(CHAR(3), default="USD")

    is_current = Column(Boolean, default=True, nullable=False, index=True)
    source_url = Column(Text, nullable=True)
    retrieved_at = Column(DateTime(timezone=True), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_status = Column(String(20), default="unverified")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    institution = relationship("Institution", back_populates="costs")
