from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.profile import StudentProfile
from app.core.auth_provider import get_auth_provider, UserClaims


async def get_current_user_claims(
    authorization: Optional[str] = Header(None)
) -> UserClaims:
    if not authorization:
        # In development without auth header, fall back to default dev student
        claims = await get_auth_provider().verify_token("Bearer dev_token")
        if claims:
            return claims
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token"
        )

    claims = await get_auth_provider().verify_token(authorization)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    return claims


def get_current_user(
    claims: UserClaims = Depends(get_current_user_claims),
    db: Session = Depends(get_db)
) -> User:
    user = db.query(User).filter(User.external_auth_id == claims.user_id).first()
    if not user:
        # Auto-provision user record on first successful authentication
        user = User(
            external_auth_id=claims.user_id,
            email=claims.email,
            email_verified=True,
            account_status="active"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_current_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Optional[StudentProfile]:
    return db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()


def require_admin_claims(
    claims: UserClaims = Depends(get_current_user_claims),
) -> UserClaims:
    if claims.role not in ("admin", "data_verifier"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative or data verifier privileges required."
        )
    return claims
