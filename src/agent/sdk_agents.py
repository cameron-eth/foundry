"""OpenAI Agents SDK-based tool builder pipeline.

Architecture
============
1. **NormalizerAgent** (gpt-4o-mini)  — Cleans / expands the raw user
   description into a precise capability specification.

2. **PlannerAgent** (gpt-4o-mini)  — Produces a structured ``ToolPlan``
   (Pydantic model) with name, schema, approach, examples.

3. **GeneratorAgent** (gpt-5.2 / configurable)  — Writes the Python code,
   calls ``validate_code`` and ``test_code`` in a loop until both pass.

4. **Final deterministic AST check** — ``validate_restricted_python()`` as
   the last gate before persisting, independent of the LLM.

Handoff flow::

    NormalizerAgent  →  PlannerAgent  →  GeneratorAgent
         (4o-mini)         (4o-mini)       (gpt-5.2)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from agents import (
    Agent,
    AgentOutputSchema,
    GuardrailFunctionOutput,
    ModelSettings,
    RunConfig,
    Runner,
    input_guardrail,
    RunContextWrapper,
    set_tracing_disabled,
)

from src.agent.prompts import (
    CODE_FEW_SHOTS,
    EXTERNAL_APIS,
    PLAN_FEW_SHOTS,
    TOOL_CONSTRAINTS,
)
from src.agent.tools import list_allowed_modules, test_code, validate_code
from src.builder.validator import validate_restricted_python, ValidationError
from src.infra.logging import get_logger

logger = get_logger("sdk_agents")


# ────────────────────────────────────────────────────────────────────────────
# Pydantic models for structured output
# ────────────────────────────────────────────────────────────────────────────

class InputSchemaProperty(BaseModel):
    type: str
    description: str = ""
    default: Any = None

class InputSchema(BaseModel):
    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)

class ToolPlanOutput(BaseModel):
    """Structured plan output from the PlannerAgent."""
    name: str = Field(description="snake_case function name")
    description: str = Field(description="Clear description of what the tool does")
    input_schema: InputSchema = Field(description="JSON Schema for main() parameters")
    output_description: str = Field(description="What main() returns")
    implementation_approach: str = Field(description="Step-by-step implementation plan")
    required_modules: List[str] = Field(default_factory=list, description="Modules from the allowed list")
    test_input: Dict[str, Any] = Field(default_factory=dict, description="Sample input for smoke test")

class GeneratedToolOutput(BaseModel):
    """Structured output from the GeneratorAgent."""
    code: str = Field(description="Complete Python source code with def main()")
    explanation: str = Field(default="", description="Brief explanation of the implementation")


# ────────────────────────────────────────────────────────────────────────────
# Input guardrail — reject dangerous / nonsensical requests
# ────────────────────────────────────────────────────────────────────────────

@input_guardrail
async def safety_guardrail(
    ctx: RunContextWrapper[None],
    agent: Agent,
    input: str | list,
):
    """Reject obviously malicious or nonsensical tool requests."""
    text = input if isinstance(input, str) else str(input)
    text_lower = text.lower()

    blocklist = [
        "rm -rf",
        "format c:",
        "sudo ",
        "DROP TABLE",
        "eval(",
        "exec(",
        "__import__",
        "os.system",
        "subprocess",
    ]
    for bad in blocklist:
        if bad.lower() in text_lower:
            return GuardrailFunctionOutput(
                output_info={"reason": f"Blocked: suspicious pattern '{bad}'"},
                tripwire_triggered=True,
            )

    return GuardrailFunctionOutput(
        output_info={"reason": "ok"},
        tripwire_triggered=False,
    )


# ────────────────────────────────────────────────────────────────────────────
# Model configuration
# ────────────────────────────────────────────────────────────────────────────

def _fast_model() -> str:
    """Return the fast/cheap model name (for normaliser & planner)."""
    return os.environ.get("FOUNDRY_FAST_MODEL", "gpt-4o-mini")

def _strong_model() -> str:
    """Return the strong model name (for code generation)."""
    custom = os.environ.get("FOUNDRY_AGENT_MODEL", "")
    if custom:
        return custom
    return os.environ.get("FOUNDRY_STRONG_MODEL", "gpt-4o")


# ────────────────────────────────────────────────────────────────────────────
# Agent definitions
# ────────────────────────────────────────────────────────────────────────────

def _create_normalizer_agent() -> Agent:
    return Agent(
        name="InputNormalizer",
        instructions="""\
You are an input normaliser for a tool-building system.

Your ONLY job is to take a raw, possibly messy user description and rewrite
it as a clear, precise, one-paragraph capability specification.

Rules:
- Fix typos and grammar.
- Expand abbreviations ("smth" → "something", "calc" → "calculate").
- Add any missing detail that a developer would need (e.g. expected input
  types, output format, edge cases to handle).
- If the request is about an external API, mention the API by name.
- Do NOT add features the user didn't ask for.
- Output ONLY the cleaned description, nothing else.
""",
        model=_fast_model(),
        model_settings=ModelSettings(temperature=0.2),
    )


def _create_planner_agent() -> Agent:
    return Agent(
        name="ToolPlanner",
        instructions=f"""\
You are a tool planner for a Python tool builder system.

Analyse the capability description and produce a structured tool plan.

{TOOL_CONSTRAINTS}

{EXTERNAL_APIS}

{PLAN_FEW_SHOTS}

IMPORTANT:
- The `test_input` field must contain a realistic sample input that can be
  used to smoke-test the generated code.
- `required_modules` must only contain modules from the allowed list.
  Call the `list_allowed_modules` tool if you are unsure.
- `name` must be snake_case, max 60 chars.
""",
        model=_fast_model(),
        model_settings=ModelSettings(temperature=0.0),
        output_type=AgentOutputSchema(ToolPlanOutput, strict_json_schema=False),
    )


def _create_generator_agent() -> Agent:
    return Agent(
        name="CodeGenerator",
        instructions=f"""\
You are an expert Python code generator for a restricted tool execution
environment.

You will receive a structured tool plan.  Your job is to write the
complete Python implementation.

{TOOL_CONSTRAINTS}

{EXTERNAL_APIS}

{CODE_FEW_SHOTS}

## Workflow

1. Write the complete Python code implementing the tool plan.
2. Call `validate_code` with your code to check it passes security rules.
3. If validation fails, read the error, fix the code, and validate again.
4. Once validation passes, call `test_code` with the code and the sample
   input from the plan to verify it runs correctly.
5. If the test fails, read the error, fix the code, re-validate, and
   re-test.
6. Once BOTH validation and testing pass, return the final code.

## Output Rules

- Return the COMPLETE Python source code in the `code` field.
- Do NOT include markdown fences — just raw Python.
- Every `main()` must have full type hints and a docstring.
- Handle edge cases (empty input, missing env vars, API errors).
""",
        model=_strong_model(),
        model_settings=ModelSettings(temperature=0.0, max_tokens=4096),
        tools=[validate_code, test_code, list_allowed_modules],
        output_type=AgentOutputSchema(GeneratedToolOutput, strict_json_schema=False),
    )


# ────────────────────────────────────────────────────────────────────────────
# Build result
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class SDKBuildResult:
    """Result of the SDK-based tool build pipeline."""
    success: bool
    tool_name: Optional[str] = None
    tool_description: Optional[str] = None
    input_schema: Optional[Dict[str, Any]] = None
    implementation: Optional[str] = None
    test_input: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None
    error: Optional[str] = None
    error_stage: Optional[str] = None
    duration_ms: Optional[int] = None


# ────────────────────────────────────────────────────────────────────────────
# Main build function
# ────────────────────────────────────────────────────────────────────────────

async def build_tool_with_sdk(
    capability_description: str,
    context: Optional[str] = None,
    max_generator_turns: int = 10,
    disable_tracing: bool = True,
) -> SDKBuildResult:
    """Build a tool using the OpenAI Agents SDK pipeline.

    This is the main entry point.  It runs three agents in sequence:
    Normalizer → Planner → Generator, then a final deterministic
    validation pass.

    Args:
        capability_description: Raw user description of the tool needed.
        context: Optional extra context (conversation history, etc.).
        max_generator_turns: Max agent loop turns for the generator
            (each turn = one LLM call + potential tool call).
        disable_tracing: Disable OpenAI tracing (set False for debugging).

    Returns:
        SDKBuildResult with the tool spec or error details.
    """
    start = datetime.now(timezone.utc)

    if disable_tracing:
        set_tracing_disabled(True)

    # Combine description + context
    full_input = capability_description
    if context:
        full_input += f"\n\nAdditional context: {context}"

    # ── Stage 1: Normalise ──────────────────────────────────────────────
    logger.info(f"[SDK] Stage 1/3 — Normalising input ({_fast_model()})")
    try:
        normalizer = _create_normalizer_agent()
        norm_result = await Runner.run(
            normalizer,
            full_input,
            max_turns=3,
            run_config=RunConfig(
                tracing_disabled=disable_tracing,
            ),
        )
        normalised = norm_result.final_output
        logger.info(f"[SDK] Normalised: {normalised[:120]}…")
    except Exception as e:
        logger.error(f"[SDK] Normalisation failed: {e}")
        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        return SDKBuildResult(
            success=False,
            error=f"Input normalisation failed: {e}",
            error_stage="normalizer",
            duration_ms=elapsed,
        )

    # ── Stage 2: Plan ───────────────────────────────────────────────────
    logger.info(f"[SDK] Stage 2/3 — Planning ({_fast_model()})")
    try:
        planner = _create_planner_agent()
        plan_result = await Runner.run(
            planner,
            normalised,
            max_turns=3,
            run_config=RunConfig(
                tracing_disabled=disable_tracing,
            ),
        )
        plan: ToolPlanOutput = plan_result.final_output
        logger.info(f"[SDK] Plan: {plan.name} — {plan.description[:80]}")
    except Exception as e:
        logger.error(f"[SDK] Planning failed: {e}")
        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        return SDKBuildResult(
            success=False,
            error=f"Planning failed: {e}",
            error_stage="planner",
            duration_ms=elapsed,
        )

    # ── Stage 3: Generate ───────────────────────────────────────────────
    logger.info(f"[SDK] Stage 3/3 — Generating code ({_strong_model()})")

    generator_input = f"""## Tool Plan

Name: {plan.name}
Description: {plan.description}

Input Schema:
{json.dumps(plan.input_schema.model_dump(), indent=2)}

Output: {plan.output_description}

Implementation Approach:
{plan.implementation_approach}

Required Modules: {', '.join(plan.required_modules) if plan.required_modules else 'None'}

Test Input (use this with test_code):
{json.dumps(plan.test_input)}
"""

    try:
        generator = _create_generator_agent()
        gen_result = await Runner.run(
            generator,
            generator_input,
            max_turns=max_generator_turns,
            run_config=RunConfig(
                tracing_disabled=disable_tracing,
            ),
        )
        generated: GeneratedToolOutput = gen_result.final_output
        code = generated.code
        logger.info(f"[SDK] Generator finished — code length: {len(code)} chars")
    except Exception as e:
        logger.error(f"[SDK] Generation failed: {e}")
        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        return SDKBuildResult(
            success=False,
            tool_name=plan.name,
            tool_description=plan.description,
            input_schema=plan.input_schema.model_dump(),
            error=f"Code generation failed: {e}",
            error_stage="generator",
            duration_ms=elapsed,
        )

    # ── Stage 4: Final deterministic validation ─────────────────────────
    logger.info("[SDK] Final AST validation gate")
    try:
        # Strip any leftover markdown fences the LLM might have added
        clean_code = _strip_markdown_fences(code)
        validate_restricted_python(clean_code)
        logger.info("[SDK] Final validation PASSED")
    except ValidationError as e:
        logger.error(f"[SDK] Final validation FAILED: {e}")
        elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        return SDKBuildResult(
            success=False,
            tool_name=plan.name,
            tool_description=plan.description,
            input_schema=plan.input_schema.model_dump(),
            implementation=clean_code,
            error=f"Final validation failed: {e}",
            error_stage="final_validation",
            duration_ms=elapsed,
        )

    elapsed = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    logger.info(f"[SDK] Build complete: {plan.name} in {elapsed}ms")

    return SDKBuildResult(
        success=True,
        tool_name=plan.name,
        tool_description=plan.description,
        input_schema=plan.input_schema.model_dump(),
        implementation=clean_code,
        test_input=plan.test_input,
        explanation=generated.explanation,
        duration_ms=elapsed,
    )


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _strip_markdown_fences(code: str) -> str:
    """Remove ```python ... ``` wrappers if present."""
    stripped = code.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        # Drop first line (```python) and last line (```)
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip().startswith("```"):
                end = i
                break
        stripped = "\n".join(lines[start:end])
    return stripped
