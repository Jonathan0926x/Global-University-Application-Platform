import io
import uuid
from datetime import date, datetime, timedelta, timezone

from app.ingestion.rag_indexer import sync_rag_knowledge_base
from app.models.provenance import DataQualityFlag
from app.models.rag import RagKnowledgeChunk, ScholarshipProgram
from app.models.requirements import Deadline
from app.services.embeddings import embed_text


def _headers(tag: str):
    return {"Authorization": f"Bearer mock_{tag}_{uuid.uuid4().hex[:8]}@uniglobe.edu"}


def _get_inst(client, query: str):
    res = client.get(f"/api/v1/institutions/search?q={query}&limit=5").json()
    assert res["total"] >= 1, f"Institution not found: {query}"
    return res["items"][0]


def test_pgvector_rag_indexer_idempotent_and_hybrid_retrieval(client, db):
    # Ensure RAG chunks & scholarships exist and re-sync is idempotent (0 duplicates)
    first_res = sync_rag_knowledge_base(db, institution_limit=100)
    second_res = sync_rag_knowledge_base(db, institution_limit=100)
    assert sum(second_res.values()) == 0
    assert db.query(RagKnowledgeChunk).count() >= 100
    assert db.query(ScholarshipProgram).count() >= 8

    # Hybrid search for MIT international aid returns MIT Need-Blind Scholarship via pgvector + FTS
    h = _headers("m6_search")
    mit = _get_inst(client, "166683")
    res = client.post(
        "/api/v1/counselor/rag/search",
        headers=h,
        json={"query": "MIT international financial aid need blind scholarship", "institution_id": mit["id"], "limit": 6},
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 2
    assert any("MIT Need-Blind" in it["title"] for it in items)
    assert all(it["epistemic_tier"] in ("official", "historical") for it in items)
    assert all(it["source_type"] for it in items)
    assert any(it["vector_score"] > 0.0 for it in items)


def test_multilingual_arabic_spanish_french_haitian_queries_and_qualification_preservation(client):
    h = _headers("m6_multi")
    client.post(
        "/api/v1/profile",
        headers=h,
        json={
            "first_name": "Nadine",
            "last_name": "Jean",
            "applicant_type": "first_year",
            "intended_major": "Computer Science",
            "country_of_residence": "HT",
        },
    )
    client.post(
        "/api/v1/profile/enrollments",
        headers=h,
        json={
            "institution_name_manual": "Institution Saint-Louis de Gonzague",
            "institution_country": "HT",
            "enrollment_type": "secondary",
            "cumulative_gpa": 16.5,
            "gpa_scale": 20.0,
        },
    )

    # 1. Arabic RTL query on MIT scholarships & requirements
    ar_res = client.post(
        "/api/v1/counselor/chat",
        headers=h,
        json={"message": "ما هي متطلبات القبول والمنح الدراسية للطلاب الدوليين في MIT؟", "language": "ar-SA"},
    )
    assert ar_res.status_code == 200
    ar_data = ar_res.json()
    assert ar_data["language"] == "ar-SA"
    assert "الحقائق المؤسسية" in ar_data["content"]
    assert any("MIT" in c["institution"] or "Massachusetts" in c["institution"] for c in ar_data["citations"])
    assert any(c["source_type"] == "official_aid_program" for c in ar_data["citations"])

    # 2. Haitian Creole query preserving 16.5/20 scale and Baccalauréat terminology
    ht_res = client.post(
        "/api/v1/counselor/chat",
        headers=h,
        json={"message": "Ki bous oswa frè pou MIT si m gen yon Baccalauréat Ayisyen?", "language": "ht-HT"},
    )
    assert ht_res.status_code == 200
    ht_data = ht_res.json()
    assert ht_data["language"] == "ht-HT"
    assert "16.5/20" in ht_data["content"]
    assert "Baccalauréat" in ht_data["content"]

    # 3. French query on Sorbonne / TUM
    fr_res = client.post(
        "/api/v1/counselor/chat",
        headers=h,
        json={"message": "Quelles sont les exigences et les frais pour Technical University of Munich ?", "language": "fr-FR"},
    )
    assert fr_res.status_code == 200
    assert fr_res.json()["language"] == "fr-FR"
    assert "Munich" in fr_res.json()["content"]

    # 4. Spanish query on UC Berkeley
    es_res = client.post(
        "/api/v1/counselor/chat",
        headers=h,
        json={"message": "¿Cuáles son los requisitos de transferencia y costos en UC Berkeley?", "language": "es-419"},
    )
    assert es_res.status_code == 200
    assert es_res.json()["language"] == "es-419"
    assert "Datos Oficiales" in es_res.json()["content"]


def test_contextual_followup_retains_institution_and_profile_transfer_workflow(client):
    h = _headers("m6_followup")
    de_anza = _get_inst(client, "113333")
    ucla = _get_inst(client, "110662")

    client.post(
        "/api/v1/profile",
        headers=h,
        json={"first_name": "Diego", "last_name": "Cruz", "applicant_type": "transfer", "intended_major": "Economics"},
    )
    enr = client.post(
        "/api/v1/profile/enrollments",
        headers=h,
        json={
            "institution_id": de_anza["id"],
            "institution_name_manual": "De Anza College",
            "institution_country": "US",
            "enrollment_type": "community_college",
            "cumulative_gpa": 3.85,
            "gpa_scale": 4.0,
        },
    ).json()
    client.post(
        f"/api/v1/profile/enrollments/{enr['id']}/courses",
        headers=h,
        json={"course_code": "ECON 2", "course_name": "Principles of Microeconomics", "credit_hours": 4.0, "credit_type": "quarter_hour", "status": "completed"},
    )

    # Turn 1 explicitly names UCLA
    turn1 = client.post(
        "/api/v1/counselor/chat",
        headers=h,
        json={"message": "How do Economics transfer requirements work at UCLA?", "language": "en-US"},
    ).json()
    conv_id = turn1["conversation_id"]
    assert turn1["epistemic_breakdown"]["context_institution_id"] == ucla["id"]

    # Turn 2 follow-up uses pronoun ("its tuition and deadlines and my credits") WITHOUT naming UCLA
    turn2 = client.post(
        "/api/v1/counselor/chat",
        headers=h,
        json={
            "conversation_id": conv_id,
            "message": "What about its tuition, deadlines, and how my credits transfer there?",
            "language": "en-US",
        },
    ).json()
    assert turn2["conversation_id"] == conv_id
    eb2 = turn2["epistemic_breakdown"]
    assert eb2["context_institution_id"] == ucla["id"]
    assert any("Los Angeles" in c["institution"] or "UCLA" in c["title"] for c in turn2["citations"])
    # Verifies Milestone 4 live transfer credit link & Milestone 5 workflow suggestion
    assert "Tier 1" in turn2["content"]
    assert any(wf["workflow_type"] == "matching" for wf in eb2["suggested_workflows"])
    assert any(wf["workflow_type"] == "transfer" for wf in eb2["suggested_workflows"])


def test_missing_uncurated_conflicting_and_outdated_detection(client):
    from app.database import SessionLocal

    h = _headers("m6_conflicts")
    client.post("/api/v1/profile", headers=h, json={"first_name": "Test", "last_name": "Audit", "applicant_type": "transfer"})

    # Query uncurated institution WITHOUT explicit institution_id (tests free-text name resolution!)
    res = client.post(
        "/api/v1/counselor/chat",
        headers=h,
        json={"message": "What are the verified transfer scholarships and requirements for Harvard University?", "language": "en-US"},
    )
    assert res.status_code == 200
    eb = res.json()["epistemic_breakdown"]
    assert eb["context_institution_name"] == "Harvard University"
    # Must explicitly admit uncurated requirements and missing scholarship info instead of fabricating
    assert any("not yet verified" in m.lower() for m in eb["missing_or_conflicting"])
    assert any("scholarship" in m.lower() for m in eb["missing_or_conflicting"])

    # Also test passed deadline & conflict chunk surfacing using real DB session visible to client
    mit = _get_inst(client, "166683")
    fl_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    with SessionLocal() as s:
        s.add(
            DataQualityFlag(
                id=fl_id,
                entity_type="institution",
                entity_id=mit["id"],
                flag_type="conflicting_data",
                severity="warning",
                description="Test cross-source tuition discrepancy between IPEDS and legacy cache.",
                resolved=False,
            )
        )
        s.add(
            RagKnowledgeChunk(
                id=chunk_id,
                institution_id=mit["id"],
                country_code="US",
                chunk_type="deadline",
                epistemic_tier="official",
                source_type="official_institutional",
                applicant_type="first_year",
                title="MIT Legacy Past Deadline Audit Check",
                content_text="Historical MIT deadline 2024-01-01 test expired cycle entry.",
                source_name="MIT Admissions Audit",
                source_url="https://mitadmissions.org/apply/",
                verified_at=datetime.now(timezone.utc) - timedelta(days=400),
                is_outdated=True,
                has_conflict=True,
                content_hash=uuid.uuid4().hex,
                embedding=embed_text("MIT deadline tuition"),
            )
        )
        s.commit()

    try:
        mit_res = client.post(
            "/api/v1/counselor/chat",
            headers=h,
            json={"message": "Check MIT deadline and tuition conflicts", "institution_id": mit["id"]},
        ).json()
        flags_out = " ".join(mit_res["epistemic_breakdown"]["missing_or_conflicting"]).lower()
        assert "conflict" in flags_out
    finally:
        with SessionLocal() as s:
            s.query(RagKnowledgeChunk).filter(RagKnowledgeChunk.id == chunk_id).delete()
            s.query(DataQualityFlag).filter(DataQualityFlag.id == fl_id).delete()
            s.commit()


def test_student_document_and_conversation_isolation(client):
    h_a = _headers("m6_iso_a")
    h_b = _headers("m6_iso_b")

    client.post("/api/v1/profile", headers=h_a, json={"first_name": "Alice", "last_name": "Secret", "applicant_type": "first_year"})
    client.post("/api/v1/profile", headers=h_b, json={"first_name": "Bob", "last_name": "Other", "applicant_type": "first_year"})

    # User A uploads a confidential transcript
    doc_bytes = b"Academic Transcript - Alice Secret - Lycee Toussaint - Average 18.5/20"
    up_res = client.post(
        "/api/v1/documents/upload",
        headers=h_a,
        files={"file": ("alice_secret_transcript.txt", io.BytesIO(doc_bytes), "text/plain")},
        data={"document_category": "transcript"},
    )
    assert up_res.status_code == 201

    # User A chats -> sees own confidential filename; User B cannot see Alice's filename or conversation
    msg_a = client.post(
        "/api/v1/counselor/chat",
        headers=h_a,
        json={"message": "How does my uploaded transcript align with MIT?"},
    ).json()
    assert "alice_secret_transcript.txt" in msg_a["content"]

    msg_b = client.post(
        "/api/v1/counselor/chat",
        headers=h_b,
        json={"message": "What documents or transcripts are uploaded for Alice Secret toward MIT?"},
    ).json()
    assert "alice_secret_transcript.txt" not in msg_b["content"]

    # Cross-user conversation get / follow-up / delete MUST return 404
    conv_a = msg_a["conversation_id"]
    assert client.get(f"/api/v1/counselor/conversations/{conv_a}", headers=h_b).status_code == 404
    assert (
        client.post(
            "/api/v1/counselor/chat",
            headers=h_b,
            json={"conversation_id": conv_a, "message": "Repeat previous answer"},
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/counselor/conversations/{conv_a}", headers=h_b).status_code == 404

    # Rag search only returns shared institutional chunks, never student vault docs
    rag_res = client.post(
        "/api/v1/counselor/rag/search",
        headers=h_b,
        json={"query": "alice_secret_transcript 18.5"},
    ).json()
    assert all("alice_secret_transcript" not in r["content_text"] for r in rag_res)
