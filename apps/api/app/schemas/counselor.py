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
    source_type: Optional[str] = "official_institutional"
    epistemic_tier: Optional[str] = "official"  # official | historical | ai_interpretation | student_vault
    retrieval_score: Optional[float] = None


class WorkflowSuggestionSchema(BaseModel):
    label: str
    href: str
    workflow_type: str  # matching | transfer | university | documents | requirements


class EpistemicBreakdownSchema(BaseModel):
    official_facts: List[str] = []
    historical_facts: List[str] = []
    ai_interpretation: List[str] = []
    missing_or_conflicting: List[str] = []
    student_context_used: List[str] = []
    context_institution_id: Optional[str] = None
    context_institution_name: Optional[str] = None
    context_applicant_type: Optional[str] = None
    retrieval_stats: Dict[str, Any] = {}
    suggested_workflows: List[WorkflowSuggestionSchema] = []


class CounselorMessageSchema(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str  # user or assistant
    content: str
    language: str
    citations: List[CitationSchema] = []
    epistemic_breakdown: Optional[Dict[str, Any]] = None
    disclaimer: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CounselorConversationSchema(BaseModel):
    id: UUID
    profile_id: UUID
    title: str
    primary_language: str
    active_institution_id: Optional[UUID] = None
    active_applicant_type: Optional[str] = None
    active_topic: Optional[str] = None
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


class RagSearchRequest(BaseModel):
    query: str
    institution_id: Optional[UUID] = None
    applicant_type: Optional[str] = None
    limit: int = 6


class RagSearchResultItem(BaseModel):
    chunk_id: UUID
    institution_id: Optional[UUID] = None
    country_code: Optional[str] = None
    chunk_type: str
    epistemic_tier: str
    source_type: str
    title: str
    content_text: str
    source_name: str
    source_url: Optional[str] = None
    verified_at: Optional[datetime] = None
    is_outdated: bool = False
    has_conflict: bool = False
    hybrid_score: float
    vector_score: float
    fts_score: float
