import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    preferred_language = Column(String(20), default="en-US", nullable=False)
    regional_locale = Column(String(20), default="en-US", nullable=False)
    preferred_script = Column(String(20), default="Latn", nullable=False)
    display_currency = Column(String(10), default="USD", nullable=False)
    calendar_system = Column(String(30), default="gregory", nullable=False)
    auto_detect_enabled = Column(Boolean, default=True, nullable=False)
    last_manually_selected_lang = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="preferences")
