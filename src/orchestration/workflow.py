"""Build workflow - manages the async tool building process.

The workflow coordinates:
1. Receiving build requests
2. Running the agent to generate tool code
3. Updating the registry
4. Emitting system events
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from src.api.schemas import ToolRegistryEntry, ToolStatus
from src.infra.logging import get_logger, LogContext

logger = get_logger("workflow")


class WorkflowState(str, Enum):
    """State of a build workflow."""

    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BuildRequest:
    """A request to build a tool."""

    # Required fields
    org_id: str
    conversation_id: str

    # Either capability_description (agent-driven) or direct tool spec
    capability_description: Optional[str] = None

    # Direct tool specification (bypasses agent)
    name: Optional[str] = None
    description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    implementation: Optional[str] = None

    # Optional configuration
    ttl_hours: int = 24
    context: Optional[str] = None

    # Internal tracking
    request_id: str = field(default_factory=lambda: f"req-{uuid.uuid4().hex[:12]}")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_agent_request(self) -> bool:
        """Check if this is an agent-driven build request."""
        return self.capability_description is not None

    @property
    def is_direct_request(self) -> bool:
        """Check if this is a direct tool creation request."""
        return (
            self.name is not None
            and self.description is not None
            and self.input_schema is not None
            and self.implementation is not None
        )

    def validate(self) -> None:
        """Validate the request has required fields."""
        if not self.is_agent_request and not self.is_direct_request:
            raise ValueError(
                "Request must have either capability_description "
                "or all of (name, description, input_schema, implementation)"
            )


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    request_id: str
    tool_id: Optional[str]
    state: WorkflowState
    success: bool
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class BuildWorkflow:
    """
    Manages the tool building workflow.

    This class coordinates the async build process:
    1. Validate the build request
    2. Run the agent (if capability_description provided)
    3. Create the tool in the registry
    4. Execute the build (prepare sandbox)
    5. Emit system event
    """

    def __init__(
        self,
        registry: Optional[Any] = None,
        event_emitter: Optional[Any] = None,
    ):
        """
        Initialize the workflow.

        Args:
            registry: Registry instance for storing tools.
            event_emitter: Event emitter for system events.
        """
        self.registry = registry
        self.event_emitter = event_emitter

    async def execute(
        self,
        request: BuildRequest,
    ) -> WorkflowResult:
        """
        Execute the build workflow.

        Args:
            request: The build request to process.

        Returns:
            WorkflowResult with the outcome.
        """
        start_time = datetime.now(timezone.utc)
        log_ctx = LogContext(
            logger,
            org_id=request.org_id,
            conversation_id=request.conversation_id,
        )

        log_ctx.info(f"Starting workflow {request.request_id}")

        # Validate request
        try:
            request.validate()
        except ValueError as e:
            log_ctx.error(f"Invalid request: {e}")
            return WorkflowResult(
                request_id=request.request_id,
                tool_id=None,
                state=WorkflowState.FAILED,
                success=False,
                error=str(e),
            )

        # Determine if agent is needed
        if request.is_agent_request:
            result = await self._execute_agent_workflow(request, log_ctx, start_time)
        else:
            result = await self._execute_direct_workflow(request, log_ctx, start_time)

        return result

    async def _execute_agent_workflow(
        self,
        request: BuildRequest,
        log_ctx: LogContext,
        start_time: datetime,
    ) -> WorkflowResult:
        """Execute workflow with agent-driven tool generation."""
        from src.agent.builder_agent import get_builder_agent

        log_ctx.info("Running agent-driven workflow")

        # Run the agent
        try:
            agent = get_builder_agent()
            build_result = await agent.build_from_description(
                capability_description=request.capability_description,
                context=request.context,
                org_id=request.org_id,
                conversation_id=request.conversation_id,
            )
        except Exception as e:
            log_ctx.error(f"Agent failed: {e}")
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return WorkflowResult(
                request_id=request.request_id,
                tool_id=None,
                state=WorkflowState.FAILED,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

        if not build_result.success:
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return WorkflowResult(
                request_id=request.request_id,
                tool_id=None,
                state=WorkflowState.FAILED,
                success=False,
                error=build_result.error,
                duration_ms=duration_ms,
            )

        # Create tool in registry
        tool_id = await self._create_tool_entry(
            request=request,
            name=build_result.tool_name,
            description=build_result.tool_description,
            input_schema=build_result.input_schema,
            implementation=build_result.implementation,
            log_ctx=log_ctx,
        )

        # Emit event
        await self._emit_tool_ready_event(
            tool_id=tool_id,
            request=request,
            log_ctx=log_ctx,
        )

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        log_ctx.info(f"Workflow complete: {tool_id} in {duration_ms}ms")

        return WorkflowResult(
            request_id=request.request_id,
            tool_id=tool_id,
            state=WorkflowState.COMPLETED,
            success=True,
            duration_ms=duration_ms,
        )

    async def _execute_direct_workflow(
        self,
        request: BuildRequest,
        log_ctx: LogContext,
        start_time: datetime,
    ) -> WorkflowResult:
        """Execute workflow with direct tool specification."""
        from src.builder.validator import validate_restricted_python

        log_ctx.info("Running direct workflow")

        # Validate implementation
        try:
            validate_restricted_python(request.implementation)
        except ValueError as e:
            log_ctx.error(f"Validation failed: {e}")
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return WorkflowResult(
                request_id=request.request_id,
                tool_id=None,
                state=WorkflowState.FAILED,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )

        # Create tool in registry
        tool_id = await self._create_tool_entry(
            request=request,
            name=request.name,
            description=request.description,
            input_schema=request.input_schema,
            implementation=request.implementation,
            log_ctx=log_ctx,
        )

        # Emit event
        await self._emit_tool_ready_event(
            tool_id=tool_id,
            request=request,
            log_ctx=log_ctx,
        )

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        log_ctx.info(f"Workflow complete: {tool_id} in {duration_ms}ms")

        return WorkflowResult(
            request_id=request.request_id,
            tool_id=tool_id,
            state=WorkflowState.COMPLETED,
            success=True,
            duration_ms=duration_ms,
        )

    async def _create_tool_entry(
        self,
        request: BuildRequest,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        implementation: str,
        log_ctx: LogContext,
    ) -> str:
        """Create a tool entry in the registry."""
        from datetime import timedelta

        tool_id = f"tool-{uuid.uuid4().hex[:12]}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=request.ttl_hours)

        entry = ToolRegistryEntry(
            tool_id=tool_id,
            org_id=request.org_id,
            conversation_id=request.conversation_id,
            name=name,
            description=description,
            status=ToolStatus.READY,
            input_schema=input_schema,
            implementation=implementation,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )

        if self.registry:
            self.registry.set(tool_id, entry)
            log_ctx.info(f"Created tool entry: {tool_id}")
        else:
            log_ctx.warning("No registry configured, tool not persisted")

        return tool_id

    async def _emit_tool_ready_event(
        self,
        tool_id: str,
        request: BuildRequest,
        log_ctx: LogContext,
    ) -> None:
        """Emit a tool ready system event."""
        from src.infra.config import get_settings

        settings = get_settings()

        if not settings.enable_event_emission:
            log_ctx.info("Event emission disabled")
            return

        if self.event_emitter:
            try:
                await self.event_emitter.emit_tool_ready(
                    org_id=request.org_id,
                    conversation_id=request.conversation_id,
                    tool_id=tool_id,
                    status="ready",
                )
                log_ctx.info(f"Emitted tool_ready event for {tool_id}")
            except Exception as e:
                log_ctx.error(f"Failed to emit event: {e}")
        else:
            log_ctx.warning("No event emitter configured")


async def process_build_request(
    request: BuildRequest,
    registry: Optional[Any] = None,
    event_emitter: Optional[Any] = None,
) -> WorkflowResult:
    """
    Process a build request through the workflow.

    This is the main entry point for async tool building.

    Args:
        request: The build request.
        registry: Optional registry instance.
        event_emitter: Optional event emitter.

    Returns:
        WorkflowResult with the outcome.
    """
    workflow = BuildWorkflow(registry=registry, event_emitter=event_emitter)
    return await workflow.execute(request)
