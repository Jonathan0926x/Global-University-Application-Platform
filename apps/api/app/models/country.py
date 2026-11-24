from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, CHAR, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Country(Base):
    __tablename__ = "countries"

    code = Column(CHAR(2), primary_key=True)  # ISO 3166-1 alpha-2
    name = Column(String(200), nullable=False)
    name_local = Column(String(200), nullable=True)
    region = Column(String(100), nullable=True, index=True)
    subregion = Column(String(100), nullable=True)
    currency_code = Column(CHAR(3), nullable=True)  # ISO 4217
    primary_languages = Column(JSONB, default=list)  # ["en", "fr"]
    higher_ed_ministry = Column(String(300), nullable=True)
    higher_ed_ministry_url = Column(Text, nullable=True)
    accreditation_body = Column(String(300), nullable=True)
    education_system_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    institutions = relationship("Institution", back_populates="country")
