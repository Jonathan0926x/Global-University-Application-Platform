from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class DocumentExtractionSchema(BaseModel):
    id: UUID
    document_id: UUID
    extracted_text: str
    detected_institution: Optional[str] = None
    detected_qualification: Optional[str] = None
    detected_grading_scale: Optional[str] = None
    extracted_data_json: Dict[str, Any] = {}
    extraction_confidence: str  # high_confidence, needs_review, uncertain_extraction
    extraction_warnings: List[str] = []
    extracted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentTranslationSchema(BaseModel):
    id: UUID
    document_id: UUID
    target_language: str
    translated_text: str
    translated_data_json: Dict[str, Any] = {}
    translation_engine: str
    translation_confidence: str
    translation_disclaimer: str
    is_human_reviewed: bool
    human_reviewer_notes: Optional[str] = None
    translated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentSummarySchema(BaseModel):
    id: UUID
    profile_id: UUID
    original_filename: str
    file_type: str
    mime_type: str = "application/octet-stream"
    file_size_bytes: int
    file_sha256: str
    storage_backend: str = "local"
    is_encrypted: bool = False
    scan_status: str = "uploaded"
    scan_engine: Optional[str] = None
    scanned_at: Optional[datetime] = None
    quarantined_at: Optional[datetime] = None
    detected_language: str
    document_category: str
    uploaded_at: datetime
    has_extraction: bool = False
    has_translation: bool = False

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailSchema(BaseModel):
    id: UUID
    profile_id: UUID
    original_filename: str
    file_type: str
    mime_type: str = "application/octet-stream"
    file_size_bytes: int
    file_sha256: str
    storage_path: str
    storage_backend: str = "local"
    storage_key: Optional[str] = None
    is_encrypted: bool = False
    scan_status: str = "uploaded"
    scan_engine: Optional[str] = None
    scan_details: Optional[str] = None
    scanned_at: Optional[datetime] = None
    quarantined_at: Optional[datetime] = None
    detected_language: str
    document_category: str
    uploaded_at: datetime
    extraction: Optional[DocumentExtractionSchema] = None
    translations: List[DocumentTranslationSchema] = []

    model_config = ConfigDict(from_attributes=True)


class DocumentTranslateRequest(BaseModel):
    target_language: str = "en-US"
    allow_external_ai: bool = False


class DocumentPresignedUrlResponse(BaseModel):
    document_id: UUID
    download_url: str
    expires_at: datetime
    expires_in_seconds: int
    sha256: str
    scan_status: str
