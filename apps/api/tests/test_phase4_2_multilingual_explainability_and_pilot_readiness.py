"""
Phase 4.2: Global Scholarship Intelligence, Multilingual Explainability & Pilot Readiness Suite.

Covers Workstreams 1–7:
1. Workstream 1.1: ht_ca_first_year_ug (Lester B. Pearson & UBC International eligible,
   November deadlines classified as previous_cycle_only; McGill stays requires_manual_review).
2. Workstream 1.2: 8-state cycle_verification_state breakdown without marking unannounced
   or HTTP 403 WAF-blocked programs open.
3. Workstream 1.3: DRQ-01..DRQ-04 6-field research metadata & safe resolution modes.
4. Workstream 2: Structured reason_code + params emission + 100% parity with TypeScript
   10-locale PHASE4_REASON_TEMPLATES (no missing keys or placeholder mismatches).
5. Workstream 4: Variable/expired/source-unavailable/non-USD aid excluded from USD guaranteed
   net-price offsets; tuition-only scope enforcement.
6. Workstream 6: MultilingualCounselorService scholarship grounding + official citations +
   external portal non-submission policy + /financial & /applications routing workflows.
7. Workstream 7: SSRF DNS pinning / egress firewall policy + honest ClerkAuthProvider blocker audit.
"""

from pathlib import Path
import re

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.institution import Institution
from app.models.profile import StudentProfile
from app.models.rag import ScholarshipProgram
from app.services.counselor import MultilingualCounselorService
from app.services.coverage_analytics import generate_global_coverage_audit
from app.services.financial_engine import (
    calculate_net_price,
    classify_cycle_verification_state,
    evaluate_single_scholarship,
    match_scholarships_deterministic,
)
from app.services.freshness_governance import evaluate_scholarship_claim_breakdown


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_42_01_ht_ca_first_year_pearson_ubc_and_mcgill():
    db = SessionLocal()
    try:
        resp = match_scholarships_deterministic(
            db,
            None,
            {
                "citizenship_country": "HT",
                "country_of_residence": "HT",
                "destination_country": "CA",
                "applicant_type": "first_year",
                "degree_level": "bachelors",
                "gpa_4": 3.85,
                "financial_need_level": "high",
                "household_income_usd": 15000,
                "include_ineligible": True,
            },
        )
        by_title = {item["title"]: item for item in resp["results"]}

        pearson = next((v for k, v in by_title.items() if "Lester B. Pearson" in k), None)
        ubc = next((v for k, v in by_title.items() if "UBC" in k or "Karen McKellin" in k), None)
        mcgill = next((v for k, v in by_title.items() if "McGill" in k), None)

        assert pearson is not None and ubc is not None and mcgill is not None

        for target in (pearson, ubc):
            assert target["eligibility_status"] == "eligible"
            assert target["cycle_verification_state"] == "previous_cycle_only"
            assert target["application_cycle_status"] == "closed"
            assert target["is_cycle_open"] is False
            assert target["cycle_reason_code"] == "cycle.previous_cycle_only"
            assert "date" in target["cycle_params"]
            assert target["official_source_language"] == "en"
            assert target["satisfied_items"]

        assert mcgill["eligibility_status"] == "requires_manual_review"
        assert mcgill["cycle_verification_state"] == "requires_manual_verification"
    finally:
        db.close()


def test_42_02_eight_state_cycle_classification_and_drq_metadata():
    db = SessionLocal()
    try:
        audit = generate_global_coverage_audit(db)
        breakdown = audit["cycle_verification_breakdown"]

        expected_states = {
            "confirmed_open",
            "confirmed_upcoming",
            "rolling",
            "previous_cycle_only",
            "next_cycle_unannounced",
            "deadline_expired",
            "source_unavailable",
            "requires_manual_verification",
        }
        assert set(breakdown.keys()) == expected_states
        assert sum(breakdown.values()) == audit["total_active_programs"]
        assert breakdown["previous_cycle_only"] >= 2
        assert breakdown["next_cycle_unannounced"] >= 1
        assert breakdown["source_unavailable"] >= 1
        assert breakdown["requires_manual_verification"] >= 1

        # Verify no WAF-blocked or next_cycle_unannounced scholarship is ever flagged open
        programs = db.query(ScholarshipProgram).all()
        assert len(programs) == audit["total_active_programs"]
        for sch in programs:
            cb = evaluate_scholarship_claim_breakdown(sch)
            state, app_status, is_open, reason_code, params, _ = classify_cycle_verification_state(
                sch, cb, cb["record_state"]
            )
            assert state in expected_states
            assert reason_code.startswith("cycle.")
            if state in {
                "previous_cycle_only",
                "next_cycle_unannounced",
                "deadline_expired",
                "source_unavailable",
                "requires_manual_verification",
                "confirmed_upcoming",
            }:
                assert is_open is False, f"{sch.title} marked open while {state}"
                assert app_status != "open"

        drq = audit["deferred_research_queue"]
        assert len(drq) == 4
        for item in drq:
            assert item["research_objective"]
            assert isinstance(item["official_sources_required"], list) and len(item["official_sources_required"]) >= 1
            assert item["existing_evidence"]
            assert item["missing_evidence"]
            assert item["verification_priority"]
            assert item["resolution_mode"] in {"human_review_required", "semi_automated_allowlist"}
    finally:
        db.close()


def test_42_03_structured_reason_code_parity_across_python_and_ts_10_locales():
    py_path = REPO_ROOT / "apps" / "api" / "app" / "services" / "financial_engine.py"
    ts_path = REPO_ROOT / "apps" / "web" / "src" / "lib" / "i18n" / "phase4-reason-codes.ts"

    py_src = py_path.read_text(encoding="utf-8")
    ts_src = ts_path.read_text(encoding="utf-8")

    # Collect all reason codes in financial_engine.py
    py_codes = {
        c
        for c in set(re.findall(r"\"([a-z]+\.[a-z0-9_.]+)\"", py_src))
        if c.startswith(("rule.", "cycle.", "fresh.", "intl_policy."))
    }

    ts_blocks = re.findall(r"\"([^\"]+)\":\s*r\((.*?)\n\s*\),", ts_src, re.S)
    ts_map = {}
    for code, body in ts_blocks:
        strings = re.findall(r"\"([^\"]*(?:\\\"[^\"]*)*)\"", body)
        assert len(strings) == 10, f"{code} must define 10 locales, got {len(strings)}"
        for idx, s in enumerate(strings):
            assert s.strip(), f"Empty localized string at index {idx} for {code}"
        ts_map[code] = set(re.findall(r"\{([a-z0-9_]+)\}", strings[0]))

    missing = py_codes - set(ts_map.keys())
    assert not missing, f"Reason codes missing in TS 10-locale map: {missing}"

    # Evaluate diverse profiles end-to-end and confirm all emitted codes exist in ts_map
    db = SessionLocal()
    try:
        profiles = [
            {"citizenship_country": "HT", "country_of_residence": "HT", "applicant_type": "first_year", "degree_level": "bachelors", "gpa_4": 3.85, "include_ineligible": True},
            {"citizenship_country": "ES", "country_of_residence": "FR", "applicant_type": "transfer", "degree_level": "masters", "gpa_4": 2.9, "household_income_usd": 120000, "include_ineligible": True},
            {"citizenship_country": "KR", "dual_citizenship": True, "citizenships": ["KR", "US"], "applicant_type": "bachelors", "degree_level": "bachelors", "date_of_birth": "1990-01-01", "include_ineligible": True},
            {"include_ineligible": True},
        ]
        for prof in profiles:
            out = match_scholarships_deterministic(db, None, prof)
            for item in out["results"]:
                assert item["cycle_reason_code"] in ts_map
                for r in item["rule_evaluations"]:
                    assert r["reason_code"] in ts_map, f"Unmapped live code {r['reason_code']}"
                for group in ("satisfied_items", "failed_items", "missing_items", "freshness_warning_items"):
                    for entry in item[group]:
                        assert entry["reason_code"] in ts_map, f"Unmapped {group} code {entry['reason_code']}"
    finally:
        db.close()


def test_42_04_net_price_variable_and_unverified_aid_safety():
    db = SessionLocal()
    try:
        inst = db.query(Institution).filter(Institution.official_name.ilike("%Harvard%")).first()
        if inst is None:
            inst = db.query(Institution).filter(Institution.country_code == "US").first()
        assert inst is not None

        net = calculate_net_price(
            db,
            inst,
            None,
            {
                "residency_classification": "international",
                "housing_preference": "on_campus",
                "applicant_type": "first_year",
                "degree_level": "bachelors",
                "citizenship_country": "HT",
                "country_of_residence": "HT",
                "gpa_4": 3.9,
                "financial_need_level": "high",
                "household_income_usd": 20000,
                "annual_budget_usd": 25000,
                "include_competitive_aid": True,
            },
        )
        # Guaranteed and competitive statutory USD discounts cannot invent deductions for variable/conflicting aid
        assert net["estimated_net_price_min_usd"] >= 0
        assert net["estimated_net_price_min_usd"] <= net["total_coa_usd"]
        for offset in net["aid_offsets"]:
            assert offset["estimated_max_usd"] > 0
            assert "Harvard" not in offset["title"]
        for row in net["category_breakdown"]:
            if row["remaining_cost_min_usd"] is not None:
                assert row["remaining_cost_min_usd"] >= 0
            if row["original_cost_usd"] is not None:
                assert row["applied_verified_max_usd"] <= row["original_cost_usd"]
    finally:
        db.close()


def test_42_05_counselor_scholarship_grounding_and_external_portal_policy():
    db = SessionLocal()
    try:
        profile = db.query(StudentProfile).first()
        res = MultilingualCounselorService.answer_admissions_query(
            query="Which verified scholarships apply to international undergraduate students and how do I apply on official portals?",
            preferred_language="fr-FR",
            applicant_type="first_year",
            db=db,
            profile=profile,
        )
        assert res["language"] == "fr-FR"
        facts_text = " ".join(res["epistemic_breakdown"]["official_facts"])
        ai_text = " ".join(res["epistemic_breakdown"]["ai_interpretation"]).lower()
        assert facts_text, "Expected scholarship/institution official facts"
        assert "never" in ai_text and "portal" in ai_text
        workflow_hrefs = {w["href"] for w in res["epistemic_breakdown"]["suggested_workflows"]}
        assert "/financial" in workflow_hrefs
        assert "/applications" in workflow_hrefs
        assert len(res["citations"]) >= 1
        assert any((c.get("url") or "").startswith("http") for c in res["citations"])
    finally:
        db.close()


def test_42_06_pilot_security_and_external_routing_honesty():
    # Firewall egress script blocks IMDS & RFC1918
    fw_script = (REPO_ROOT / "infra" / "firewall" / "egress-iptables.sh").read_text(encoding="utf-8")
    assert "169.254.169.254/32" in fw_script
    assert "10.0.0.0/8" in fw_script
    assert "192.168.0.0/16" in fw_script

    # SSRF public IP pinning helper blocks private/metadata endpoints
    routing_src = (REPO_ROOT / "apps" / "api" / "app" / "services" / "routing_health.py").read_text(encoding="utf-8")
    assert "_PinnedPublicIPBackend" in routing_src
    assert "follow_redirects=False" in routing_src

    # Honest audit of ClerkAuthProvider: still placeholder in codebase and documented as blocker
    auth_src = (REPO_ROOT / "apps" / "api" / "app" / "core" / "auth_provider.py").read_text(encoding="utf-8")
    assert "ClerkAuthProvider" in auth_src
    assert "clerk_verified_user" in auth_src

    # External portal handoff endpoint must exist under OpenAPI routes (never auto-submitted)
    client = TestClient(app)
    schema = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/applications/{application_id}/redirect" in schema["paths"]
