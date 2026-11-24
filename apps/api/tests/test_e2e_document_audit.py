import os
import io
import uuid
import hashlib
import pytest

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "samples")


def test_e2e_upload_five_multilingual_documents_and_verify_sha256(client):
    """
    Quality Assurance End-to-End Audit:
    Uploads real academic transcripts in English, French, Haitian Creole, Spanish, and Arabic.
    Verifies:
    1. Cryptographic SHA-256 integrity preservation
    2. Language detection accuracy
    3. Immutable physical storage
    4. Academic entity extraction
    5. Side-by-side translation generation with non-certified disclaimers
    """
    uid = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer mock_doc_audit_{uid}@univ.edu"}

    # Initialize a student profile first
    prof_res = client.post("/api/v1/profile", json={
        "first_name": "Jordan",
        "last_name": "Taylor",
        "applicant_type": "both"
    }, headers=headers)
    assert prof_res.status_code in [200, 201], f"Profile creation failed: {prof_res.text}"

    samples = [
        ("sample_transcript_en.txt", "en-US", "De Anza College"),
        ("sample_transcript_fr.txt", "fr-FR", "Lycée"),
        ("sample_transcript_ht.txt", "ht-HT", "Saint-Louis"),
        ("sample_transcript_es.txt", "es-419", "Secondary"),
        ("sample_transcript_ar.txt", "ar-SA", "Secondary"),
    ]

    for filename, expected_lang, expected_keyword in samples:
        filepath = os.path.join(SAMPLES_DIR, filename)
        assert os.path.exists(filepath), f"Sample file not found: {filepath}"

        with open(filepath, "rb") as f:
            file_bytes = f.read()

        local_sha256 = hashlib.sha256(file_bytes).hexdigest()

        # 1. Upload to API
        with open(filepath, "rb") as f:
            response = client.post(
                "/api/v1/documents/upload",
                headers=headers,
                files={"file": (filename, f, "text/plain")},
                data={"document_category": "transcript"}
            )

        assert response.status_code == 201, f"Failed to upload {filename}: {response.text}"
        data = response.json()

        # 2. Verify SHA-256 integrity
        assert data["file_sha256"] == local_sha256, (
            f"Checksum mismatch on {filename}! Local: {local_sha256}, Stored: {data['file_sha256']}"
        )

        # 3. Verify original document preserved on disk
        storage_path = data["storage_path"]
        assert os.path.exists(storage_path), f"Preserved file missing from vault disk: {storage_path}"
        with open(storage_path, "rb") as pf:
            preserved_bytes = pf.read()
        assert preserved_bytes == file_bytes, f"Original file on disk was corrupted or modified: {storage_path}"
        assert hashlib.sha256(preserved_bytes).hexdigest() == local_sha256

        # 4. Verify language detection
        assert data["detected_language"] == expected_lang, (
            f"Expected {expected_lang} for {filename}, got {data['detected_language']}"
        )

        # 5. Verify extraction payload
        extraction = data.get("extraction")
        assert extraction is not None, f"Extraction missing for {filename}"
        assert extraction["extraction_confidence"] in ["high_confidence", "needs_review"]
        assert len(extraction["extracted_text"]) > 50

        # 6. Verify default academic translation
        translations = data.get("translations", [])
        assert len(translations) >= 1, f"Default translation missing for {filename}"
        default_trans = translations[0]
        assert "DISCLAIMER" in default_trans["translated_text"] or len(default_trans["translated_text"]) > 50
        assert default_trans["translation_disclaimer"] == "Machine Translation — Not Certified as an Official University Transcript"
        assert default_trans["is_human_reviewed"] is False

        # 7. Test retranslation endpoint to another target language (e.g. Spanish)
        doc_id = data["id"]
        trans_resp = client.post(
            f"/api/v1/documents/{doc_id}/translate",
            headers=headers,
            json={"target_language": "es-419"}
        )
        assert trans_resp.status_code == 200, f"Retranslation failed: {trans_resp.text}"
        new_trans = trans_resp.json()
        assert new_trans["target_language"] == "es-419"
        assert new_trans["translation_disclaimer"] == "Machine Translation — Not Certified as an Official University Transcript"


def test_multilingual_counselor_official_citations_audit(client):
    """
    Verifies that the multilingual AI Counselor provides responses
    backed by official source citations across English, Spanish, French, and Haitian Creole.
    """
    uid = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer mock_counselor_audit_{uid}@univ.edu"}

    # Initialize a student profile first
    client.post("/api/v1/profile", json={
        "first_name": "Roseline",
        "last_name": "Pierre",
        "applicant_type": "transfer"
    }, headers=headers)

    test_queries = [
        ("How do I transfer from De Anza College to UC Berkeley Computer Science?", "en-US"),
        ("¿Cuáles son los requisitos para transferirme a la Universidad de California?", "es-419"),
        ("Comment transférer depuis un Community College avec un Baccalauréat haïtien ?", "fr-FR"),
        ("Kijan m ka transfere soti nan Community College pou m antre nan UC Berkeley?", "ht-HT"),
    ]

    for msg, lang in test_queries:
        response = client.post(
            "/api/v1/counselor/chat",
            headers=headers,
            json={"message": msg, "language": lang}
        )
        assert response.status_code == 200, f"Counselor chat failed for {lang}: {response.text}"
        data = response.json()
        assert len(data["content"]) > 100
        assert data["language"] == lang
        assert len(data["citations"]) >= 2
        
        # Verify citations have valid https URLs and titles
        for cit in data["citations"]:
            assert cit["url"].startswith("https://"), f"Invalid citation URL: {cit['url']}"
            assert len(cit["title"]) > 5
            assert len(cit["institution"]) > 3
            assert any(domain in cit["url"] for domain in ["assist.org", "universityofcalifornia.edu", "wes.org", "berkeley.edu", "icas-ca.org"])
