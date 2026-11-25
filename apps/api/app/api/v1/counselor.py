from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.profile import StudentProfile
from app.models.counselor import CounselorConversation, CounselorMessage
from app.schemas.counselor import (
    CounselorQueryRequest,
    CounselorMessageSchema,
    CounselorConversationSchema,
    RagSearchRequest,
    RagSearchResultItem,
)
from app.services.counselor import MultilingualCounselorService, retrieve_grounded_chunks

router = APIRouter()


@router.post("/counselor/chat", response_model=CounselorMessageSchema, status_code=status.HTTP_200_OK, tags=["AI Counselor"])
def chat_with_admissions_counselor(
    request: CounselorQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile must exist to converse with the AI admissions counselor.",
        )

    # 1. Resolve or Create Conversation Thread (strictly scoped by profile_id)
    conversation = None
    if request.conversation_id:
        conversation = (
            db.query(CounselorConversation)
            .filter(
                CounselorConversation.id == request.conversation_id,
                CounselorConversation.profile_id == profile.id,
            )
            .first()
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found for this student profile.",
            )

    preferred_lang = request.language or current_user.preferred_language or "en-US"

    if not conversation:
        title = request.message[:60] + ("..." if len(request.message) > 60 else "")
        conversation = CounselorConversation(
            profile_id=profile.id,
            title=title,
            primary_language=preferred_lang,
            active_institution_id=request.institution_id,
            active_applicant_type=request.applicant_type or profile.applicant_type,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # 2. Record User Message
    user_msg = CounselorMessage(
        conversation_id=conversation.id,
        role="user",
        content=request.message,
        language=preferred_lang,
        citations=[],
    )
    db.add(user_msg)

    # 3. Generate Hybrid pgvector + FTS Grounded Answer with Follow-Up Context Retention
    answer_data = MultilingualCounselorService.answer_admissions_query(
        query=request.message,
        preferred_language=preferred_lang,
        applicant_type=request.applicant_type,
        db=db,
        institution_id=request.institution_id,
        profile=profile,
        conversation_context={
            "active_institution_id": conversation.active_institution_id,
            "active_applicant_type": conversation.active_applicant_type,
            "active_topic": conversation.active_topic,
        },
    )

    breakdown = answer_data.get("epistemic_breakdown") or {}
    ctx_inst_id = breakdown.get("context_institution_id")
    if ctx_inst_id:
        conversation.active_institution_id = UUID(str(ctx_inst_id))
    if breakdown.get("context_applicant_type"):
        conversation.active_applicant_type = breakdown["context_applicant_type"]
    if breakdown.get("active_topic"):
        conversation.active_topic = breakdown["active_topic"]
    conversation.updated_at = datetime.now(timezone.utc)

    # 4. Record Assistant Response
    assistant_msg = CounselorMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=answer_data["content"],
        language=answer_data["language"],
        citations=answer_data["citations"],
        epistemic_breakdown=breakdown,
        disclaimer=answer_data["disclaimer"],
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return assistant_msg


@router.get("/counselor/history", response_model=List[CounselorConversationSchema], tags=["AI Counselor"])
def list_counselor_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        return []

    conversations = (
        db.query(CounselorConversation)
        .filter(CounselorConversation.profile_id == profile.id)
        .order_by(CounselorConversation.updated_at.desc())
        .all()
    )
    return conversations


@router.get("/counselor/conversations/{conversation_id}", response_model=CounselorConversationSchema, tags=["AI Counselor"])
def get_counselor_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")
    conv = (
        db.query(CounselorConversation)
        .filter(
            CounselorConversation.id == conversation_id,
            CounselorConversation.profile_id == profile.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return conv


@router.delete("/counselor/conversations/{conversation_id}", tags=["AI Counselor"])
def delete_counselor_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found.")
    conv = (
        db.query(CounselorConversation)
        .filter(
            CounselorConversation.id == conversation_id,
            CounselorConversation.profile_id == profile.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    db.delete(conv)
    db.commit()
    return {"deleted": True, "conversation_id": str(conversation_id)}


@router.post("/counselor/rag/search", response_model=List[RagSearchResultItem], tags=["AI Counselor"])
def search_rag_knowledge_chunks(
    payload: RagSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Hybrid pgvector + PostgreSQL full-text retrieval endpoint across verified shared
    institutional knowledge chunks (excludes all student-private data).
    """
    selected, _ = retrieve_grounded_chunks(
        db=db,
        query=payload.query,
        institution_ids=[payload.institution_id] if payload.institution_id else None,
        applicant_type=payload.applicant_type,
        limit=max(1, min(20, payload.limit)),
    )
    out: List[RagSearchResultItem] = []
    for item in selected:
        ch = item["chunk"]
        out.append(
            RagSearchResultItem(
                chunk_id=ch.id,
                institution_id=ch.institution_id,
                country_code=ch.country_code,
                chunk_type=ch.chunk_type,
                epistemic_tier=ch.epistemic_tier,
                source_type=ch.source_type,
                title=ch.title,
                content_text=ch.content_text,
                source_name=ch.source_name,
                source_url=ch.source_url,
                verified_at=ch.verified_at,
                is_outdated=ch.is_outdated,
                has_conflict=ch.has_conflict,
                hybrid_score=item["hybrid_score"],
                vector_score=item["vector_score"],
                fts_score=item["fts_score"],
            )
        )
    return out
