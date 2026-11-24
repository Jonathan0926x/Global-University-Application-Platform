from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.profile import StudentProfile
from app.models.document import Document, DocumentExtraction, DocumentTranslation
from app.schemas.document import (
    DocumentSummarySchema,
    DocumentDetailSchema,
    DocumentTranslateRequest,
    DocumentTranslationSchema,
)
from app.services.document_vault import DocumentVaultService

router = APIRouter()


@router.post("/documents/upload", response_model=DocumentDetailSchema, status_code=status.HTTP_201_CREATED, tags=["Document Vault"])
async def upload_academic_document(
    file: UploadFile = File(...),
    document_category: str = Form("transcript"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile must be created before uploading academic documents."
        )

    # 1. Store original file immutably in sandboxed vault & get SHA-256 checksum
    storage_path, sha256_hash, file_size, file_ext = await DocumentVaultService.store_original_file(
        str(profile.id), file
    )

    # 2. Extract Document Intelligence & entities
    content_bytes = await file.read()
    extraction_data = DocumentVaultService.extract_document_intelligence(
        file.filename or "uploaded_document",
        content_bytes,
        file_ext
    )

    # 3. Create Document Record
    doc = Document(
        profile_id=profile.id,
        original_filename=file.filename or "uploaded_document",
        file_type=file_ext,
        file_size_bytes=file_size,
        file_sha256=sha256_hash,
        storage_path=storage_path,
        detected_language=extraction_data["detected_language"],
        document_category=document_category
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 4. Save Extracted Representation
    extraction = DocumentExtraction(
        document_id=doc.id,
        extracted_text=extraction_data["extracted_text"],
        detected_institution=extraction_data["detected_institution"],
        detected_qualification=extraction_data["detected_qualification"],
        detected_grading_scale=extraction_data["detected_grading_scale"],
        extracted_data_json=extraction_data["extracted_data"],
        extraction_confidence=extraction_data["extraction_confidence"],
        extraction_warnings=extraction_data["extraction_warnings"]
    )
    db.add(extraction)

    # 5. Generate Default Translation to English (or target language)
    translation_data = DocumentVaultService.generate_academic_translation(extraction_data, "en-US")
    translation = DocumentTranslation(
        document_id=doc.id,
        target_language=translation_data["target_language"],
        translated_text=translation_data["translated_text"],
        translated_data_json=translation_data["translated_data"],
        translation_engine=translation_data["translation_engine"],
        translation_confidence=translation_data["translation_confidence"],
        translation_disclaimer=translation_data["translation_disclaimer"],
        is_human_reviewed=False
    )
    db.add(translation)

    db.commit()
    db.refresh(doc)

    return doc


@router.get("/documents", response_model=List[DocumentSummarySchema], tags=["Document Vault"])
def list_student_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        return []

    docs = db.query(Document).filter(
        Document.profile_id == profile.id,
        Document.is_archived == False
    ).order_by(Document.uploaded_at.desc()).all()

    results = []
    for d in docs:
        results.append(DocumentSummarySchema(
            id=d.id,
            profile_id=d.profile_id,
            original_filename=d.original_filename,
            file_type=d.file_type,
            file_size_bytes=d.file_size_bytes,
            file_sha256=d.file_sha256,
            detected_language=d.detected_language,
            document_category=d.document_category,
            uploaded_at=d.uploaded_at,
            has_extraction=d.extraction is not None,
            has_translation=len(d.translations) > 0
        ))
    return results


@router.get("/documents/{document_id}", response_model=DocumentDetailSchema, tags=["Document Vault"])
def get_document_details(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.profile_id == profile.id
    ).first()

    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic document not found")

    return doc


@router.post("/documents/{document_id}/translate", response_model=DocumentTranslationSchema, tags=["Document Vault"])
def translate_document(
    document_id: UUID,
    request: DocumentTranslateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.profile_id == profile.id
    ).first()

    if not doc or not doc.extraction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document extraction not found")

    # Generate academic translation with strict provenance metadata
    extraction_dict = {
        "detected_language": doc.detected_language,
        "detected_institution": doc.extraction.detected_institution,
        "detected_qualification": doc.extraction.detected_qualification,
        "extracted_data": doc.extraction.extracted_data_json,
    }

    translation_data = DocumentVaultService.generate_academic_translation(extraction_dict, request.target_language)

    translation = DocumentTranslation(
        document_id=doc.id,
        target_language=translation_data["target_language"],
        translated_text=translation_data["translated_text"],
        translated_data_json=translation_data["translated_data"],
        translation_engine=translation_data["translation_engine"],
        translation_confidence=translation_data["translation_confidence"],
        translation_disclaimer=translation_data["translation_disclaimer"],
        is_human_reviewed=False
    )
    db.add(translation)
    db.commit()
    db.refresh(translation)

    return translation
