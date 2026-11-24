import uuid
import io
from app.core.i18n import get_language, is_rtl, GLOBAL_LANGUAGES


def test_language_registry_bcp47():
    # Verify core languages are registered
    en = get_language("en-US")
    assert en.tag == "en-US"
    assert en.direction == "ltr"
    assert en.tier == "fully_supported"

    # Verify Haitian Creole
    ht = get_language("ht-HT")
    assert ht.tag == "ht-HT"
    assert ht.iso639_1 == "ht"
    assert ht.native_name == "Kreyòl Ayisyen"
    assert ht.tier == "fully_supported"

    # Verify Arabic RTL
    ar = get_language("ar-SA")
    assert ar.direction == "rtl"
    assert is_rtl("ar-SA") is True
    assert is_rtl("en-US") is False


def test_user_preferences_persistence(client):
    uid = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer mock_pref_{uid}@univ.edu"}

    # 1. Fetch initial default preferences
    get_res = client.get("/api/v1/preferences", headers=headers)
    assert get_res.status_code == 200
    pref = get_res.json()
    assert pref["preferred_language"] in ["en", "en-US"]
    assert pref["display_currency"] == "USD"

    # 2. Update preferences with Haitian Creole and Haitian Gourde
    update_payload = {
        "preferred_language": "ht-HT",
        "regional_locale": "ht-HT",
        "display_currency": "HTG",
        "calendar_system": "gregory"
    }
    put_res = client.put("/api/v1/preferences", json=update_payload, headers=headers)
    assert put_res.status_code == 200
    updated_pref = put_res.json()
    assert updated_pref["preferred_language"] == "ht-HT"
    assert updated_pref["display_currency"] == "HTG"

    # 3. Verify persistence
    verify_res = client.get("/api/v1/preferences", headers=headers)
    assert verify_res.status_code == 200
    assert verify_res.json()["preferred_language"] == "ht-HT"


def test_multilingual_counselor_reasoning(client):
    uid = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer mock_counselor_{uid}@univ.edu"}

    # Initialize profile
    client.post("/api/v1/profile", json={
        "first_name": "Roseline",
        "last_name": "Pierre",
        "applicant_type": "transfer"
    }, headers=headers)

    # Ask in Haitian Creole
    query_payload = {
        "message": "Kijan mwen ka transfere soti nan yon community college pou ale nan UC Berkeley si mwen gen yon Baccalauréat Ayisyen?",
        "language": "ht-HT"
    }
    chat_res = client.post("/api/v1/counselor/chat", json=query_payload, headers=headers)
    assert chat_res.status_code == 200
    answer = chat_res.json()
    assert answer["role"] == "assistant"
    assert answer["language"] == "ht-HT"
    assert "Community College" in answer["content"]
    assert len(answer["citations"]) >= 2

    # Citations must preserve official university source links
    urls = [c["url"] for c in answer["citations"]]
    assert any("assist.org" in u for u in urls)
    assert any("universityofcalifornia.edu" in u for u in urls)

    # Disclaimers must be present
    assert "AI Interpretation" in answer["disclaimer"]


def test_document_vault_preservation_and_translation(client):
    uid = uuid.uuid4().hex[:8]
    headers = {"Authorization": f"Bearer mock_vault_{uid}@univ.edu"}

    # Initialize profile
    client.post("/api/v1/profile", json={
        "first_name": "Marc",
        "last_name": "Antoine",
        "applicant_type": "both"
    }, headers=headers)

    # Simulate transcript upload
    file_content = b"Institution Saint-Louis de Gonzague. Releve de notes Baccalaureat haitien. Mathematiques: 16/20, Sciences Physiques: 15/20."
    file_tuple = ("Bulletin_Notes_Bac_Haiti.txt", io.BytesIO(file_content), "text/plain")

    upload_res = client.post(
        "/api/v1/documents/upload",
        files={"file": file_tuple},
        data={"document_category": "transcript"},
        headers=headers
    )
    assert upload_res.status_code == 201
    doc = upload_res.json()

    # 1. Original Document Preservation Checks
    assert doc["original_filename"] == "Bulletin_Notes_Bac_Haiti.txt"
    assert doc["file_type"] == "txt"
    assert len(doc["file_sha256"]) == 64  # SHA-256 hex string

    # 2. Extracted Representation Checks
    assert doc["extraction"] is not None
    assert "Saint-Louis de Gonzague" in doc["extraction"]["detected_institution"]
    assert "Baccalauréat haïtien" in doc["extraction"]["detected_qualification"]
    assert doc["extraction"]["extraction_confidence"] in ["high_confidence", "needs_review"]

    # 3. Translation Representation Checks
    assert len(doc["translations"]) > 0
    translation = doc["translations"][0]
    assert translation["target_language"] == "en-US"
    assert "Machine Translation" in translation["translation_disclaimer"]
    assert translation["is_human_reviewed"] is False

    # 4. Generate translation to French
    trans_res = client.post(
        f"/api/v1/documents/{doc['id']}/translate",
        json={"target_language": "fr-FR"},
        headers=headers
    )
    assert trans_res.status_code == 200
    fr_trans = trans_res.json()
    assert fr_trans["target_language"] == "fr-FR"
    assert "Machine Translation" in fr_trans["translation_disclaimer"]
