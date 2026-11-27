from datetime import datetime, timedelta, timezone
import hashlib
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, status, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.core.security_logging import log_security_event
from app.database import get_db
from app.models.document import Document, DocumentExtraction, DocumentTranslation
from app.models.profile import StudentProfile
from app.models.user import User
from app.schemas.document import (
    DocumentDetailSchema,
    DocumentPresignedUrlResponse,
    DocumentSummarySchema,
    DocumentTranslateRequest,
    DocumentTranslationSchema,
)
from app.services.document_vault import (
    DocumentVaultService,
    LocalVaultStorageProvider,
    get_vault_storage_provider,
)

router = APIRouter()


@router.post("/documents/upload", response_model=DocumentDetailSchema, status_code=status.HTTP_201_CREATED, tags=["Document Vault"])
async def upload_academic_document(
    file: UploadFile = File(...),
    document_category: str = Form("transcript"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile must be created before uploading academic documents.",
        )

    ingested = await DocumentVaultService.validate_and_ingest_file(str(profile.id), file)

    doc = Document(
        profile_id=profile.id,
        original_filename=ingested["safe_filename"],
        file_type=ingested["file_ext"],
        mime_type=ingested["mime_type"],
        file_size_bytes=ingested["file_size_bytes"],
        file_sha256=ingested["file_sha256"],
        storage_path=ingested["storage_path"],
        storage_backend=ingested["storage_backend"],
        storage_key=ingested["storage_key"],
        is_encrypted=ingested["is_encrypted"],
        scan_status=ingested["scan_status"],
        scan_engine=ingested["scan_engine"],
        scan_details=ingested["scan_details"],
        scanned_at=ingested["scanned_at"],
        quarantined_at=ingested["quarantined_at"],
        detected_language="en-US",
        document_category=document_category,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Only clean-scanned files undergo extraction and translation!
    if doc.scan_status == "scan_clean":
        extraction_data = DocumentVaultService.extract_document_intelligence(
            doc.original_filename,
            ingested["content_bytes"],
            doc.file_type,
        )
        doc.detected_language = extraction_data["detected_language"]
        extraction = DocumentExtraction(
            document_id=doc.id,
            extracted_text=extraction_data["extracted_text"],
            detected_institution=extraction_data["detected_institution"],
            detected_qualification=extraction_data["detected_qualification"],
            detected_grading_scale=extraction_data["detected_grading_scale"],
            extracted_data_json=extraction_data["extracted_data"],
            extraction_confidence=extraction_data["extraction_confidence"],
            extraction_warnings=extraction_data["extraction_warnings"],
        )
        db.add(extraction)

        translation_data = DocumentVaultService.generate_academic_translation(extraction_data, "en-US")
        translation = DocumentTranslation(
            document_id=doc.id,
            target_language=translation_data["target_language"],
            translated_text=translation_data["translated_text"],
            translated_data_json=translation_data["translated_data"],
            translation_engine=translation_data["translation_engine"],
            translation_confidence=translation_data["translation_confidence"],
            translation_disclaimer=translation_data["translation_disclaimer"],
            is_human_reviewed=False,
        )
        db.add(translation)
        db.commit()
        db.refresh(doc)

    log_security_event(
        "vault_upload",
        doc.scan_status,
        actor_user_id=str(current_user.id),
        resource_type="document",
        resource_id=str(doc.id),
        details={"scan_status": doc.scan_status, "backend": doc.storage_backend, "size": doc.file_size_bytes},
    )
    return doc


@router.get("/documents", response_model=List[DocumentSummarySchema], tags=["Document Vault"])
def list_student_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        return []

    docs = (
        db.query(Document)
        .filter(
            Document.profile_id == profile.id,
            Document.is_archived == False,
        )
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    results = []
    for d in docs:
        results.append(
            DocumentSummarySchema(
                id=d.id,
                profile_id=d.profile_id,
                original_filename=d.original_filename,
                file_type=d.file_type,
                mime_type=d.mime_type or "application/octet-stream",
                file_size_bytes=d.file_size_bytes,
                file_sha256=d.file_sha256,
                storage_backend=d.storage_backend or "local",
                is_encrypted=bool(d.is_encrypted),
                scan_status=d.scan_status or "uploaded",
                scan_engine=d.scan_engine,
                scanned_at=d.scanned_at,
                quarantined_at=d.quarantined_at,
                detected_language=d.detected_language,
                document_category=d.document_category,
                uploaded_at=d.uploaded_at,
                has_extraction=d.extraction is not None,
                has_translation=len(d.translations) > 0,
            )
        )
    return results


@router.get("/documents/{document_id}", response_model=DocumentDetailSchema, tags=["Document Vault"])
def get_document_details(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.profile_id == profile.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic document not found")

    return doc


@router.get(
    "/documents/{document_id}/presigned-url",
    response_model=DocumentPresignedUrlResponse,
    tags=["Document Vault"],
)
def get_document_presigned_download_url(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.profile_id == profile.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic document not found")

    DocumentVaultService.assert_document_accessible(doc)

    ttl = max(30, min(900, int(settings.VAULT_PRESIGNED_TTL_SECONDS)))
    provider = get_vault_storage_provider()
    url = provider.generate_presigned_download_url(
        document_id=str(doc.id),
        profile_id=str(profile.id),
        storage_key=doc.storage_key or doc.storage_path,
        original_filename=doc.original_filename,
        ttl_seconds=ttl,
    )
    log_security_event(
        "vault_presigned_url",
        "issued",
        actor_user_id=str(current_user.id),
        resource_type="document",
        resource_id=str(doc.id),
        details={"ttl": ttl, "backend": provider.backend_name},
    )
    return DocumentPresignedUrlResponse(
        document_id=doc.id,
        download_url=url,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl),
        expires_in_seconds=ttl,
        sha256=doc.file_sha256,
        scan_status=doc.scan_status,
    )


@router.get("/documents/{document_id}/download", tags=["Document Vault"])
def download_student_document(
    document_id: UUID,
    expires: Optional[int] = Query(None),
    sig: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.profile_id == profile.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic document not found")

    if expires is not None or sig is not None:
        if expires is None or not sig or not LocalVaultStorageProvider.verify_signed_download(
            str(doc.id), str(profile.id), int(expires), sig
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Pre-signed download link is expired or invalid.",
            )

    DocumentVaultService.assert_document_accessible(doc)

    provider = get_vault_storage_provider()
    raw_bytes = provider.get_bytes(doc.storage_key or "", doc.storage_path)
    actual_sha = hashlib.sha256(raw_bytes).hexdigest()
    if actual_sha != doc.file_sha256:
        log_security_event(
            "vault_integrity_mismatch",
            "blocked",
            actor_user_id=str(current_user.id),
            resource_type="document",
            resource_id=str(doc.id),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document SHA-256 integrity verification failed.",
        )

    return Response(
        content=raw_bytes,
        media_type=doc.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{doc.original_filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "X-Document-SHA256": doc.file_sha256,
        },
    )


@router.post("/documents/{document_id}/translate", response_model=DocumentTranslationSchema, tags=["Document Vault"])
def translate_document(
    document_id: UUID,
    request: DocumentTranslateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.profile_id == profile.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Academic document not found")

    DocumentVaultService.assert_document_accessible(doc)
    if not doc.extraction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document extraction not found")

    extraction_dict = {
        "detected_language": doc.detected_language,
        "detected_institution": doc.extraction.detected_institution,
        "detected_qualification": doc.extraction.detected_qualification,
        "extracted_data": doc.extraction.extracted_data_json,
    }

    translation_data = DocumentVaultService.generate_academic_translation(
        extraction_dict,
        request.target_language,
        allow_external_ai=request.allow_external_ai,
    )

    translation = DocumentTranslation(
        document_id=doc.id,
        target_language=translation_data["target_language"],
        translated_text=translation_data["translated_text"],
        translated_data_json=translation_data["translated_data"],
        translation_engine=translation_data["translation_engine"],
        translation_confidence=translation_data["translation_confidence"],
        translation_disclaimer=translation_data["translation_disclaimer"],
        is_human_reviewed=False,
    )
    db.add(translation)
    db.commit()
    db.refresh(translation)

    return translation
