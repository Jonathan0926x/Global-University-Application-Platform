from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class CitationSchema(BaseModel):
    title: str
    url: str
    institution: str
    verified_at: str
    summary: Optional[str] = None


class CounselorMessageSchema(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str  # user or assistant
    content: str
    language: str
    citations: List[CitationSchema] = []
    disclaimer: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CounselorConversationSchema(BaseModel):
    id: UUID
    profile_id: UUID
    title: str
    primary_language: str
    created_at: datetime
    updated_at: datetime
    messages: List[CounselorMessageSchema] = []

    model_config = ConfigDict(from_attributes=True)


class CounselorQueryRequest(BaseModel):
    message: str
    conversation_id: Optional[UUID] = None
    language: Optional[str] = None  # Student preferred language BCP 47
    institution_id: Optional[UUID] = None
    applicant_type: Optional[str] = None
