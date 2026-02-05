"""LLM Provider abstraction for Tool Foundry.

Supports multiple LLM providers:
- Anthropic (Claude)
- OpenAI (GPT, Codex)

Configure via environment variables:
- FOUNDRY_LLM_PROVIDER: "anthropic" or "openai" (default: "anthropic")
- FOUNDRY_AGENT_MODEL: model name (auto-detected based on provider if not set)
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from src.infra.logging import get_logger

logger = get_logger("providers")


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str
    model: str
    usage: dict


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude client."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("FOUNDRY_AGENT_MODEL", "claude-sonnet-4-20250514")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                if not self.api_key:
                    raise ValueError("Anthropic API key not configured (ANTHROPIC_API_KEY)")
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
        return self._client

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        import asyncio

        client = self._get_client()

        def _call():
            return client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

        response = await asyncio.to_thread(_call)

        return LLMResponse(
            content=response.content[0].text.strip(),
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    @property
    def provider_name(self) -> str:
        return "anthropic"


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT/Codex client."""

    # Default models for different use cases
    DEFAULT_MODELS = {
        "default": "gpt-4o",
        "codex": "codex-5.2",  # GPT Codex 5.2
        "fast": "gpt-4o-mini",
    }

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        # Support various model name formats
        model_env = os.environ.get("FOUNDRY_AGENT_MODEL", "")
        if model:
            self.model = model
        elif model_env and ("gpt" in model_env.lower() or "codex" in model_env.lower()):
            self.model = model_env
        else:
            self.model = self.DEFAULT_MODELS["codex"]  # Default to Codex 5.2
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import openai
                if not self.api_key:
                    raise ValueError("OpenAI API key not configured (OPENAI_API_KEY)")
                self._client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        import asyncio

        client = self._get_client()

        def _call():
            # GPT-5+ models use max_completion_tokens instead of max_tokens
            is_gpt5_plus = "gpt-5" in self.model.lower() or "o1" in self.model.lower()
            
            params = {
                "model": self.model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            }
            
            if is_gpt5_plus:
                params["max_completion_tokens"] = max_tokens
            else:
                params["max_tokens"] = max_tokens
            
            return client.chat.completions.create(**params)

        response = await asyncio.to_thread(_call)

        return LLMResponse(
            content=response.choices[0].message.content.strip(),
            model=response.model,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
        )

    @property
    def provider_name(self) -> str:
        return "openai"


def get_llm_provider() -> LLMProvider:
    """Get the configured LLM provider."""
    provider_str = os.environ.get("FOUNDRY_LLM_PROVIDER", "").lower()
    
    # Check explicit provider setting FIRST
    if provider_str == "openai":
        logger.info("Using OpenAI provider (explicit config)")
        return LLMProvider.OPENAI
    elif provider_str == "anthropic":
        logger.info("Using Anthropic provider (explicit config)")
        return LLMProvider.ANTHROPIC
    
    # Auto-detect from model name if provider not explicitly set
    model = os.environ.get("FOUNDRY_AGENT_MODEL", "")
    if model:
        if "gpt" in model.lower() or "codex" in model.lower() or "o1" in model.lower():
            logger.info(f"Using OpenAI provider (auto-detected from model: {model})")
            return LLMProvider.OPENAI
        elif "claude" in model.lower():
            logger.info(f"Using Anthropic provider (auto-detected from model: {model})")
            return LLMProvider.ANTHROPIC
    
    # Default to Anthropic
    logger.info("Using Anthropic provider (default)")
    return LLMProvider.ANTHROPIC


def create_llm_client(
    provider: Optional[LLMProvider] = None,
    model: Optional[str] = None,
) -> BaseLLMClient:
    """
    Create an LLM client for the specified provider.

    Args:
        provider: LLM provider (auto-detected if not specified)
        model: Model name (uses default for provider if not specified)

    Returns:
        Configured LLM client
    """
    if provider is None:
        provider = get_llm_provider()

    logger.info(f"Creating LLM client: provider={provider.value}, model={model or 'default'}")

    if provider == LLMProvider.OPENAI:
        return OpenAIClient(model=model)
    else:
        return AnthropicClient(model=model)


def get_llm_client() -> BaseLLMClient:
    """Get an LLM client based on current environment configuration.
    
    Note: Creates a new client each time to pick up any config changes.
    The clients themselves cache their underlying SDK clients.
    """
    return create_llm_client()


def reset_llm_client():
    """Reset clients (for compatibility - no-op now)."""
    pass
