import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Document(Base):
    """
    Original Academic Document Record
    MANDATORY PRESERVATION: Original uploaded files are NEVER overwritten,
    mutated, or substituted by machine translations.
    """
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, docx, txt, jpg, png, csv, etc.
    file_size_bytes = Column(Integer, nullable=False)
    file_sha256 = Column(String(64), nullable=False, index=True)  # Cryptographic integrity checksum
    storage_path = Column(String(500), nullable=False)
    detected_language = Column(String(20), default="en-US", nullable=False)
    document_category = Column(String(50), default="transcript")  # transcript, diploma, test_score, syllabus
    is_archived = Column(Boolean, default=False, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    profile = relationship("StudentProfile", back_populates="documents")
    extraction = relationship("DocumentExtraction", back_populates="document", uselist=False, cascade="all, delete-orphan")
    translations = relationship("DocumentTranslation", back_populates="document", cascade="all, delete-orphan")


class DocumentExtraction(Base):
    """
    Extracted Document Data & OCR Metadata
    """
    __tablename__ = "document_extractions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    extracted_text = Column(Text, nullable=False)
    detected_institution = Column(String(255), nullable=True)
    detected_qualification = Column(String(255), nullable=True)  # e.g., Baccalauréat haïtien, Associate Degree
    detected_grading_scale = Column(String(100), nullable=True)  # e.g., 20-point scale, 4.0 scale
    extracted_data_json = Column(JSONB, default=dict)  # courses, credits, grades, terms
    extraction_confidence = Column(String(50), default="high_confidence")  # high_confidence, needs_review, uncertain_extraction
    extraction_warnings = Column(JSONB, default=list)  # warnings for human verification
    extracted_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="extraction")


class DocumentTranslation(Base):
    """
    Translated Academic Content with Provenance Disclaimers
    Maintained as a strictly isolated representation from original files.
    """
    __tablename__ = "document_translations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    target_language = Column(String(20), nullable=False)  # BCP 47 code (e.g. en-US)
    translated_text = Column(Text, nullable=False)
    translated_data_json = Column(JSONB, default=dict)
    translation_engine = Column(String(100), default="UniGlobe Academic Intelligence v1")
    translation_confidence = Column(String(50), default="high_confidence")  # high_confidence, needs_review
    translation_disclaimer = Column(
        String(255),
        default="Machine Translation — Not Certified as an Official University Document",
        nullable=False
    )
    is_human_reviewed = Column(Boolean, default=False, nullable=False)
    human_reviewer_notes = Column(Text, nullable=True)
    translated_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="translations")
