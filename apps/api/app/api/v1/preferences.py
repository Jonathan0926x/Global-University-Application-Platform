from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.preference import UserPreference
from app.schemas.preferences import UserPreferenceSchema, UserPreferenceUpdate

router = APIRouter()


@router.get("/preferences", response_model=UserPreferenceSchema, tags=["Preferences"])
def get_user_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserPreference(
            user_id=current_user.id,
            preferred_language=current_user.preferred_language or "en-US",
            regional_locale="en-US",
            preferred_script="Latn",
            display_currency="USD",
            calendar_system="gregory",
            auto_detect_enabled=True,
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)
    return pref


@router.put("/preferences", response_model=UserPreferenceSchema, tags=["Preferences"])
def update_user_preferences(
    update_data: UserPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pref = db.query(UserPreference).filter(UserPreference.user_id == current_user.id).first()
    if not pref:
        pref = UserPreference(user_id=current_user.id)
        db.add(pref)

    for field, value in update_data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(pref, field, value)
            if field == "preferred_language":
                # keep User.preferred_language in sync
                current_user.preferred_language = value

    db.commit()
    db.refresh(pref)
    return pref
