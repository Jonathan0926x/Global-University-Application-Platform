import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import Base


class ScholarshipProgram(Base):
    """
    Verified institutional, federal, or national scholarship / financial-aid program
    grounded strictly in official published program documentation.
    """
    __tablename__ = "scholarship_programs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    country_code = Column(String(2), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    applicant_type = Column(String(30), default="all", nullable=False)  # first_year | transfer | all
    funding_type = Column(String(50), default="need_based", nullable=False)  # need_based | merit | tuition_free | statutory_aid
    covers_international = Column(Boolean, default=False, nullable=False)
    max_award_info = Column(String(255), nullable=True)
    eligibility_summary = Column(Text, nullable=False)
    source_name = Column(String(255), nullable=False)
    source_url = Column(String(500), nullable=False)
    verified_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    is_verified = Column(Boolean, default=True, nullable=False)
    is_current = Column(Boolean, default=True, nullable=False)

    institution = relationship("Institution")


class RagKnowledgeChunk(Base):
    """
    Shared public institutional & admissions knowledge chunk indexed for hybrid
    pgvector cosine similarity + PostgreSQL full-text search (TSVECTOR).

    NEVER stores student-private profile, transcript, or document vault records.
    """
    __tablename__ = "rag_knowledge_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    country_code = Column(String(2), nullable=True, index=True)

    # requirement | deadline | cost | scholarship | program | articulation | qualification | institutional_overview
    chunk_type = Column(String(50), nullable=False, index=True)
    # official | historical | ai_interpretation
    epistemic_tier = Column(String(30), default="official", nullable=False, index=True)
    # official_institutional | federal_ipeds | federal_scorecard | articulation_agreement | historical_transfer | country_qualification | official_aid_program
    source_type = Column(String(50), default="official_institutional", nullable=False)

    applicant_type = Column(String(30), default="all", nullable=False, index=True)
    title = Column(String(300), nullable=False)
    content_text = Column(Text, nullable=False)

    source_name = Column(String(255), nullable=False)
    source_url = Column(String(500), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    is_outdated = Column(Boolean, default=False, nullable=False)
    has_conflict = Column(Boolean, default=False, nullable=False)

    metadata_json = Column(JSONB, default=dict, nullable=False)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)

    embedding = Column(Vector(384), nullable=False)
    search_tsv = Column(TSVECTOR, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    institution = relationship("Institution")

    __table_args__ = (
        Index("ix_rag_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_rag_chunks_tsv_gin", "search_tsv", postgresql_using="gin"),
    )
