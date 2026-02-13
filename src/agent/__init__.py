"""Agent layer for Tool Foundry.

This module contains the AI agent that generates tools from
capability descriptions.

Supports two build backends:

1. **OpenAI Agents SDK** (default when OPENAI_API_KEY is set)
   Multi-agent pipeline: Normalizer → Planner → Generator
   with self-correcting code validation and testing.

2. **Legacy provider** (fallback for Anthropic or when SDK disabled)
   Single-shot planner + generator via the LLM provider abstraction.

Configure via environment:
- FOUNDRY_USE_AGENTS_SDK: "true" / "false" (auto-detected if unset)
- FOUNDRY_LLM_PROVIDER: "anthropic" or "openai" (for legacy path)
- FOUNDRY_AGENT_MODEL: model name (strong model for code gen)
- FOUNDRY_FAST_MODEL: model for normalizer/planner (default: gpt-4o-mini)
"""

from src.agent.builder_agent import (
    ToolBuilderAgent,
    BuildResult,
    BuildStatus,
    get_builder_agent,
    reset_builder_agent,
)
from src.agent.planner import ToolPlanner, ToolPlan
from src.agent.generator import CodeGenerator, GeneratedCode
from src.agent.providers import (
    LLMProvider,
    BaseLLMClient,
    AnthropicClient,
    OpenAIClient,
    create_llm_client,
    get_llm_client,
    get_llm_provider,
)

__all__ = [
    # Builder
    "ToolBuilderAgent",
    "BuildResult",
    "BuildStatus",
    "get_builder_agent",
    "reset_builder_agent",
    # Planner (legacy)
    "ToolPlanner",
    "ToolPlan",
    # Generator (legacy)
    "CodeGenerator",
    "GeneratedCode",
    # Providers (legacy)
    "LLMProvider",
    "BaseLLMClient",
    "AnthropicClient",
    "OpenAIClient",
    "create_llm_client",
    "get_llm_client",
    "get_llm_provider",
]
