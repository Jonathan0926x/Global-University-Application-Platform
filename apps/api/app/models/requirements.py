import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CHAR,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RequirementTemplate(Base):
    """
    Canonical reusable admission requirement definition across first-year, transfer,
    international, financial, and examination categories.
    """
    __tablename__ = "requirement_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_key = Column(String(160), unique=True, nullable=False, index=True)
    requirement_type = Column(String(60), nullable=False, index=True)
    requirement_subtype = Column(String(100), nullable=True)
    display_name = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, index=True)  # document, academic, administrative, exam, financial
    default_importance = Column(String(30), default="required", nullable=False)
    can_be_satisfied_from_profile = Column(Boolean, default=False, nullable=False)
    profile_source_table = Column(String(100), nullable=True)
    profile_source_filter = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    institution_requirements = relationship(
        "InstitutionRequirement",
        back_populates="template",
        cascade="all, delete-orphan",
    )


class InstitutionRequirement(Base):
    """
    Normalized institution- and program-specific admission requirement with full
    source verification, applicant-category scoping, and academic-year versioning.
    """
    __tablename__ = "institution_requirements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("academic_programs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    program_name_filter = Column(String(200), nullable=True, index=True)
    cip_code = Column(String(20), nullable=True, index=True)

    requirement_template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("requirement_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Applicant scoping: first_year, transfer, international_first_year, international_transfer, all
    applicant_type = Column(String(30), nullable=False, index=True)
    # Importance: required, strongly_recommended, recommended, optional, conditional, not_accepted
    importance = Column(String(30), nullable=False, default="required", index=True)

    title_override = Column(String(300), nullable=True)
    institution_specific_notes = Column(Text, nullable=True)
    quantity = Column(Integer, default=1, nullable=True)
    minimum_value = Column(String(120), nullable=True)
    maximum_value = Column(String(120), nullable=True)

    fee_amount = Column(Numeric(10, 2), nullable=True)
    fee_currency = Column(CHAR(3), nullable=True)
    fee_waiver_available = Column(Boolean, nullable=True)

    academic_year = Column(String(9), nullable=False, index=True)
    is_current = Column(Boolean, default=True, nullable=False, index=True)

    # Verification & Provenance (Mandatory — distinguish verified vs historical/unverified/AI-extracted)
    source_name = Column(String(200), nullable=False)
    source_type = Column(String(50), nullable=False, default="official_website")
    source_url = Column(Text, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    confidence_level = Column(String(30), nullable=False, default="verified", index=True)
    verification_status = Column(String(30), nullable=False, default="verified", index=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    institution = relationship("Institution")
    program = relationship("AcademicProgram")
    template = relationship("RequirementTemplate", back_populates="institution_requirements")
    conditions = relationship(
        "RequirementCondition",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_inst_req_lookup",
            "institution_id",
            "applicant_type",
            "academic_year",
            "is_current",
        ),
    )


class RequirementCondition(Base):
    """
    Conditional rule modifying requirement applicability/importance based on student profile attributes
    (e.g., English proficiency required if non-English country; HS transcript needed if credits < 30).
    """
    __tablename__ = "requirement_conditions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requirement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institution_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    condition_type = Column(String(50), nullable=False)  # language, citizenship, residency, credits, gpa, education_country
    condition_field = Column(String(100), nullable=False)
    condition_operator = Column(String(20), nullable=False)  # equals, not_equals, in, not_in, greater_than, less_than, between
    condition_value = Column(JSONB, nullable=False)
    result_importance = Column(String(30), nullable=False)  # required, not_applicable, waived, optional, conditional
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    requirement = relationship("InstitutionRequirement", back_populates="conditions")


class Deadline(Base):
    """
    Official institutional or program-specific application, exam, document, and deposit deadlines.
    """
    __tablename__ = "deadlines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("academic_programs.id", ondelete="SET NULL"),
        nullable=True,
    )
    program_name_filter = Column(String(200), nullable=True)

    applicant_type = Column(String(30), nullable=False, index=True)
    deadline_type = Column(String(50), nullable=False, index=True)
    # regular_decision, early_action, early_decision, transfer_fall, transfer_spring,
    # ucas_oxbridge, ucas_equal_consideration, supporting_documents, financial_aid, entrance_exam, rolling
    intake_term = Column(String(40), nullable=False)
    deadline_date = Column(Date, nullable=True, index=True)
    deadline_time = Column(String(40), nullable=True)
    timezone = Column(String(50), nullable=True)
    is_firm = Column(Boolean, default=True, nullable=False)
    notification_date = Column(Date, nullable=True)
    enrollment_deposit_deadline = Column(Date, nullable=True)

    academic_year = Column(String(9), nullable=False, index=True)
    is_current = Column(Boolean, default=True, nullable=False, index=True)
    notes = Column(Text, nullable=True)

    source_name = Column(String(200), nullable=False)
    source_url = Column(Text, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_status = Column(String(30), nullable=False, default="verified", index=True)
    confidence_level = Column(String(30), nullable=False, default="verified")

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    institution = relationship("Institution")

    __table_args__ = (
        Index(
            "ix_deadlines_lookup",
            "institution_id",
            "applicant_type",
            "academic_year",
            "is_current",
        ),
    )


class CountryQualification(Base):
    """
    Normalized country-level secondary diplomas, national examinations, and entrance credentials
    (e.g., Haitian NS4/Bac II, French Baccalauréat, German Abitur, India CUET/JEE, UK A-Levels).
    """
    __tablename__ = "country_qualifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_code = Column(
        CHAR(2),
        ForeignKey("countries.code", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    qualification_name = Column(String(200), nullable=False)
    qualification_type = Column(String(50), nullable=False, index=True)
    # secondary_diploma, national_exam, university_entrance_exam, transfer_credential
    grading_scale = Column(String(120), nullable=True)
    passing_threshold = Column(String(120), nullable=True)
    equivalency_notes = Column(Text, nullable=True)
    recognition_rules = Column(JSONB, default=dict)

    source_name = Column(String(200), nullable=False)
    source_url = Column(Text, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_status = Column(String(30), nullable=False, default="verified")
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    country = relationship("Country")
