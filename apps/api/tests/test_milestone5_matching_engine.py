import uuid

from app.services.matching_engine import _normalize_student_gpa_to_4


def _headers(tag: str):
    return {"Authorization": f"Bearer mock_{tag}_{uuid.uuid4().hex[:8]}@uniglobe.edu"}


def _get_inst(client, query: str):
    res = client.get(f"/api/v1/institutions/search?q={query}&limit=5").json()
    assert res["total"] >= 1, f"Institution not found: {query}"
    return res["items"][0]


def test_international_gpa_normalization_preserves_context():
    # French / Haitian 20-point scale
    conv_fr, lbl_fr = _normalize_student_gpa_to_4(16.0, 20.0, "FR")
    assert 3.2 <= conv_fr <= 3.6
    assert "16.0/20" in lbl_fr

    # Percentage scale
    conv_pct, lbl_pct = _normalize_student_gpa_to_4(88.0, 100.0, "IN")
    assert 3.2 <= conv_pct <= 3.5
    assert "88.0%" in lbl_pct

    # German inverse Abitur scale (1.0 best)
    conv_de, lbl_de = _normalize_student_gpa_to_4(1.3, 6.0, "DE")
    assert conv_de == 3.7
    assert "German" in lbl_de

    # Missing GPA returns None safely (never 0.0)
    conv_none, lbl_none = _normalize_student_gpa_to_4(None, None, "US")
    assert conv_none is None
    assert lbl_none == "Not Reported"


def test_matching_preferences_persistence_and_user_isolation(client):
    h1 = _headers("m5_pref_a")
    h2 = _headers("m5_pref_b")

    # Save User A preferences
    put_res = client.put(
        "/api/v1/matching/preferences",
        headers=h1,
        json={
            "preferred_countries": ["DE", "US"],
            "preferred_institution_types": ["university"],
            "max_annual_budget": 18000,
            "weight_academic": 0.40,
            "weight_financial": 0.35,
            "weight_readiness": 0.25,
            "weight_transfer": 0.00,
        },
    )
    assert put_res.status_code == 200
    saved_a = put_res.json()
    assert saved_a["preferred_countries"] == ["DE", "US"]
    assert saved_a["max_annual_budget"] == 18000

    # User B should still get clean default preferences (no leakage from User A)
    get_b = client.get("/api/v1/matching/preferences", headers=h2)
    assert get_b.status_code == 200
    prefs_b = get_b.json()
    assert prefs_b["preferred_countries"] == ["US"]
    assert prefs_b["max_annual_budget"] is None


def test_first_year_mode_never_penalizes_transfer_dimension_and_audits_formula(client):
    h = _headers("m5_fy")
    client.post(
        "/api/v1/profile",
        headers=h,
        json={
            "first_name": "Claire",
            "last_name": "Laurent",
            "applicant_type": "first_year",
            "intended_major": "Computer Science",
            "citizenship_country": "FR",
            "target_countries": ["US", "DE"],
        },
    )
    client.post(
        "/api/v1/profile/enrollments",
        headers=h,
        json={
            "institution_name_manual": "Lycée Louis-le-Grand",
            "institution_country": "FR",
            "enrollment_type": "secondary",
            "cumulative_gpa": 17.0,
            "gpa_scale": 20.0,
        },
    )

    tum = _get_inst(client, "Munich")
    run = client.post(
        "/api/v1/matching/run",
        headers=h,
        json={
            "applicant_type": "first_year",
            "intended_major": "Computer Science",
            "max_annual_budget": 20000,
            "limit": 10,
            "persist": True,
        },
    )
    assert run.status_code == 200
    data = run.json()
    assert data["applicant_type"] == "first_year"
    assert len(data["recommendations"]) >= 1
    assert "not admission probabilities" in data["disclaimer"].lower()

    rec = client.post(
        f"/api/v1/matching/evaluate/{tum['id']}?applicant_type=first_year&intended_major=Computer Science",
        headers=h,
    ).json()

    dims = {d["key"]: d for d in rec["dimensions"]}
    # First-year MUST mark Transfer Compatibility as not_applicable with weight_applied 0 and never penalize
    assert dims["transfer"]["status"] == "not_applicable"
    assert dims["transfer"]["weight_applied"] == 0.0

    # Active weights must sum to ~1.0 and formula composite score must match weighted sum
    active_weights = sum(d["weight_applied"] for d in rec["dimensions"] if d["status"] != "not_applicable")
    assert abs(active_weights - 1.0) < 0.02
    recomputed = sum(
        d["score"] * d["weight_applied"]
        for d in rec["dimensions"]
        if d["status"] != "not_applicable"
    )
    assert abs(recomputed - rec["composite_score"]) < 0.25
    assert " + " in rec["calculation_formula"]


def test_missing_data_yields_insufficient_information_not_negative_penalty(client):
    h = _headers("m5_sparse")
    # Blank profile: no GPA, no budget, no country, no tests
    ucb = _get_inst(client, "110635")
    res = client.post(
        f"/api/v1/matching/evaluate/{ucb['id']}?applicant_type=transfer",
        headers=h,
    )
    assert res.status_code == 200
    rec = res.json()

    # Low Data Confidence Score triggers insufficient_data category cleanly
    assert rec["match_category"] == "insufficient_data"
    assert rec["data_confidence_score"] < 0.55
    assert len(rec["missing_information"]) >= 3

    dims = {d["key"]: d for d in rec["dimensions"]}
    fin_statuses = {f["status"] for f in dims["financial"]["factors"]}
    assert "insufficient_information" in fin_statuses
    # Financial dimension stays neutral (>= 50) when budget is omitted rather than failing
    assert dims["financial"]["score"] >= 50.0


def test_financial_compatibility_budget_vs_concern(client):
    ucb = _get_inst(client, "110635")

    # Tight budget ($12,000) for US public flagship -> potential_concern
    h_tight = _headers("m5_tight_budget")
    client.post(
        "/api/v1/profile",
        headers=h_tight,
        json={"first_name": "Ana", "last_name": "Costa", "applicant_type": "first_year", "citizenship_country": "BR"},
    )
    client.put(
        "/api/v1/matching/preferences",
        headers=h_tight,
        json={"max_annual_budget": 12000},
    )
    rec_tight = client.post(
        f"/api/v1/matching/evaluate/{ucb['id']}?applicant_type=first_year",
        headers=h_tight,
    ).json()
    fin_tight = next(d for d in rec_tight["dimensions"] if d["key"] == "financial")
    assert fin_tight["score"] < 45.0
    assert any(f["status"] == "potential_concern" for f in fin_tight["factors"])
    assert len(rec_tight["financial_concerns"]) >= 1

    # Generous budget ($95,000) -> verified_match and significantly higher financial score
    h_high = _headers("m5_high_budget")
    client.post(
        "/api/v1/profile",
        headers=h_high,
        json={"first_name": "Liam", "last_name": "Park", "applicant_type": "first_year", "citizenship_country": "US"},
    )
    client.put(
        "/api/v1/matching/preferences",
        headers=h_high,
        json={"max_annual_budget": 95000},
    )
    rec_high = client.post(
        f"/api/v1/matching/evaluate/{ucb['id']}?applicant_type=first_year",
        headers=h_high,
    ).json()
    fin_high = next(d for d in rec_high["dimensions"] if d["key"] == "financial")
    assert fin_high["score"] >= 85.0
    assert fin_high["score"] > fin_tight["score"] + 40.0


def test_transfer_tier1_credit_compatibility_and_compare_shortlist(client):
    h = _headers("m5_transfer")
    de_anza = _get_inst(client, "113333")
    ucla = _get_inst(client, "110662")
    ucb = _get_inst(client, "110635")
    tum = _get_inst(client, "Munich")

    client.post(
        "/api/v1/profile",
        headers=h,
        json={
            "first_name": "Mateo",
            "last_name": "Rivas",
            "applicant_type": "transfer",
            "intended_major": "Economics",
            "citizenship_country": "US",
        },
    )
    enr = client.post(
        "/api/v1/profile/enrollments",
        headers=h,
        json={
            "institution_name_manual": "De Anza College",
            "institution_country": "US",
            "enrollment_type": "community_college",
            "cumulative_gpa": 3.85,
            "gpa_scale": 4.0,
        },
    ).json()

    # Enroll in Tier-1 ASSIST-verified Economics transfer prep courses
    for code, title in [
        ("ECON 2", "Principles of Microeconomics"),
        ("ECON 1", "Principles of Macroeconomics"),
        ("MATH 1A", "Calculus I"),
    ]:
        client.post(
            f"/api/v1/profile/enrollments/{enr['id']}/courses",
            headers=h,
            json={
                "course_code": code,
                "course_name": title,
                "credit_hours": 5.0,
                "credit_type": "quarter_hour",
                "status": "completed",
            },
        )

    rec_ucla = client.post(
        f"/api/v1/matching/evaluate/{ucla['id']}?applicant_type=transfer&intended_major=Economics",
        headers=h,
    ).json()
    trans_ucla = next(d for d in rec_ucla["dimensions"] if d["key"] == "transfer")
    assert trans_ucla["status"] == "verified_match"
    assert trans_ucla["score"] >= 80.0

    # Save shortlist + verify user isolation
    save_res = client.post(
        f"/api/v1/matching/recommendations/{ucla['id']}/save?saved=true",
        headers=h,
    )
    assert save_res.status_code == 200 and save_res.json()["is_saved_by_student"] is True

    shortlist = client.get("/api/v1/matching/shortlist", headers=h).json()
    assert len(shortlist) == 1
    assert shortlist[0]["institution_id"] == ucla["id"]

    other_shortlist = client.get("/api/v1/matching/shortlist", headers=_headers("m5_other")).json()
    assert other_shortlist == []

    # Side-by-side comparison across UCLA, UC Berkeley, and TUM
    cmp_res = client.post(
        "/api/v1/matching/compare",
        headers=h,
        json={
            "institution_ids": [ucla["id"], ucb["id"], tum["id"]],
            "applicant_type": "transfer",
            "intended_major": "Economics",
        },
    )
    assert cmp_res.status_code == 200
    cmp_items = cmp_res.json()
    assert len(cmp_items) == 3
    assert {c["institution_id"] for c in cmp_items} == {ucla["id"], ucb["id"], tum["id"]}
