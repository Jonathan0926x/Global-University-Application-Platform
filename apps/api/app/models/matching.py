import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    CHAR,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MatchingPreference(Base):
    """
    Student's persisted 4-dimensional matching priorities, affordability constraints,
    and geographic/institutional discovery preferences.
    """
    __tablename__ = "matching_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    max_annual_budget = Column(Numeric(10, 2), nullable=True)
    currency = Column(CHAR(3), default="USD", nullable=False)
    requires_full_aid = Column(Boolean, default=False, nullable=False)
    requires_merit_scholarships = Column(Boolean, default=False, nullable=False)

    preferred_countries = Column(JSONB, default=lambda: ["US"])
    preferred_states_provinces = Column(JSONB, default=list)
    preferred_institution_types = Column(JSONB, default=list)
    preferred_languages = Column(JSONB, default=lambda: ["en"])

    # Four Independent Dimension Weights (default: 0.30, 0.25, 0.25, 0.20)
    weight_academic = Column(Numeric(4, 2), default=0.30, nullable=False)
    weight_financial = Column(Numeric(4, 2), default=0.25, nullable=False)
    weight_readiness = Column(Numeric(4, 2), default=0.25, nullable=False)
    weight_transfer = Column(Numeric(4, 2), default=0.20, nullable=False)

    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    profile = relationship("StudentProfile")


class UniversityRecommendation(Base):
    """
    Auditable 4-Dimensional University Compatibility Evaluation & Student Shortlist Record.
    Never stores admission probability predictions; strictly tracks traceable compatibility inputs.
    """
    __tablename__ = "university_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    applicant_type = Column(String(30), default="first_year", nullable=False, index=True)
    intended_major = Column(String(200), nullable=True)
    match_category = Column(String(30), nullable=False, index=True)
    # reach, target, likely, insufficient_data

    composite_score = Column(Numeric(5, 2), nullable=False)
    score_academic = Column(Numeric(5, 2), nullable=False)
    score_financial = Column(Numeric(5, 2), nullable=False)
    score_readiness = Column(Numeric(5, 2), nullable=False)
    score_transfer = Column(Numeric(5, 2), nullable=False)
    data_confidence_score = Column(Numeric(4, 2), nullable=False)

    explanation_breakdown = Column(JSONB, default=dict, nullable=False)
    outstanding_prerequisites = Column(JSONB, default=list, nullable=False)
    missing_documents = Column(JSONB, default=list, nullable=False)
    financial_concerns = Column(JSONB, default=list, nullable=False)
    transfer_uncertainties = Column(JSONB, default=list, nullable=False)
    upcoming_deadlines = Column(JSONB, default=list, nullable=False)

    estimated_net_cost = Column(Numeric(10, 2), nullable=True)
    cost_is_estimated = Column(Boolean, default=True, nullable=False)

    is_saved_by_student = Column(Boolean, default=False, nullable=False, index=True)
    is_dismissed = Column(Boolean, default=False, nullable=False)
    computed_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    profile = relationship("StudentProfile")
    institution = relationship("Institution")

    __table_args__ = (
        UniqueConstraint("profile_id", "institution_id", name="uq_rec_profile_institution"),
        Index("ix_recs_profile_saved", "profile_id", "is_saved_by_student"),
    )
