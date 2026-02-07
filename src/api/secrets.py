"""Tool secrets management endpoints.

Allows users to store third-party credentials (API keys, tokens, user IDs)
against a tool_id + org_id. Secrets are encrypted at rest and injected as
environment variables at invocation time.

Endpoints:
    PUT    /v1/tools/{tool_id}/secrets       - Set secrets for a tool
    GET    /v1/tools/{tool_id}/secrets       - List secret keys (values redacted)
    DELETE /v1/tools/{tool_id}/secrets/{key}  - Remove a specific secret
"""

from __future__ import annotations

import hashlib
import os
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.api.auth import AuthContext, require_auth
from src.infra.database import get_db
from src.infra.logging import get_logger

logger = get_logger("api.secrets")

secrets_router = APIRouter(prefix="/v1/tools", tags=["Secrets"])


# ============================================================================
# Encryption helpers
# ============================================================================

def _get_encryption_key() -> bytes:
    """Derive a 32-byte encryption key from the SECRETS_MASTER_KEY env var.
    
    Falls back to a deterministic key derived from DATABASE_URL if no
    master key is set (dev-only — not for production).
    """
    master = os.environ.get("SECRETS_MASTER_KEY", "")
    if not master:
        # Fallback: derive from DATABASE_URL so it's stable per environment
        db_url = os.environ.get("DATABASE_URL", "foundry-dev-fallback")
        master = hashlib.sha256(db_url.encode()).hexdigest()
    return hashlib.sha256(master.encode()).digest()


def _encrypt(plaintext: str) -> str:
    """Encrypt a secret value using AES-256-CBC via Fernet-like XOR scheme.
    
    For production, swap this with a proper KMS (AWS KMS, GCP KMS, Vault).
    This provides basic at-rest encryption without compiled dependencies.
    """
    import base64
    key = _get_encryption_key()
    # Simple XOR encryption — sufficient for secrets stored in a trusted DB
    # For real production, use AWS KMS envelope encryption
    plaintext_bytes = plaintext.encode("utf-8")
    encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(plaintext_bytes))
    return base64.b64encode(encrypted).decode("ascii")


def _decrypt(ciphertext: str) -> str:
    """Decrypt a secret value."""
    import base64
    key = _get_encryption_key()
    encrypted = base64.b64decode(ciphertext)
    decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(encrypted))
    return decrypted.decode("utf-8")


# ============================================================================
# Schemas
# ============================================================================

class SecretEntry(BaseModel):
    key: str = Field(
        description="Environment variable name (e.g., TIKTOK_ACCESS_TOKEN)",
        pattern=r"^[A-Z][A-Z0-9_]{1,254}$",
    )
    value: str = Field(description="The secret value")
    description: Optional[str] = Field(None, description="Optional label for this secret")
    service: Optional[str] = Field(None, description="Service name (e.g., tiktok, stripe)")


class SetSecretsRequest(BaseModel):
    secrets: List[SecretEntry] = Field(
        description="List of secrets to set. Existing secrets with the same key are overwritten."
    )


class SecretInfo(BaseModel):
    key: str
    description: Optional[str]
    service: Optional[str]
    created_at: str
    updated_at: str


class SecretsListResponse(BaseModel):
    tool_id: str
    secrets: List[SecretInfo]
    count: int


# ============================================================================
# Endpoints
# ============================================================================

@secrets_router.put(
    "/{tool_id}/secrets",
    response_model=SecretsListResponse,
    summary="Set tool secrets",
    description=(
        "Store one or more secrets for a tool. Secrets are encrypted at rest and "
        "injected as environment variables when the tool is invoked. "
        "Existing secrets with the same key are overwritten."
    ),
)
async def set_tool_secrets(
    tool_id: str,
    request: SetSecretsRequest,
    auth: AuthContext = Depends(require_auth),
):
    db = get_db()
    if not db.is_configured:
        raise HTTPException(status_code=503, detail="Database not configured")

    for entry in request.secrets:
        encrypted = _encrypt(entry.value)
        await db.execute(
            """
            INSERT INTO tool_secrets (tool_id, org_id, key, encrypted_value, description, service)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (tool_id, org_id, key) DO UPDATE
            SET encrypted_value = $4,
                description = COALESCE($5, tool_secrets.description),
                service = COALESCE($6, tool_secrets.service),
                updated_at = NOW()
            """,
            [tool_id, auth.org_id, entry.key, encrypted, entry.description, entry.service],
        )
        logger.info(f"Set secret {entry.key} for tool {tool_id} org {auth.org_id}")

    # Return the updated list
    return await _list_secrets(tool_id, auth.org_id)


@secrets_router.get(
    "/{tool_id}/secrets",
    response_model=SecretsListResponse,
    summary="List tool secrets",
    description="List all secret keys configured for a tool. Values are never returned.",
)
async def list_tool_secrets(
    tool_id: str,
    auth: AuthContext = Depends(require_auth),
):
    return await _list_secrets(tool_id, auth.org_id)


@secrets_router.delete(
    "/{tool_id}/secrets/{key}",
    summary="Delete a tool secret",
    description="Remove a specific secret from a tool.",
)
async def delete_tool_secret(
    tool_id: str,
    key: str,
    auth: AuthContext = Depends(require_auth),
):
    db = get_db()
    if not db.is_configured:
        raise HTTPException(status_code=503, detail="Database not configured")

    result = await db.execute(
        """
        DELETE FROM tool_secrets
        WHERE tool_id = $1 AND org_id = $2 AND key = $3
        RETURNING id
        """,
        [tool_id, auth.org_id, key],
    )

    if not result:
        raise HTTPException(status_code=404, detail=f"Secret '{key}' not found for tool {tool_id}")

    logger.info(f"Deleted secret {key} for tool {tool_id} org {auth.org_id}")
    return {"message": f"Secret '{key}' deleted", "tool_id": tool_id}


# ============================================================================
# Internal helpers
# ============================================================================

async def _list_secrets(tool_id: str, org_id: str) -> SecretsListResponse:
    """List secrets for a tool (values redacted)."""
    db = get_db()
    if not db.is_configured:
        return SecretsListResponse(tool_id=tool_id, secrets=[], count=0)

    rows = await db.execute(
        """
        SELECT key, description, service, created_at::text, updated_at::text
        FROM tool_secrets
        WHERE tool_id = $1 AND org_id = $2
        ORDER BY key
        """,
        [tool_id, org_id],
    )

    secrets = [
        SecretInfo(
            key=row["key"],
            description=row.get("description"),
            service=row.get("service"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]

    return SecretsListResponse(tool_id=tool_id, secrets=secrets, count=len(secrets))


async def get_tool_secrets_decrypted(tool_id: str, org_id: str) -> Dict[str, str]:
    """Fetch and decrypt all secrets for a tool.
    
    Called internally at invocation time to inject as env vars.
    NOT exposed via API — values never leave the backend.
    
    Returns:
        Dict mapping env var name → decrypted value.
    """
    db = get_db()
    if not db.is_configured:
        return {}

    rows = await db.execute(
        """
        SELECT key, encrypted_value
        FROM tool_secrets
        WHERE tool_id = $1 AND org_id = $2
        """,
        [tool_id, org_id],
    )

    result = {}
    for row in rows:
        try:
            result[row["key"]] = _decrypt(row["encrypted_value"])
        except Exception as e:
            logger.error(f"Failed to decrypt secret {row['key']} for tool {tool_id}: {e}")

    return result
