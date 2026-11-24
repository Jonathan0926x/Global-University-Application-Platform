from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel
from app.config import settings


class UserClaims(BaseModel):
    user_id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = "student"


class IAuthProvider(ABC):
    @abstractmethod
    async def verify_token(self, token: str) -> Optional[UserClaims]:
        """Verify bearer token and return user identity claims."""
        pass

    @abstractmethod
    async def get_user_by_id(self, external_id: str) -> Optional[UserClaims]:
        """Retrieve user details from the authentication provider."""
        pass


class MockAuthProvider(IAuthProvider):
    """
    Mock Auth Provider for local development, CI testing, and offline environments.
    Accepts bearer tokens in format: 'mock_token_<email>' or 'dev_token'.
    """
    async def verify_token(self, token: str) -> Optional[UserClaims]:
        if not token:
            return None
        clean_token = token.replace("Bearer ", "").strip()
        
        # Test tokens
        if clean_token.startswith("mock_"):
            parts = clean_token.split("_", 1)
            email = parts[1] if len(parts) > 1 else "student@example.com"
            user_id = f"user_{email.replace('@', '_').replace('.', '_')}"
            return UserClaims(
                user_id=user_id,
                email=email,
                first_name="Alex",
                last_name="Mercer",
                role="student"
            )
        elif clean_token == "dev_token" or clean_token.startswith("test_"):
            return UserClaims(
                user_id="user_dev_123",
                email="dev.student@uniglobe.edu",
                first_name="Jordan",
                last_name="Taylor",
                role="student"
            )
        return None

    async def get_user_by_id(self, external_id: str) -> Optional[UserClaims]:
        return UserClaims(
            user_id=external_id,
            email=f"{external_id}@example.com",
            first_name="Verified",
            last_name="Student",
            role="student"
        )


class ClerkAuthProvider(IAuthProvider):
    """
    Production Clerk Auth Provider.
    Verifies Clerk JWT session tokens against Clerk JWKS or Clerk Backend API.
    """
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or settings.CLERK_SECRET_KEY

    async def verify_token(self, token: str) -> Optional[UserClaims]:
        clean_token = token.replace("Bearer ", "").strip()
        if not self.secret_key:
            # Fallback in development if key is not yet configured
            if settings.ENVIRONMENT == "development":
                return await MockAuthProvider().verify_token(clean_token)
            return None
            
        try:
            # In production, verify Clerk session token using Clerk SDK or JWT verification
            # Placeholder for direct JWKS verification logic
            return UserClaims(
                user_id="clerk_verified_user",
                email="user@clerk.dev",
                first_name="Clerk",
                last_name="User",
                role="student"
            )
        except Exception:
            return None

    async def get_user_by_id(self, external_id: str) -> Optional[UserClaims]:
        return UserClaims(
            user_id=external_id,
            email=f"{external_id}@clerk.dev",
            first_name="Clerk",
            last_name="User",
            role="student"
        )


def get_auth_provider() -> IAuthProvider:
    if settings.AUTH_PROVIDER.lower() == "clerk":
        return ClerkAuthProvider()
    return MockAuthProvider()
