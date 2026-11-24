import uuid


def test_institutions_and_application_workspaces(client):
    uid = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer mock_app_{uid}@univ.edu"}

    # 1. Initialize user profile
    profile_payload = {
        "first_name": "Maya",
        "last_name": "Lin",
        "applicant_type": "both",
        "intended_major": "Architecture"
    }
    client.post("/api/v1/profile", json=profile_payload, headers=headers)


    # 2. List institutions
    inst_res = client.get("/api/v1/institutions")
    assert inst_res.status_code == 200
    institutions = inst_res.json()
    assert len(institutions) >= 3
    berkeley = next((i for i in institutions if "Berkeley" in i["official_name"]), None)
    assert berkeley is not None

    # 3. Create Transfer Application Workspace
    transfer_app_payload = {
        "institution_id": berkeley["id"],
        "applicant_type": "transfer",
        "intended_major": "Architecture"
    }
    app_res = client.post("/api/v1/applications", json=transfer_app_payload, headers=headers)
    assert app_res.status_code == 201
    transfer_app = app_res.json()
    assert transfer_app["applicant_type"] == "transfer"
    assert transfer_app["status"] == "planning"
    assert len(transfer_app["requirements_status"]) > 0

    # Verify Transfer checklist items
    titles = [req["title"] for req in transfer_app["requirements_status"]]
    assert any("College Transcript" in t for t in titles)
    assert any("Transfer" in t for t in titles)

    # 4. Create First-Year Application Workspace
    sfsu = next((i for i in institutions if "San Francisco State" in i["official_name"]), None)
    first_year_app_payload = {
        "institution_id": sfsu["id"],
        "applicant_type": "first_year",
        "intended_major": "Computer Science"
    }
    fy_res = client.post("/api/v1/applications", json=first_year_app_payload, headers=headers)
    assert fy_res.status_code == 201
    fy_app = fy_res.json()
    assert fy_app["applicant_type"] == "first_year"

    # Verify First-Year checklist items
    fy_titles = [req["title"] for req in fy_app["requirements_status"]]
    assert any("High School" in t for t in fy_titles)

    # 5. Test Filtering by Pathway
    list_all = client.get("/api/v1/applications", headers=headers)
    assert len(list_all.json()) >= 2

    list_transfer = client.get("/api/v1/applications?applicant_type=transfer", headers=headers)
    assert len(list_transfer.json()) == 1
    assert list_transfer.json()[0]["applicant_type"] == "transfer"

    list_fy = client.get("/api/v1/applications?applicant_type=first_year", headers=headers)
    assert len(list_fy.json()) == 1
    assert list_fy.json()[0]["applicant_type"] == "first_year"
