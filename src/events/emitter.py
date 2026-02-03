"""Event system event emission.

This module handles sending system events to the Event backend
to notify agents when tools are ready for use.
"""

from __future__ import annotations

from typing import Dict, Literal, Optional

import httpx

from src.infra.logging import get_logger
from src.infra.secrets import get_event_credentials

logger = get_logger("events")


class EventEventEmitter:
    """Client for emitting system events to Event backend."""

    def __init__(self, api_base_url: str, api_key: str):
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key

    async def emit_event(
        self,
        org_id: str,
        conversation_id: str,
        event_type: str,
        payload: Dict,
    ) -> bool:
        """
        Emit a system event to the Event backend.

        Args:
            org_id: The organization ID.
            conversation_id: The conversation to emit the event to.
            event_type: The type of event (e.g., "tool_foundry.tool_ready").
            payload: The event payload.

        Returns:
            True if the event was emitted successfully, False otherwise.
        """
        url = f"{self.api_base_url}/v1/{org_id}/conversation/{conversation_id}/system-event"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "event_type": event_type,
                        "payload": payload,
                    },
                )
                response.raise_for_status()
                logger.info(
                    f"Emitted {event_type} event to {org_id}/{conversation_id}",
                )
                return True
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to emit event: HTTP {e.response.status_code} - {e.response.text}"
            )
            return False
        except httpx.RequestError as e:
            logger.error(f"Failed to emit event: {e}")
            return False

    async def emit_tool_ready(
        self,
        org_id: str,
        conversation_id: str,
        tool_id: str,
        status: Literal["ready", "failed"],
        manifest_url: Optional[str] = None,
        invoke_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """
        Emit a tool_foundry.tool_ready event.

        Args:
            org_id: The organization ID.
            conversation_id: The conversation ID.
            tool_id: The tool ID.
            status: "ready" or "failed".
            manifest_url: URL to fetch manifest.
            invoke_url: URL to invoke tool.
            error: Error message if failed.

        Returns:
            True if emitted successfully.
        """
        from src.infra.config import get_settings

        settings = get_settings()
        base_url = settings.api_base_url or "https://your-app--foundry-api.modal.run"

        payload = {
            "tool_id": tool_id,
            "status": status,
            "manifest_url": manifest_url or f"{base_url}/v1/tools/{tool_id}/manifest",
            "invoke_url": invoke_url or f"{base_url}/v1/tools/{tool_id}:invoke",
        }
        if error:
            payload["error"] = error

        return await self.emit_event(
            org_id=org_id,
            conversation_id=conversation_id,
            event_type="tool_foundry.tool_ready",
            payload=payload,
        )


def create_event_emitter() -> Optional[EventEventEmitter]:
    """
    Create an event emitter from configured credentials.

    Returns:
        EventEventEmitter if credentials configured, None otherwise.
    """
    from src.infra.config import get_settings

    settings = get_settings()

    if not settings.enable_event_emission:
        logger.debug("Event emission disabled in settings")
        return None

    credentials = get_event_credentials()
    if not credentials:
        logger.debug("Event credentials not configured")
        return None

    return EventEventEmitter(
        api_base_url=credentials.api_base_url,
        api_key=credentials.api_key,
    )


async def emit_tool_ready_event(
    org_id: str,
    conversation_id: str,
    tool_id: str,
    status: Literal["ready", "failed"],
    manifest_url: Optional[str] = None,
    invoke_url: Optional[str] = None,
    error: Optional[str] = None,
) -> bool:
    """
    Emit a tool_foundry.tool_ready system event.

    This notifies the agent that a tool has finished building and is
    ready for use (or failed to build).

    Args:
        org_id: The organization ID.
        conversation_id: The conversation that requested the tool.
        tool_id: The unique tool identifier.
        status: Whether the tool is "ready" or "failed".
        manifest_url: URL to fetch the tool manifest.
        invoke_url: URL to invoke the tool.
        error: Error message if status is "failed".

    Returns:
        True if the event was emitted successfully.
    """
    emitter = create_event_emitter()
    if not emitter:
        logger.warning("Event emitter not available, skipping event emission")
        return False

    return await emitter.emit_tool_ready(
        org_id=org_id,
        conversation_id=conversation_id,
        tool_id=tool_id,
        status=status,
        manifest_url=manifest_url,
        invoke_url=invoke_url,
        error=error,
    )
