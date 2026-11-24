from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.profile import StudentProfile
from app.schemas.auth import AuthSessionResponse, UserResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/session", response_model=AuthSessionResponse, tags=["Auth"])
def get_auth_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
    return AuthSessionResponse(
        authenticated=True,
        user=UserResponse.model_validate(current_user),
        has_profile=profile is not None,
        applicant_type=profile.applicant_type if profile else None
    )
