import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, SmallInteger, Date, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class StandardizedTest(Base):
    __tablename__ = "standardized_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    test_type = Column(String(50), nullable=False) # SAT, ACT, TOEFL, IELTS, AP, IB, etc.
    test_name = Column(String(200), nullable=True)
    test_date = Column(Date, nullable=True)
    total_score = Column(String(20), nullable=True)
    section_scores = Column(JSONB, nullable=True)
    score_reporting_status = Column(String(30), default="self_reported")

    profile = relationship("StudentProfile", back_populates="standardized_tests")


class ExtracurricularActivity(Base):
    __tablename__ = "extracurricular_activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    category = Column(String(50), nullable=False) # leadership, athletics, volunteer, research, work
    activity_name = Column(String(300), nullable=False)
    organization = Column(String(300), nullable=True)
    role_title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    hours_per_week = Column(SmallInteger, nullable=True)
    weeks_per_year = Column(SmallInteger, nullable=True)
    display_order = Column(Integer, default=0)

    profile = relationship("StudentProfile", back_populates="extracurriculars")


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    institution_id = Column(UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False, index=True)

    applicant_type = Column(String(30), nullable=False, index=True) # first_year, transfer
    status = Column(String(30), default="exploring", nullable=False, index=True)
    # exploring, planning, in_progress, awaiting_documents, ready_to_submit, submitted, under_review, accepted, rejected, waitlisted

    intended_major = Column(String(200), nullable=True)
    intended_term = Column(String(20), nullable=True)
    academic_year = Column(String(9), nullable=True)

    readiness_pct = Column(SmallInteger, default=0)
    notes = Column(Text, nullable=True)

    submitted_at = Column(DateTime(timezone=True), nullable=True)
    submitted_via = Column(String(100), nullable=True) # Common App, Direct Portal, UC Application, ApplyTexas

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("StudentProfile", back_populates="applications")
    institution = relationship("Institution", back_populates="applications")
    requirements_status = relationship("ApplicationRequirementStatus", back_populates="application", cascade="all, delete-orphan")


class ApplicationRequirementStatus(Base):
    __tablename__ = "application_requirement_status"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    institution_requirement_id = Column(UUID(as_uuid=True), ForeignKey("institution_requirements.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(300), nullable=False)
    category = Column(String(50), nullable=False) # document, academic, administrative, exam, financial
    importance = Column(String(30), default="required", nullable=False) # required, strongly_recommended, recommended, optional, conditional, not_accepted
    status = Column(String(30), default="pending", nullable=False) # completed, in_progress, pending, not_applicable, waived, needs_verification, missing
    notes = Column(Text, nullable=True)

    satisfied_by_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    satisfied_by_profile_field = Column(String(200), nullable=True)
    auto_matched = Column(Boolean, default=False, nullable=False)
    verification_status = Column(String(30), nullable=True)
    source_url = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    application = relationship("Application", back_populates="requirements_status")
