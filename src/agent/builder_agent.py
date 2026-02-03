"""Builder agent - orchestrates the tool building process.

The ToolBuilderAgent coordinates the planner and generator to transform
a capability description into a working tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from src.agent.generator import CodeGenerator, GeneratedCode
from src.agent.planner import ToolPlan, ToolPlanner
from src.infra.logging import get_logger, LogContext

logger = get_logger("builder_agent")


class BuildStatus(str, Enum):
    """Status of a build operation."""

    PLANNING = "planning"
    GENERATING = "generating"
    VALIDATING = "validating"
    READY = "ready"
    FAILED = "failed"


@dataclass
class BuildResult:
    """Result of the tool building process."""

    success: bool
    status: BuildStatus
    tool_name: Optional[str] = None
    tool_description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    implementation: Optional[str] = None
    plan: Optional[ToolPlan] = None
    error: Optional[str] = None
    error_stage: Optional[str] = None
    duration_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "status": self.status.value,
            "tool_name": self.tool_name,
            "tool_description": self.tool_description,
            "input_schema": self.input_schema,
            "error": self.error,
            "error_stage": self.error_stage,
            "duration_ms": self.duration_ms,
        }
        if self.plan:
            result["plan"] = self.plan.to_dict()
        return result


class ToolBuilderAgent:
    """
    Agent that builds tools from capability descriptions.

    The agent coordinates the full workflow:
    1. Planning - Analyze the capability description
    2. Code Generation - Generate Python implementation
    3. Validation - Validate the generated code
    4. Return the complete tool specification
    """

    def __init__(
        self,
        anthropic_client: Optional[Any] = None,
        planner: Optional[ToolPlanner] = None,
        generator: Optional[CodeGenerator] = None,
    ):
        """
        Initialize the builder agent.

        Args:
            anthropic_client: Optional shared Anthropic client.
            planner: Optional custom planner instance.
            generator: Optional custom generator instance.
        """
        self.planner = planner or ToolPlanner(anthropic_client)
        self.generator = generator or CodeGenerator(anthropic_client)

    async def build_from_description(
        self,
        capability_description: str,
        context: Optional[str] = None,
        org_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> BuildResult:
        """
        Build a tool from a capability description.

        Args:
            capability_description: Natural language description of the needed capability.
            context: Optional additional context.
            org_id: Organization ID for logging.
            conversation_id: Conversation ID for logging.

        Returns:
            BuildResult with the tool specification or error.
        """
        start_time = datetime.now(timezone.utc)
        log_ctx = LogContext(
            logger,
            org_id=org_id,
            conversation_id=conversation_id,
        )

        log_ctx.info(f"Starting build: {capability_description[:100]}...")

        # Stage 1: Planning
        try:
            log_ctx.info("Stage 1: Planning tool structure")
            plan = await self.planner.create_plan(capability_description, context)
            log_ctx.info(f"Planning complete: {plan.name}")
        except Exception as e:
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            log_ctx.error(f"Planning failed: {e}")
            return BuildResult(
                success=False,
                status=BuildStatus.FAILED,
                error=str(e),
                error_stage="planning",
                duration_ms=duration_ms,
            )

        # Stage 2: Code Generation
        try:
            log_ctx.info("Stage 2: Generating implementation")
            generated = await self.generator.generate_code(plan)
        except Exception as e:
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            log_ctx.error(f"Generation failed: {e}")
            return BuildResult(
                success=False,
                status=BuildStatus.FAILED,
                tool_name=plan.name,
                tool_description=plan.description,
                input_schema=plan.input_schema,
                plan=plan,
                error=str(e),
                error_stage="generating",
                duration_ms=duration_ms,
            )

        # Stage 3: Validate result
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        if not generated.is_valid:
            log_ctx.error(f"Validation failed: {generated.validation_error}")
            return BuildResult(
                success=False,
                status=BuildStatus.FAILED,
                tool_name=plan.name,
                tool_description=plan.description,
                input_schema=plan.input_schema,
                plan=plan,
                error=generated.validation_error,
                error_stage="validating",
                duration_ms=duration_ms,
            )

        log_ctx.info(f"Build complete: {plan.name} in {duration_ms}ms")

        return BuildResult(
            success=True,
            status=BuildStatus.READY,
            tool_name=plan.name,
            tool_description=plan.description,
            input_schema=plan.input_schema,
            implementation=generated.code,
            plan=plan,
            duration_ms=duration_ms,
        )

    def build_from_description_sync(
        self,
        capability_description: str,
        context: Optional[str] = None,
        org_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> BuildResult:
        """Synchronous wrapper for build_from_description."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self.build_from_description(
                capability_description, context, org_id, conversation_id
            )
        )

    async def build_with_implementation(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        implementation: str,
    ) -> BuildResult:
        """
        Build a tool with a pre-written implementation.

        This bypasses the LLM and just validates the provided code.

        Args:
            name: Tool name.
            description: Tool description.
            input_schema: JSON schema for inputs.
            implementation: Pre-written Python code.

        Returns:
            BuildResult with the tool specification or error.
        """
        from src.agent.generator import generate_simple_tool

        start_time = datetime.now(timezone.utc)

        generated = generate_simple_tool(
            name=name,
            description=description,
            input_schema=input_schema,
            implementation=implementation,
        )

        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        if not generated.is_valid:
            return BuildResult(
                success=False,
                status=BuildStatus.FAILED,
                tool_name=name,
                tool_description=description,
                input_schema=input_schema,
                error=generated.validation_error,
                error_stage="validating",
                duration_ms=duration_ms,
            )

        return BuildResult(
            success=True,
            status=BuildStatus.READY,
            tool_name=name,
            tool_description=description,
            input_schema=input_schema,
            implementation=generated.code,
            duration_ms=duration_ms,
        )


# Singleton for convenience
_default_agent: Optional[ToolBuilderAgent] = None


def get_builder_agent() -> ToolBuilderAgent:
    """Get the default builder agent instance."""
    global _default_agent
    if _default_agent is None:
        _default_agent = ToolBuilderAgent()
    return _default_agent
