from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID


class UserPreferenceSchema(BaseModel):
    id: UUID
    user_id: UUID
    preferred_language: str
    regional_locale: str
    preferred_script: str
    display_currency: str
    calendar_system: str
    auto_detect_enabled: bool
    last_manually_selected_lang: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPreferenceUpdate(BaseModel):
    preferred_language: Optional[str] = None
    regional_locale: Optional[str] = None
    preferred_script: Optional[str] = None
    display_currency: Optional[str] = None
    calendar_system: Optional[str] = None
    auto_detect_enabled: Optional[bool] = None
    last_manually_selected_lang: Optional[str] = None
