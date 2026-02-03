"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolStatus(str, Enum):
    """Status of a tool in the registry."""

    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"
    DEPRECATED = "deprecated"


class CreateToolRequest(BaseModel):
    """Request to create a new tool with explicit implementation."""

    name: str = Field(..., description="Human-readable tool name")
    description: str = Field(..., description="Description of what the tool does")
    input_schema: Dict[str, Any] = Field(..., description="JSON Schema for tool inputs")
    implementation: str = Field(
        ...,
        description="Python code implementing the tool. Must define a main() function.",
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Pip packages to install (from allowlist only)",
    )
    ttl_hours: int = Field(default=24, ge=1, le=168, description="Time to live in hours")
    org_id: str = Field(..., description="Organization ID for scoping")
    conversation_id: str = Field(..., description="Conversation ID for system events")


class CreateCapabilityRequest(BaseModel):
    """Request to create a tool from a capability description (agent-driven)."""

    capability_description: str = Field(
        ...,
        description="Natural language description of the needed capability",
        min_length=10,
        max_length=2000,
    )
    context: Optional[str] = Field(
        default=None,
        description="Additional context for the agent (e.g., conversation history)",
        max_length=5000,
    )
    ttl_hours: int = Field(default=24, ge=1, le=168, description="Time to live in hours")
    org_id: str = Field(..., description="Organization ID for scoping")
    conversation_id: str = Field(..., description="Conversation ID for system events")
    async_build: bool = Field(
        default=True,
        description="If True, return immediately and emit event when ready",
    )


class CreateToolResponse(BaseModel):
    """Response after creating a tool."""

    tool_id: str = Field(..., description="Unique identifier for the tool")
    status: ToolStatus = Field(..., description="Current build status")
    manifest_url: str = Field(..., description="URL to fetch the tool manifest")
    invoke_url: str = Field(..., description="URL to invoke the tool")
    message: str = Field(default="", description="Status message or error details")


class CreateCapabilityResponse(BaseModel):
    """Response after submitting a capability request."""

    request_id: str = Field(..., description="Unique identifier for the build request")
    tool_id: Optional[str] = Field(
        default=None,
        description="Tool ID if build completed synchronously",
    )
    status: str = Field(..., description="Current status (building, ready, failed)")
    message: str = Field(default="", description="Status message or error details")
    manifest_url: Optional[str] = Field(
        default=None,
        description="URL to fetch the tool manifest (if ready)",
    )
    invoke_url: Optional[str] = Field(
        default=None,
        description="URL to invoke the tool (if ready)",
    )


class ToolManifest(BaseModel):
    """Manifest describing how to invoke a tool."""

    tool_id: str
    name: str
    description: str
    status: ToolStatus
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "object"},
        description="JSON Schema for tool output",
    )
    invoke_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None


class InvokeRequest(BaseModel):
    """Request to invoke a tool."""

    input: Dict[str, Any] = Field(..., description="Input data matching the tool's input_schema")


class ResultType(str, Enum):
    """Type of result returned by a tool."""

    TEXT = "text"
    NUMBER = "number"
    IMAGE = "image"
    TABLE = "table"
    OBJECT = "object"


class TypedResult(BaseModel):
    """Typed result envelope - agents always know the shape."""

    text: Optional[str] = Field(default=None, description="String result")
    number: Optional[float] = Field(default=None, description="Numeric result")
    image_base64: Optional[str] = Field(default=None, description="Base64-encoded image (PNG/JPEG)")
    table: Optional[List[Dict[str, Any]]] = Field(default=None, description="Tabular data as list of rows")
    object: Optional[Dict[str, Any]] = Field(default=None, description="Complex object/dict result")


class InvokeResponse(BaseModel):
    """Response from invoking a tool - always predictable shape for agents."""

    success: bool = Field(..., description="Whether the invocation succeeded")
    result_type: Optional[ResultType] = Field(
        default=None,
        description="Which field in 'result' contains the data: text, number, image, table, object"
    )
    result: TypedResult = Field(
        default_factory=TypedResult,
        description="Typed result envelope - check result_type for which field has data"
    )
    raw_result: Any = Field(
        default=None,
        description="Original untyped result (for backwards compatibility)"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time_ms: int = Field(..., description="Execution time in milliseconds")


class ToolRegistryEntry(BaseModel):
    """Internal registry entry for a tool."""

    tool_id: str
    org_id: str
    conversation_id: str
    name: str
    description: str
    status: ToolStatus
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    implementation: str
    sandbox_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None


class BuildStatusResponse(BaseModel):
    """Response for checking build status."""

    request_id: str
    tool_id: Optional[str] = None
    status: str
    error: Optional[str] = None
    created_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str = "0.1.0"
    features: Dict[str, bool] = Field(default_factory=dict)


class RebuildToolRequest(BaseModel):
    """Request to rebuild an existing tool."""

    capability_description: Optional[str] = Field(
        default=None,
        description="New capability description (if changing functionality)",
    )
    fix_instructions: Optional[str] = Field(
        default=None,
        description="Instructions to fix a broken tool (e.g., 'handle empty results')",
    )
    async_build: bool = Field(
        default=True,
        description="If True, return immediately and emit event when ready",
    )


class RebuildToolResponse(BaseModel):
    """Response after rebuilding a tool."""

    tool_id: str
    previous_version: Optional[str] = None
    status: str
    message: str = ""
    manifest_url: Optional[str] = None
    invoke_url: Optional[str] = None


class DeprecateToolRequest(BaseModel):
    """Request to deprecate/disable a tool."""

    reason: Optional[str] = Field(
        default=None,
        description="Reason for deprecation",
    )
    replacement_tool_id: Optional[str] = Field(
        default=None,
        description="ID of the replacement tool, if any",
    )
