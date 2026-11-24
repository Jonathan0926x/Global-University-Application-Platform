import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name = Column(String(200), nullable=False, index=True)
    source_type = Column(String(50), nullable=False)  # ipeds_csv, urban_api, scorecard_api, openalex_ror, assist_api, manual
    license_type = Column(String(100), nullable=True)  # Public Domain, ODC-By-1.0, CC0-1.0, UC-EULA
    status = Column(String(30), nullable=False, default="running", index=True)  # running, completed, failed, partial

    records_fetched = Column(Integer, default=0)
    records_created = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_flagged = Column(Integer, default=0)

    metadata_json = Column(JSONB, default=dict)
    error_summary = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class DataProvenance(Base):
    """
    Centralized non-destructive provenance & audit history.
    Historical changes are appended with `previous_value` and `is_current=True`
    rather than silently overwriting prior records.
    """
    __tablename__ = "data_provenance"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False, index=True)  # institution, program, cost, deadline, route, requirement
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    field_name = Column(String(100), nullable=True)  # None indicates full-record snapshot

    source_type = Column(String(50), nullable=False)  # ipeds, college_scorecard, openalex_ror, official_website, government_db, api, manual_entry
    source_url = Column(Text, nullable=True)
    source_name = Column(String(200), nullable=False)
    collection_method = Column(String(50), nullable=False, default="api")  # api, bulk_csv, official_html, manual_curation

    retrieved_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    academic_year = Column(String(9), nullable=True, index=True)

    confidence_level = Column(String(30), nullable=False, default="unverified", index=True)
    # verified, likely_accurate, unverified, outdated, disputed

    data_hash = Column(String(64), nullable=True, index=True)  # SHA-256 of canonical snapshot
    previous_value = Column(JSONB, nullable=True)
    is_current = Column(Boolean, default=True, nullable=False, index=True)

    ingestion_run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class DataQualityFlag(Base):
    __tablename__ = "data_quality_flags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    flag_type = Column(String(50), nullable=False, index=True)
    # broken_link, expired_deadline, stale_data, missing_required_field, conflicting_data, suspicious_value, user_reported
    severity = Column(String(20), nullable=False, default="warning")  # info, warning, error, critical
    description = Column(Text, nullable=True)

    auto_detected = Column(Boolean, default=True, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False, index=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
