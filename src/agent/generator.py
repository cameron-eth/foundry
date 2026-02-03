"""Code generator - generates Python implementation from tool plans.

The generator takes a ToolPlan and produces valid, restricted Python code
that implements the planned functionality.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.agent.planner import ToolPlan
from src.builder.validator import ALLOWED_MODULES, validate_restricted_python
from src.infra.logging import get_logger

logger = get_logger("generator")


@dataclass
class GeneratedCode:
    """Result of code generation."""

    code: str
    validation_passed: bool
    validation_error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.validation_passed and self.validation_error is None


GENERATOR_SYSTEM_PROMPT = """You are a Python code generator for a restricted tool execution environment.

Your job is to generate Python code that implements a tool based on the provided plan.

## Strict Requirements

1. Define a `main()` function as the entry point
2. The main function parameters MUST match the input_schema properties
3. Only use these allowed modules: {allowed_modules}
4. NO async/await
5. NO file operations (open, read, write)
6. NO eval(), exec(), compile(), __import__()
7. NO accessing __dunder__ attributes
8. NO lambda expressions (use def instead)

## Network Access

You CAN use `httpx` or `requests` to call external APIs. Available APIs:

### Exa Search API
- API Key: `os.environ.get("EXA_API_KEY")`
- Endpoint: `https://api.exa.ai/search`
- Headers: `{{"x-api-key": api_key, "Content-Type": "application/json"}}`
- Body: `{{"query": "search query", "num_results": 10, "type": "neural"}}`

Example:
```python
import httpx
import os

def main(query: str, num_results: int = 10) -> dict:
    api_key = os.environ.get("EXA_API_KEY")
    response = httpx.post(
        "https://api.exa.ai/search",
        headers={{"x-api-key": api_key, "Content-Type": "application/json"}},
        json={{"query": query, "num_results": num_results, "type": "neural"}},
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()
```

## Visualization with Matplotlib

You CAN use `matplotlib` for generating charts/plots. Return images as base64-encoded strings.

Example:
```python
import matplotlib.pyplot as plt
import numpy as np
import base64
import io

def main(data: list, title: str = "Chart") -> dict:
    \"\"\"Generate a chart from data.\"\"\"
    plt.figure(figsize=(10, 6))
    plt.plot(data)
    plt.title(title)
    plt.grid(True)
    
    # Save to base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    return {{
        "image_base64": base64.b64encode(buf.read()).decode(),
        "format": "png",
        "title": title
    }}
```

## Code Style

- Use type hints for function parameters and return values
- Add a docstring to the main function
- Handle edge cases gracefully
- Return meaningful error messages via exceptions when appropriate

## Output Format

Output ONLY the Python code, no markdown code blocks or explanations.

## Example

For a tool that calculates compound interest:

import math

def main(principal: float, rate: float, time: float, n: int = 12) -> float:
    \"\"\"
    Calculate compound interest.
    
    Args:
        principal: The initial investment amount
        rate: Annual interest rate (as decimal, e.g., 0.05 for 5%)
        time: Time period in years
        n: Number of times interest is compounded per year (default: 12)
    
    Returns:
        The final amount after compound interest
    \"\"\"
    if principal < 0:
        raise ValueError("Principal must be non-negative")
    if rate < 0:
        raise ValueError("Rate must be non-negative")
    if time < 0:
        raise ValueError("Time must be non-negative")
    if n <= 0:
        raise ValueError("Compounding frequency must be positive")
    
    amount = principal * math.pow((1 + rate / n), n * time)
    return round(amount, 2)
"""


class CodeGenerator:
    """Generates Python code from tool plans."""

    def __init__(self, anthropic_client: Optional[Any] = None):
        """
        Initialize the generator.

        Args:
            anthropic_client: Optional Anthropic client.
        """
        self._client = anthropic_client
        self._allowed_modules = sorted(ALLOWED_MODULES)

    def _get_client(self) -> Any:
        """Get or create Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                from src.infra.secrets import get_anthropic_api_key

                api_key = get_anthropic_api_key()
                if not api_key:
                    raise ValueError("Anthropic API key not configured")
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                raise ImportError("anthropic package required for agent features")
        return self._client

    async def generate_code(
        self,
        plan: ToolPlan,
        max_retries: int = 2,
    ) -> GeneratedCode:
        """
        Generate Python code from a tool plan.

        Args:
            plan: The tool plan to implement.
            max_retries: Number of retries if validation fails.

        Returns:
            GeneratedCode with the implementation.
        """
        from src.infra.config import get_settings

        settings = get_settings()
        client = self._get_client()

        # Build the prompt
        user_message = f"""Generate Python code for this tool:

Name: {plan.name}
Description: {plan.description}

Input Schema:
{json.dumps(plan.input_schema, indent=2)}

Output: {plan.output_description}

Implementation Approach:
{plan.implementation_approach}

Required Modules: {', '.join(plan.required_modules) if plan.required_modules else 'None'}

Examples:
{json.dumps(plan.examples, indent=2) if plan.examples else 'None provided'}
"""

        last_error: Optional[str] = None
        generated_code: Optional[str] = None

        for attempt in range(max_retries + 1):
            logger.info(f"Generating code for {plan.name}, attempt {attempt + 1}")

            # Add error context for retries
            if last_error and attempt > 0:
                retry_message = f"{user_message}\n\nPrevious attempt failed validation with error: {last_error}\nPlease fix the code."
            else:
                retry_message = user_message

            # Call Claude (run sync client in thread pool for async compatibility)
            import asyncio

            def _call_claude():
                return client.messages.create(
                    model=settings.agent_model,
                    max_tokens=settings.agent_max_tokens,
                    temperature=settings.agent_temperature,
                    system=GENERATOR_SYSTEM_PROMPT.format(
                        allowed_modules=", ".join(self._allowed_modules)
                    ),
                    messages=[{"role": "user", "content": retry_message}],
                )

            response = await asyncio.to_thread(_call_claude)

            generated_code = response.content[0].text.strip()

            # Remove markdown code blocks if present
            if generated_code.startswith("```"):
                lines = generated_code.split("\n")
                code_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```") and not in_block:
                        in_block = True
                        continue
                    elif line.startswith("```") and in_block:
                        break
                    elif in_block:
                        code_lines.append(line)
                generated_code = "\n".join(code_lines)

            # Validate the generated code
            try:
                validate_restricted_python(generated_code)
                logger.info(f"Generated valid code for {plan.name}")
                return GeneratedCode(
                    code=generated_code,
                    validation_passed=True,
                    validation_error=None,
                )
            except ValueError as e:
                last_error = str(e)
                logger.warning(f"Validation failed on attempt {attempt + 1}: {last_error}")

        # All retries exhausted
        logger.error(f"Failed to generate valid code for {plan.name} after {max_retries + 1} attempts")
        return GeneratedCode(
            code=generated_code or "",
            validation_passed=False,
            validation_error=last_error,
        )

    def generate_code_sync(
        self,
        plan: ToolPlan,
        max_retries: int = 2,
    ) -> GeneratedCode:
        """Synchronous wrapper for generate_code."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self.generate_code(plan, max_retries)
        )


def generate_simple_tool(
    name: str,
    description: str,
    input_schema: Dict[str, Any],
    implementation: str,
) -> GeneratedCode:
    """
    Validate a pre-written implementation without using the LLM.

    This is useful when the user provides their own implementation.

    Args:
        name: Tool name.
        description: Tool description.
        input_schema: Input JSON schema.
        implementation: Pre-written Python code.

    Returns:
        GeneratedCode with validation result.
    """
    try:
        validate_restricted_python(implementation)
        return GeneratedCode(
            code=implementation,
            validation_passed=True,
            validation_error=None,
        )
    except ValueError as e:
        return GeneratedCode(
            code=implementation,
            validation_passed=False,
            validation_error=str(e),
        )
