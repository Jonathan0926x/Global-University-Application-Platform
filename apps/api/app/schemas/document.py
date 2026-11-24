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
    file_size_bytes: int
    file_sha256: str
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
    file_size_bytes: int
    file_sha256: str
    storage_path: str
    detected_language: str
    document_category: str
    uploaded_at: datetime
    extraction: Optional[DocumentExtractionSchema] = None
    translations: List[DocumentTranslationSchema] = []

    model_config = ConfigDict(from_attributes=True)


class DocumentTranslateRequest(BaseModel):
    target_language: str = "en-US"
