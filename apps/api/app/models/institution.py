import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, CHAR, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.database import Base


class Institution(Base):
    __tablename__ = "institutions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    official_name = Column(String(500), nullable=False, index=True)
    alternative_names = Column(JSONB, default=list) # e.g. ["UC Berkeley", "Cal"]
    abbreviation = Column(String(50), nullable=True)

    country_code = Column(CHAR(2), nullable=False, default="US", index=True)
    state_province = Column(String(100), nullable=True, index=True)
    city = Column(String(200), nullable=True)

    institution_type = Column(String(50), nullable=False, index=True) # university, community_college, liberal_arts
    control_type = Column(String(30), nullable=True) # public, private_nonprofit, private_forprofit

    official_website = Column(Text, nullable=True)
    admissions_website = Column(Text, nullable=True)

    total_enrollment = Column(Integer, nullable=True)
    acceptance_rate = Column(Numeric(5, 2), nullable=True)

    # Costs (in-state and out-of-state/international)
    tuition_in_state = Column(Numeric(10, 2), nullable=True)
    tuition_out_of_state = Column(Numeric(10, 2), nullable=True)
    currency = Column(CHAR(3), default="USD")

    # Transfer & First-year specifics
    accepts_transfer = Column(Boolean, default=True)
    accepts_first_year = Column(Boolean, default=True)
    accepts_international = Column(Boolean, default=True)

    # Vector embedding for semantic discovery / matching
    embedding = Column(Vector(1536), nullable=True)

    is_verified = Column(Boolean, default=True)
    is_published = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    applications = relationship("Application", back_populates="institution")
