import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ApplicationRoute(Base):
    """
    Verified directory of official application destinations (institutional portals,
    centralized national/state platforms such as Common App, UC Application, UCAS,
    OUAC, Études en France, uni-assist) with strict verification provenance.
    """
    __tablename__ = "application_routes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    platform_name = Column(String(200), nullable=False)
    platform_type = Column(String(50), default="direct_portal", nullable=False, index=True)
    # direct_portal | centralized_platform | country_platform | state_system

    country_code = Column(String(2), nullable=False, index=True)
    applicant_type = Column(String(40), default="all", nullable=False, index=True)
    # first_year | transfer | international_first_year | international_transfer | all

    official_url = Column(Text, nullable=False)
    international_instructions = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    source_name = Column(String(200), nullable=False)
    source_url = Column(Text, nullable=True)
    verification_status = Column(String(30), default="verified", nullable=False, index=True)
    # verified | needs_verification | unverified
    confidence_level = Column(String(20), default="high", nullable=False)
    # high | medium | low

    verified_at = Column(DateTime(timezone=True), nullable=True)
    last_checked_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    institution = relationship("Institution")


class ApplicationStatusHistory(Base):
    """
    Immutable audit trail preserving timestamps and actors for every lifecycle transition.
    """
    __tablename__ = "application_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=False, index=True)
    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_role = Column(String(30), default="student", nullable=False)
    reason = Column(Text, nullable=True)
    metadata_json = Column(JSONB, default=dict, nullable=False)
    changed_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    application = relationship("Application", back_populates="status_history")


class ApplicationSubmissionEvidence(Base):
    """
    Private student-uploaded submission confirmation evidence (confirmation emails,
    portal screenshots, fee receipts) linked to Document Vault and explicit review status.
    """
    __tablename__ = "application_submission_evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evidence_type = Column(String(50), default="portal_screenshot", nullable=False)
    # confirmation_email | portal_screenshot | receipt_pdf | reference_slip

    external_confirmation_number = Column(String(120), nullable=True)
    submitted_note = Column(Text, nullable=True)

    review_status = Column(String(30), default="pending", nullable=False, index=True)
    # pending | accepted | rejected
    reviewer_user_id = Column(UUID(as_uuid=True), nullable=True)
    reviewer_notes = Column(Text, nullable=True)

    submitted_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    application = relationship("Application", back_populates="submission_evidence")
    document = relationship("Document")
