"""
Core Ingestion Pipeline & Provenance Engine.
Implements idempotent upserts, SHA-256 diff detection, authority/year guards
(never overwriting newer/verified data with older/less reliable data),
non-destructive historical provenance logging, completeness scoring,
structured validation reports, and automated quality flags.
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
from app.ingestion.dedup import normalize_inst_name


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

SOURCE_AUTHORITY: Dict[str, int] = {
    "official_website": 100,
    "ipeds": 90,
    "government_db": 85,
    "college_scorecard": 80,
    "manual_entry": 75,
    "api": 60,
    "openalex_ror": 50,
}


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
    net_price_calculator_url: Optional[str] = None
    application_portal_url: Optional[str] = None

    accreditation_status: Optional[str] = None
    accrediting_body: Optional[str] = None
    accreditation_details: Dict[str, Any] = Field(default_factory=dict)
    open_admissions: Optional[bool] = None
    calendar_system: Optional[str] = None
    undergrad_application_fee: Optional[float] = None

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

    completion_rate_4yr: Optional[float] = None
    completion_rate_less_4yr: Optional[float] = None
    retention_rate: Optional[float] = None
    median_earnings_10yr: Optional[float] = None
    median_debt: Optional[float] = None
    pct_international: Optional[float] = None
    pct_pell: Optional[float] = None
    student_demographics: Dict[str, Any] = Field(default_factory=dict)

    tuition_in_state: Optional[float] = None
    tuition_out_of_state: Optional[float] = None
    avg_net_price: Optional[float] = None
    cost_of_attendance: Optional[float] = None
    currency: str = "USD"

    ipeds_unit_id: Optional[str] = None
    ope_id: Optional[str] = None
    ope6_id: Optional[str] = None
    ucas_code: Optional[str] = None
    ror_id: Optional[str] = None
    openalex_id: Optional[str] = None
    external_ids: Dict[str, Any] = Field(default_factory=dict)

    parent_ror_id: Optional[str] = None
    parent_ipeds_unit_id: Optional[str] = None
    parent_ope6_id: Optional[str] = None
    campus_name: Optional[str] = None
    is_main_campus: bool = True

    accepts_transfer: bool = True
    accepts_first_year: bool = True
    accepts_international: bool = True

    costs: List[NormalizedCost] = Field(default_factory=list)
    programs: List[NormalizedProgram] = Field(default_factory=list)

    # Provenance metadata
    source_type: str = "api"
    source_name: str = "Unknown"
    source_url: Optional[str] = None
    collection_method: str = "api"
    confidence_level: str = "verified"
    academic_year: Optional[str] = None


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
        bool(inst.admissions_website or inst.application_portal_url),
        bool(inst.ipeds_unit_id or inst.ror_id or inst.openalex_id or inst.ucas_code or inst.external_ids),
        inst.tuition_in_state is not None or inst.tuition_out_of_state is not None,
        inst.total_enrollment is not None or inst.acceptance_rate is not None,
    ]
    return round(sum(1 for c in checks if c) / len(checks), 2)


def _parse_year_start(year_str: Optional[str]) -> int:
    if not year_str:
        return 0
    try:
        return int(str(year_str).strip()[:4])
    except Exception:
        return 0


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
        "application_portal_url",
        "tuition_in_state",
        "tuition_out_of_state",
        "avg_net_price",
        "cost_of_attendance",
        "total_enrollment",
        "acceptance_rate",
        "completion_rate_4yr",
        "ipeds_unit_id",
        "ope_id",
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

            stats = self.ingest_institutions(records, run)
            run.records_created = stats["created"]
            run.records_updated = stats["updated"]
            run.records_flagged = stats["flagged"]
            run.metadata_json = {
                **(run.metadata_json or {}),
                "validation_report": stats,
            }
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

    def _build_lookup_caches(self) -> Dict[str, Dict[Any, Institution]]:
        all_insts = self.db.query(Institution).all()
        by_ipeds: Dict[str, Institution] = {}
        by_ror: Dict[str, Institution] = {}
        by_openalex: Dict[str, Institution] = {}
        by_ope: Dict[str, Institution] = {}
        by_name_cc: Dict[Tuple[str, str], Institution] = {}
        main_by_ope6: Dict[str, Institution] = {}

        for inst in all_insts:
            if inst.ipeds_unit_id:
                by_ipeds[inst.ipeds_unit_id] = inst
            if inst.ror_id:
                by_ror[inst.ror_id] = inst
            if inst.openalex_id:
                by_openalex[inst.openalex_id] = inst
            if inst.ope_id:
                by_ope[inst.ope_id] = inst
            if inst.ope6_id and inst.is_main_campus:
                main_by_ope6[inst.ope6_id] = inst
            key = (normalize_inst_name(inst.official_name), (inst.country_code or "US").upper())
            if key not in by_name_cc:
                by_name_cc[key] = inst

        return {
            "ipeds": by_ipeds,
            "ror": by_ror,
            "openalex": by_openalex,
            "ope": by_ope,
            "name_cc": by_name_cc,
            "main_ope6": main_by_ope6,
        }

    def _find_cached(self, item: NormalizedInstitution, caches: Dict[str, Dict[Any, Institution]]) -> Optional[Institution]:
        if item.ipeds_unit_id and item.ipeds_unit_id in caches["ipeds"]:
            return caches["ipeds"][item.ipeds_unit_id]
        if item.ror_id and item.ror_id in caches["ror"]:
            return caches["ror"][item.ror_id]
        if item.openalex_id and item.openalex_id in caches["openalex"]:
            return caches["openalex"][item.openalex_id]
        key = (normalize_inst_name(item.official_name), item.country_code.strip().upper()[:2])
        if key in caches["name_cc"]:
            candidate = caches["name_cc"][key]
            # Avoid wrongly merging two distinct campuses that share a name but have different IPEDS UNITIDs
            if not (item.ipeds_unit_id and candidate.ipeds_unit_id and item.ipeds_unit_id != candidate.ipeds_unit_id):
                return candidate
        return None

    def _register_in_cache(self, inst: Institution, caches: Dict[str, Dict[Any, Institution]]):
        if inst.ipeds_unit_id:
            caches["ipeds"][inst.ipeds_unit_id] = inst
        if inst.ror_id:
            caches["ror"][inst.ror_id] = inst
        if inst.openalex_id:
            caches["openalex"][inst.openalex_id] = inst
        if inst.ope6_id and inst.is_main_campus:
            caches["main_ope6"][inst.ope6_id] = inst
        caches["name_cc"][(normalize_inst_name(inst.official_name), (inst.country_code or "US").upper())] = inst

    def _snapshot_dict(self, inst: Institution) -> Dict[str, Any]:
        snap: Dict[str, Any] = {}
        for f in self.PROVENANCE_FIELDS:
            val = getattr(inst, f, None)
            if isinstance(val, Decimal):
                val = float(val)
            snap[f] = val
        return snap

    def _values_equal(self, attr: str, old_cmp: Any, new_val: Any) -> bool:
        if attr in ("latitude", "longitude") and old_cmp is not None and new_val is not None:
            return round(float(old_cmp), 6) == round(float(new_val), 6)
        if isinstance(old_cmp, float) or isinstance(new_val, float):
            if old_cmp is not None and new_val is not None:
                return round(float(old_cmp), 2) == round(float(new_val), 2)
        return old_cmp == new_val

    def _upsert_costs_and_programs(self, inst: Institution, item: NormalizedInstitution) -> Tuple[int, int]:
        costs_added = 0
        progs_added = 0
        now = datetime.now(timezone.utc)

        if item.costs:
            existing_costs = {
                (c.academic_year, c.student_type, c.degree_level): c
                for c in self.db.query(InstitutionCost).filter(InstitutionCost.institution_id == inst.id).all()
            }
            for c_in in item.costs:
                key = (c_in.academic_year, c_in.student_type, c_in.degree_level)
                if key in existing_costs:
                    c_db = existing_costs[key]
                    changed = False
                    for attr in ("tuition", "mandatory_fees", "room_board", "books_supplies", "personal_expenses", "total_estimated_cost"):
                        new_v = getattr(c_in, attr)
                        old_v = float(getattr(c_db, attr)) if getattr(c_db, attr) is not None else None
                        if new_v is not None and old_v != round(float(new_v), 2):
                            setattr(c_db, attr, new_v)
                            changed = True
                    if changed:
                        c_db.retrieved_at = now
                else:
                    # Mark older years non-current if this year is newer
                    self.db.query(InstitutionCost).filter(
                        InstitutionCost.institution_id == inst.id,
                        InstitutionCost.student_type == c_in.student_type,
                        InstitutionCost.academic_year < c_in.academic_year,
                    ).update({"is_current": False})
                    self.db.add(InstitutionCost(
                        institution_id=inst.id,
                        academic_year=c_in.academic_year,
                        student_type=c_in.student_type,
                        degree_level=c_in.degree_level,
                        tuition=c_in.tuition,
                        mandatory_fees=c_in.mandatory_fees,
                        room_board=c_in.room_board,
                        books_supplies=c_in.books_supplies,
                        personal_expenses=c_in.personal_expenses,
                        transportation=c_in.transportation,
                        health_insurance=c_in.health_insurance,
                        total_estimated_cost=c_in.total_estimated_cost,
                        currency=c_in.currency,
                        is_current=True,
                        source_url=c_in.source_url,
                        retrieved_at=now,
                        verified_at=now if c_in.verification_status == "verified" else None,
                        verification_status=c_in.verification_status,
                    ))
                    costs_added += 1

        if item.programs:
            existing_progs = {
                (p.cip_code or p.program_name.lower(), p.degree_level): p
                for p in self.db.query(AcademicProgram).filter(AcademicProgram.institution_id == inst.id).all()
            }
            for p_in in item.programs:
                key = (p_in.cip_code or p_in.program_name.lower(), p_in.degree_level)
                if key not in existing_progs:
                    self.db.add(AcademicProgram(
                        institution_id=inst.id,
                        program_name=p_in.program_name,
                        degree_level=p_in.degree_level,
                        degree_type=p_in.degree_type,
                        department=p_in.department,
                        cip_code=p_in.cip_code,
                        isced_code=p_in.isced_code,
                        duration_years=p_in.duration_years,
                        credit_requirements=p_in.credit_requirements,
                        language_of_instruction=p_in.language_of_instruction,
                        delivery_mode=p_in.delivery_mode,
                        program_url=p_in.program_url,
                        accepts_transfer_students=p_in.accepts_transfer_students,
                        academic_year=p_in.academic_year,
                        source_url=p_in.source_url,
                        verified_at=now,
                        verification_status=p_in.verification_status,
                    ))
                    progs_added += 1

        return costs_added, progs_added

    def ingest_institutions(
        self, items: List[NormalizedInstitution], run: Optional[IngestionRun] = None
    ) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "created": 0,
            "updated": 0,
            "flagged": 0,
            "duplicates_merged": 0,
            "skipped_stale": 0,
            "conflicts_detected": 0,
            "missing_website_count": 0,
            "missing_tuition_count": 0,
            "missing_enrollment_count": 0,
            "cost_records_upserted": 0,
            "program_records_upserted": 0,
        }
        now = datetime.now(timezone.utc)
        caches = self._build_lookup_caches()
        pending_parents: List[Tuple[Institution, NormalizedInstitution]] = []
        seen_batch_keys: set = set()

        for idx, item in enumerate(items):
            ensure_country_exists(self.db, item.country_code, item.country_name)
            inst_type = item.institution_type if item.institution_type in ALLOWED_INSTITUTION_TYPES else "other"
            control_type = item.control_type if item.control_type in ALLOWED_CONTROL_TYPES else None

            if not item.official_website:
                stats["missing_website_count"] += 1
            if item.tuition_in_state is None and item.tuition_out_of_state is None:
                stats["missing_tuition_count"] += 1
            if item.total_enrollment is None and item.undergraduate_enrollment is None:
                stats["missing_enrollment_count"] += 1

            batch_key = item.ipeds_unit_id or item.ror_id or (item.official_name.strip().lower(), item.country_code.upper())
            if batch_key in seen_batch_keys:
                stats["duplicates_merged"] += 1
            seen_batch_keys.add(batch_key)

            existing = self._find_cached(item, caches)
            incoming_auth = SOURCE_AUTHORITY.get(item.source_type, 50)
            incoming_year = _parse_year_start(item.academic_year)

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
                    net_price_calculator_url=item.net_price_calculator_url,
                    application_portal_url=item.application_portal_url,
                    accreditation_status=item.accreditation_status,
                    accrediting_body=item.accrediting_body,
                    accreditation_details=item.accreditation_details,
                    open_admissions=item.open_admissions,
                    calendar_system=item.calendar_system,
                    undergrad_application_fee=item.undergrad_application_fee,
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
                    completion_rate_4yr=item.completion_rate_4yr,
                    completion_rate_less_4yr=item.completion_rate_less_4yr,
                    retention_rate=item.retention_rate,
                    median_earnings_10yr=item.median_earnings_10yr,
                    median_debt=item.median_debt,
                    pct_international=item.pct_international,
                    pct_pell=item.pct_pell,
                    student_demographics=item.student_demographics or {},
                    tuition_in_state=item.tuition_in_state,
                    tuition_out_of_state=item.tuition_out_of_state,
                    avg_net_price=item.avg_net_price,
                    cost_of_attendance=item.cost_of_attendance,
                    currency=(item.currency or "USD").upper()[:3],
                    ipeds_unit_id=item.ipeds_unit_id,
                    ope_id=item.ope_id,
                    ope6_id=item.ope6_id,
                    ucas_code=item.ucas_code,
                    ror_id=item.ror_id,
                    openalex_id=item.openalex_id,
                    external_ids=item.external_ids or {},
                    accepts_transfer=item.accepts_transfer,
                    accepts_first_year=item.accepts_first_year,
                    accepts_international=item.accepts_international,
                    is_verified=(item.confidence_level == "verified"),
                    is_published=True,
                    data_reporting_year=item.academic_year,
                    primary_source=item.source_type,
                    last_verified_at=now if item.confidence_level == "verified" else None,
                )
                inst.data_completeness_score = compute_completeness_score(inst)
                self.db.add(inst)
                self.db.flush()
                self._register_in_cache(inst, caches)

                c_added, p_added = self._upsert_costs_and_programs(inst, item)
                stats["cost_records_upserted"] += c_added
                stats["program_records_upserted"] += p_added

                snapshot = self._snapshot_dict(inst)
                self.db.add(DataProvenance(
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
                ))
                stats["created"] += 1
                stats["flagged"] += self._evaluate_quality_flags(inst)
                if item.parent_ror_id or item.parent_ipeds_unit_id or item.parent_ope6_id:
                    pending_parents.append((inst, item))
            else:
                existing_year = _parse_year_start(existing.data_reporting_year)
                existing_auth = SOURCE_AUTHORITY.get(existing.primary_source or "", 40)

                # Guard: never overwrite newer verified record with older record
                if existing.is_verified and existing_year > 0 and incoming_year > 0 and incoming_year < existing_year:
                    stats["skipped_stale"] += 1
                    continue

                prev_snapshot = self._snapshot_dict(existing)
                prev_hash = compute_canonical_hash(prev_snapshot)
                changed_fields: Dict[str, Any] = {}

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

                if item.student_demographics:
                    merged_demo = dict(existing.student_demographics or {})
                    demo_changed = False
                    for dk, dv in item.student_demographics.items():
                        if dk not in merged_demo:
                            merged_demo[dk] = dv
                            demo_changed = True
                        elif incoming_auth >= existing_auth and round(float(merged_demo[dk]), 0) != round(float(dv), 0):
                            merged_demo[dk] = dv
                            demo_changed = True
                    if demo_changed:
                        existing.student_demographics = merged_demo
                        changed_fields["student_demographics"] = True

                # Authority-guarded attribute enrichment
                enrich_attrs = [
                    "abbreviation", "campus_name", "state_province", "city", "postal_code",
                    "latitude", "longitude", "control_type", "carnegie_classification",
                    "official_website", "admissions_website", "financial_aid_website",
                    "international_admissions_website", "net_price_calculator_url", "application_portal_url",
                    "accreditation_status", "accrediting_body", "open_admissions", "calendar_system",
                    "undergrad_application_fee", "total_enrollment", "undergraduate_enrollment",
                    "graduate_enrollment", "acceptance_rate", "student_faculty_ratio",
                    "sat_math_25", "sat_math_75", "sat_ebrw_25", "sat_ebrw_75",
                    "act_composite_25", "act_composite_75", "gpa_25", "gpa_75",
                    "completion_rate_4yr", "completion_rate_less_4yr", "retention_rate",
                    "median_earnings_10yr", "median_debt", "pct_international", "pct_pell",
                    "tuition_in_state", "tuition_out_of_state", "avg_net_price", "cost_of_attendance",
                    "ipeds_unit_id", "ope_id", "ope6_id", "ucas_code", "ror_id", "openalex_id",
                ]
                for attr in enrich_attrs:
                    new_val = getattr(item, attr, None)
                    if new_val is None:
                        continue
                    old_val = getattr(existing, attr, None)
                    old_cmp = float(old_val) if isinstance(old_val, Decimal) else old_val
                    if self._values_equal(attr, old_cmp, new_val):
                        continue

                    # If existing non-null value comes from strictly higher-authority source for same/newer year, preserve it & log conflict if tuition diverges >25%
                    if old_cmp is not None and existing.is_verified and existing_year >= incoming_year and existing_auth > incoming_auth:
                        if attr in ("tuition_in_state", "tuition_out_of_state") and float(old_cmp) > 0:
                            if abs(float(new_val) - float(old_cmp)) / float(old_cmp) > 0.25:
                                stats["conflicts_detected"] += 1
                                msg = f"{attr} conflict: kept {existing.primary_source}={old_cmp} over {item.source_type}={new_val}"
                                has_flag = self.db.query(DataQualityFlag).filter(
                                    DataQualityFlag.entity_id == existing.id,
                                    DataQualityFlag.flag_type == "conflicting_data",
                                    DataQualityFlag.description == msg,
                                ).first()
                                if not has_flag:
                                    self.db.add(DataQualityFlag(
                                        entity_type="institution",
                                        entity_id=existing.id,
                                        flag_type="conflicting_data",
                                        severity="info",
                                        description=msg,
                                        auto_detected=True,
                                    ))
                        continue

                    changed_fields[attr] = old_cmp
                    setattr(existing, attr, new_val)

                # Update institution_type when higher authority provides specific classification
                if inst_type != "other" and (
                    existing.institution_type in ("other", None)
                    or incoming_auth > existing_auth
                ) and existing.institution_type != inst_type:
                    changed_fields["institution_type"] = existing.institution_type
                    existing.institution_type = inst_type

                if not item.is_main_campus and existing.is_main_campus:
                    existing.is_main_campus = False
                    changed_fields["is_main_campus"] = True

                c_added, p_added = self._upsert_costs_and_programs(existing, item)
                stats["cost_records_upserted"] += c_added
                stats["program_records_upserted"] += p_added

                existing.data_completeness_score = compute_completeness_score(existing)
                if item.confidence_level == "verified":
                    existing.is_verified = True
                    existing.last_verified_at = now
                if incoming_year >= existing_year and incoming_auth >= existing_auth:
                    if item.academic_year:
                        existing.data_reporting_year = item.academic_year
                    existing.primary_source = item.source_type

                self._register_in_cache(existing, caches)

                # Reverification trigger: if institutional website or portal URL changed, flag verified routes
                for url_field in ("official_website", "admissions_website", "application_portal_url"):
                    if url_field in changed_fields:
                        from app.services.routing_health import flag_routes_for_institution_website_change

                        flag_routes_for_institution_website_change(
                            db=self.db,
                            institution_id=existing.id,
                            old_website=changed_fields[url_field],
                            new_website=getattr(existing, url_field),
                            field_name=url_field,
                            actor_role="system",
                            commit=False,
                        )

                new_snapshot = self._snapshot_dict(existing)
                new_hash = compute_canonical_hash(new_snapshot)

                if new_hash != prev_hash or changed_fields:
                    self.db.query(DataProvenance).filter(
                        DataProvenance.entity_type == "institution",
                        DataProvenance.entity_id == existing.id,
                        DataProvenance.field_name.is_(None),
                        DataProvenance.is_current == True,
                    ).update({"is_current": False})

                    self.db.add(DataProvenance(
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
                    ))
                    stats["updated"] += 1

                if item.parent_ror_id or item.parent_ipeds_unit_id or item.parent_ope6_id:
                    pending_parents.append((existing, item))

            if (idx + 1) % 500 == 0:
                self.db.flush()

        # Resolve multi-campus parent FKs
        for inst, item in pending_parents:
            parent = None
            if item.parent_ipeds_unit_id and item.parent_ipeds_unit_id in caches["ipeds"]:
                parent = caches["ipeds"][item.parent_ipeds_unit_id]
            elif item.parent_ror_id and item.parent_ror_id in caches["ror"]:
                parent = caches["ror"][item.parent_ror_id]
            elif item.parent_ope6_id and item.parent_ope6_id in caches["main_ope6"]:
                parent = caches["main_ope6"][item.parent_ope6_id]
            if parent and parent.id != inst.id:
                inst.parent_institution_id = parent.id

        self.db.commit()
        return stats

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
