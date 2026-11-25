import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class GradeConversionRule(Base):
    """
    Criterion-referenced international grade conversion bracket preserving native scale
    meaning alongside informational US 4.0 benchmark equivalents.
    """
    __tablename__ = "grade_conversion_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_country_code = Column(String(2), nullable=False, index=True)
    grading_system_key = Column(String(60), nullable=False, index=True)
    scale_name = Column(String(160), nullable=False)
    academic_level = Column(String(30), default="secondary", nullable=False)
    band_order = Column(Integer, default=0, nullable=False)

    min_numeric = Column(Numeric(7, 2), nullable=True)
    max_numeric = Column(Numeric(7, 2), nullable=True)
    raw_grade_label = Column(String(40), nullable=True)

    classification_label = Column(String(120), nullable=False)
    target_letter_equivalent = Column(String(20), nullable=False)
    target_gpa_low = Column(Numeric(4, 2), nullable=False)
    target_gpa_high = Column(Numeric(4, 2), nullable=False)
    target_gpa_point = Column(Numeric(4, 2), nullable=False)

    is_passing = Column(Boolean, default=True, nullable=False)
    is_inverted_scale = Column(Boolean, default=False, nullable=False)
    methodology = Column(String(50), default="distribution_percentile", nullable=False)
    methodology_citation = Column(Text, nullable=False)
    percentile_note = Column(Text, nullable=True)
    confidence_level = Column(String(20), default="high", nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Step 1 Provenance, Structure & Freshness Governance
    issuing_authority = Column(String(255), nullable=True)
    grading_structure = Column(String(120), nullable=True)
    framework_version = Column(String(64), nullable=True)
    equivalency_classification = Column(String(40), default="reference_benchmark", nullable=False)
    source_url = Column(String(500), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(String(255), nullable=True)
    verification_expires_at = Column(DateTime(timezone=True), nullable=True)
    freshness_status = Column(String(40), default="requires_manual_review", nullable=False, index=True)


class CredentialRecognitionRule(Base):
    """
    Source-country to destination-country credential recognition & evaluation gatekeeping rule.
    """
    __tablename__ = "credential_recognition_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_country_code = Column(String(2), nullable=False, index=True)
    destination_country_code = Column(String(2), nullable=False, index=True)
    source_credential_name = Column(String(255), nullable=False)

    is_directly_recognized = Column(Boolean, default=True, nullable=False)
    requires_external_evaluation = Column(Boolean, default=False, nullable=False)
    accepted_evaluation_agencies = Column(JSONB, default=list, nullable=False)

    requires_official_translation = Column(Boolean, default=False, nullable=False)
    translation_requirements = Column(Text, nullable=True)
    requires_apostille_or_legalization = Column(Boolean, default=False, nullable=False)
    requires_direct_institutional_dispatch = Column(Boolean, default=True, nullable=False)

    english_waiver_policy = Column(Text, nullable=True)
    pathway_notes = Column(Text, nullable=False)

    source_name = Column(String(255), nullable=False)
    source_url = Column(String(500), nullable=False)
    verified_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    verification_status = Column(String(20), default="verified", nullable=False)

    # Step 1 Provenance, Structure & Freshness Governance
    issuing_authority = Column(String(255), nullable=True)
    education_level = Column(String(40), default="secondary", nullable=False)
    exam_structure = Column(String(200), nullable=True)
    framework_version = Column(String(64), nullable=True)
    equivalency_classification = Column(String(40), default="official_equivalency", nullable=False)
    verified_by = Column(String(255), nullable=True)
    verification_expires_at = Column(DateTime(timezone=True), nullable=True)
    freshness_status = Column(String(40), default="requires_manual_review", nullable=False, index=True)
