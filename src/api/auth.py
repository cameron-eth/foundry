"""API authentication middleware.

Validates API keys, enforces rate limits, and tracks usage for the Foundry API.

Environment variables:
    FOUNDRY_REQUIRE_AUTH  – Set to "true" to reject unauthenticated requests
                           on all protected routes (default: false → open access).
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from src.infra.database import get_db
from src.infra.logging import get_logger

logger = get_logger("auth")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ---------------------------------------------------------------------------
# Auth context
# ---------------------------------------------------------------------------

@dataclass
class AuthContext:
    """Authentication context for a request."""
    
    org_id: str
    user_id: Optional[str]
    api_key_id: str
    plan: str
    scopes: List[str]
    
    # Usage limits
    monthly_build_limit: int
    monthly_invoke_limit: int
    monthly_search_limit: int
    
    # Per-key rate limit (requests per minute); -1 or 0 = unlimited
    rate_limit_rpm: int = 60


# ---------------------------------------------------------------------------
# Sliding-window rate limiter (in-memory)
# ---------------------------------------------------------------------------

class _SlidingWindowLimiter:
    """In-memory sliding-window rate limiter keyed by API key ID.

    Stores a list of request timestamps per key and evicts expired entries
    on each check.  Sufficient for a single-process deployment (Modal runs
    one container per ASGI worker).
    """

    def __init__(self, window_seconds: int = 60):
        self._window = window_seconds
        self._buckets: Dict[str, List[float]] = defaultdict(list)

    def check(self, key: str, limit: int) -> Tuple[bool, int, int]:
        """Check if a request is within the rate limit.

        Returns:
            Tuple of (allowed, remaining, reset_seconds).
        """
        if limit <= 0:
            return True, 999, 0

        now = time.monotonic()
        cutoff = now - self._window
        bucket = self._buckets[key]

        # Evict expired timestamps
        bucket[:] = [t for t in bucket if t > cutoff]

        remaining = max(0, limit - len(bucket))
        reset_seconds = int(self._window - (now - bucket[0])) if bucket else self._window

        if len(bucket) >= limit:
            return False, 0, reset_seconds

        bucket.append(now)
        return True, remaining - 1, reset_seconds


_limiter = _SlidingWindowLimiter(window_seconds=60)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_auth_required() -> bool:
    """Return True when the deployment mandates authentication."""
    import os
    return os.environ.get("FOUNDRY_REQUIRE_AUTH", "").lower() in ("true", "1", "yes")


def hash_api_key(key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Core validators
# ---------------------------------------------------------------------------

async def validate_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[AuthContext]:
    """
    Validate an API key and return the auth context.

    Behaviour depends on the ``FOUNDRY_REQUIRE_AUTH`` env-var:
    • **false** (default): returns ``None`` when no key is provided, so
      unauthenticated requests still pass through (useful for dev/demo).
    • **true**: raises 401 whenever no valid key is presented.

    Invalid or expired keys always raise 401/403 regardless of mode.
    """
    if not api_key:
        if _is_auth_required():
            raise HTTPException(
                status_code=401,
                detail="API key required. Include X-API-Key header. Register at POST /v1/keys/register",
            )
        return None

    db = get_db()

    if not db.is_configured:
        # Database not configured — allow through with default context
        logger.debug("Database not configured, using default auth context")
        return AuthContext(
            org_id="default",
            user_id=None,
            api_key_id="default",
            plan="free",
            scopes=["tools:create", "tools:invoke", "tools:read", "search"],
            monthly_build_limit=100,
            monthly_invoke_limit=1000,
            monthly_search_limit=500,
            rate_limit_rpm=60,
        )

    # Look up the key
    key_hash = hash_api_key(api_key)

    result = await db.execute_one(
        """
        SELECT 
            k.id as key_id,
            k.org_id,
            k.created_by as user_id,
            k.scopes,
            k.is_active,
            k.expires_at,
            k.rate_limit_rpm,
            o.plan,
            o.monthly_build_limit,
            o.monthly_invoke_limit,
            o.monthly_search_limit
        FROM api_keys k
        JOIN organizations o ON o.id = k.org_id
        WHERE k.key_hash = $1
        """,
        [key_hash],
    )

    if not result:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not result["is_active"]:
        raise HTTPException(status_code=403, detail="API key is revoked")

    if result.get("expires_at"):
        from datetime import datetime, timezone
        expires = result["expires_at"]
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires:
            raise HTTPException(status_code=403, detail="API key has expired")

    # ── Rate limiting ────────────────────────────────────────────────────
    key_id_str = str(result["key_id"])
    rpm = int(result.get("rate_limit_rpm") or 60)  # default 60 RPM

    allowed, remaining, reset = _limiter.check(key_id_str, rpm)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({rpm} requests/minute). Retry after {reset}s.",
            headers={
                "Retry-After": str(reset),
                "X-RateLimit-Limit": str(rpm),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset),
            },
        )

    # Update last_used_at (fire-and-forget — don't block the response)
    try:
        await db.execute(
            "UPDATE api_keys SET last_used_at = NOW() WHERE id = $1",
            [key_id_str],
        )
    except Exception:
        pass  # Non-critical

    # Neon HTTP API may return arrays as strings like "{a,b,c}"
    scopes = result.get("scopes", [])
    if isinstance(scopes, str):
        scopes = [s.strip() for s in scopes.strip("{}").split(",") if s.strip()]

    return AuthContext(
        org_id=str(result["org_id"]),
        user_id=str(result["user_id"]) if result.get("user_id") else None,
        api_key_id=key_id_str,
        plan=result["plan"],
        scopes=scopes,
        monthly_build_limit=int(result["monthly_build_limit"]),
        monthly_invoke_limit=int(result["monthly_invoke_limit"]),
        monthly_search_limit=int(result["monthly_search_limit"]),
        rate_limit_rpm=rpm,
    )


async def require_auth(auth: Optional[AuthContext] = Security(validate_api_key)) -> AuthContext:
    """Require authentication — raises 401 if no valid API key."""
    if auth is None:
        raise HTTPException(
            status_code=401,
            detail="API key required. Include X-API-Key header.",
        )
    return auth


async def require_scope(scope: str, auth: AuthContext = Security(require_auth)) -> AuthContext:
    """Require a specific scope."""
    if scope not in auth.scopes:
        raise HTTPException(
            status_code=403,
            detail=f"API key missing required scope: {scope}",
        )
    return auth


async def check_usage_limit(auth: AuthContext, event_type: str) -> bool:
    """Check if the org is within usage limits for the given event type.
    
    Uses Autumn billing when configured; falls back to DB-based limits.
    Returns True if within limits, raises 429 if exceeded.
    """
    # ── Autumn check (preferred) ──────────────────────────────────────
    from src.infra.autumn import get_autumn, EVENT_TO_FEATURE

    autumn = get_autumn()
    feature_id = EVENT_TO_FEATURE.get(event_type)

    if autumn.is_enabled and feature_id:
        result = await autumn.check(auth.org_id, feature_id)
        if not result.allowed:
            # If balance/usage are None, Autumn has no feature config for this
            # customer's plan yet — fall through to DB limits instead of hard-blocking
            if result.balance is None and result.usage is None:
                logger.warning(
                    f"Autumn returned allowed=False with no balance data for "
                    f"{auth.org_id}/{feature_id} — falling back to DB limits"
                )
            else:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Usage limit reached for {event_type} "
                        f"(balance: {result.balance}, usage: {result.usage}/{result.included_usage}). "
                        f"Upgrade your plan at https://foundry.ai/pricing"
                    ),
                )
        else:
            return True

    # ── Fallback: DB-based limits ─────────────────────────────────────
    db = get_db()

    if not db.is_configured:
        return True

    db_result = await db.execute_one(
        "SELECT * FROM get_current_usage($1)",
        [auth.org_id],
    )

    if not db_result:
        return True

    limit_map = {
        "tool_build": ("builds", auth.monthly_build_limit),
        "tool_invoke": ("invocations", auth.monthly_invoke_limit),
        "search": ("searches", auth.monthly_search_limit),
    }

    if event_type in limit_map:
        field, limit = limit_map[event_type]
        current = db_result.get(field, 0)

        if limit != -1 and current >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Monthly {event_type} limit exceeded ({current}/{limit}). Upgrade your plan at https://foundry.ai/pricing",
            )

    return True


async def track_usage(
    auth: AuthContext,
    event_type: str,
    tool_id: Optional[str] = None,
    request_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    status_code: int = 200,
    execution_time_ms: int = 0,
    tokens_used: int = 0,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Track a usage event in both Autumn (billing) and the local DB."""

    # ── Autumn track (billing-authoritative) ──────────────────────────
    try:
        from src.infra.autumn import get_autumn, EVENT_TO_FEATURE

        autumn = get_autumn()
        feature_id = EVENT_TO_FEATURE.get(event_type)

        if autumn.is_enabled and feature_id and status_code < 500:
            # Only count successful operations toward billing
            await autumn.track(
                customer_id=auth.org_id,
                feature_id=feature_id,
                value=1,
                properties={
                    "tool_id": tool_id or "",
                    "endpoint": endpoint or "",
                    "execution_time_ms": execution_time_ms,
                },
                idempotency_key=request_id,
            )
    except Exception as e:
        logger.error(f"Autumn track failed: {e}")

    # ── Local DB track (analytics / dashboard) ────────────────────────
    db = get_db()

    if not db.is_configured:
        return

    # Calculate compute units
    compute_units = 0.0
    if event_type == "tool_build":
        compute_units = 1.0  # 1 CU per build
    elif event_type == "tool_invoke":
        compute_units = 0.1 + (execution_time_ms / 10000)  # base + time-based
    elif event_type == "search":
        compute_units = 0.05  # per search query

    try:
        await db.execute(
            """
            INSERT INTO usage_events 
                (org_id, user_id, api_key_id, event_type, tool_id, 
                 tokens_used, execution_time_ms, compute_units,
                 request_id, endpoint, status_code, error, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            [
                auth.org_id,
                auth.user_id,
                auth.api_key_id,
                event_type,
                tool_id,
                tokens_used,
                execution_time_ms,
                compute_units,
                request_id,
                endpoint,
                status_code,
                error,
                metadata or {},
            ],
        )
    except Exception as e:
        logger.error(f"Failed to track usage: {e}")
        # Don't fail the request if usage tracking fails
