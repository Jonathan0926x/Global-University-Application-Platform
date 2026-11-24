import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, ForeignKey, Boolean, CHAR, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class EducationalSystem(Base):
    __tablename__ = "educational_systems"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_code = Column(CHAR(2), nullable=False, index=True)
    system_name = Column(String(200), nullable=False) # e.g. "US High School", "French Baccalaureat", "Haitian NSIV"
    system_type = Column(String(50), nullable=False) # secondary, community_college, undergraduate
    description = Column(Text, nullable=True)


class GradingSystem(Base):
    __tablename__ = "grading_systems"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    educational_system_id = Column(UUID(as_uuid=True), ForeignKey("educational_systems.id"), nullable=True)
    name = Column(String(100), nullable=False) # "US 4.0 Scale", "French 0-20", "A-Level Grades"
    scale_type = Column(String(30), nullable=False) # numeric, letter, percentage
    scale_min = Column(Numeric(5, 2), nullable=True)
    scale_max = Column(Numeric(5, 2), nullable=True)
    passing_grade = Column(String(20), nullable=True)
    grade_descriptors = Column(JSONB, nullable=True)


class EnrollmentRecord(Base):
    __tablename__ = "enrollment_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    institution_id = Column(UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True)
    institution_name_manual = Column(String(300), nullable=True)
    institution_country = Column(CHAR(2), nullable=True)
    institution_city = Column(String(100), nullable=True)

    educational_system_id = Column(UUID(as_uuid=True), ForeignKey("educational_systems.id"), nullable=True)
    grading_system_id = Column(UUID(as_uuid=True), ForeignKey("grading_systems.id"), nullable=True)

    enrollment_type = Column(String(30), nullable=False) # secondary, community_college, undergraduate
    enrollment_status = Column(String(30), default="current", nullable=False) # current, completed, transferred
    
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    expected_graduation = Column(Date, nullable=True)

    degree_type = Column(String(50), nullable=True) # High School Diploma, Associate of Science, Bachelor
    major = Column(String(200), nullable=True)
    academic_standing = Column(String(30), nullable=True)

    # GPA and Credits
    cumulative_gpa = Column(Numeric(4, 2), nullable=True)
    gpa_scale = Column(Numeric(4, 2), default=4.0)
    total_credits_attempted = Column(Numeric(6, 1), nullable=True)
    total_credits_earned = Column(Numeric(6, 1), nullable=True)
    class_rank = Column(Integer, nullable=True)
    class_size = Column(Integer, nullable=True)

    is_current_institution = Column(Boolean, default=False)
    display_order = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("StudentProfile", back_populates="enrollments")
    courses = relationship("Course", back_populates="enrollment", cascade="all, delete-orphan")
    institution = relationship("Institution")
