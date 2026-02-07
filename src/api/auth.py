"""API authentication middleware.

Validates API keys and tracks usage for the Foundry API.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from src.infra.database import get_db
from src.infra.logging import get_logger

logger = get_logger("auth")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


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


def hash_api_key(key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(key.encode()).hexdigest()


async def validate_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[AuthContext]:
    """
    Validate an API key and return the auth context.
    
    Returns None if no API key is provided (allows unauthenticated access
    to public endpoints). Raises 401/403 for invalid/expired keys.
    """
    if not api_key:
        return None
    
    db = get_db()
    
    if not db.is_configured:
        # Database not configured - allow through with default context
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
    
    # Update last_used_at
    await db.execute(
        "UPDATE api_keys SET last_used_at = NOW() WHERE id = $1",
        [str(result["key_id"])],
    )
    
    # Neon HTTP API may return arrays as strings like "{a,b,c}"
    scopes = result.get("scopes", [])
    if isinstance(scopes, str):
        scopes = [s.strip() for s in scopes.strip("{}").split(",") if s.strip()]
    
    return AuthContext(
        org_id=str(result["org_id"]),
        user_id=str(result["user_id"]) if result.get("user_id") else None,
        api_key_id=str(result["key_id"]),
        plan=result["plan"],
        scopes=scopes,
        monthly_build_limit=int(result["monthly_build_limit"]),
        monthly_invoke_limit=int(result["monthly_invoke_limit"]),
        monthly_search_limit=int(result["monthly_search_limit"]),
    )


async def require_auth(auth: Optional[AuthContext] = Security(validate_api_key)) -> AuthContext:
    """Require authentication - raises 401 if no valid API key."""
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
    
    Returns True if within limits, raises 429 if exceeded.
    """
    db = get_db()
    
    if not db.is_configured:
        return True
    
    result = await db.execute_one(
        "SELECT * FROM get_current_usage($1)",
        [auth.org_id],
    )
    
    if not result:
        return True
    
    limit_map = {
        "tool_build": ("builds", auth.monthly_build_limit),
        "tool_invoke": ("invocations", auth.monthly_invoke_limit),
        "search": ("searches", auth.monthly_search_limit),
    }
    
    if event_type in limit_map:
        field, limit = limit_map[event_type]
        current = result.get(field, 0)
        
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
    """Track a usage event."""
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
