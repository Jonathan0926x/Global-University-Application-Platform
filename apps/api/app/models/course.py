import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Course(Base):
    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("enrollment_records.id", ondelete="CASCADE"), nullable=False, index=True)

    course_code = Column(String(50), nullable=True) # e.g. "CS 101", "MATH 1A"
    course_name = Column(String(300), nullable=False)
    department = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)

    credit_hours = Column(Numeric(4, 1), nullable=True)
    credit_type = Column(String(20), default="semester_hour") # semester_hour, quarter_hour, ects, unit
    grade = Column(String(20), nullable=True) # "A", "15/20", "Pass"
    grade_points = Column(Numeric(4, 2), nullable=True)
    course_level = Column(String(20), nullable=True) # 100-level, 200-level, AP, honors

    status = Column(String(20), default="completed", nullable=False) # completed, in_progress, planned
    academic_term = Column(String(30), nullable=True) # "Fall 2025"
    academic_year = Column(String(9), nullable=True) # "2025-2026"

    is_ap_ib_dual = Column(Boolean, default=False)
    ap_ib_score = Column(String(10), nullable=True)
    is_transferable = Column(Boolean, nullable=True)
    learning_outcomes = Column(JSONB, default=list)
    syllabus_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    enrollment = relationship("EnrollmentRecord", back_populates="courses")
