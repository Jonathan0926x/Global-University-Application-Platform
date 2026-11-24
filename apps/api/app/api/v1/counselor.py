from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
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
)
from app.services.counselor import MultilingualCounselorService

router = APIRouter()


@router.post("/counselor/chat", response_model=CounselorMessageSchema, status_code=status.HTTP_200_OK, tags=["AI Counselor"])
def chat_with_admissions_counselor(
    request: CounselorQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student profile must exist to converse with the AI admissions counselor."
        )

    # 1. Resolve or Create Conversation Thread
    conversation = None
    if request.conversation_id:
        conversation = db.query(CounselorConversation).filter(
            CounselorConversation.id == request.conversation_id,
            CounselorConversation.profile_id == profile.id
        ).first()

    preferred_lang = request.language or current_user.preferred_language or "en-US"

    if not conversation:
        title = request.message[:50] + ("..." if len(request.message) > 50 else "")
        conversation = CounselorConversation(
            profile_id=profile.id,
            title=title,
            primary_language=preferred_lang
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
        citations=[]
    )
    db.add(user_msg)

    # 3. Generate Multilingual Grounded Answer
    answer_data = MultilingualCounselorService.answer_admissions_query(
        query=request.message,
        preferred_language=preferred_lang,
        applicant_type=profile.applicant_type
    )

    # 4. Record Assistant Response
    assistant_msg = CounselorMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=answer_data["content"],
        language=answer_data["language"],
        citations=answer_data["citations"],
        disclaimer=answer_data["disclaimer"]
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return assistant_msg


@router.get("/counselor/history", response_model=List[CounselorConversationSchema], tags=["AI Counselor"])
def list_counselor_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    if not profile:
        return []

    conversations = db.query(CounselorConversation).filter(
        CounselorConversation.profile_id == profile.id
    ).order_by(CounselorConversation.updated_at.desc()).all()

    return conversations
