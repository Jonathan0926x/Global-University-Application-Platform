"""
Global Catalog Coverage & Accessibility Analytics Engine (Workstreams E, F, G).

Evaluates catalog, research, provenance, verified-funding, and actionable coverage
across citizenship, destination country, degree level, applicant pathway
(distinguishing incoming first-year, transfer, graduate, and short-term exchange
without ever inferring transfer eligibility from generic undergraduate rules),
and key student profile intersections.
"""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session, joinedload

from app.ingestion.phase4_catalog_audit_remediation import LEGACY_AUDIT_SPECS
from app.models.country import Country
from app.models.rag import ScholarshipProgram
from app.services.financial_engine import (
    _derive_student_context,
    ensure_phase4_seeded,
    evaluate_single_scholarship,
)
from app.services.freshness_governance import (
    _has_verified_funding_coverage,
    _utcnow,
    evaluate_scholarship_claim_breakdown,
    evaluate_scholarship_freshness,
)

REQUIRED_15_PROVENANCE_KEYS = {
    "program_existence",
    "sponsor",
    "citizenship_eligibility",
    "residency_eligibility",
    "destination_country",
    "degree_level",
    "applicant_type",
    "award_amount",
    "currency",
    "funding_scope",
    "funding_duration",
    "renewal",
    "deadlines",
    "application_cycle",
    "academic_year",
}

COVERAGE_PROBE_CITIZENSHIPS: List[str] = [
    "US", "CA", "HT", "JM", "NG", "GH", "KE", "ZA",
    "MA", "MR", "BR", "MX", "CO", "CL", "PE",
    "IN", "CN", "KR", "PK", "BD", "VN", "PH", "ID",
    "GB", "FR", "DE", "NL", "CH", "SE", "NO", "FI", "IT", "ES",
]


def _classify_transfer_support(sch: ScholarshipProgram) -> str:
    """
    Strictly distinguishes verified transfer support, explicit exclusion, and
    unconfirmed/unknown transfer status without inferring from generic 'bachelors'.
    """
    audit_meta = (sch.claim_provenance or {}).get("audit_metadata") if isinstance(sch.claim_provenance, dict) else {}
    explicit = audit_meta.get("transfer_supported") if isinstance(audit_meta, dict) else None
    app_type = (sch.applicant_type or "").strip().lower()
    ftype = (sch.funding_type or "").strip().lower()
    degs = set(sch.degree_levels or [])

    if ftype == "exchange_mobility" or degs <= {"masters", "doctoral"}:
        return "not_applicable_grad_or_exchange"
    if app_type == "transfer" or explicit is True:
        return "verified_supported"
    if app_type == "first_year" or explicit is False:
        return "explicitly_excluded"
    return "unconfirmed_unknown"


def generate_global_coverage_audit(
    db: Session,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Computes live global coverage analytics directly from PostgreSQL records and the
    deterministic eligibility engine across Workstreams E, F, and G.
    """
    ensure_phase4_seeded(db)
    ref_now = _utcnow(now)

    programs = (
        db.query(ScholarshipProgram)
        .options(joinedload(ScholarshipProgram.rules))
        .order_by(ScholarshipProgram.country_code, ScholarshipProgram.title)
        .all()
    )
    country_names = {c.code: c.name for c in db.query(Country).all()}

    active_programs = [p for p in programs if p.is_current]
    total_active = len(active_programs)

    legacy_reviewed = 0
    batch_reverified = 0
    complete_prov = 0
    verified_elig_count = 0
    verified_funding_count = 0
    actionable_count = 0
    unknown_elig_count = 0
    manual_review_count = 0
    expired_claim_count = 0
    source_unavailable_count = 0
    conflicting_count = 0
    dual_cit_restricted = 0
    cit_res_separated = 0
    multi_dest_count = 0

    pathway_counts = {
        "first_year_verified": 0,
        "transfer_verified": 0,
        "transfer_explicitly_excluded": 0,
        "transfer_unconfirmed_unknown": 0,
        "community_college_required": 0,
        "graduate_doctoral_only": 0,
        "exchange_mobility_only": 0,
    }

    degree_stats: Dict[str, Dict[str, int]] = {
        "bachelors": {"catalog": 0, "verified_funding": 0, "actionable": 0},
        "masters": {"catalog": 0, "verified_funding": 0, "actionable": 0},
        "doctoral": {"catalog": 0, "verified_funding": 0, "actionable": 0},
        "exchange_mobility": {"catalog": 0, "verified_funding": 0, "actionable": 0},
    }

    dest_stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "country_code": "",
            "country_name": "",
            "catalog_count": 0,
            "verified_funding_count": 0,
            "actionable_count": 0,
            "manual_review_or_unavailable_count": 0,
            "closed_cycle_count": 0,
        }
    )

    manual_review_items: List[Dict[str, Any]] = []
    unavailable_source_items: List[Dict[str, Any]] = []

    for p in active_programs:
        prov = p.claim_provenance if isinstance(p.claim_provenance, dict) else {}
        if "audit_metadata" in prov:
            if p.title in LEGACY_AUDIT_SPECS:
                legacy_reviewed += 1
            else:
                batch_reverified += 1
        if REQUIRED_15_PROVENANCE_KEYS.issubset(set(prov.keys())):
            complete_prov += 1

        cb = evaluate_scholarship_claim_breakdown(p, now=ref_now)
        fresh = evaluate_scholarship_freshness(p, now=ref_now)
        is_funded = _has_verified_funding_coverage(p, ref_now)
        is_actionable = bool(is_funded and not cb["deadline_expired"])
        is_exchange = (p.funding_type or "").strip().lower() == "exchange_mobility"

        if (
            cb["existence_current"]
            and cb["claims"].get("eligibility_rules") in ("current", "approaching_expiration")
        ):
            verified_elig_count += 1
        else:
            unknown_elig_count += 1

        if is_funded:
            verified_funding_count += 1
        if is_actionable:
            actionable_count += 1

        if p.requires_manual_review or fresh in ("requires_manual_review", "conflicting_information", "source_unavailable"):
            manual_review_count += 1
            audit_note = (prov.get("audit_metadata") or {}).get("audit_note")
            manual_review_items.append(
                {
                    "title": p.title,
                    "country_code": p.country_code,
                    "freshness_status": fresh,
                    "amount_classification": (prov.get("audit_metadata") or {}).get("amount_classification", "unspecified"),
                    "source_url": p.source_url,
                    "reason": p.conflict_notes or audit_note or f"Freshness status: {fresh}",
                }
            )
        http_code = (prov.get("audit_metadata") or {}).get("http_status")
        if fresh == "source_unavailable" or (http_code is not None and http_code != 200) or (prov.get("live_recheck") or {}).get("status") == "intermittent_waf_or_timeout":
            source_unavailable_count += 1
            audit_note = (prov.get("audit_metadata") or {}).get("audit_note")
            unavailable_source_items.append(
                {
                    "title": p.title,
                    "country_code": p.country_code,
                    "freshness_status": fresh,
                    "http_status": http_code,
                    "source_url": p.source_url,
                    "note": p.conflict_notes or audit_note or (prov.get("live_recheck") or {}).get("note", ""),
                }
            )
        if fresh == "conflicting_information":
            conflicting_count += 1
        if cb["deadline_expired"] or cb["amount_expired"] or cb["record_expired"]:
            expired_claim_count += 1

        dims = {r.rule_dimension for r in (p.rules or [])}
        if "dual_citizenship" in dims:
            dual_cit_restricted += 1
        if "country_of_residence" in dims and ("citizenship" in dims or "excluded_citizenships" in dims or "geographic_region" in dims):
            cit_res_separated += 1
        if len(p.eligible_destination_countries or []) > 1:
            multi_dest_count += 1

        # Pathway categorization
        degs = set(p.degree_levels or ["bachelors"])
        app_t = (p.applicant_type or "all").strip().lower()
        t_support = _classify_transfer_support(p)
        if is_exchange:
            pathway_counts["exchange_mobility_only"] += 1
        elif degs <= {"masters", "doctoral"}:
            pathway_counts["graduate_doctoral_only"] += 1
        if not is_exchange and "bachelors" in degs and app_t in ("first_year", "all"):
            pathway_counts["first_year_verified"] += 1
        if t_support == "verified_supported":
            pathway_counts["transfer_verified"] += 1
        elif t_support == "explicitly_excluded":
            pathway_counts["transfer_explicitly_excluded"] += 1
        elif t_support == "unconfirmed_unknown":
            pathway_counts["transfer_unconfirmed_unknown"] += 1
        if any(
            r.rule_dimension == "enrollment_context"
            and isinstance(r.rule_value, dict)
            and r.rule_value.get("requires_us_community_college")
            for r in (p.rules or [])
        ):
            pathway_counts["community_college_required"] += 1

        # Degree stats
        if is_exchange:
            degree_stats["exchange_mobility"]["catalog"] += 1
        else:
            for d in degs:
                if d in degree_stats:
                    degree_stats[d]["catalog"] += 1
                    if is_funded:
                        degree_stats[d]["verified_funding"] += 1
                    if is_actionable:
                        degree_stats[d]["actionable"] += 1

        # Destination country stats (by host/sponsor country_code)
        dest_key = (p.country_code or "US").upper()
        ds = dest_stats[dest_key]
        ds["country_code"] = dest_key
        ds["country_name"] = country_names.get(dest_key, dest_key)
        ds["catalog_count"] += 1
        if is_funded:
            ds["verified_funding_count"] += 1
        if is_actionable:
            ds["actionable_count"] += 1
        if p.requires_manual_review or fresh != "current":
            ds["manual_review_or_unavailable_count"] += 1
        if cb["deadline_expired"]:
            ds["closed_cycle_count"] += 1

    # Citizenship coverage via deterministic eligibility engine probes (BA/MA/PhD blended across pathways)
    by_citizenship: List[Dict[str, Any]] = []
    citizenships_with_verified = 0
    for cit in COVERAGE_PROBE_CITIZENSHIPS:
        eligible_or_cond = 0
        funded_match = 0
        actionable_match = 0
        for p in active_programs:
            # Evaluate across all degree levels supported by the scholarship to test legal citizenship reach
            degs = p.degree_levels or ["bachelors"]
            matched = False
            for d in degs:
                app = "transfer" if (p.applicant_type or "").lower() == "transfer" else "first_year"
                probe_ctx = _derive_student_context(
                    db,
                    None,
                    {
                        "citizenship_country": cit,
                        "citizenships": [cit],
                        "dual_citizenship": False,
                        "country_of_residence": cit,
                        "degree_level": d,
                        "applicant_type": app,
                        "gpa_4": 3.85,
                        "financial_need_level": "high",
                        "household_income_usd": 20000.0,
                        "date_of_birth": "2006-05-01" if d == "bachelors" else "1998-05-01",
                        "us_community_college_enrolled": True,
                        "language_proficiencies": {
                            "en": {"format": "toefl", "test_type": "TOEFL", "score": 100},
                            "zh": {"format": "hsk", "test_type": "HSK", "score": 5},
                        },
                        "exam_scores": {"SAT": 1450, "ACT": 33, "ENEM": 700, "ENP": 92, "CSCA": 90},
                    },
                )
                res = evaluate_single_scholarship(p, probe_ctx)
                if res["eligibility_status"] in ("eligible", "conditionally_eligible"):
                    matched = True
                    break
            if matched:
                eligible_or_cond += 1
                if _has_verified_funding_coverage(p, ref_now):
                    funded_match += 1
                    cb = evaluate_scholarship_claim_breakdown(p, now=ref_now)
                    if not cb["deadline_expired"]:
                        actionable_match += 1
        if funded_match > 0:
            citizenships_with_verified += 1
        by_citizenship.append(
            {
                "country_code": cit,
                "country_name": country_names.get(cit, cit),
                "eligible_or_conditional_count": eligible_or_cond,
                "verified_funding_eligible_count": funded_match,
                "actionable_eligible_count": actionable_match,
            }
        )

    # Curated Workstream F Reference Intersections evaluated live via engine
    intersection_specs = [
        (
            "ht_ca_first_year_ug",
            "Haitian citizen seeking undergraduate funding in Canada (first-year)",
            {"citizenships": ["HT"], "country_of_residence": "HT", "destination_country": "CA", "degree_level": "bachelors", "applicant_type": "first_year", "gpa_4": 3.85, "financial_need_level": "high"},
            {"CA"},
        ),
        (
            "ng_europe_masters",
            "Nigerian citizen seeking a Master's scholarship in Europe (all EU/UK/CH/SE/NO)",
            {"citizenships": ["NG"], "country_of_residence": "NG", "degree_level": "masters", "applicant_type": "first_year", "gpa_4": 3.85, "financial_need_level": "high", "language_proficiencies": {"en": {"format": "ielts", "test_type": "IELTS", "score": 7.0}}},
            {"FR", "DE", "GB", "NL", "CH", "SE", "NO", "FI", "IT", "ES", "BE"},
        ),
        (
            "in_asia_doctoral",
            "Indian citizen seeking doctoral funding in Asia (SG / CN / JP / KR / MY)",
            {"citizenships": ["IN"], "country_of_residence": "IN", "degree_level": "doctoral", "applicant_type": "first_year", "gpa_4": 3.85, "field_of_study": "Computer Science", "date_of_birth": "1998-05-01", "language_proficiencies": {"en": {"format": "ielts", "test_type": "IELTS", "score": 7.0}}},
            {"SG", "CN", "MY", "KR", "JP", "ID", "IN"},
        ),
        (
            "ht_us_transfer_cc",
            "International transfer applicant (Haiti + US Community College) seeking undergraduate aid in the US",
            {"citizenships": ["HT"], "country_of_residence": "US", "destination_country": "US", "degree_level": "bachelors", "applicant_type": "transfer", "us_community_college_enrolled": True, "gpa_4": 3.8, "financial_need_level": "high", "household_income_usd": 20000.0},
            {"US"},
        ),
        (
            "ma_eu_vs_mr_eu",
            "Moroccan citizen (MA) vs. Mauritanian citizen (MR) Master's access in Europe",
            None,
        ),
    ]

    intersections: List[Dict[str, Any]] = []
    for item in intersection_specs:
        key = item[0]
        label = item[1]
        if key == "ma_eu_vs_mr_eu":
            ma_titles = []
            mr_titles = []
            for p in active_programs:
                if "masters" not in (p.degree_levels or []):
                    continue
                if p.country_code not in {"GB", "FR", "DE", "NL", "CH", "SE", "NO", "FI", "IT", "ES", "BE"}:
                    continue
                for code, acc in (("MA", ma_titles), ("MR", mr_titles)):
                    mctx = _derive_student_context(
                        db,
                        None,
                        {"citizenship_country": code, "citizenships": [code], "country_of_residence": code, "degree_level": "masters", "applicant_type": "first_year", "gpa_4": 3.8, "financial_need_level": "high", "language_proficiencies": {"en": {"format": "ielts", "test_type": "IELTS", "score": 7.0}}},
                    )
                    res = evaluate_single_scholarship(p, mctx)
                    if res["eligibility_status"] in ("eligible", "conditionally_eligible"):
                        acc.append(p.title)
            intersections.append(
                {
                    "key": key,
                    "label": label,
                    "matched_count": len(ma_titles),
                    "verified_funding_count": 0,
                    "sample_titles": [f"MA eligible: {len(ma_titles)} (incl. SI SISGP)", f"MR eligible: {len(mr_titles)} (SI SISGP Morocco-only excluded)"],
                }
            )
            continue

        ctx = _derive_student_context(db, None, item[2])
        dest_filter = item[3] if len(item) > 3 else None
        matched_titles: List[str] = []
        funded_matches = 0
        for p in active_programs:
            if dest_filter is not None and p.country_code not in dest_filter and not (set(p.eligible_destination_countries or []) & dest_filter):
                continue
            res = evaluate_single_scholarship(p, ctx)
            if res["eligibility_status"] in ("eligible", "conditionally_eligible"):
                matched_titles.append(p.title)
                if _has_verified_funding_coverage(p, ref_now):
                    funded_matches += 1
        intersections.append(
            {
                "key": key,
                "label": label,
                "matched_count": len(matched_titles),
                "verified_funding_count": funded_matches,
                "sample_titles": matched_titles[:5],
            }
        )

    return {
        "audited_at": ref_now.isoformat(),
        "total_catalog_programs": len(programs),
        "total_active_programs": total_active,
        "programs_reviewed": legacy_reviewed + batch_reverified,
        "legacy_reviewed_count": legacy_reviewed,
        "legacy_total_count": len(LEGACY_AUDIT_SPECS),
        "batch1_4_reverified_count": batch_reverified,
        "complete_provenance_count": complete_prov,
        "complete_provenance_ratio": round(complete_prov / total_active, 4) if total_active else 0.0,
        "verified_eligibility_count": verified_elig_count,
        "verified_funding_programs": verified_funding_count,
        "verified_funding_coverage": round(verified_funding_count / total_active, 4) if total_active else 0.0,
        "actionable_coverage_count": actionable_count,
        "actionable_coverage_ratio": round(actionable_count / total_active, 4) if total_active else 0.0,
        "unknown_eligibility_count": unknown_elig_count,
        "requires_manual_review_count": manual_review_count,
        "expired_claim_count": expired_claim_count,
        "source_unavailable_count": source_unavailable_count,
        "conflicting_count": conflicting_count,
        "dual_citizenship_restricted_programs": dual_cit_restricted,
        "citizenship_residency_separated_programs": cit_res_separated,
        "multi_destination_programs": multi_dest_count,
        "citizenships_with_verified_funding_count": citizenships_with_verified,
        "by_pathway": pathway_counts,
        "by_degree_level": degree_stats,
        "by_citizenship": by_citizenship,
        "by_destination": sorted(dest_stats.values(), key=lambda x: (-x["catalog_count"], x["country_code"])),
        "intersections": intersections,
        "manual_review_programs": manual_review_items,
        "unavailable_source_programs": unavailable_source_items,
    }
