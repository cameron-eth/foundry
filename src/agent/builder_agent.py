"""Builder agent - orchestrates the tool building process.

Supports two backends:
  1. **OpenAI Agents SDK** (default when OPENAI_API_KEY is set)
     Uses the multi-agent pipeline: Normalizer → Planner → Generator
     with self-correcting code validation and testing.

  2. **Legacy provider** (fallback)
     Single-shot planner + generator using the raw LLM provider
     abstraction (Anthropic or OpenAI).

Set FOUNDRY_USE_AGENTS_SDK=false to force the legacy path.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

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
    plan: Optional[Any] = None
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
        if self.plan and hasattr(self.plan, "to_dict"):
            result["plan"] = self.plan.to_dict()
        return result


def _use_agents_sdk() -> bool:
    """Decide whether to use the Agents SDK pipeline."""
    # Explicit override
    flag = os.environ.get("FOUNDRY_USE_AGENTS_SDK", "").lower()
    if flag == "false":
        return False
    if flag == "true":
        return True

    # Auto-detect: use SDK if we have an OpenAI key
    if os.environ.get("OPENAI_API_KEY"):
        return True

    return False


class ToolBuilderAgent:
    """
    Agent that builds tools from capability descriptions.

    Automatically selects the best backend:
    - OpenAI Agents SDK (multi-agent, self-correcting)
    - Legacy single-shot (Anthropic or OpenAI via providers.py)
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        planner: Optional[Any] = None,
        generator: Optional[Any] = None,
        force_legacy: bool = False,
    ):
        self._llm_client = llm_client
        self._planner = planner
        self._generator = generator
        self._force_legacy = force_legacy

    async def build_from_description(
        self,
        capability_description: str,
        context: Optional[str] = None,
        org_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> BuildResult:
        """
        Build a tool from a capability description.

        Routes to the SDK pipeline or legacy pipeline based on config.
        """
        if not self._force_legacy and _use_agents_sdk():
            return await self._build_with_sdk(
                capability_description, context, org_id, conversation_id
            )
        else:
            return await self._build_legacy(
                capability_description, context, org_id, conversation_id
            )

    # ── SDK pipeline ────────────────────────────────────────────────────

    async def _build_with_sdk(
        self,
        capability_description: str,
        context: Optional[str],
        org_id: Optional[str],
        conversation_id: Optional[str],
    ) -> BuildResult:
        """Build using the OpenAI Agents SDK multi-agent pipeline."""
        from src.agent.sdk_agents import build_tool_with_sdk

        log_ctx = LogContext(logger, org_id=org_id, conversation_id=conversation_id)
        log_ctx.info("Using OpenAI Agents SDK pipeline")

        try:
            sdk_result = await build_tool_with_sdk(
                capability_description=capability_description,
                context=context,
            )
        except Exception as e:
            log_ctx.error(f"SDK pipeline crashed: {e}")
            return BuildResult(
                success=False,
                status=BuildStatus.FAILED,
                error=f"SDK pipeline error: {e}",
                error_stage="sdk",
            )

        if sdk_result.success:
            return BuildResult(
                success=True,
                status=BuildStatus.READY,
                tool_name=sdk_result.tool_name,
                tool_description=sdk_result.tool_description,
                input_schema=sdk_result.input_schema,
                implementation=sdk_result.implementation,
                duration_ms=sdk_result.duration_ms,
            )
        else:
            return BuildResult(
                success=False,
                status=BuildStatus.FAILED,
                tool_name=sdk_result.tool_name,
                tool_description=sdk_result.tool_description,
                input_schema=sdk_result.input_schema,
                implementation=sdk_result.implementation,
                error=sdk_result.error,
                error_stage=sdk_result.error_stage,
                duration_ms=sdk_result.duration_ms,
            )

    # ── Legacy pipeline ─────────────────────────────────────────────────

    async def _build_legacy(
        self,
        capability_description: str,
        context: Optional[str],
        org_id: Optional[str],
        conversation_id: Optional[str],
    ) -> BuildResult:
        """Build using the legacy planner + generator pipeline."""
        from src.agent.generator import CodeGenerator, GeneratedCode
        from src.agent.planner import ToolPlan, ToolPlanner

        start_time = datetime.now(timezone.utc)
        log_ctx = LogContext(logger, org_id=org_id, conversation_id=conversation_id)
        log_ctx.info("Using legacy single-shot pipeline")

        planner = self._planner or ToolPlanner(self._llm_client)
        generator = self._generator or CodeGenerator(self._llm_client)

        # Stage 1: Planning
        try:
            log_ctx.info("Stage 1: Planning tool structure")
            plan = await planner.create_plan(capability_description, context)
            log_ctx.info(f"Planning complete: {plan.name}")
        except Exception as e:
            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
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
            generated = await generator.generate_code(plan)
        except Exception as e:
            duration_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
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
        duration_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

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

    # ── Direct (pre-written code) ───────────────────────────────────────

    async def build_with_implementation(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        implementation: str,
    ) -> BuildResult:
        """
        Build a tool with a pre-written implementation (no LLM needed).
        Just validates the provided code.
        """
        from src.agent.generator import generate_simple_tool

        start_time = datetime.now(timezone.utc)

        generated = generate_simple_tool(
            name=name,
            description=description,
            input_schema=input_schema,
            implementation=implementation,
        )

        duration_ms = int(
            (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        )

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


# Singleton for convenience
_default_agent: Optional[ToolBuilderAgent] = None


def get_builder_agent() -> ToolBuilderAgent:
    """Get the default builder agent instance."""
    global _default_agent
    if _default_agent is None:
        _default_agent = ToolBuilderAgent()
    return _default_agent


def reset_builder_agent() -> None:
    """Reset the singleton (for testing)."""
    global _default_agent
    _default_agent = None
