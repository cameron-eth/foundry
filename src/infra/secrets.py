"""Secrets management for Tool Foundry.

In Modal, secrets are injected as environment variables.
This module provides a clean interface for accessing them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from src.infra.logging import get_logger

logger = get_logger("secrets")


class SecretNotFoundError(Exception):
    """Raised when a required secret is not found."""

    pass


def get_secret(name: str, required: bool = True) -> Optional[str]:
    """
    Get a secret value from environment.

    In Modal, secrets are configured via `modal secret create` and
    attached to functions via `secrets=[modal.Secret.from_name(...)]`.

    Args:
        name: The environment variable name.
        required: If True, raises SecretNotFoundError if not found.

    Returns:
        The secret value, or None if not found and not required.

    Raises:
        SecretNotFoundError: If required and not found.
    """
    value = os.environ.get(name)

    if value is None and required:
        logger.error(f"Required secret '{name}' not found")
        raise SecretNotFoundError(f"Secret '{name}' is required but not set")

    return value


@dataclass
class AmigoCredentials:
    """Credentials for Amigo API integration."""

    api_base_url: str
    api_key: str


@lru_cache()
def get_amigo_credentials() -> Optional[AmigoCredentials]:
    """
    Get Amigo API credentials.

    These should be set via Modal secrets:
        modal secret create amigo-credentials \
            AMIGO_API_BASE_URL=https://api.amigo.ai \
            AMIGO_API_KEY=your-api-key

    Returns:
        AmigoCredentials if configured, None otherwise.
    """
    api_base_url = get_secret("AMIGO_API_BASE_URL", required=False)
    api_key = get_secret("AMIGO_API_KEY", required=False)

    if api_base_url and api_key:
        return AmigoCredentials(api_base_url=api_base_url, api_key=api_key)

    logger.warning("Amigo credentials not configured, event emission disabled")
    return None


@lru_cache()
def get_anthropic_api_key() -> Optional[str]:
    """
    Get Anthropic API key for the agent.

    Set via Modal secrets:
        modal secret create anthropic-credentials \
            ANTHROPIC_API_KEY=your-api-key

    Returns:
        API key if configured, None otherwise.
    """
    key = get_secret("ANTHROPIC_API_KEY", required=False)
    if not key:
        logger.warning("Anthropic API key not configured, agent features disabled")
    return key


def validate_required_secrets() -> bool:
    """
    Validate that all required secrets are present.

    Returns:
        True if all required secrets are present.

    Raises:
        SecretNotFoundError: If any required secret is missing.
    """
    # For now, no secrets are strictly required (graceful degradation)
    # In production, you might want to require certain secrets
    return True
