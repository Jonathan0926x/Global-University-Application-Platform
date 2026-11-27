from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from typing import Optional

from app.config import settings
from app.core.auth_provider import (
    SecurityConfigurationError,
    UserClaims,
    get_auth_provider,
)
from app.database import get_db
from app.models.profile import StudentProfile
from app.models.user import User


def _allow_implicit_dev_token() -> bool:
    env = (settings.ENVIRONMENT or "development").strip().lower()
    prov = (settings.AUTH_PROVIDER or "mock").strip().lower()
    return env in ("development", "dev", "test", "testing", "local") and prov == "mock" and bool(
        settings.ALLOW_DEV_MOCK_DEFAULT_USER
    )


async def get_current_user_claims(
    authorization: Optional[str] = Header(None),
) -> UserClaims:
    try:
        provider = get_auth_provider()
    except SecurityConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service configuration error.",
        )

    if not authorization:
        if _allow_implicit_dev_token():
            claims = await provider.verify_token("Bearer dev_token")
            if claims:
                return claims
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = await provider.verify_token(authorization)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims


def get_current_user(
    claims: UserClaims = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
) -> User:
    user = db.query(User).filter(User.external_auth_id == claims.user_id).first()
    if not user:
        user = User(
            external_auth_id=claims.user_id,
            email=claims.email,
            email_verified=claims.email_verified,
            account_status="active",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    if user.account_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive or suspended.",
        )
    return user


def get_current_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Optional[StudentProfile]:
    return db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()


def require_admin_claims(
    claims: UserClaims = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
) -> UserClaims:
    if claims.role not in ("admin", "data_verifier"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative or data verifier privileges required.",
        )
    # Also ensure an active DB user check if a corresponding record exists
    user = db.query(User).filter(User.external_auth_id == claims.user_id).first()
    if user and user.account_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator account is inactive or suspended.",
        )
    return claims


def require_strict_admin_claims(
    claims: UserClaims = Depends(require_admin_claims),
) -> UserClaims:
    if claims.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Strict system administrator privileges required.",
        )
    return claims
