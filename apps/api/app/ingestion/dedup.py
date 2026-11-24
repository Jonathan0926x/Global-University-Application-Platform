"""
Institutional Duplicate Detection & Canonical Merging Utility.
Detects duplicate US/global institutional records caused by punctuation variants
(e.g., 'University of California, Berkeley' vs 'University of California-Berkeley')
or ROR vs IPEDS main-campus naming ('University of Washington' vs 'University of Washington-Seattle Campus')
by matching normalized names and canonical website domains.
"""

import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from app.models.institution import Institution, AcademicProgram, InstitutionCost
from app.models.application import Application
from app.models.enrollment import EnrollmentRecord
from app.models.provenance import DataProvenance, DataQualityFlag


def normalize_inst_name(name: str) -> str:
    return re.sub(r"[-,.'\s]+", " ", (name or "").lower()).strip()


def extract_root_domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host or None
    except Exception:
        return None


def merge_duplicate_pair(db: Session, canonical: Institution, duplicate: Institution) -> None:
    """
    Merges `duplicate` into `canonical`, preserving external identifiers (ROR, OpenAlex, alt names),
    re-pointing foreign keys (`applications`, `enrollment_records`, `campuses`, `costs`, `programs`,
    `data_provenance`, `data_quality_flags`), and deleting `duplicate`.
    """
    # Preserve ROR / OpenAlex / external IDs / alt names on canonical
    if duplicate.ror_id and not canonical.ror_id:
        ror = duplicate.ror_id
        duplicate.ror_id = None
        db.flush()
        canonical.ror_id = ror
    if duplicate.openalex_id and not canonical.openalex_id:
        oa = duplicate.openalex_id
        duplicate.openalex_id = None
        db.flush()
        canonical.openalex_id = oa

    merged_alts = list(dict.fromkeys(
        (canonical.alternative_names or [])
        + (duplicate.alternative_names or [])
        + ([duplicate.official_name] if duplicate.official_name != canonical.official_name else [])
    ))
    canonical.alternative_names = merged_alts

    if duplicate.external_ids:
        canonical.external_ids = {**(duplicate.external_ids or {}), **(canonical.external_ids or {})}

    # Re-point FKs safely
    db.query(Application).filter(Application.institution_id == duplicate.id).update({"institution_id": canonical.id})
    db.query(EnrollmentRecord).filter(EnrollmentRecord.institution_id == duplicate.id).update({"institution_id": canonical.id})
    db.query(Institution).filter(Institution.parent_institution_id == duplicate.id).update({"parent_institution_id": canonical.id})
    db.query(DataProvenance).filter(
        DataProvenance.entity_type == "institution",
        DataProvenance.entity_id == duplicate.id,
    ).update({"entity_id": canonical.id, "is_current": False})
    db.query(DataQualityFlag).filter(
        DataQualityFlag.entity_type == "institution",
        DataQualityFlag.entity_id == duplicate.id,
    ).delete()

    # Delete costs/programs on duplicate only if canonical already has them, else move
    if db.query(InstitutionCost).filter(InstitutionCost.institution_id == canonical.id).count() == 0:
        db.query(InstitutionCost).filter(InstitutionCost.institution_id == duplicate.id).update({"institution_id": canonical.id})
    if db.query(AcademicProgram).filter(AcademicProgram.institution_id == canonical.id).count() == 0:
        db.query(AcademicProgram).filter(AcademicProgram.institution_id == duplicate.id).update({"institution_id": canonical.id})

    db.delete(duplicate)
    db.flush()


def deduplicate_us_non_ipeds(db: Session) -> List[Tuple[str, str, str]]:
    """
    Finds US records lacking `ipeds_unit_id` that match an IPEDS-verified main campus
    by normalized name or root domain + city/name prefix, and merges them cleanly.
    Returns list of (merged_duplicate_name, canonical_name, ipeds_unit_id).
    """
    non_ipeds = (
        db.query(Institution)
        .filter(Institution.country_code == "US", Institution.ipeds_unit_id.is_(None))
        .all()
    )
    if not non_ipeds:
        return []

    ipeds_rows = (
        db.query(Institution)
        .filter(Institution.country_code == "US", Institution.ipeds_unit_id.isnot(None))
        .all()
    )

    by_norm_name: Dict[str, Institution] = {}
    by_domain: Dict[str, List[Institution]] = {}
    for row in ipeds_rows:
        by_norm_name.setdefault(normalize_inst_name(row.official_name), row)
        dom = extract_root_domain(row.official_website)
        if dom:
            by_domain.setdefault(dom, []).append(row)

    merged: List[Tuple[str, str, str]] = []
    for dup in non_ipeds:
        norm = normalize_inst_name(dup.official_name)
        target: Optional[Institution] = by_norm_name.get(norm)

        if not target:
            dom = extract_root_domain(dup.official_website)
            if dom and dom in by_domain:
                candidates = by_domain[dom]
                # Prefer main campus or prefix match
                for c in candidates:
                    if c.is_main_campus and normalize_inst_name(c.official_name).startswith(norm):
                        target = c
                        break
                if not target and len(candidates) == 1:
                    target = candidates[0]

        if target and target.id != dup.id:
            dup_name = dup.official_name
            merge_duplicate_pair(db, target, dup)
            merged.append((dup_name, target.official_name, target.ipeds_unit_id or ""))

    db.commit()
    return merged
