"""API key management endpoints.

Handles creating, listing, revoking API keys, and new user registration.
"""

from __future__ import annotations

import secrets
import hashlib
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.api.auth import AuthContext, require_auth, hash_api_key
from src.infra.database import get_db
from src.infra.logging import get_logger

logger = get_logger("api.keys")

keys_router = APIRouter(prefix="/v1/keys", tags=["API Keys"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """Register a new organization and get your first API key."""
    org_name: str = Field(description="Your organization or project name")
    email: Optional[str] = Field(default=None, description="Contact email (optional)")
    plan: str = Field(default="paygo", description="Billing plan: paygo, pro")
    user_id: Optional[str] = Field(default=None, description="Better Auth user ID (set by web signup flow)")


class RegisterResponse(BaseModel):
    org_id: str
    org_name: str
    api_key: str = Field(description="Your API key (save this — shown only once)")
    key_prefix: str
    plan: str
    message: str


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


# ---------------------------------------------------------------------------
# Public Registration (no auth required)
# ---------------------------------------------------------------------------

@keys_router.post("/register", response_model=RegisterResponse)
async def register(request: RegisterRequest):
    """Register a new organization and receive your first API key.
    
    This is the only endpoint that does not require authentication.
    Save the returned API key — it is shown only once.
    """
    db = get_db()
    
    if not db.is_configured:
        raise HTTPException(status_code=503, detail="Database not configured")
    
    # Validate plan
    valid_plans = {"paygo", "pro"}
    if request.plan not in valid_plans:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan '{request.plan}'. Choose from: {', '.join(sorted(valid_plans))}",
        )
    
    # Check for duplicate org name (slug)
    slug = request.org_name.lower().strip().replace(" ", "-")[:50]
    existing = await db.execute_one(
        "SELECT id FROM organizations WHERE slug = $1",
        [slug],
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Organization '{request.org_name}' already exists. Use a different name or contact support.",
        )
    
    # Look up plan limits
    plan_row = await db.execute_one(
        """
        SELECT monthly_builds, monthly_invocations, monthly_searches, concurrent_tools
        FROM billing_plans WHERE id = $1
        """,
        [request.plan],
    )
    
    if not plan_row:
        raise HTTPException(status_code=500, detail="Plan configuration not found")
    
    org_id = str(uuid.uuid4())
    
    # Create organization (owner_user_id from Better Auth if provided)
    await db.execute(
        """
        INSERT INTO organizations (id, name, slug, plan, monthly_build_limit,
                                   monthly_invoke_limit, monthly_search_limit, concurrent_tools_limit,
                                   owner_user_id, owner_email)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
        [
            org_id,
            request.org_name.strip(),
            slug,
            request.plan,
            plan_row["monthly_builds"],
            plan_row["monthly_invocations"],
            plan_row["monthly_searches"],
            plan_row["concurrent_tools"],
            request.user_id,   # nullable — None for SDK registrations
            request.email,
        ],
    )

    # Generate first API key (created_by is now nullable)
    full_key, prefix, key_hash = generate_api_key()

    await db.execute(
        """
        INSERT INTO api_keys (org_id, created_by, name, key_prefix, key_hash, scopes)
        VALUES ($1, $2, $3, $4, $5, ARRAY['tools:create','tools:invoke','tools:read','search'])
        """,
        [org_id, request.user_id, "Default Key", prefix, key_hash],
    )
    
    # ── Create Autumn customer & attach free plan ─────────────────────
    try:
        from src.infra.autumn import get_autumn
        autumn = get_autumn()
        if autumn.is_enabled:
            await autumn.create_customer(
                customer_id=org_id,
                name=request.org_name.strip(),
                email=request.email,
            )
            # Attach the appropriate product
            product_map = {"paygo": "paygo", "pro": "pro"}
            product_id = product_map.get(request.plan, "paygo")
            await autumn.attach(org_id, product_id)
            logger.info(f"Autumn: created customer {org_id} with product '{product_id}'")
    except Exception as e:
        logger.error(f"Autumn customer setup failed (non-blocking): {e}")
    
    logger.info(f"Registered new org '{request.org_name}' ({org_id}) on plan '{request.plan}'")
    
    return RegisterResponse(
        org_id=org_id,
        org_name=request.org_name.strip(),
        api_key=full_key,
        key_prefix=prefix,
        plan=request.plan,
        message=f"Welcome to Foundry! Save your API key — it won't be shown again.",
    )
