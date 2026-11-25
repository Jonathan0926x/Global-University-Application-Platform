import uuid
from datetime import datetime
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
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


class ScholarshipProgram(Base):
    """
    Verified institutional, federal, or national scholarship / financial-aid program
    grounded strictly in official published program documentation.
    """
    __tablename__ = "scholarship_programs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    country_code = Column(String(2), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    applicant_type = Column(String(30), default="all", nullable=False)  # first_year | transfer | all
    funding_type = Column(String(50), default="need_based", nullable=False)  # need_based | merit | tuition_free | statutory_aid
    covers_international = Column(Boolean, default=False, nullable=False)
    max_award_info = Column(String(255), nullable=True)
    eligibility_summary = Column(Text, nullable=False)

    # Phase 4 structured financial & eligibility metadata
    provider_type = Column(String(40), default="university", nullable=False)
    award_type = Column(String(40), default="fixed_amount", nullable=False)
    award_amount_min_usd = Column(Numeric(12, 2), nullable=True)
    award_amount_max_usd = Column(Numeric(12, 2), nullable=True)
    award_currency = Column(CHAR(3), default="USD", nullable=False)
    is_renewable = Column(Boolean, default=True, nullable=False)

    covers_tuition = Column(Boolean, default=True, nullable=False)
    covers_fees = Column(Boolean, default=False, nullable=False)
    covers_housing = Column(Boolean, default=False, nullable=False)
    covers_meals = Column(Boolean, default=False, nullable=False)
    covers_health_insurance = Column(Boolean, default=False, nullable=False)
    provides_living_stipend = Column(Boolean, default=False, nullable=False)

    application_deadline_date = Column(Date, nullable=True)
    is_deadline_rolling = Column(Boolean, default=False, nullable=False)
    min_gpa_4 = Column(Numeric(4, 2), nullable=True)
    requires_financial_need = Column(Boolean, default=False, nullable=False)

    eligible_citizenships = Column(JSONB, default=list, nullable=False)
    eligible_residency_states = Column(JSONB, default=list, nullable=False)
    eligible_destination_countries = Column(JSONB, default=list, nullable=False)
    degree_levels = Column(JSONB, default=lambda: ["bachelors"], nullable=False)
    is_guaranteed_statutory = Column(Boolean, default=False, nullable=False)

    source_name = Column(String(255), nullable=False)
    source_url = Column(String(500), nullable=False)
    verified_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    is_verified = Column(Boolean, default=True, nullable=False)
    is_current = Column(Boolean, default=True, nullable=False)

    # Step 1 Provenance, Native Financial & Data Freshness Governance
    sponsoring_institution = Column(String(255), nullable=True)
    source_type = Column(String(40), default="unknown", nullable=False)
    source_version = Column(String(64), nullable=True)
    academic_year = Column(String(20), nullable=True)
    award_fixed_usd = Column(Numeric(12, 2), nullable=True)
    native_amount_min = Column(Numeric(14, 2), nullable=True)
    native_amount_max = Column(Numeric(14, 2), nullable=True)
    covers_travel = Column(Boolean, default=False, nullable=False)
    funding_duration_years = Column(Numeric(4, 2), nullable=True)
    max_funding_periods = Column(Integer, nullable=True)
    renewal_conditions = Column(Text, nullable=True)
    verification_method = Column(String(60), default="unknown", nullable=False)
    verified_by = Column(String(255), nullable=True)
    verification_expires_at = Column(DateTime(timezone=True), nullable=True)
    freshness_status = Column(String(40), default="requires_manual_review", nullable=False, index=True)
    requires_manual_review = Column(Boolean, default=False, nullable=False)
    claim_provenance = Column(JSONB, default=dict, nullable=False)
    conflict_notes = Column(Text, nullable=True)

    institution = relationship("Institution")
    rules = relationship(
        "ScholarshipEligibilityRule",
        back_populates="scholarship",
        cascade="all, delete-orphan",
    )


class ScholarshipEligibilityRule(Base):
    """
    Deterministic eligibility rule attached to a verified ScholarshipProgram.
    """
    __tablename__ = "scholarship_eligibility_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scholarship_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scholarship_programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_dimension = Column(String(50), nullable=False, index=True)
    rule_operator = Column(String(30), nullable=False)
    rule_value = Column(JSONB, default=dict, nullable=False)
    human_label = Column(String(255), nullable=False)
    is_mandatory = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    scholarship = relationship("ScholarshipProgram", back_populates="rules")


class RagKnowledgeChunk(Base):
    """
    Shared public institutional & admissions knowledge chunk indexed for hybrid
    pgvector cosine similarity + PostgreSQL full-text search (TSVECTOR).

    NEVER stores student-private profile, transcript, or document vault records.
    """
    __tablename__ = "rag_knowledge_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    country_code = Column(String(2), nullable=True, index=True)

    # requirement | deadline | cost | scholarship | program | articulation | qualification | institutional_overview
    chunk_type = Column(String(50), nullable=False, index=True)
    # official | historical | ai_interpretation
    epistemic_tier = Column(String(30), default="official", nullable=False, index=True)
    # official_institutional | federal_ipeds | federal_scorecard | articulation_agreement | historical_transfer | country_qualification | official_aid_program
    source_type = Column(String(50), default="official_institutional", nullable=False)

    applicant_type = Column(String(30), default="all", nullable=False, index=True)
    title = Column(String(300), nullable=False)
    content_text = Column(Text, nullable=False)

    source_name = Column(String(255), nullable=False)
    source_url = Column(String(500), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    is_outdated = Column(Boolean, default=False, nullable=False)
    has_conflict = Column(Boolean, default=False, nullable=False)

    metadata_json = Column(JSONB, default=dict, nullable=False)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)

    embedding = Column(Vector(384), nullable=False)
    search_tsv = Column(TSVECTOR, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    institution = relationship("Institution")

    __table_args__ = (
        Index("ix_rag_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_rag_chunks_tsv_gin", "search_tsv", postgresql_using="gin"),
    )
