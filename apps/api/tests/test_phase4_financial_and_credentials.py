from pathlib import Path
import subprocess
import uuid

from app.database import SessionLocal
from app.ingestion.phase4_seed import seed_phase4_financial_and_credentials


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_production_outbound_firewall_rules_block_private_and_metadata():
    iptables_script = REPO_ROOT / "infra" / "firewall" / "egress-iptables.sh"
    k8s_policy = REPO_ROOT / "infra" / "firewall" / "k8s-api-worker-egress-networkpolicy.yaml"
    prod_compose = REPO_ROOT / "infra" / "firewall" / "docker-compose.prod.yml"

    assert iptables_script.exists()
    assert k8s_policy.exists()
    assert prod_compose.exists()

    iptables_text = iptables_script.read_text(encoding="utf-8")
    k8s_text = k8s_policy.read_text(encoding="utf-8")

    required_blocked = [
        "169.254.169.254/32",
        "169.254.0.0/16",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "100.64.0.0/10",
        "::1/128",
        "fe80::/10",
        "fc00::/7",
        "::ffff:169.254.169.254/128",
    ]
    for cidr in required_blocked:
        assert cidr in iptables_text, f"{cidr} missing from egress-iptables.sh"
        assert cidr in k8s_text, f"{cidr} missing from k8s-api-worker-egress-networkpolicy.yaml"

    dry_run = subprocess.run(
        ["bash", str(iptables_script), "--dry-run"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "169.254.169.254/32 -j REJECT" in dry_run.stdout
    assert "10.0.0.0/8 -j REJECT" in dry_run.stdout


def test_phase4_verified_scholarships_and_deterministic_eligibility(client):
    db = SessionLocal()
    try:
        seed_phase4_financial_and_credentials(db)
        second = seed_phase4_financial_and_credentials(db)
        assert second["scholarships_created"] == 0
        assert second["grade_rules_created"] == 0
        assert second["recognition_rules_created"] == 0
    finally:
        db.close()

    # Scenario 1: Haitian international transfer applicant (3.75 GPA, high financial need, dest US)
    ht_transfer = client.post(
        "/api/v1/financial/scholarships/match",
        json={
            "citizenship_country": "HT",
            "applicant_type": "transfer",
            "degree_level": "bachelors",
            "gpa_4": 3.75,
            "financial_need_level": "high",
            "household_income_usd": 24000,
            "destination_country": "US",
            "include_ineligible": True,
        },
    )
    assert ht_transfer.status_code == 200
    body = ht_transfer.json()
    assert body["total_scholarships"] >= 22
    by_title = {r["title"]: r for r in body["results"]}

    assert by_title["MIT Need-Blind Admissions & Full-Need Institutional Aid"]["eligibility_status"] == "eligible"
    assert by_title["Yale Need-Blind Worldwide & Full-Need Financial Aid"]["eligibility_status"] == "eligible"
    assert by_title["Princeton Financial Aid — No-Loan Full-Need Grant"]["eligibility_status"] == "eligible"
    assert (
        by_title["OAS Academic Scholarship Program (Upper-Division Transfer / Final 2 Years)"]["eligibility_status"]
        == "eligible"
    )
    # Without US community college enrollment in context, JKC must be insufficient_information (missing enrollment records)
    assert by_title["Jack Kent Cooke Undergraduate Transfer Scholarship"]["eligibility_status"] == "insufficient_information"
    # Graduate-only Fulbright must NOT appear in undergraduate bachelors matching
    assert "Fulbright Foreign Student Program (Graduate & Research)" not in by_title

    # With US community college enrollment verified, Jack Kent Cooke evaluates to eligible
    ht_cc_transfer = client.post(
        "/api/v1/financial/scholarships/match",
        json={
            "citizenship_country": "HT",
            "applicant_type": "transfer",
            "degree_level": "bachelors",
            "us_community_college_enrolled": True,
            "gpa_4": 3.75,
            "financial_need_level": "high",
            "household_income_usd": 24000,
            "destination_country": "US",
            "include_ineligible": True,
        },
    )
    assert ht_cc_transfer.status_code == 200
    cc_by_title = {r["title"]: r for r in ht_cc_transfer.json()["results"]}
    assert cc_by_title["Jack Kent Cooke Undergraduate Transfer Scholarship"]["eligibility_status"] == "eligible"

    # Masters degree query surfaces Fulbright as eligible
    ht_masters = client.post(
        "/api/v1/financial/scholarships/match",
        json={
            "citizenship_country": "HT",
            "applicant_type": "first_year",
            "degree_level": "masters",
            "gpa_4": 3.75,
            "financial_need_level": "high",
            "destination_country": "US",
            "include_ineligible": True,
        },
    )
    assert ht_masters.status_code == 200
    masters_by_title = {r["title"]: r for r in ht_masters.json()["results"]}
    assert masters_by_title["Fulbright Foreign Student Program (Graduate & Research)"]["eligibility_status"] == "eligible"

    # Must deterministically mark domestic/CA-only & non-US awards ineligible with clear reasons
    assert by_title["UC Blue and Gold Opportunity Plan (UC Berkeley)"]["eligibility_status"] == "ineligible"
    assert len(by_title["UC Blue and Gold Opportunity Plan (UC Berkeley)"]["failed_reasons"]) >= 1
    assert by_title["UC Blue and Gold Opportunity Plan (UCLA)"]["eligibility_status"] == "ineligible"
    assert by_title["UC Blue and Gold Opportunity Plan (UC San Diego)"]["eligibility_status"] == "ineligible"
    assert by_title["Federal Pell Grant (US Statutory Need Aid)"]["eligibility_status"] == "ineligible"
    assert by_title["Lester B. Pearson International Scholarship"]["eligibility_status"] == "ineligible"

    # Scenario 2: California in-state first-year resident ($55k family income)
    ca_fy = client.post(
        "/api/v1/financial/scholarships/match",
        json={
            "citizenship_country": "US",
            "residency_state": "CA",
            "applicant_type": "first_year",
            "degree_level": "bachelors",
            "gpa_4": 3.80,
            "financial_need_level": "high",
            "household_income_usd": 55000,
            "destination_country": "US",
            "include_ineligible": True,
        },
    )
    assert ca_fy.status_code == 200
    ca_by_title = {r["title"]: r for r in ca_fy.json()["results"]}
    assert ca_by_title["UC Blue and Gold Opportunity Plan (UC Berkeley)"]["eligibility_status"] == "eligible"
    assert ca_by_title["UC Blue and Gold Opportunity Plan (UCLA)"]["eligibility_status"] == "eligible"
    assert ca_by_title["UC Blue and Gold Opportunity Plan (UC San Diego)"]["eligibility_status"] == "eligible"
    assert ca_by_title["Federal Pell Grant (US Statutory Need Aid)"]["eligibility_status"] == "eligible"
    assert ca_by_title["UMich Go Blue Guarantee"]["eligibility_status"] == "ineligible"


def test_phase4_net_price_calculator_breakdown_and_offsets(client):
    insts = client.get("/api/v1/institutions").json()
    mit = next((i for i in insts if "Massachusetts Institute of Technology" in i["official_name"]), None)
    ucb = next((i for i in insts if "University of California-Berkeley" in i["official_name"]), None)
    assert mit is not None and ucb is not None

    # 1. International high-need student at MIT -> legacy unreviewed MIT policy must be separated into review_required_aid (not verified discount)
    mit_net = client.post(
        "/api/v1/financial/net-price",
        json={
            "institution_id": mit["id"],
            "residency_classification": "international",
            "housing_preference": "on_campus",
            "applicant_type": "first_year",
            "degree_level": "bachelors",
            "citizenship_country": "HT",
            "gpa_4": 3.9,
            "financial_need_level": "high",
            "household_income_usd": 20000,
            "annual_budget_usd": 15000,
        },
    )
    assert mit_net.status_code == 200
    mit_body = mit_net.json()
    assert mit_body["total_coa_usd"] is not None and mit_body["total_coa_usd"] > 50000
    assert mit_body["guaranteed_aid_max_usd"] == 0.0
    assert mit_body["competitive_aid_max_usd"] == 0.0
    assert mit_body["estimated_net_price_min_usd"] >= 0.0
    assert any("MIT" in a["title"] for a in mit_body["review_required_aid"])
    assert not any("Fulbright" in a["title"] for a in mit_body["aid_offsets"] + mit_body["review_required_aid"])

    # 2. International student at UC Berkeley -> non-CA international gets $0 UC Blue & Gold, sees international health warning
    ucb_intl = client.post(
        "/api/v1/financial/net-price",
        json={
            "institution_id": ucb["id"],
            "residency_classification": "international",
            "housing_preference": "on_campus",
            "applicant_type": "transfer",
            "degree_level": "bachelors",
            "citizenship_country": "FR",
            "gpa_4": 3.8,
            "financial_need_level": "high",
            "household_income_usd": 40000,
            "annual_budget_usd": 20000,
            "program_years": 2,
            "include_competitive_aid": False,
        },
    )
    assert ucb_intl.status_code == 200
    ucb_intl_body = ucb_intl.json()
    assert ucb_intl_body["guaranteed_aid_max_usd"] == 0.0
    assert ucb_intl_body["eligible_aid_max_usd"] == 0.0
    assert ucb_intl_body["affordability_status"] == "exceeds_budget"
    assert any("health insurance" in w.lower() for w in ucb_intl_body["warnings"])

    # 3. California resident ($55k) at UC Berkeley -> eligible for Blue & Gold + Pell, segregated to review_required_aid until cycle expiry verified
    ucb_ca = client.post(
        "/api/v1/financial/net-price",
        json={
            "institution_id": ucb["id"],
            "residency_classification": "in_state",
            "housing_preference": "with_family",
            "applicant_type": "transfer",
            "degree_level": "bachelors",
            "citizenship_country": "US",
            "residency_state": "CA",
            "gpa_4": 3.7,
            "financial_need_level": "high",
            "household_income_usd": 55000,
            "annual_budget_usd": 15000,
            "program_years": 2,
        },
    )
    assert ucb_ca.status_code == 200
    ucb_ca_body = ucb_ca.json()
    assert ucb_ca_body["guaranteed_aid_max_usd"] == 0.0
    assert any("Blue and Gold" in a["title"] for a in ucb_ca_body["review_required_aid"])


def test_phase4_international_credential_evaluation_dual_view(client):
    systems_res = client.get("/api/v1/credentials/systems")
    assert systems_res.status_code == 200
    sys_keys = {s["grading_system_key"] for s in systems_res.json()}
    for expected in ("fr_20", "ht_20", "de_abitur", "uk_alevel", "in_pct", "ib_45", "ng_waec"):
        assert expected in sys_keys

    # 1. France 14.5 / 20 -> Mention Bien (~3.70-3.89 US equiv), NEVER naive 72.5% C-
    fr_eval = client.post(
        "/api/v1/credentials/evaluate",
        json={
            "source_country_code": "FR",
            "grading_system_key": "fr_20",
            "raw_grade": "14.5",
            "destination_country_code": "US",
        },
    )
    assert fr_eval.status_code == 200
    fr_body = fr_eval.json()
    assert fr_body["conversion"]["native_record"]["classification"] == "Mention Bien"
    assert fr_body["conversion"]["informational_equivalency"]["us_4_0_point"] >= 3.7
    assert any("WES" in r["accepted_evaluation_agencies"] for r in fr_body["recognition_rules"])
    assert "NOT an official" in fr_body["advisory_disclaimer"]

    # 2. Germany Abitur 1.3 (inverted scale) -> Sehr Gut, Modified Bavarian 1.30
    de_eval = client.post(
        "/api/v1/credentials/evaluate",
        json={
            "source_country_code": "DE",
            "grading_system_key": "de_abitur",
            "raw_grade": "1.3",
            "destination_country_code": "US",
        },
    )
    assert de_eval.status_code == 200
    de_body = de_eval.json()
    assert de_body["conversion"]["native_record"]["is_inverted_scale"] is True
    assert "Sehr Gut" in de_body["conversion"]["native_record"]["classification"]
    assert de_body["conversion"]["informational_equivalency"]["us_4_0_point"] >= 3.9
    assert de_body["conversion"]["informational_equivalency"]["german_bavarian_equivalent"] == 1.3

    # 3. India Class XII -> Germany surfaces mandatory APS + Studienkolleg / JEE rule
    in_de = client.post(
        "/api/v1/credentials/evaluate",
        json={
            "source_country_code": "IN",
            "grading_system_key": "in_pct",
            "raw_grade": "89",
            "destination_country_code": "DE",
        },
    )
    assert in_de.status_code == 200
    in_body = in_de.json()
    assert "Distinction" in in_body["conversion"]["native_record"]["classification"]
    assert len(in_body["recognition_rules"]) >= 1
    assert any("APS" in agency for r in in_body["recognition_rules"] for agency in r["accepted_evaluation_agencies"])

    # 4. Nigeria WAEC C4 passes university credit standard, whereas D7 is marked non-credit failing threshold
    ng_pass = client.post(
        "/api/v1/credentials/evaluate",
        json={"source_country_code": "NG", "grading_system_key": "ng_waec", "raw_grade": "C4", "destination_country_code": "US"},
    ).json()
    assert ng_pass["conversion"]["native_record"]["is_passing"] is True

    ng_fail = client.post(
        "/api/v1/credentials/evaluate",
        json={"source_country_code": "NG", "grading_system_key": "ng_waec", "raw_grade": "D7", "destination_country_code": "US"},
    ).json()
    assert ng_fail["conversion"]["native_record"]["is_passing"] is False


def test_phase4_profile_linked_credential_evaluation(client):
    uid = uuid.uuid4().hex[:8]
    # Fresh authenticated user with no StudentProfile yet returns empty profile signal cleanly
    no_prof_headers = {"Authorization": f"Bearer mock_noprofile_{uid}@uniglobe.edu"}
    no_prof = client.get("/api/v1/credentials/profile-evaluate?destination_country=US", headers=no_prof_headers)
    assert no_prof.status_code == 200
    assert no_prof.json()["has_profile"] is False
    assert no_prof.json()["enrollments_evaluated"] == []

    headers = {"Authorization": f"Bearer mock_p4_cred_{uid}@uniglobe.edu"}

    prof_res = client.post(
        "/api/v1/profile",
        headers=headers,
        json={
            "first_name": "Nadine",
            "last_name": "Pierre",
            "country_code": "HT",
            "country_of_residence": "US",
            "applicant_type": "transfer",
            "intended_major": "Computer Science",
            "intended_degree_level": "bachelors",
        },
    )
    assert prof_res.status_code == 201

    enrollments_payload = [
        {
            "institution_name_manual": "Institution Saint-Louis de Gonzague",
            "institution_country": "HT",
            "enrollment_type": "high_school",
            "enrollment_status": "graduated",
            "cumulative_gpa": 15.5,
            "gpa_scale": 20.0,
        },
        {
            "institution_name_manual": "Université Paris-Saclay",
            "institution_country": "FR",
            "enrollment_type": "university_undergraduate",
            "enrollment_status": "attended",
            "cumulative_gpa": 14.5,
            "gpa_scale": 20.0,
        },
        {
            "institution_name_manual": "De Anza College",
            "institution_country": "US",
            "enrollment_type": "community_college",
            "enrollment_status": "attending",
            "cumulative_gpa": 3.85,
            "gpa_scale": 4.0,
        },
    ]
    for enr in enrollments_payload:
        enr_res = client.post("/api/v1/profile/enrollments", headers=headers, json=enr)
        assert enr_res.status_code == 201

    eval_res = client.get("/api/v1/credentials/profile-evaluate?destination_country=US", headers=headers)
    assert eval_res.status_code == 200
    body = eval_res.json()
    assert body["has_profile"] is True
    assert body["destination_country_code"] == "US"
    assert len(body["enrollments_evaluated"]) == 3
    by_country = {item["institution_country"]: item for item in body["enrollments_evaluated"]}
    assert by_country["HT"]["inferred_system_key"] == "ht_20"
    assert by_country["FR"]["inferred_system_key"] == "fr_20"
    assert by_country["FR"]["evaluation"]["conversion"]["native_record"]["classification"] == "Mention Bien"
    assert by_country["US"]["inferred_system_key"] == "us_4"
    assert "NOT an official" in body["advisory_disclaimer"]

    # Profile's US community college enrollment also automatically unlocks JKC eligibility on /financial/scholarships/match
    sch_res = client.post(
        "/api/v1/financial/scholarships/match",
        headers=headers,
        json={"financial_need_level": "high", "household_income_usd": 22000, "destination_country": "US"},
    )
    assert sch_res.status_code == 200
    sch_by_title = {r["title"]: r for r in sch_res.json()["results"]}
    assert sch_by_title["Jack Kent Cooke Undergraduate Transfer Scholarship"]["eligibility_status"] == "eligible"
