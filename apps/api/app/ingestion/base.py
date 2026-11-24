"""
Core Ingestion Pipeline & Provenance Engine.
Implements idempotent upserts, SHA-256 diff detection, non-destructive
historical provenance logging, completeness scoring, and automated quality flags.
"""

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.institution import Institution, AcademicProgram, InstitutionCost
from app.models.provenance import IngestionRun, DataProvenance, DataQualityFlag
from app.ingestion.countries_seed import ensure_country_exists


ALLOWED_INSTITUTION_TYPES = {
    "university",
    "liberal_arts_college",
    "community_college",
    "technical_college",
    "vocational",
    "specialized",
    "online",
    "branch_campus",
    "other",
}

ALLOWED_CONTROL_TYPES = {"public", "private_nonprofit", "private_forprofit"}


class NormalizedInstitution(BaseModel):
    official_name: str
    alternative_names: List[str] = Field(default_factory=list)
    abbreviation: Optional[str] = None

    country_code: str = "US"
    country_name: Optional[str] = None
    state_province: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    institution_type: str = "university"
    control_type: Optional[str] = None
    carnegie_classification: Optional[str] = None

    official_website: Optional[str] = None
    admissions_website: Optional[str] = None
    financial_aid_website: Optional[str] = None
    international_admissions_website: Optional[str] = None

    accreditation_status: Optional[str] = None
    accrediting_body: Optional[str] = None
    accreditation_details: Dict[str, Any] = Field(default_factory=dict)

    total_enrollment: Optional[int] = None
    undergraduate_enrollment: Optional[int] = None
    graduate_enrollment: Optional[int] = None
    acceptance_rate: Optional[float] = None
    student_faculty_ratio: Optional[str] = None

    sat_math_25: Optional[int] = None
    sat_math_75: Optional[int] = None
    sat_ebrw_25: Optional[int] = None
    sat_ebrw_75: Optional[int] = None
    act_composite_25: Optional[int] = None
    act_composite_75: Optional[int] = None
    gpa_25: Optional[float] = None
    gpa_75: Optional[float] = None

    tuition_in_state: Optional[float] = None
    tuition_out_of_state: Optional[float] = None
    currency: str = "USD"

    ipeds_unit_id: Optional[str] = None
    ope_id: Optional[str] = None
    ucas_code: Optional[str] = None
    ror_id: Optional[str] = None
    openalex_id: Optional[str] = None
    external_ids: Dict[str, Any] = Field(default_factory=dict)

    parent_ror_id: Optional[str] = None
    parent_ipeds_unit_id: Optional[str] = None
    campus_name: Optional[str] = None
    is_main_campus: bool = True

    accepts_transfer: bool = True
    accepts_first_year: bool = True
    accepts_international: bool = True

    # Provenance metadata
    source_type: str = "api"
    source_name: str = "Unknown"
    source_url: Optional[str] = None
    collection_method: str = "api"
    confidence_level: str = "verified"
    academic_year: Optional[str] = None


class NormalizedCost(BaseModel):
    academic_year: str
    student_type: str  # in_state, out_of_state, international, domestic
    degree_level: str = "bachelors"
    tuition: Optional[float] = None
    mandatory_fees: Optional[float] = None
    room_board: Optional[float] = None
    books_supplies: Optional[float] = None
    personal_expenses: Optional[float] = None
    transportation: Optional[float] = None
    health_insurance: Optional[float] = None
    total_estimated_cost: Optional[float] = None
    currency: str = "USD"
    source_url: Optional[str] = None
    verification_status: str = "verified"


class NormalizedProgram(BaseModel):
    program_name: str
    degree_level: str = "bachelors"
    degree_type: Optional[str] = None
    department: Optional[str] = None
    cip_code: Optional[str] = None
    isced_code: Optional[str] = None
    duration_years: Optional[float] = None
    credit_requirements: Optional[int] = None
    language_of_instruction: str = "en"
    delivery_mode: str = "in_person"
    program_url: Optional[str] = None
    accepts_transfer_students: Optional[bool] = None
    academic_year: Optional[str] = None
    source_url: Optional[str] = None
    verification_status: str = "verified"


class BaseInstitutionConnector(ABC):
    source_name: str = "base"
    source_type: str = "api"
    license_type: str = "Unknown"

    @abstractmethod
    def fetch_institutions(self, **kwargs) -> List[NormalizedInstitution]:
        """Retrieve and normalize institutional records from the permitted source."""
        pass


def compute_canonical_hash(payload: Dict[str, Any]) -> str:
    """Computes a deterministic SHA-256 hash over normalized provenance-tracked fields."""
    serialized = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_completeness_score(inst: Institution) -> float:
    """Computes normalized 0.00-1.00 completeness score across key intelligence fields."""
    checks = [
        bool(inst.official_name),
        bool(inst.country_code),
        bool(inst.city),
        bool(inst.institution_type),
        bool(inst.control_type),
        bool(inst.official_website),
        bool(inst.admissions_website),
        bool(inst.ipeds_unit_id or inst.ror_id or inst.openalex_id or inst.ucas_code or inst.external_ids),
        inst.tuition_in_state is not None or inst.tuition_out_of_state is not None,
        inst.total_enrollment is not None or inst.acceptance_rate is not None,
    ]
    return round(sum(1 for c in checks if c) / len(checks), 2)


class IngestionPipeline:
    """Executes connectors inside tracked IngestionRuns with non-destructive DataProvenance."""

    PROVENANCE_FIELDS = [
        "official_name",
        "country_code",
        "state_province",
        "city",
        "institution_type",
        "control_type",
        "official_website",
        "admissions_website",
        "tuition_in_state",
        "tuition_out_of_state",
        "total_enrollment",
        "acceptance_rate",
        "ipeds_unit_id",
        "ror_id",
        "openalex_id",
    ]

    def __init__(self, db: Session):
        self.db = db

    def run_connector(self, connector: BaseInstitutionConnector, **fetch_kwargs) -> IngestionRun:
        run = IngestionRun(
            source_name=connector.source_name,
            source_type=connector.source_type,
            license_type=connector.license_type,
            status="running",
            metadata_json={"kwargs": {k: str(v) for k, v in fetch_kwargs.items()}},
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            records = connector.fetch_institutions(**fetch_kwargs)
            run.records_fetched = len(records)

            created, updated, flagged = self.ingest_institutions(records, run)
            run.records_created = created
            run.records_updated = updated
            run.records_flagged = flagged
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(run)
            return run
        except Exception as exc:
            self.db.rollback()
            run_db = self.db.query(IngestionRun).filter(IngestionRun.id == run.id).first()
            if run_db:
                run_db.status = "failed"
                run_db.error_summary = str(exc)[:2000]
                run_db.completed_at = datetime.now(timezone.utc)
                self.db.commit()
            raise

    def _find_existing_institution(self, item: NormalizedInstitution) -> Optional[Institution]:
        if item.ipeds_unit_id:
            found = self.db.query(Institution).filter(Institution.ipeds_unit_id == item.ipeds_unit_id).first()
            if found:
                return found
        if item.ror_id:
            found = self.db.query(Institution).filter(Institution.ror_id == item.ror_id).first()
            if found:
                return found
        if item.openalex_id:
            found = self.db.query(Institution).filter(Institution.openalex_id == item.openalex_id).first()
            if found:
                return found

        # Canonical name + country fallback (preserves seeded rows without duplicating)
        name_lower = item.official_name.strip().lower()
        cc = item.country_code.strip().upper()[:2]
        query = self.db.query(Institution).filter(
            func.lower(Institution.official_name) == name_lower,
            Institution.country_code == cc,
        )
        if item.campus_name:
            found = query.filter(func.lower(Institution.campus_name) == item.campus_name.strip().lower()).first()
            if found:
                return found
        return query.first()

    def _snapshot_dict(self, inst: Institution) -> Dict[str, Any]:
        snap: Dict[str, Any] = {}
        for f in self.PROVENANCE_FIELDS:
            val = getattr(inst, f, None)
            if isinstance(val, Decimal):
                val = float(val)
            snap[f] = val
        return snap

    def ingest_institutions(
        self, items: List[NormalizedInstitution], run: Optional[IngestionRun] = None
    ) -> Tuple[int, int, int]:
        created_count = 0
        updated_count = 0
        flagged_count = 0
        now = datetime.now(timezone.utc)

        # Defer parent campus linking until all records in batch are flushed
        pending_parents: List[Tuple[Institution, NormalizedInstitution]] = []

        for item in items:
            ensure_country_exists(self.db, item.country_code, item.country_name)
            inst_type = item.institution_type if item.institution_type in ALLOWED_INSTITUTION_TYPES else "other"
            control_type = item.control_type if item.control_type in ALLOWED_CONTROL_TYPES else None

            existing = self._find_existing_institution(item)

            if not existing:
                inst = Institution(
                    official_name=item.official_name.strip(),
                    alternative_names=list(dict.fromkeys(item.alternative_names)),
                    abbreviation=item.abbreviation,
                    campus_name=item.campus_name,
                    is_main_campus=item.is_main_campus,
                    country_code=item.country_code.strip().upper()[:2],
                    state_province=item.state_province,
                    city=item.city,
                    postal_code=item.postal_code,
                    latitude=item.latitude,
                    longitude=item.longitude,
                    institution_type=inst_type,
                    control_type=control_type,
                    carnegie_classification=item.carnegie_classification,
                    official_website=item.official_website,
                    admissions_website=item.admissions_website,
                    financial_aid_website=item.financial_aid_website,
                    international_admissions_website=item.international_admissions_website,
                    accreditation_status=item.accreditation_status,
                    accrediting_body=item.accrediting_body,
                    accreditation_details=item.accreditation_details,
                    total_enrollment=item.total_enrollment,
                    undergraduate_enrollment=item.undergraduate_enrollment,
                    graduate_enrollment=item.graduate_enrollment,
                    acceptance_rate=item.acceptance_rate,
                    student_faculty_ratio=item.student_faculty_ratio,
                    sat_math_25=item.sat_math_25,
                    sat_math_75=item.sat_math_75,
                    sat_ebrw_25=item.sat_ebrw_25,
                    sat_ebrw_75=item.sat_ebrw_75,
                    act_composite_25=item.act_composite_25,
                    act_composite_75=item.act_composite_75,
                    gpa_25=item.gpa_25,
                    gpa_75=item.gpa_75,
                    tuition_in_state=item.tuition_in_state,
                    tuition_out_of_state=item.tuition_out_of_state,
                    currency=(item.currency or "USD").upper()[:3],
                    ipeds_unit_id=item.ipeds_unit_id,
                    ope_id=item.ope_id,
                    ucas_code=item.ucas_code,
                    ror_id=item.ror_id,
                    openalex_id=item.openalex_id,
                    external_ids=item.external_ids or {},
                    accepts_transfer=item.accepts_transfer,
                    accepts_first_year=item.accepts_first_year,
                    accepts_international=item.accepts_international,
                    is_verified=(item.confidence_level == "verified"),
                    is_published=True,
                    last_verified_at=now if item.confidence_level == "verified" else None,
                )
                inst.data_completeness_score = compute_completeness_score(inst)
                self.db.add(inst)
                self.db.flush()

                snapshot = self._snapshot_dict(inst)
                prov = DataProvenance(
                    entity_type="institution",
                    entity_id=inst.id,
                    field_name=None,
                    source_type=item.source_type,
                    source_url=item.source_url,
                    source_name=item.source_name,
                    collection_method=item.collection_method,
                    retrieved_at=now,
                    verified_at=now if item.confidence_level == "verified" else None,
                    academic_year=item.academic_year,
                    confidence_level=item.confidence_level,
                    data_hash=compute_canonical_hash(snapshot),
                    previous_value=None,
                    is_current=True,
                    ingestion_run_id=run.id if run else None,
                )
                self.db.add(prov)
                created_count += 1
                flagged_count += self._evaluate_quality_flags(inst)
                if item.parent_ror_id or item.parent_ipeds_unit_id:
                    pending_parents.append((inst, item))
            else:
                # Track previous snapshot BEFORE non-destructive merge
                prev_snapshot = self._snapshot_dict(existing)
                prev_hash = compute_canonical_hash(prev_snapshot)

                changed_fields: Dict[str, Any] = {}

                # Merge alternative names and external_ids cleanly
                if item.alternative_names:
                    merged_alts = list(dict.fromkeys((existing.alternative_names or []) + item.alternative_names))
                    if merged_alts != (existing.alternative_names or []):
                        existing.alternative_names = merged_alts
                        changed_fields["alternative_names"] = prev_snapshot.get("alternative_names")

                if item.external_ids:
                    merged_ext = {**(existing.external_ids or {}), **item.external_ids}
                    if merged_ext != (existing.external_ids or {}):
                        existing.external_ids = merged_ext
                        changed_fields["external_ids"] = True

                # Non-null enrichments only (never wipe curated fields with None)
                enrich_attrs = [
                    "abbreviation", "campus_name", "state_province", "city", "postal_code",
                    "latitude", "longitude", "control_type", "carnegie_classification",
                    "official_website", "admissions_website", "financial_aid_website",
                    "international_admissions_website", "accreditation_status", "accrediting_body",
                    "total_enrollment", "undergraduate_enrollment", "graduate_enrollment",
                    "acceptance_rate", "student_faculty_ratio",
                    "sat_math_25", "sat_math_75", "sat_ebrw_25", "sat_ebrw_75",
                    "act_composite_25", "act_composite_75", "gpa_25", "gpa_75",
                    "tuition_in_state", "tuition_out_of_state",
                    "ipeds_unit_id", "ope_id", "ucas_code", "ror_id", "openalex_id",
                ]
                for attr in enrich_attrs:
                    new_val = getattr(item, attr, None)
                    if new_val is not None:
                        old_val = getattr(existing, attr, None)
                        old_cmp = float(old_val) if isinstance(old_val, Decimal) else old_val
                        if attr in ("latitude", "longitude") and old_cmp is not None:
                            if round(float(old_cmp), 6) == round(float(new_val), 6):
                                continue
                        elif isinstance(old_cmp, float) or isinstance(new_val, float):
                            if old_cmp is not None and round(float(old_cmp), 2) == round(float(new_val), 2):
                                continue
                        if old_cmp != new_val:
                            changed_fields[attr] = old_cmp
                            setattr(existing, attr, new_val)

                # Update institution_type if existing was generic and new is specific
                if inst_type != "other" and existing.institution_type in ("other", None):
                    changed_fields["institution_type"] = existing.institution_type
                    existing.institution_type = inst_type

                existing.data_completeness_score = compute_completeness_score(existing)
                if item.confidence_level == "verified":
                    existing.is_verified = True
                    existing.last_verified_at = now

                new_snapshot = self._snapshot_dict(existing)
                new_hash = compute_canonical_hash(new_snapshot)

                if new_hash != prev_hash or changed_fields:
                    # Mark previous current provenance snapshot non-current
                    self.db.query(DataProvenance).filter(
                        DataProvenance.entity_type == "institution",
                        DataProvenance.entity_id == existing.id,
                        DataProvenance.field_name.is_(None),
                        DataProvenance.is_current == True,
                    ).update({"is_current": False})

                    prov = DataProvenance(
                        entity_type="institution",
                        entity_id=existing.id,
                        field_name=None,
                        source_type=item.source_type,
                        source_url=item.source_url,
                        source_name=item.source_name,
                        collection_method=item.collection_method,
                        retrieved_at=now,
                        verified_at=now if item.confidence_level == "verified" else None,
                        academic_year=item.academic_year,
                        confidence_level=item.confidence_level,
                        data_hash=new_hash,
                        previous_value=changed_fields or prev_snapshot,
                        is_current=True,
                        ingestion_run_id=run.id if run else None,
                    )
                    self.db.add(prov)
                    updated_count += 1

                if item.parent_ror_id or item.parent_ipeds_unit_id:
                    pending_parents.append((existing, item))

        # Resolve multi-campus parent FKs
        for inst, item in pending_parents:
            parent = None
            if item.parent_ipeds_unit_id:
                parent = self.db.query(Institution).filter(Institution.ipeds_unit_id == item.parent_ipeds_unit_id).first()
            if not parent and item.parent_ror_id:
                parent = self.db.query(Institution).filter(Institution.ror_id == item.parent_ror_id).first()
            if parent and parent.id != inst.id:
                inst.parent_institution_id = parent.id

        self.db.commit()
        return created_count, updated_count, flagged_count

    def _evaluate_quality_flags(self, inst: Institution) -> int:
        flags = 0
        if not inst.official_website:
            existing_flag = self.db.query(DataQualityFlag).filter(
                DataQualityFlag.entity_type == "institution",
                DataQualityFlag.entity_id == inst.id,
                DataQualityFlag.flag_type == "missing_required_field",
                DataQualityFlag.resolved == False,
            ).first()
            if not existing_flag:
                self.db.add(DataQualityFlag(
                    entity_type="institution",
                    entity_id=inst.id,
                    flag_type="missing_required_field",
                    severity="warning",
                    description="Institution record is missing an official_website URL.",
                    auto_detected=True,
                ))
                flags += 1
        return flags
