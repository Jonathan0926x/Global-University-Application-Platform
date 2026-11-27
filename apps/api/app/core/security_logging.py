import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_sec_logger = logging.getLogger("uniglobe.security.audit")

_SENSITIVE_KEYS = {
    "authorization",
    "token",
    "jwt",
    "secret",
    "password",
    "clerk_secret_key",
    "storage_secret_access_key",
    "vault_signing_secret",
    "vault_encryption_key",
    "sig",
}


def sanitize_log_context(ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not ctx:
        return {}
    clean: Dict[str, Any] = {}
    for k, v in ctx.items():
        if str(k).lower() in _SENSITIVE_KEYS:
            clean[k] = "[REDACTED]"
        else:
            clean[k] = v
    return clean


def log_security_event(
    event_type: str,
    outcome: str,
    *,
    actor_user_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Emit structured JSON security telemetry without ever leaking JWTs, secrets, or student file text."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "outcome": outcome,
        "actor_user_id": actor_user_id,
        "actor_role": actor_role,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": sanitize_log_context(details),
    }
    level = logging.WARNING if outcome in ("denied", "blocked", "error", "quarantined") else logging.INFO
    _sec_logger.log(level, json.dumps(record, default=str))
    return record
