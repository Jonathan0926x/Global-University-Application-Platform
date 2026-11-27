from abc import ABC, abstractmethod
import asyncio
import json
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Sequence
import jwt
from jwt.algorithms import RSAAlgorithm
from jwt.exceptions import InvalidTokenError
import httpx
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger("uniglobe.security.auth")

_PRODUCTION_ENVS = {"production", "prod", "staging"}
_DEV_TEST_ENVS = {"development", "dev", "test", "testing", "local"}
_ALLOWED_ROLES = {"student", "data_verifier", "admin"}


class SecurityConfigurationError(RuntimeError):
    """Raised when production/staging security configuration is invalid or insecure."""


class UserClaims(BaseModel):
    user_id: str
    email: str
    email_verified: bool = False
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = "student"
    auth_method: str = "mock"


class IAuthProvider(ABC):
    @abstractmethod
    async def verify_token(self, token: str) -> Optional[UserClaims]:
        """Verify bearer token and return user identity claims."""
        pass

    @abstractmethod
    async def get_user_by_id(self, external_id: str) -> Optional[UserClaims]:
        """Retrieve user details from the authentication provider."""
        pass


def _is_production_like() -> bool:
    return (settings.ENVIRONMENT or "development").strip().lower() in _PRODUCTION_ENVS


def _normalize_role(raw_role: Any) -> str:
    if isinstance(raw_role, str):
        norm = raw_role.strip().lower()
        if norm in _ALLOWED_ROLES:
            return norm
    return "student"


def _strip_bearer(token: str) -> Optional[str]:
    if not token or not isinstance(token, str):
        return None
    stripped = token.strip()
    if stripped.lower().startswith("bearer "):
        stripped = stripped[7:].strip()
    return stripped or None


class MockAuthProvider(IAuthProvider):
    """
    Mock Auth Provider strictly restricted to explicit local development and CI testing.
    Accepts bearer tokens in format: 'mock_token_<email>', 'mock_admin_<email>',
    'mock_verifier_<email>', or 'dev_token'.
    Always refuses authentication in staging or production environments.
    """

    async def verify_token(self, token: str) -> Optional[UserClaims]:
        if _is_production_like():
            logger.error("MockAuthProvider rejected in %s environment", settings.ENVIRONMENT)
            return None

        clean_token = _strip_bearer(token)
        if not clean_token:
            return None

        if clean_token.startswith("mock_admin_"):
            email = clean_token.split("mock_admin_", 1)[1] or "admin@uniglobe.edu"
            return UserClaims(
                user_id=f"admin_{email.replace('@', '_').replace('.', '_')}",
                email=email,
                email_verified=True,
                first_name="System",
                last_name="Admin",
                role="admin",
                auth_method="mock",
            )
        if clean_token.startswith("mock_verifier_"):
            email = clean_token.split("mock_verifier_", 1)[1] or "verifier@uniglobe.edu"
            return UserClaims(
                user_id=f"verifier_{email.replace('@', '_').replace('.', '_')}",
                email=email,
                email_verified=True,
                first_name="Data",
                last_name="Verifier",
                role="data_verifier",
                auth_method="mock",
            )
        if clean_token.startswith("mock_"):
            parts = clean_token.split("_", 1)
            email = parts[1] if len(parts) > 1 else "student@example.com"
            user_id = f"user_{email.replace('@', '_').replace('.', '_')}"
            return UserClaims(
                user_id=user_id,
                email=email,
                email_verified=True,
                first_name="Alex",
                last_name="Mercer",
                role="student",
                auth_method="mock",
            )
        if clean_token == "dev_token" or clean_token.startswith("test_"):
            return UserClaims(
                user_id="user_dev_123",
                email="dev.student@uniglobe.edu",
                email_verified=True,
                first_name="Jordan",
                last_name="Taylor",
                role="student",
                auth_method="mock",
            )
        return None

    async def get_user_by_id(self, external_id: str) -> Optional[UserClaims]:
        if _is_production_like():
            return None
        return UserClaims(
            user_id=external_id,
            email=f"{external_id}@example.com",
            email_verified=True,
            first_name="Verified",
            last_name="Student",
            role="student",
            auth_method="mock",
        )


JWKSFetcher = Callable[[str], Awaitable[Dict[str, Any]]]


def _sync_fetch_jwks(jwks_url: str) -> Dict[str, Any]:
    """Synchronously fetch Clerk JWKS with SSRF DNS-pinning, no redirects, and no env proxies."""
    from urllib.parse import urlparse
    from app.services.routing_health import _PinnedPublicIPBackend, _resolve_and_validate_public_ips

    parsed = urlparse(jwks_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Clerk JWKS URL must use https:// with a clean public hostname.")

    port = parsed.port or 443
    pinned_ips = _resolve_and_validate_public_ips(parsed.hostname, port)
    transport = httpx.HTTPTransport(retries=0, trust_env=False)
    transport._pool._network_backend = _PinnedPublicIPBackend(parsed.hostname, pinned_ips)

    with httpx.Client(
        timeout=5.0,
        follow_redirects=False,
        trust_env=False,
        transport=transport,
    ) as client:
        resp = client.get(jwks_url, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
            raise ValueError("Invalid JWKS payload structure.")
        return data


async def _default_jwks_fetcher(jwks_url: str) -> Dict[str, Any]:
    """Fetch Clerk JWKS securely using connection-time pinned public IPs."""
    return await asyncio.to_thread(_sync_fetch_jwks, jwks_url)


class JWKSKeyCache:
    """Thread-safe async JWKS key cache supporting controlled rotation refreshes."""

    def __init__(
        self,
        jwks_url: str,
        ttl_seconds: int = 3600,
        min_refresh_interval_seconds: int = 10,
        fetcher: Optional[JWKSFetcher] = None,
    ) -> None:
        self.jwks_url = jwks_url
        self.ttl_seconds = max(30, int(ttl_seconds))
        self.min_refresh_interval_seconds = max(0, int(min_refresh_interval_seconds))
        self._fetcher = fetcher or _default_jwks_fetcher
        self._keys_by_kid: Dict[str, Any] = {}
        self._fetched_at: float = 0.0
        self._last_forced_refresh_at: float = 0.0
        self._lock = asyncio.Lock()

    def _parse_jwks(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {}
        for jwk in payload.get("keys") or []:
            if not isinstance(jwk, dict):
                continue
            kid = jwk.get("kid")
            kty = jwk.get("kty")
            use = jwk.get("use")
            if not kid or kty != "RSA" or (use and use != "sig"):
                continue
            parsed[str(kid)] = RSAAlgorithm.from_jwk(json.dumps(jwk))
        return parsed

    async def get_signing_key(self, kid: str) -> Optional[Any]:
        now = time.monotonic()
        cache_valid = bool(self._keys_by_kid) and (now - self._fetched_at) < self.ttl_seconds
        if cache_valid and kid in self._keys_by_kid:
            return self._keys_by_kid[kid]

        async with self._lock:
            now = time.monotonic()
            cache_valid = bool(self._keys_by_kid) and (now - self._fetched_at) < self.ttl_seconds
            if cache_valid and kid in self._keys_by_kid:
                return self._keys_by_kid[kid]

            # Controlled key-rotation refresh when kid is missing or cache TTL expired
            should_refresh = (not cache_valid) or (
                (now - self._last_forced_refresh_at) >= self.min_refresh_interval_seconds
            )
            if not should_refresh:
                return self._keys_by_kid.get(kid)

            payload = await self._fetcher(self.jwks_url)
            new_keys = self._parse_jwks(payload)
            self._keys_by_kid = new_keys
            self._fetched_at = time.monotonic()
            if cache_valid:
                self._last_forced_refresh_at = self._fetched_at
            return self._keys_by_kid.get(kid)


class ClerkAuthProvider(IAuthProvider):
    """
    Production Clerk Auth Provider performing genuine cryptographic JWT/JWKS verification.
    Fails closed on any configuration gap, signature mismatch, algorithm mismatch, expired/nbf/iat
    violation, issuer/audience mismatch, unknown kid, or JWKS outage. Never logs raw JWTs.
    """

    def __init__(
        self,
        issuer: Optional[str] = None,
        jwks_url: Optional[str] = None,
        audience: Optional[str] = None,
        accepted_algorithms: Optional[Sequence[str]] = None,
        jwks_cache_ttl_seconds: Optional[int] = None,
        leeway_seconds: Optional[int] = None,
        max_iat_age_seconds: Optional[int] = None,
        jwks_min_refresh_interval_seconds: int = 10,
        jwks_fetcher: Optional[JWKSFetcher] = None,
    ) -> None:
        raw_issuer = issuer if issuer is not None else settings.CLERK_ISSUER
        self.issuer = raw_issuer.rstrip("/") if raw_issuer else None

        raw_jwks = jwks_url if jwks_url is not None else settings.CLERK_JWKS_URL
        if not raw_jwks and self.issuer:
            raw_jwks = f"{self.issuer}/.well-known/jwks.json"
        self.jwks_url = raw_jwks

        raw_aud = audience if audience is not None else settings.CLERK_AUDIENCE
        self.audience = [a.strip() for a in raw_aud.split(",") if a.strip()] if isinstance(raw_aud, str) else raw_aud
        if isinstance(self.audience, list) and len(self.audience) == 1:
            self.audience = self.audience[0]
        elif isinstance(self.audience, list) and len(self.audience) == 0:
            self.audience = None

        if accepted_algorithms is not None:
            algs = [a.strip().upper() for a in accepted_algorithms if a and a.strip()]
        else:
            algs = [a.strip().upper() for a in settings.CLERK_ACCEPTED_ALGORITHMS.split(",") if a.strip()]
        # Enforce strict asymmetric RS256-only default policy (never allow HS* or none)
        self.accepted_algorithms = [a for a in algs if a in {"RS256", "RS384", "RS512"}] or ["RS256"]

        self.leeway_seconds = (
            settings.CLERK_CLOCK_SKEW_SECONDS if leeway_seconds is None else max(0, int(leeway_seconds))
        )
        self.max_iat_age_seconds = (
            settings.CLERK_MAX_IAT_AGE_SECONDS if max_iat_age_seconds is None else int(max_iat_age_seconds)
        )
        ttl = (
            settings.CLERK_JWKS_CACHE_TTL_SECONDS
            if jwks_cache_ttl_seconds is None
            else int(jwks_cache_ttl_seconds)
        )
        self._jwks_cache: Optional[JWKSKeyCache] = (
            JWKSKeyCache(
                jwks_url=self.jwks_url,
                ttl_seconds=ttl,
                min_refresh_interval_seconds=jwks_min_refresh_interval_seconds,
                fetcher=jwks_fetcher,
            )
            if self.jwks_url
            else None
        )

    async def verify_token(self, token: str) -> Optional[UserClaims]:
        clean_token = _strip_bearer(token)
        if not clean_token or clean_token.count(".") != 2:
            logger.warning("Clerk JWT rejected: malformed token structure")
            return None

        if not self.issuer or not self._jwks_cache:
            logger.error("Clerk JWT rejected: CLERK_ISSUER or CLERK_JWKS_URL not configured")
            return None

        try:
            header = jwt.get_unverified_header(clean_token)
        except InvalidTokenError:
            logger.warning("Clerk JWT rejected: invalid JWT header")
            return None

        alg = str(header.get("alg") or "").upper()
        kid = header.get("kid")
        if alg not in self.accepted_algorithms:
            logger.warning("Clerk JWT rejected: disallowed algorithm alg=%s", alg or "missing")
            return None
        if not kid or not isinstance(kid, str):
            logger.warning("Clerk JWT rejected: missing key identifier (kid)")
            return None

        try:
            signing_key = await self._jwks_cache.get_signing_key(kid)
        except Exception as exc:
            logger.error("Clerk JWKS retrieval failed: %s", exc.__class__.__name__)
            return None

        if signing_key is None:
            logger.warning("Clerk JWT rejected: unknown signing key kid=%s", kid[:16])
            return None

        try:
            decode_options = {
                "require": ["sub", "exp", "iss", "iat"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_iss": True,
                "verify_aud": bool(self.audience),
            }
            payload = jwt.decode(
                clean_token,
                key=signing_key,
                algorithms=self.accepted_algorithms,
                issuer=self.issuer,
                audience=self.audience if self.audience else None,
                leeway=self.leeway_seconds,
                options=decode_options,
            )
        except InvalidTokenError as exc:
            logger.warning("Clerk JWT verification failed: %s", exc.__class__.__name__)
            return None

        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub.strip():
            logger.warning("Clerk JWT rejected: missing subject claim")
            return None

        iat = payload.get("iat")
        now_ts = time.time()
        if not isinstance(iat, (int, float)):
            logger.warning("Clerk JWT rejected: invalid iat claim")
            return None
        if self.max_iat_age_seconds > 0 and (now_ts - float(iat)) > self.max_iat_age_seconds + self.leeway_seconds:
            logger.warning("Clerk JWT rejected: token exceeds max_iat_age_seconds policy")
            return None

        # Role is derived strictly from server-signed JWT metadata (never client headers/body)
        raw_role = (
            payload.get("role")
            or (payload.get("metadata") or {}).get("role")
            or (payload.get("public_metadata") or {}).get("role")
        )
        role = _normalize_role(raw_role)

        email = payload.get("email") or payload.get("primary_email") or f"{sub}@clerk.local"
        return UserClaims(
            user_id=sub.strip(),
            email=str(email).strip(),
            email_verified=bool(payload.get("email_verified", False)),
            first_name=payload.get("given_name") or payload.get("first_name"),
            last_name=payload.get("family_name") or payload.get("last_name"),
            role=role,
            auth_method="clerk_jwt",
        )

    async def get_user_by_id(self, external_id: str) -> Optional[UserClaims]:
        if not settings.CLERK_SECRET_KEY:
            return None
        from urllib.parse import urlparse
        from app.services.routing_health import _resolve_and_validate_public_ips

        url = f"https://api.clerk.com/v1/users/{external_id}"
        parsed = urlparse(url)
        _resolve_and_validate_public_ips(parsed.hostname, 443)
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=False, trust_env=False) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            emails = data.get("email_addresses") or []
            primary_email = emails[0].get("email_address") if emails else f"{external_id}@clerk.local"
            pub_meta = data.get("public_metadata") or {}
            return UserClaims(
                user_id=external_id,
                email=primary_email,
                email_verified=True,
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
                role=_normalize_role(pub_meta.get("role")),
                auth_method="clerk_api",
            )


_CACHED_CLERK_PROVIDER: Optional[ClerkAuthProvider] = None


def reset_auth_provider_cache() -> None:
    global _CACHED_CLERK_PROVIDER
    _CACHED_CLERK_PROVIDER = None


def get_auth_provider() -> IAuthProvider:
    global _CACHED_CLERK_PROVIDER
    env = (settings.ENVIRONMENT or "development").strip().lower()
    provider_name = (settings.AUTH_PROVIDER or "mock").strip().lower()

    if env in _PRODUCTION_ENVS and provider_name != "clerk":
        raise SecurityConfigurationError(
            f"AUTH_PROVIDER='{provider_name}' is prohibited in '{env}' environment; 'clerk' is required."
        )

    if provider_name == "clerk":
        if _CACHED_CLERK_PROVIDER is None:
            _CACHED_CLERK_PROVIDER = ClerkAuthProvider()
        return _CACHED_CLERK_PROVIDER

    if provider_name == "mock":
        if env not in _DEV_TEST_ENVS:
            raise SecurityConfigurationError(
                f"MockAuthProvider is allowed only in development/test environments, not '{env}'."
            )
        return MockAuthProvider()

    raise SecurityConfigurationError(f"Unsupported AUTH_PROVIDER: '{provider_name}'.")
