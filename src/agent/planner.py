"""Tool planner - analyzes capability descriptions and creates tool plans.

The planner takes a natural language description of what capability is needed
and produces a structured plan including:
- Tool name and description
- Input/output schema
- Implementation approach
- Required modules
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.builder.validator import ALLOWED_MODULES
from src.infra.logging import get_logger

logger = get_logger("planner")


@dataclass
class ToolPlan:
    """A plan for building a tool."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    output_description: str
    implementation_approach: str
    required_modules: List[str] = field(default_factory=list)
    examples: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_description": self.output_description,
            "implementation_approach": self.implementation_approach,
            "required_modules": self.required_modules,
            "examples": self.examples,
        }


PLANNER_SYSTEM_PROMPT = """You are a tool planning assistant for a Python tool builder system.

Your job is to analyze a capability description and create a detailed plan for implementing a Python tool.

## Constraints

The tool must:
1. Define a `main()` function as the entry point
2. Only use allowed Python modules: {allowed_modules}
3. Be synchronous (no async/await)
4. Be pure functional where possible (input -> output)

## Available External APIs

Tools can make HTTP requests using `httpx` or `requests` to these APIs:

### Exa Search API
- Endpoint: https://api.exa.ai/search
- API Key available via: `os.environ.get("EXA_API_KEY")`
- Use for: web search, finding content, research
- Example:
  ```python
  import httpx
  import os
  
  def main(query: str) -> dict:
      response = httpx.post(
          "https://api.exa.ai/search",
          headers={{"x-api-key": os.environ.get("EXA_API_KEY")}},
          json={{"query": query, "num_results": 10}}
      )
      return response.json()
  ```

### Polymarket Prediction Markets API (No API Key Required)
- Base URL: https://gamma-api.polymarket.com
- Use for: prediction market data, odds, events, betting markets
- Endpoints:
  - GET /markets - List/search prediction markets
  - GET /events - List events with markets
  
- Query Parameters for /markets:
  - limit (int): Number of results (default 100)
  - offset (int): Pagination offset
  - order (str): Field to order by (e.g., "volume", "liquidity")
  - ascending (bool): Sort direction
  - closed (bool): Filter by closed/open status
  - tag_id (int): Filter by tag
  
- Example - Search Markets:
  ```python
  import httpx
  
  def main(limit: int = 10, order: str = "volume") -> dict:
      response = httpx.get(
          "https://gamma-api.polymarket.com/markets",
          params={{"limit": limit, "order": order, "ascending": False, "closed": False}},
          timeout=30.0
      )
      response.raise_for_status()
      markets = response.json()
      return {{
          "markets": [
              {{
                  "question": m.get("question"),
                  "slug": m.get("slug"),
                  "volume": m.get("volume"),
                  "liquidity": m.get("liquidity"),
                  "outcomes": m.get("outcomes"),
                  "outcomePrices": m.get("outcomePrices"),
                  "endDate": m.get("endDate"),
              }}
              for m in markets
          ]
      }}
  ```

- Example - Get Market by Slug:
  ```python
  import httpx
  
  def main(slug: str) -> dict:
      response = httpx.get(
          "https://gamma-api.polymarket.com/markets",
          params={{"slug": [slug]}},
          timeout=30.0
      )
      response.raise_for_status()
      markets = response.json()
      if not markets:
          return {{"error": "Market not found"}}
      m = markets[0]
      return {{
          "question": m.get("question"),
          "description": m.get("description"),
          "volume": m.get("volume"),
          "liquidity": m.get("liquidity"),
          "outcomes": m.get("outcomes"),
          "outcomePrices": m.get("outcomePrices"),
          "endDate": m.get("endDate"),
          "active": m.get("active"),
      }}
  ```

When a capability requires search, external data, or prediction markets, use these APIs.

## Output Format

Respond with a JSON object containing:
- name: A snake_case function name (e.g., "calculate_compound_interest")
- description: A clear description of what the tool does
- input_schema: A JSON Schema object describing the inputs
- output_description: Description of what the tool returns
- implementation_approach: Step-by-step approach to implement the logic
- required_modules: List of modules needed from the allowed list
- examples: List of example input/output pairs

## Example

For "I need a tool to calculate the area of a circle given its radius":

```json
{{
    "name": "calculate_circle_area",
    "description": "Calculate the area of a circle given its radius",
    "input_schema": {{
        "type": "object",
        "properties": {{
            "radius": {{
                "type": "number",
                "description": "The radius of the circle"
            }}
        }},
        "required": ["radius"]
    }},
    "output_description": "The area of the circle as a float",
    "implementation_approach": "Use the formula: area = π * radius². Import math module for pi constant.",
    "required_modules": ["math"],
    "examples": [
        {{"input": {{"radius": 5}}, "output": 78.54}}
    ]
}}
```

Only output valid JSON, no other text."""


class ToolPlanner:
    """Plans tool structure from capability descriptions."""

    def __init__(self, llm_client: Optional[Any] = None):
        """
        Initialize the planner.

        Args:
            llm_client: Optional LLM client (BaseLLMClient). If not provided,
                        will use the default provider.
        """
        self._llm_client = llm_client
        self._allowed_modules = sorted(ALLOWED_MODULES)

    def _get_llm_client(self) -> Any:
        """Get or create LLM client."""
        if self._llm_client is None:
            from src.agent.providers import get_llm_client
            self._llm_client = get_llm_client()
        return self._llm_client

    async def create_plan(
        self,
        capability_description: str,
        context: Optional[str] = None,
    ) -> ToolPlan:
        """
        Create a tool plan from a capability description.

        Args:
            capability_description: Natural language description of the needed capability.
            context: Optional additional context (e.g., conversation history).

        Returns:
            A ToolPlan with the structured plan.
        """
        from src.infra.config import get_settings

        settings = get_settings()
        llm = self._get_llm_client()

        # Build the user message
        user_message = f"Create a tool plan for: {capability_description}"
        if context:
            user_message += f"\n\nAdditional context: {context}"

        logger.info(f"Creating plan for: {capability_description[:100]}... (using {llm.provider_name})")

        # Call LLM
        response = await llm.generate(
            system_prompt=PLANNER_SYSTEM_PROMPT.format(
                allowed_modules=", ".join(self._allowed_modules)
            ),
            user_message=user_message,
            max_tokens=settings.agent_max_tokens,
            temperature=settings.agent_temperature,
        )

        # Parse the response
        response_text = response.content

        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            # Extract JSON from code block
            lines = response_text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            response_text = "\n".join(json_lines)

        try:
            plan_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse plan response: {e}")
            raise ValueError(f"Failed to parse planning response: {e}")

        # Validate required fields
        required_fields = ["name", "description", "input_schema", "output_description"]
        for field in required_fields:
            if field not in plan_data:
                raise ValueError(f"Plan missing required field: {field}")

        # Validate modules are allowed
        required_modules = plan_data.get("required_modules", [])
        for module in required_modules:
            base_module = module.split(".")[0]
            if base_module not in ALLOWED_MODULES:
                logger.warning(f"Plan requested disallowed module: {module}")
                required_modules.remove(module)

        plan = ToolPlan(
            name=plan_data["name"],
            description=plan_data["description"],
            input_schema=plan_data["input_schema"],
            output_description=plan_data["output_description"],
            implementation_approach=plan_data.get("implementation_approach", ""),
            required_modules=required_modules,
            examples=plan_data.get("examples", []),
        )

        logger.info(f"Created plan for tool: {plan.name}")
        return plan

    def create_plan_sync(
        self,
        capability_description: str,
        context: Optional[str] = None,
    ) -> ToolPlan:
        """Synchronous wrapper for create_plan."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(
            self.create_plan(capability_description, context)
        )
