"""
Tool Foundry - Modal Application

This is the main entry point for the Tool Foundry service.
Deploy with: modal deploy foundry.py
Serve locally with: modal serve foundry.py
"""

from __future__ import annotations

import modal

# Create the Modal app
app = modal.App("toolfoundry")

# Base image with all dependencies pre-installed
# Updated: force httpx availability for tool execution
foundry_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        # Core dependencies
        "fastapi>=0.109.0",
        "pydantic>=2.0.0",
        "httpx>=0.27.0",
        "requests>=2.31.0",
        # Agent dependencies
        "anthropic>=0.18.0",
        # Allowed packages for tools
        "numpy",
        "pandas",
        "scipy",
        "scikit-learn",
        "matplotlib",
    )
    .run_commands("python -c 'import httpx; print(httpx.__version__)'")  # Verify httpx
    .add_local_python_source("src")
)

# Secrets configuration
# Create with:
#   modal secret create anthropic-credentials ANTHROPIC_API_KEY=...
#   modal secret create exa-credentials EXA_API_KEY=...
anthropic_secret = modal.Secret.from_name("anthropic-credentials")
exa_secret = modal.Secret.from_name("exa-credentials")

# Optional Amigo credentials (for event emission)
optional_amigo_secret = modal.Secret.from_dict({
    "AMIGO_API_BASE_URL": "",
    "AMIGO_API_KEY": "",
})


@app.function(
    image=foundry_image,
    secrets=[anthropic_secret, exa_secret, optional_amigo_secret],
    timeout=300,
    memory=512,
)
@modal.asgi_app()
def serve():
    """
    Main API endpoint for Tool Foundry.

    This exposes the FastAPI application as a Modal web endpoint.
    The URL will be: https://{workspace}--tool-foundry-foundry-api.modal.run
    """
    from src.api.routes import web_app
    from src.infra.logging import setup_logging

    setup_logging()
    return web_app


@app.function(
    image=foundry_image,
    secrets=[anthropic_secret, exa_secret, optional_amigo_secret],
    timeout=120,
    memory=1024,
)
async def build_tool_async(
    capability_description: str,
    org_id: str,
    conversation_id: str,
    context: str | None = None,
    ttl_hours: int = 24,
) -> dict:
    """
    Build a tool asynchronously from a capability description.

    This function is spawned by the API to handle async builds.

    Args:
        capability_description: Natural language description of needed capability.
        org_id: Organization ID.
        conversation_id: Conversation ID.
        context: Optional additional context.
        ttl_hours: Time to live in hours.

    Returns:
        Dict with build result including tool_id if successful.
    """
    from src.orchestration.workflow import BuildRequest, process_build_request
    from src.registry.store import get_registry
    from src.events.amigo import create_event_emitter
    from src.infra.logging import setup_logging, get_logger

    setup_logging()
    logger = get_logger("build_worker")

    logger.info(f"Starting async build for {org_id}/{conversation_id}")

    # Create build request
    build_request = BuildRequest(
        org_id=org_id,
        conversation_id=conversation_id,
        capability_description=capability_description,
        context=context,
        ttl_hours=ttl_hours,
    )

    # Get registry (use Modal Dict in production)
    registry = get_registry(use_modal=True)

    # Get event emitter
    event_emitter = create_event_emitter()

    # Process the build
    result = await process_build_request(
        request=build_request,
        registry=registry,
        event_emitter=event_emitter,
    )

    logger.info(f"Build complete: success={result.success}, tool_id={result.tool_id}")

    return {
        "success": result.success,
        "request_id": result.request_id,
        "tool_id": result.tool_id,
        "state": result.state.value,
        "error": result.error,
        "duration_ms": result.duration_ms,
    }


@app.function(
    image=foundry_image,
    secrets=[optional_amigo_secret],
    schedule=modal.Cron("0 * * * *"),  # Every hour
    timeout=120,
)
def cleanup_expired_tools():
    """Periodically clean up expired tools from the registry."""
    from src.registry.store import get_registry
    from src.infra.logging import setup_logging, get_logger

    setup_logging()
    logger = get_logger("cleanup")

    try:
        # Use Modal Dict registry for persistence
        registry = get_registry(use_modal=True)
        expired_count = registry.cleanup_expired()

        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired tools")
        else:
            logger.debug("No expired tools to clean up")

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")


@app.function(
    image=foundry_image,
    timeout=60,
)
def health_check() -> dict:
    """Health check function for monitoring."""
    from src.infra.config import get_settings

    settings = get_settings()

    return {
        "status": "healthy",
        "service": "tool-foundry",
        "environment": settings.environment,
        "features": {
            "agent": True,
            "sandbox": settings.enable_sandbox_execution,
            "async_builds": settings.enable_async_builds,
            "events": settings.enable_event_emission,
        },
    }


# Local entrypoint for testing
@app.local_entrypoint()
def main():
    """Local entrypoint for testing."""
    print("=" * 60)
    print("Tool Foundry")
    print("=" * 60)
    print()
    print("Commands:")
    print("  modal serve foundry.py    # Local development with hot reload")
    print("  modal deploy foundry.py   # Deploy to Modal")
    print()
    print("Setup secrets:")
    print("  modal secret create anthropic-credentials ANTHROPIC_API_KEY=...")
    print("  modal secret create amigo-credentials \\")
    print("    AMIGO_API_BASE_URL=https://api.amigo.ai \\")
    print("    AMIGO_API_KEY=...")
    print()

    # Run health check
    result = health_check.local()
    print("Health check:", result)
