"""Centralized configuration for Tool Foundry."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Application settings."""

    # Environment
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment",
    )

    # Modal configuration
    modal_app_name: str = Field(default="tool-foundry", description="Modal app name")
    modal_registry_dict_name: str = Field(
        default="tool-foundry-registry",
        description="Modal Dict name for registry",
    )

    # API configuration
    api_base_url: Optional[str] = Field(
        default=None,
        description="Base URL for the deployed API (set by Modal)",
    )

    # Tool execution limits
    tool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    tool_memory_mb: int = Field(default=256, ge=128, le=2048)
    tool_cpu: float = Field(default=0.25, ge=0.1, le=2.0)
    tool_max_code_size_bytes: int = Field(default=50_000, ge=1000)

    # TTL configuration
    default_ttl_hours: int = Field(default=24, ge=1, le=168)
    max_ttl_hours: int = Field(default=168, ge=1, le=720)

    # Rate limiting
    rate_limit_requests_per_minute: int = Field(default=60, ge=1)
    rate_limit_tools_per_hour: int = Field(default=100, ge=1)

    # Agent configuration
    agent_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model to use for tool generation",
    )
    agent_max_tokens: int = Field(default=4096, ge=256, le=8192)
    agent_temperature: float = Field(default=0.0, ge=0.0, le=1.0)

    # Amigo integration
    amigo_api_base_url: Optional[str] = Field(
        default=None,
        description="Amigo API base URL for system events",
    )

    # Feature flags
    enable_sandbox_execution: bool = Field(
        default=True,
        description="Use Modal Sandbox for tool execution (vs exec)",
    )
    enable_async_builds: bool = Field(
        default=True,
        description="Build tools asynchronously with events",
    )
    enable_event_emission: bool = Field(
        default=True,
        description="Emit system events to Amigo",
    )

    class Config:
        env_prefix = "FOUNDRY_"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings(
        environment=os.getenv("FOUNDRY_ENVIRONMENT", "development"),
        api_base_url=os.getenv("FOUNDRY_API_BASE_URL"),
        amigo_api_base_url=os.getenv("AMIGO_API_BASE_URL"),
        agent_model=os.getenv("FOUNDRY_AGENT_MODEL", "claude-sonnet-4-20250514"),
    )


def is_production() -> bool:
    """Check if running in production environment."""
    return get_settings().environment == "production"


def is_development() -> bool:
    """Check if running in development environment."""
    return get_settings().environment == "development"
