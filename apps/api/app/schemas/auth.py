from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional
from uuid import UUID


class UserResponse(BaseModel):
    id: UUID
    external_auth_id: str
    email: EmailStr
    account_status: str
    preferred_language: str

    model_config = ConfigDict(from_attributes=True)


class AuthSessionResponse(BaseModel):
    authenticated: bool
    user: Optional[UserResponse] = None
    has_profile: bool = False
    applicant_type: Optional[str] = None

