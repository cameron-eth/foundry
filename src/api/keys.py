"""API key management endpoints.

Handles creating, listing, and revoking API keys.
Called from the Next.js dashboard via server-side API routes.
"""

from __future__ import annotations

import secrets
import hashlib
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.api.auth import AuthContext, require_auth, hash_api_key
from src.infra.database import get_db
from src.infra.logging import get_logger

logger = get_logger("api.keys")

keys_router = APIRouter(prefix="/v1/keys", tags=["API Keys"])


class CreateKeyRequest(BaseModel):
    name: str = Field(default="Default", description="Name for the API key")
    scopes: List[str] = Field(
        default=["tools:create", "tools:invoke", "tools:read", "search"],
        description="Permission scopes for the key",
    )


class CreateKeyResponse(BaseModel):
    key: str = Field(description="The full API key (only shown once)")
    key_id: str = Field(description="Key ID for reference")
    prefix: str = Field(description="Key prefix for identification")
    name: str


class KeyInfo(BaseModel):
    key_id: str
    name: str
    prefix: str
    scopes: List[str]
    is_active: bool
    created_at: str
    last_used_at: Optional[str]


class KeyListResponse(BaseModel):
    keys: List[KeyInfo]


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.
    
    Returns:
        Tuple of (full_key, prefix, key_hash).
    """
    # Generate 32 random bytes -> 64 hex chars
    raw = secrets.token_hex(32)
    full_key = f"fnd_{raw}"
    prefix = full_key[:12]
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, key_hash


@keys_router.post("/create", response_model=CreateKeyResponse)
async def create_api_key(
    request: CreateKeyRequest,
    auth: AuthContext = Depends(require_auth),
):
    """Create a new API key for the authenticated organization."""
    db = get_db()
    
    if not db.is_configured:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    full_key, prefix, key_hash = generate_api_key()
    
    result = await db.execute_one(
        """
        INSERT INTO api_keys (org_id, created_by, name, key_prefix, key_hash, scopes)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        [auth.org_id, auth.user_id, request.name, prefix, key_hash, request.scopes],
    )
    
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create API key")
    
    logger.info(f"Created API key {prefix}... for org {auth.org_id}")
    
    return CreateKeyResponse(
        key=full_key,
        key_id=str(result["id"]),
        prefix=prefix,
        name=request.name,
    )


@keys_router.get("/list", response_model=KeyListResponse)
async def list_api_keys(
    auth: AuthContext = Depends(require_auth),
):
    """List all API keys for the authenticated organization."""
    db = get_db()
    
    if not db.is_configured:
        return KeyListResponse(keys=[])
    
    rows = await db.execute(
        """
        SELECT id, name, key_prefix, scopes, is_active, 
               created_at::text, last_used_at::text
        FROM api_keys
        WHERE org_id = $1 AND revoked_at IS NULL
        ORDER BY created_at DESC
        """,
        [auth.org_id],
    )
    
    return KeyListResponse(
        keys=[
            KeyInfo(
                key_id=str(row["id"]),
                name=row["name"],
                prefix=row["key_prefix"],
                scopes=row.get("scopes", []),
                is_active=row["is_active"],
                created_at=row["created_at"],
                last_used_at=row.get("last_used_at"),
            )
            for row in rows
        ]
    )


@keys_router.post("/{key_id}/revoke")
async def revoke_api_key(
    key_id: str,
    auth: AuthContext = Depends(require_auth),
):
    """Revoke an API key."""
    db = get_db()
    
    if not db.is_configured:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    result = await db.execute(
        """
        UPDATE api_keys 
        SET is_active = FALSE, revoked_at = NOW()
        WHERE id = $1 AND org_id = $2
        RETURNING id
        """,
        [key_id, auth.org_id],
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="API key not found")
    
    logger.info(f"Revoked API key {key_id} for org {auth.org_id}")
    
    return {"message": "API key revoked", "key_id": key_id}
