"""Agent layer for Tool Foundry.

This module contains the AI agent that generates tools from
capability descriptions.

Supports multiple LLM providers:
- Anthropic Claude (default)
- OpenAI GPT / Codex 5.2

Configure via environment:
- FOUNDRY_LLM_PROVIDER: "anthropic" or "openai"
- FOUNDRY_AGENT_MODEL: model name
"""

from src.agent.builder_agent import ToolBuilderAgent, BuildResult, get_builder_agent
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
    "get_builder_agent",
    # Planner
    "ToolPlanner",
    "ToolPlan",
    # Generator
    "CodeGenerator",
    "GeneratedCode",
    # Providers
    "LLMProvider",
    "BaseLLMClient",
    "AnthropicClient",
    "OpenAIClient",
    "create_llm_client",
    "get_llm_client",
    "get_llm_provider",
]
