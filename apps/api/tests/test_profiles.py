import uuid


def test_auth_session(client):
    uid = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer mock_test_{uid}@univ.edu"}
    response = client.get("/api/v1/session", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["user"]["email"] == f"test_{uid}@univ.edu"


def test_create_and_get_profile(client):
    uid = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer mock_firstyear_{uid}@global.edu"}
    
    # 1. Profile initially not found
    get_res = client.get("/api/v1/profile", headers=headers)
    assert get_res.status_code == 404

    # 2. Create First-Year Profile
    payload = {
        "first_name": "Jean-Claude",
        "last_name": "Augustin",
        "name_format": "western",
        "date_of_birth": "2006-05-14",
        "country_code": "HT",
        "country_of_residence": "HT",
        "applicant_type": "first_year",
        "intended_major": "Computer Science",
        "intended_enrollment_term": "Fall 2027",
        "intended_enrollment_year": 2027
    }
    create_res = client.post("/api/v1/profile", json=payload, headers=headers)
    assert create_res.status_code == 201
    profile_data = create_res.json()
    assert profile_data["first_name"] == "Jean-Claude"
    assert profile_data["applicant_type"] == "first_year"
    assert profile_data["profile_completion_pct"] > 0

    # 3. Add Secondary School Enrollment
    enroll_payload = {
        "institution_name_manual": "Institution Saint-Louis de Gonzague",
        "institution_country": "HT",
        "institution_city": "Port-au-Prince",
        "enrollment_type": "secondary",
        "degree_type": "Baccalauréat haïtien",
        "cumulative_gpa": 3.8,
        "is_current_institution": True
    }
    enroll_res = client.post("/api/v1/profile/enrollments", json=enroll_payload, headers=headers)
    assert enroll_res.status_code == 201
    enrollment_id = enroll_res.json()["id"]

    # 4. Add Course line item
    course_payload = {
        "course_name": "Mathématiques et Sciences Physiques",
        "course_code": "MATH-NS4",
        "grade": "16/20",
        "credit_hours": 4.0,
        "status": "completed"
    }
    course_res = client.post(f"/api/v1/profile/enrollments/{enrollment_id}/courses", json=course_payload, headers=headers)
    assert course_res.status_code == 201
    assert course_res.json()["course_name"] == "Mathématiques et Sciences Physiques"


def test_transfer_student_flow(client):
    uid = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer mock_transfer_{uid}@cc.edu"}

    # 1. Create Transfer Profile
    payload = {
        "first_name": "Sarah",
        "last_name": "Chen",
        "applicant_type": "transfer",
        "intended_major": "Data Science",
        "intended_enrollment_term": "Fall 2027",
        "country_code": "US",
        "country_of_residence": "US"
    }
    create_res = client.post("/api/v1/profile", json=payload, headers=headers)
    assert create_res.status_code == 201
    assert create_res.json()["applicant_type"] == "transfer"

    # 2. Add Community College Enrollment
    enroll_payload = {
        "institution_name_manual": "De Anza College",
        "institution_country": "US",
        "institution_city": "Cupertino",
        "enrollment_type": "community_college",
        "degree_type": "Associate Degree for Transfer (ADT)",
        "cumulative_gpa": 3.85,
        "total_credits_earned": 45.0,
        "is_current_institution": True
    }
    enroll_res = client.post("/api/v1/profile/enrollments", json=enroll_payload, headers=headers)
    assert enroll_res.status_code == 201

