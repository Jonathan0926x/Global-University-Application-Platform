import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, SmallInteger, Date, DateTime, ForeignKey, CHAR
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    # Legal Name
    first_name = Column(String(100), nullable=True)
    middle_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    suffix = Column(String(20), nullable=True)

    # International and preferred name handling
    preferred_first_name = Column(String(100), nullable=True)
    preferred_last_name = Column(String(100), nullable=True)
    name_format = Column(String(20), default="western") # western, eastern, single_name
    full_name_native_script = Column(String(200), nullable=True)

    # Demographics
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(30), nullable=True)
    pronouns = Column(String(50), nullable=True)

    # Contact & Address
    phone_country_code = Column(String(5), nullable=True)
    phone_number = Column(String(20), nullable=True)
    address_line_1 = Column(String(200), nullable=True)
    address_line_2 = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    state_province = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country_code = Column(CHAR(2), nullable=True)
    country_of_residence = Column(CHAR(2), nullable=True)
    residency_status = Column(String(50), nullable=True)

    # Pathway context (First-Year, Transfer, or Both)
    applicant_type = Column(String(20), default="undecided", nullable=False, index=True)
    intended_enrollment_term = Column(String(20), nullable=True)
    intended_enrollment_year = Column(Integer, nullable=True)
    intended_major = Column(String(200), nullable=True)
    intended_degree_level = Column(String(30), default="bachelors")

    # Progress & Completion
    profile_completion_pct = Column(SmallInteger, default=0)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="profile")
    citizenships = relationship("CitizenshipRecord", back_populates="profile", cascade="all, delete-orphan")
    enrollments = relationship("EnrollmentRecord", back_populates="profile", cascade="all, delete-orphan", order_by="EnrollmentRecord.display_order")
    standardized_tests = relationship("StandardizedTest", back_populates="profile", cascade="all, delete-orphan")
    extracurriculars = relationship("ExtracurricularActivity", back_populates="profile", cascade="all, delete-orphan", order_by="ExtracurricularActivity.display_order")
    applications = relationship("Application", back_populates="profile", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="profile", cascade="all, delete-orphan")


class CitizenshipRecord(Base):
    __tablename__ = "citizenship_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    country_code = Column(CHAR(2), nullable=False)
    citizenship_type = Column(String(30), default="citizen") # citizen, dual_citizen, permanent_resident
    is_primary = Column(CHAR(1), default="Y")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    profile = relationship("StudentProfile", back_populates="citizenships")
