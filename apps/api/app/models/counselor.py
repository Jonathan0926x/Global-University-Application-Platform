import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class CounselorConversation(Base):
    __tablename__ = "counselor_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), default="Admissions Inquiry", nullable=False)
    primary_language = Column(String(20), default="en-US", nullable=False)
    active_institution_id = Column(UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True)
    active_applicant_type = Column(String(30), nullable=True)
    active_topic = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    messages = relationship("CounselorMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="CounselorMessage.created_at")


class CounselorMessage(Base):
    __tablename__ = "counselor_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("counselor_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    language = Column(String(20), default="en-US", nullable=False)
    citations = Column(JSONB, default=list)  # List of {title, url, institution, verified_at, summary, source_type, epistemic_tier}
    epistemic_breakdown = Column(JSONB, default=dict)  # {official_facts, historical_facts, ai_interpretation, missing_or_conflicting, suggested_workflows}
    disclaimer = Column(
        String(255),
        default="AI Interpretation only — not an official university admissions decision.",
        nullable=False
    )
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    conversation = relationship("CounselorConversation", back_populates="messages")
