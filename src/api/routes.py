"""FastAPI routes for Tool Foundry API.

Organized with versioned routers and proper separation of concerns.
"""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, APIRouter, Depends, Header, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from src.api.schemas import (
    BuildStatusResponse,
    CreateCapabilityRequest,
    CreateCapabilityResponse,
    CreateToolRequest,
    CreateToolResponse,
    DeprecateToolRequest,
    HealthResponse,
    InvokeRequest,
    InvokeResponse,
    RebuildToolRequest,
    RebuildToolResponse,
    ToolManifest,
    ToolRegistryEntry,
    ToolStatus,
)
from src.builder.validator import validate_restricted_python
from src.infra.config import get_settings
from src.infra.logging import get_logger, setup_logging
from src.infra.secrets import get_anthropic_api_key

# Setup logging on import
setup_logging()
logger = get_logger("api")

# =============================================================================
# Registry Setup
# =============================================================================

from src.registry.store import RegistryBase, InMemoryRegistry, ModalDictRegistry

_registry_instance: Optional[RegistryBase] = None


def get_registry() -> RegistryBase:
    """Get the registry instance, initializing if needed."""
    global _registry_instance
    if _registry_instance is not None:
        return _registry_instance

    try:
        import os

        if os.environ.get("MODAL_ENVIRONMENT"):
            _registry_instance = ModalDictRegistry("tool-foundry-registry")
            logger.info("Using Modal Dict registry for persistence")
            return _registry_instance
    except Exception as e:
        logger.warning(f"Could not initialize Modal Dict: {e}")

    _registry_instance = InMemoryRegistry()
    logger.info("Using in-memory registry")
    return _registry_instance


# =============================================================================
# API Key Authentication
# =============================================================================

# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Valid API keys (loaded from environment)
_valid_api_keys: Optional[set] = None


def _get_valid_api_keys() -> set:
    """Load valid API keys from environment."""
    global _valid_api_keys
    if _valid_api_keys is not None:
        return _valid_api_keys

    import os
    keys_str = os.environ.get("TOOLFOUNDRY_API_KEYS", "")
    if keys_str:
        _valid_api_keys = set(k.strip() for k in keys_str.split(",") if k.strip())
    else:
        _valid_api_keys = set()

    return _valid_api_keys


def _is_auth_enabled() -> bool:
    """Check if API key auth is enabled."""
    import os
    return os.environ.get("TOOLFOUNDRY_REQUIRE_AUTH", "false").lower() == "true"


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """Verify the API key if authentication is enabled."""
    if not _is_auth_enabled():
        return None  # Auth disabled, allow all

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide X-API-Key header.",
        )

    valid_keys = _get_valid_api_keys()
    if not valid_keys:
        logger.warning("Auth enabled but no API keys configured")
        raise HTTPException(
            status_code=500,
            detail="Server misconfigured: no API keys set",
        )

    if api_key not in valid_keys:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key",
        )

    return api_key
    return _registry_instance


# In-memory build requests tracking
_build_requests: Dict[str, Dict] = {}


def get_base_url() -> str:
    """Get the base URL for the deployed service."""
    import os

    modal_url = os.environ.get("MODAL_SERVE_URL")
    if modal_url:
        return modal_url.rstrip("/")

    settings = get_settings()
    if settings.api_base_url:
        return settings.api_base_url.rstrip("/")

    return "https://cameron-40558--toolfoundry-serve.modal.run"


# =============================================================================
# FastAPI App with Metadata
# =============================================================================

web_app = FastAPI(
    title="Tool Foundry API",
    description="""
## Dynamic Tool Creation & Execution Service

Tool Foundry enables AI agents to dynamically create, manage, and execute tools.

### Key Features
- **Agent-Driven Creation**: Describe a capability in natural language, get a working tool
- **Direct Creation**: Provide Python code directly for full control
- **Secure Execution**: Sandboxed execution with validated code
- **Persistent Registry**: Tools survive deployments

### Quick Start
1. Create a tool via `/v1/capabilities` (agent-driven) or `/v1/tools` (direct)
2. Invoke it via `/v1/tools/{id}/invoke`
3. Manage with rebuild, deprecate, or delete endpoints
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "health",
            "description": "Health checks and service status",
        },
        {
            "name": "construct",
            "description": "Agent-driven tool construction from natural language descriptions",
        },
        {
            "name": "tools",
            "description": "Tool management: create, list, get, update, delete",
        },
        {
            "name": "execution",
            "description": "Tool invocation and execution",
        },
    ],
)


# =============================================================================
# Routers
# =============================================================================

# Health router (no version prefix, no auth required)
health_router = APIRouter(tags=["health"])

# V1 API routers (auth required when enabled)
construct_router = APIRouter(
    prefix="/v1/construct",
    tags=["construct"],
    dependencies=[Depends(verify_api_key)],
)
tools_router = APIRouter(
    prefix="/v1/tools",
    tags=["tools"],
    dependencies=[Depends(verify_api_key)],
)
execution_router = APIRouter(
    prefix="/v1/tools",
    tags=["execution"],
    dependencies=[Depends(verify_api_key)],
)
builds_router = APIRouter(
    prefix="/v1/builds",
    tags=["construct"],
    dependencies=[Depends(verify_api_key)],
)


# =============================================================================
# Health Endpoints
# =============================================================================


@health_router.get("/", include_in_schema=False)
async def root():
    """API root - redirect info."""
    return {
        "service": "Tool Foundry",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "api": "/v1",
    }


@health_router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check service health and feature availability."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        service="tool-foundry",
        version="1.0.0",
        features={
            "agent_enabled": bool(get_anthropic_api_key()),
            "sandbox_enabled": settings.enable_sandbox_execution,
            "async_builds": settings.enable_async_builds,
            "event_emission": settings.enable_event_emission,
        },
    )


@health_router.get("/v1", include_in_schema=False)
async def v1_info():
    """V1 API information."""
    return {
        "version": "v1",
        "endpoints": {
            "capabilities": "/v1/capabilities",
            "tools": "/v1/tools",
            "builds": "/v1/builds",
        },
    }


# =============================================================================
# Capabilities Endpoints (Agent-Driven Creation)
# =============================================================================


def get_builder_agent():
    """Get or create the builder agent."""
    from src.agent import get_builder_agent as _get_agent

    return _get_agent()


async def _build_capability_async(
    request_id: str,
    request: CreateCapabilityRequest = None,
    description: str = None,
    org_id: str = None,
    conversation_id: str = None,
    ttl_hours: int = 24,
) -> None:
    """Background task to build a capability."""
    try:
        agent = get_builder_agent()

        # Use request object or individual params
        if request:
            desc = request.capability_description
            ctx = request.context
            o_id = request.org_id
            c_id = request.conversation_id
            ttl = request.ttl_hours
        else:
            desc = description
            ctx = None
            o_id = org_id
            c_id = conversation_id
            ttl = ttl_hours

        result = await agent.build_from_description(
            capability_description=desc,
            context=ctx,
            org_id=o_id,
            conversation_id=c_id,
        )

        if not result.success:
            _build_requests[request_id]["status"] = "failed"
            _build_requests[request_id]["error"] = result.error
            return

        # Create tool entry
        tool_id = f"tool-{uuid.uuid4().hex[:12]}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl)

        entry = ToolRegistryEntry(
            tool_id=tool_id,
            org_id=o_id,
            conversation_id=c_id,
            name=result.tool_name,
            description=result.tool_description,
            status=ToolStatus.READY,
            input_schema=result.input_schema,
            implementation=result.implementation,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )

        get_registry()[tool_id] = entry

        _build_requests[request_id]["status"] = "ready"
        _build_requests[request_id]["tool_id"] = tool_id

        logger.info(f"Async build complete: {request_id} -> {tool_id}")

    except Exception as e:
        logger.error(f"Async build failed: {request_id}: {e}")
        _build_requests[request_id]["status"] = "failed"
        _build_requests[request_id]["error"] = str(e)


@construct_router.post(
    "",
    response_model=CreateCapabilityResponse,
    summary="Create tool from description",
    description="Use AI to generate a tool from a natural language capability description.",
)
async def create_capability(
    request: CreateCapabilityRequest,
    background_tasks: BackgroundTasks,
) -> CreateCapabilityResponse:
    """Create a tool from a capability description using the AI agent."""
    request_id = f"req-{uuid.uuid4().hex[:12]}"
    base_url = get_base_url()

    if not get_anthropic_api_key():
        return CreateCapabilityResponse(
            request_id=request_id,
            status="failed",
            message="Agent not available: Anthropic API key not configured",
        )

    settings = get_settings()

    # Async build
    if request.async_build and settings.enable_async_builds:
        _build_requests[request_id] = {
            "status": "building",
            "tool_id": None,
            "error": None,
            "created_at": datetime.now(timezone.utc),
        }

        background_tasks.add_task(_build_capability_async, request_id, request)

        logger.info(f"Queued async build: {request_id}")
        return CreateCapabilityResponse(
            request_id=request_id,
            status="building",
            message="Build started. Poll /v1/builds/{request_id} for status.",
        )

    # Synchronous build
    try:
        agent = get_builder_agent()
        result = await agent.build_from_description(
            capability_description=request.capability_description,
            context=request.context,
            org_id=request.org_id,
            conversation_id=request.conversation_id,
        )

        if not result.success:
            return CreateCapabilityResponse(
                request_id=request_id,
                status="failed",
                message=f"Build failed: {result.error}",
            )

        tool_id = f"tool-{uuid.uuid4().hex[:12]}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=request.ttl_hours)

        entry = ToolRegistryEntry(
            tool_id=tool_id,
            org_id=request.org_id,
            conversation_id=request.conversation_id,
            name=result.tool_name,
            description=result.tool_description,
            status=ToolStatus.READY,
            input_schema=result.input_schema,
            implementation=result.implementation,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )

        get_registry()[tool_id] = entry
        logger.info(f"Created tool from capability: {tool_id}")

        return CreateCapabilityResponse(
            request_id=request_id,
            tool_id=tool_id,
            status="ready",
            message="Tool created successfully",
            manifest_url=f"{base_url}/v1/tools/{tool_id}",
            invoke_url=f"{base_url}/v1/tools/{tool_id}/invoke",
        )

    except Exception as e:
        logger.error(f"Capability creation failed: {e}")
        return CreateCapabilityResponse(
            request_id=request_id,
            status="failed",
            message=f"Build failed: {str(e)}",
        )


# =============================================================================
# Build Status Endpoints
# =============================================================================


@builds_router.get(
    "/{request_id}",
    response_model=BuildStatusResponse,
    summary="Check build status",
    description="Check the status of an async build request.",
)
async def get_build_status(request_id: str) -> BuildStatusResponse:
    """Check the status of an async build request."""
    if request_id not in _build_requests:
        raise HTTPException(status_code=404, detail=f"Build request {request_id} not found")

    build = _build_requests[request_id]
    return BuildStatusResponse(
        request_id=request_id,
        tool_id=build.get("tool_id"),
        status=build["status"],
        error=build.get("error"),
        created_at=build.get("created_at"),
    )


# =============================================================================
# Tools Management Endpoints
# =============================================================================


@tools_router.post(
    "",
    response_model=CreateToolResponse,
    summary="Create tool with code",
    description="Create a tool by providing Python implementation directly.",
)
async def create_tool(request: CreateToolRequest) -> CreateToolResponse:
    """Create a tool by providing Python implementation directly."""
    tool_id = f"tool-{uuid.uuid4().hex[:12]}"
    base_url = get_base_url()

    # Validate the implementation
    try:
        validate_restricted_python(request.implementation)
    except Exception as e:
        return CreateToolResponse(
            tool_id=tool_id,
            status=ToolStatus.FAILED,
            manifest_url=f"{base_url}/v1/tools/{tool_id}",
            invoke_url=f"{base_url}/v1/tools/{tool_id}/invoke",
            message=f"Validation failed: {str(e)}",
        )

    # Create registry entry
    expires_at = datetime.now(timezone.utc) + timedelta(hours=request.ttl_hours)
    entry = ToolRegistryEntry(
        tool_id=tool_id,
        org_id=request.org_id,
        conversation_id=request.conversation_id,
        name=request.name,
        description=request.description,
        status=ToolStatus.READY,
        input_schema=request.input_schema,
        implementation=request.implementation,
        created_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )

    get_registry()[tool_id] = entry
    logger.info(f"Created tool {tool_id}: {request.name}")

    return CreateToolResponse(
        tool_id=tool_id,
        status=ToolStatus.READY,
        manifest_url=f"{base_url}/v1/tools/{tool_id}",
        invoke_url=f"{base_url}/v1/tools/{tool_id}/invoke",
        message="Tool created successfully",
    )


@tools_router.get(
    "",
    summary="List tools",
    description="List all tools, optionally filtered by organization.",
)
async def list_tools(org_id: Optional[str] = None) -> Dict[str, List[ToolManifest]]:
    """List all tools, optionally filtered by org_id."""
    base_url = get_base_url()
    tools = []

    for entry in get_registry().values():
        if org_id and entry.org_id != org_id:
            continue

        if entry.expires_at and datetime.now(timezone.utc) > entry.expires_at:
            entry.status = ToolStatus.EXPIRED
            get_registry()[entry.tool_id] = entry

        tools.append(
            ToolManifest(
                tool_id=entry.tool_id,
                name=entry.name,
                description=entry.description,
                status=entry.status,
                input_schema=entry.input_schema,
                output_schema=entry.output_schema,
                invoke_url=f"{base_url}/v1/tools/{entry.tool_id}/invoke",
                created_at=entry.created_at,
                expires_at=entry.expires_at,
            )
        )
    return {"tools": tools}


@tools_router.get(
    "/{tool_id}",
    response_model=ToolManifest,
    summary="Get tool manifest",
    description="Get the manifest/schema for a specific tool.",
)
async def get_tool(tool_id: str) -> ToolManifest:
    """Get the manifest for a specific tool."""
    entry = get_registry().get(tool_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    base_url = get_base_url()
    return ToolManifest(
        tool_id=entry.tool_id,
        name=entry.name,
        description=entry.description,
        status=entry.status,
        input_schema=entry.input_schema,
        output_schema=entry.output_schema,
        invoke_url=f"{base_url}/v1/tools/{entry.tool_id}/invoke",
        created_at=entry.created_at,
        expires_at=entry.expires_at,
    )


@tools_router.delete(
    "/{tool_id}",
    summary="Delete tool",
    description="Permanently delete a tool from the registry.",
)
async def delete_tool(tool_id: str) -> Dict[str, str]:
    """Delete a tool from the registry."""
    if tool_id not in get_registry():
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    del get_registry()[tool_id]
    logger.info(f"Deleted tool {tool_id}")
    return {"status": "deleted", "tool_id": tool_id}


@tools_router.post(
    "/{tool_id}/deprecate",
    summary="Deprecate tool",
    description="Mark a tool as deprecated (soft delete).",
)
async def deprecate_tool(tool_id: str, request: DeprecateToolRequest) -> Dict[str, Any]:
    """Deprecate a tool (soft delete)."""
    entry = get_registry().get(tool_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    entry.status = ToolStatus.DEPRECATED
    if request.reason:
        entry.error_message = f"Deprecated: {request.reason}"

    get_registry()[tool_id] = entry
    logger.info(f"Deprecated tool {tool_id}: {request.reason or 'No reason given'}")

    response: Dict[str, Any] = {
        "status": "deprecated",
        "tool_id": tool_id,
        "message": request.reason or "Tool deprecated",
    }
    if request.replacement_tool_id:
        response["replacement_tool_id"] = request.replacement_tool_id

    return response


@tools_router.post(
    "/{tool_id}/rebuild",
    response_model=RebuildToolResponse,
    summary="Rebuild tool",
    description="Rebuild a tool with new instructions or fix a broken tool.",
)
async def rebuild_tool(
    tool_id: str,
    request: RebuildToolRequest,
    background_tasks: BackgroundTasks,
) -> RebuildToolResponse:
    """Rebuild a tool with new instructions or fix a broken tool."""
    entry = get_registry().get(tool_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    if request.capability_description:
        description = request.capability_description
    elif request.fix_instructions:
        description = f"Fix the following tool: {entry.description}. Issues to fix: {request.fix_instructions}. Previous implementation had status: {entry.status}"
        if entry.error_message:
            description += f". Error was: {entry.error_message}"
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either capability_description or fix_instructions",
        )

    base_url = get_base_url()

    # Mark old tool as deprecated
    entry.status = ToolStatus.DEPRECATED
    get_registry()[tool_id] = entry

    if request.async_build:
        request_id = f"rebuild-{secrets.token_hex(6)}"
        _build_requests[request_id] = {
            "status": "building",
            "tool_id": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "previous_tool_id": tool_id,
        }

        background_tasks.add_task(
            _build_capability_async,
            request_id=request_id,
            description=description,
            org_id=entry.org_id,
            conversation_id=entry.conversation_id,
            ttl_hours=24,
        )

        logger.info(f"Started rebuild for tool {tool_id}, request {request_id}")
        return RebuildToolResponse(
            tool_id=tool_id,
            previous_version=tool_id,
            status="rebuilding",
            message=f"Rebuild started. Check status at /v1/builds/{request_id}",
        )
    else:
        try:
            from src.agent import get_builder_agent

            agent = get_builder_agent()
            result = await agent.build_from_description(description)

            if not result.success:
                raise HTTPException(
                    status_code=500,
                    detail=f"Rebuild failed: {result.error or 'Unknown error'}",
                )

            new_tool_id = f"tool-{secrets.token_hex(6)}"
            new_entry = ToolRegistryEntry(
                tool_id=new_tool_id,
                org_id=entry.org_id,
                conversation_id=entry.conversation_id,
                name=result.tool_name or "rebuilt_tool",
                description=result.tool_description or description[:100],
                status=ToolStatus.READY,
                input_schema=result.input_schema or {"type": "object"},
                implementation=result.implementation,
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            get_registry()[new_tool_id] = new_entry

            logger.info(f"Rebuilt tool {tool_id} as {new_tool_id}")
            return RebuildToolResponse(
                tool_id=new_tool_id,
                previous_version=tool_id,
                status="ready",
                message="Tool rebuilt successfully",
                manifest_url=f"{base_url}/v1/tools/{new_tool_id}",
                invoke_url=f"{base_url}/v1/tools/{new_tool_id}/invoke",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rebuild failed for {tool_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Execution Endpoints
# =============================================================================


@execution_router.post(
    "/{tool_id}/invoke",
    response_model=InvokeResponse,
    summary="Invoke tool",
    description="Execute a tool with the provided input.",
)
async def invoke_tool(tool_id: str, request: InvokeRequest) -> InvokeResponse:
    """Execute a tool with the provided input."""
    from src.api.schemas import ResultType, TypedResult

    entry = get_registry().get(tool_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")

    if entry.status == ToolStatus.EXPIRED:
        raise HTTPException(status_code=410, detail=f"Tool {tool_id} has expired")

    if entry.status == ToolStatus.DEPRECATED:
        raise HTTPException(status_code=410, detail=f"Tool {tool_id} is deprecated")

    if entry.status != ToolStatus.READY:
        raise HTTPException(
            status_code=400,
            detail=f"Tool {tool_id} is not ready (status: {entry.status})",
        )

    logger.info(f"Invoking tool {tool_id}")

    try:
        from src.builder.sandbox import get_executor

        executor = get_executor()
        exec_result = executor.execute(
            implementation=entry.implementation,
            input_data=request.input,
            timeout_seconds=30,
        )

        if not exec_result.success:
            logger.warning(f"Tool {tool_id} execution failed: {exec_result.error}")
            return InvokeResponse(
                success=False,
                result_type=None,
                result=TypedResult(),
                raw_result=None,
                error=exec_result.error,
                execution_time_ms=exec_result.execution_time_ms,
            )

        # Classify and wrap the result in typed envelope
        raw = exec_result.result
        result_type, typed_result = _classify_result(raw)

        return InvokeResponse(
            success=True,
            result_type=result_type,
            result=typed_result,
            raw_result=raw,
            error=None,
            execution_time_ms=exec_result.execution_time_ms,
        )

    except Exception as e:
        logger.error(f"Tool {tool_id} invocation error: {e}")
        return InvokeResponse(
            success=False,
            result_type=None,
            result=TypedResult(),
            raw_result=None,
            error=str(e),
            execution_time_ms=0,
        )


def _classify_result(raw: Any) -> tuple:
    """Classify raw result into typed envelope."""
    from src.api.schemas import ResultType, TypedResult

    # Check for base64 image (string starting with image markers or long base64)
    if isinstance(raw, str):
        # Check if it looks like base64 image data
        if (
            raw.startswith("iVBOR")  # PNG
            or raw.startswith("/9j/")  # JPEG
            or raw.startswith("R0lGOD")  # GIF
            or (len(raw) > 1000 and raw.replace("+", "").replace("/", "").replace("=", "").isalnum())
        ):
            return ResultType.IMAGE, TypedResult(image_base64=raw)
        # Regular text
        return ResultType.TEXT, TypedResult(text=raw)

    # Check for number
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return ResultType.NUMBER, TypedResult(number=float(raw))

    # Check for table (list of dicts)
    if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], dict):
        return ResultType.TABLE, TypedResult(table=raw)

    # Check for dict with image_base64 key (common pattern)
    if isinstance(raw, dict):
        if "image_base64" in raw or "image" in raw:
            img = raw.get("image_base64") or raw.get("image")
            if isinstance(img, str):
                return ResultType.IMAGE, TypedResult(image_base64=img)
        # Regular object
        return ResultType.OBJECT, TypedResult(object=raw)

    # Fallback - convert to object
    return ResultType.OBJECT, TypedResult(object={"value": raw})


# Legacy endpoint for backward compatibility
@execution_router.post(
    "/{tool_id}:invoke",
    response_model=InvokeResponse,
    include_in_schema=False,  # Hide from docs, keep for compatibility
)
async def invoke_tool_legacy(tool_id: str, request: InvokeRequest) -> InvokeResponse:
    """Legacy invoke endpoint (use /invoke instead)."""
    return await invoke_tool(tool_id, request)


# Legacy manifest endpoint
@tools_router.get(
    "/{tool_id}/manifest",
    response_model=ToolManifest,
    include_in_schema=False,
)
async def get_manifest_legacy(tool_id: str) -> ToolManifest:
    """Legacy manifest endpoint (use GET /v1/tools/{id} instead)."""
    return await get_tool(tool_id)


# =============================================================================
# Register Routers
# =============================================================================

web_app.include_router(health_router)
web_app.include_router(construct_router)
web_app.include_router(builds_router)
web_app.include_router(tools_router)
web_app.include_router(execution_router)


# =============================================================================
# Legacy Exports for Tests
# =============================================================================

def get_registry_instance():
    """Get the registry instance (for tests)."""
    return get_registry()
