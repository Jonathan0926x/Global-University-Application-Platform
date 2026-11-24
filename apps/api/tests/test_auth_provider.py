import pytest
from app.core.auth_provider import MockAuthProvider, ClerkAuthProvider, get_auth_provider


@pytest.mark.asyncio
async def test_mock_auth_provider_valid_token():
    provider = MockAuthProvider()
    claims = await provider.verify_token("Bearer mock_marie.curie@science.edu")
    assert claims is not None
    assert claims.email == "marie.curie@science.edu"
    assert claims.role == "student"


@pytest.mark.asyncio
async def test_mock_auth_provider_invalid_token():
    provider = MockAuthProvider()
    claims = await provider.verify_token("")
    assert claims is None


@pytest.mark.asyncio
async def test_get_auth_provider_factory():
    provider = get_auth_provider()
    assert provider is not None
