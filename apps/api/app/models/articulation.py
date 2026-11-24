import uuid
from datetime import datetime, timezone
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CourseCatalog(Base):
    """
    Normalized institution course catalog capturing official course descriptions,
    learning outcomes, prerequisites, academic level, and local pgvector semantic embeddings.
    """
    __tablename__ = "course_catalog"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    course_code = Column(String(50), nullable=False, index=True)
    normalized_code = Column(String(50), nullable=False, index=True)
    course_name = Column(String(500), nullable=False)
    department = Column(String(200), nullable=True, index=True)
    subject_area = Column(String(100), nullable=True, index=True)
    description = Column(Text, nullable=True)
    learning_outcomes = Column(JSONB, default=list)
    prerequisites = Column(Text, nullable=True)

    credit_hours = Column(Numeric(5, 2), nullable=True)
    contact_hours = Column(Numeric(5, 2), nullable=True)
    credit_system = Column(String(30), default="us_semester", nullable=False)
    # us_semester, us_quarter, ects, uk_cat, ca_credit, other
    course_level = Column(String(30), nullable=True)  # 100, 200, 300, 400, lower_division, upper_division
    is_lab = Column(Boolean, default=False, nullable=False)

    description_embedding = Column(Vector(384), nullable=True)

    catalog_year = Column(String(9), nullable=False, default="2026-2027")
    source_name = Column(String(200), nullable=False, default="Institution Catalog")
    source_url = Column(Text, nullable=True)
    retrieved_at = Column(DateTime(timezone=True), default=_utcnow, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    institution = relationship("Institution")

    __table_args__ = (
        UniqueConstraint("institution_id", "course_code", "catalog_year", name="uq_catalog_inst_code_year"),
    )


class ArticulationAgreement(Base):
    """
    Published inter-institutional articulation agreement (e.g. ASSIST.org bilateral major agreement,
    UC/CSU general education agreement, or international transfer protocol).
    """
    __tablename__ = "articulation_agreements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    agreement_type = Column(String(50), nullable=False, default="major_articulation")
    # major_articulation, general_education, guaranteed_transfer, bilateral, historical_pattern
    program_name = Column(String(300), nullable=True)
    cip_code = Column(String(20), nullable=True)
    effective_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)
    academic_year = Column(String(9), nullable=False, default="2026-2027")
    notes = Column(Text, nullable=True)

    source_name = Column(String(200), nullable=False)
    source_url = Column(Text, nullable=False)
    retrieved_at = Column(DateTime(timezone=True), default=_utcnow, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_status = Column(String(30), nullable=False, default="verified")

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    source_institution = relationship("Institution", foreign_keys=[source_institution_id])
    target_institution = relationship("Institution", foreign_keys=[target_institution_id])


class CourseEquivalency(Base):
    """
    3-Tier Transfer Course Equivalency & Degree Applicability Matrix:
    - Tier 1: Officially Verified (published articulation agreement / ASSIST.org)
    - Tier 2: Historically Observed (documented historical transfer outcomes)
    - Tier 3: AI Predicted (description + learning outcome + credit/level similarity)
    """
    __tablename__ = "course_equivalencies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    source_institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_course_id = Column(
        UUID(as_uuid=True),
        ForeignKey("course_catalog.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_course_code = Column(String(80), nullable=False, index=True)
    source_course_name = Column(String(500), nullable=True)

    target_institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_course_id = Column(
        UUID(as_uuid=True),
        ForeignKey("course_catalog.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_course_code = Column(String(80), nullable=True, index=True)
    target_course_name = Column(String(500), nullable=True)

    equivalency_tier = Column(SmallInteger, nullable=False, index=True)  # 1, 2, or 3
    equivalency_type = Column(String(30), nullable=False, default="direct")
    # direct, partial, combined, elective_only, no_equivalent
    confidence_score = Column(Numeric(4, 3), nullable=True)

    source_credits = Column(Numeric(5, 2), nullable=True)
    source_credit_system = Column(String(30), default="us_semester", nullable=False)
    target_credits = Column(Numeric(5, 2), nullable=True)
    target_credit_system = Column(String(30), default="us_semester", nullable=False)
    credits_transferable = Column(Numeric(5, 2), nullable=True)

    # Degree Applicability Distinction (Section 4)
    satisfies_major_requirement = Column(Boolean, default=False, nullable=False)
    satisfies_ge_requirement = Column(Boolean, default=False, nullable=False)
    ge_category = Column(String(120), nullable=True)
    satisfies_prerequisite = Column(Boolean, default=False, nullable=False)
    elective_only = Column(Boolean, default=False, nullable=False)
    applies_to_degree_programs = Column(JSONB, default=list)

    # Provenance & Versioning
    source_type = Column(String(50), nullable=False, default="assist_org")
    # assist_org, institution_website, historical_transfer_outcome, ai_prediction
    source_name = Column(String(200), nullable=False)
    source_url = Column(Text, nullable=True)
    articulation_agreement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("articulation_agreements.id", ondelete="SET NULL"),
        nullable=True,
    )
    supporting_evidence = Column(Text, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    academic_year = Column(String(9), nullable=True, index=True)
    is_current = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    source_institution = relationship("Institution", foreign_keys=[source_institution_id])
    target_institution = relationship("Institution", foreign_keys=[target_institution_id])
    source_course = relationship("CourseCatalog", foreign_keys=[source_course_id])
    target_course = relationship("CourseCatalog", foreign_keys=[target_course_id])
    agreement = relationship("ArticulationAgreement", foreign_keys=[articulation_agreement_id])

    __table_args__ = (
        Index(
            "ix_equiv_pair_tier",
            "source_institution_id",
            "target_institution_id",
            "equivalency_tier",
            "is_current",
        ),
    )
