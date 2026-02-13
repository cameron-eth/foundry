"""Shared prompt context for Tool Foundry agents.

This module centralises all API documentation, constraints, and examples
so the Planner and Generator agents stay in sync when we add new
integrations or change the security rules.
"""

from __future__ import annotations

from src.builder.validator import ALLOWED_MODULES

# ---------------------------------------------------------------------------
# Dynamic values
# ---------------------------------------------------------------------------
ALLOWED_MODULES_STR = ", ".join(sorted(ALLOWED_MODULES))

# ---------------------------------------------------------------------------
# Shared constraint block  (referenced by both planner & generator)
# ---------------------------------------------------------------------------
TOOL_CONSTRAINTS = f"""\
## Constraints

The tool MUST:
1. Define a `main()` function as the single entry point.
2. Only import from the allowed module set: {ALLOWED_MODULES_STR}
3. Be fully synchronous — no `async def`, no `await`.
4. Be pure-functional where possible (input → output).
5. Use type hints for **every** parameter and the return value.
6. Include a docstring in `main()` describing args and return value.
7. Handle edge cases gracefully (empty inputs, missing keys, bad data).
8. Always set `timeout=30.0` on HTTP requests.
9. Return JSON-serialisable values (dicts, lists, strings, numbers, bools, None).

The tool MUST NOT:
- Use `eval()`, `exec()`, `compile()`, `__import__()`.
- Access dunder attributes (`__class__`, `__subclasses__`, …).
- Use `open()` for file I/O.
- Use lambda expressions — use `def` instead.
- Use `getattr`, `setattr`, `delattr`, `hasattr`.
"""

# ---------------------------------------------------------------------------
# Available external APIs
# ---------------------------------------------------------------------------
EXTERNAL_APIS = """\
## Available External APIs

### Exa Search API
- Endpoint: `https://api.exa.ai/search`
- Auth: `os.environ.get("EXA_API_KEY")` in `x-api-key` header
- Use for: web search, research, content discovery

```python
import httpx, os

def main(query: str, num_results: int = 10) -> dict:
    \"\"\"Search the web using Exa.\"\"\"
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        return {"error": "EXA_API_KEY not configured"}
    resp = httpx.post(
        "https://api.exa.ai/search",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json={"query": query, "num_results": num_results, "type": "neural"},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()
```

### Polymarket Prediction Markets API (no key required)
- Base URL: `https://gamma-api.polymarket.com`
- Endpoints: `GET /markets`, `GET /events`
- Params: `limit`, `offset`, `order`, `ascending`, `closed`, `tag_id`

```python
import httpx

def main(limit: int = 10, order_by: str = "volume") -> dict:
    \"\"\"Get top prediction markets from Polymarket.\"\"\"
    resp = httpx.get(
        "https://gamma-api.polymarket.com/markets",
        params={"limit": limit, "order": order_by, "ascending": False, "closed": False},
        timeout=30.0,
    )
    resp.raise_for_status()
    markets = resp.json()
    return {
        "count": len(markets),
        "markets": [
            {
                "question": m.get("question"),
                "volume": m.get("volume"),
                "outcomes": m.get("outcomes"),
                "outcomePrices": m.get("outcomePrices"),
            }
            for m in markets
        ],
    }
```

### User-Provided Third-Party Credentials
Users store their own API keys via `PUT /v1/tools/{tool_id}/secrets`.
They are injected as environment variables at runtime.

Access pattern:
```python
import os

api_key = os.environ.get("STRIPE_API_KEY")
if not api_key:
    return {"error": "STRIPE_API_KEY not configured. Set it via PUT /v1/tools/{tool_id}/secrets"}
```

Naming convention: `SCREAMING_SNAKE_CASE` (e.g. `TIKTOK_ACCESS_TOKEN`, `GITHUB_TOKEN`).

### Matplotlib Visualisation
Return charts as base64-encoded PNG strings:
```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io, base64

def main(values: list, title: str = "Chart") -> dict:
    \"\"\"Generate a line chart.\"\"\"
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(values)
    ax.set_title(title)
    ax.grid(True)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return {"image_base64": base64.b64encode(buf.read()).decode(), "format": "png"}
```
"""

# ---------------------------------------------------------------------------
# Few-shot examples  — diverse coverage
# ---------------------------------------------------------------------------
PLAN_FEW_SHOTS = """\
## Examples

### Example 1 — Simple calculation
Description: "Calculate compound interest"
```json
{
    "name": "calculate_compound_interest",
    "description": "Calculate compound interest given principal, rate, time, and compounding frequency",
    "input_schema": {
        "type": "object",
        "properties": {
            "principal": {"type": "number", "description": "Initial investment amount"},
            "rate": {"type": "number", "description": "Annual interest rate as decimal (e.g. 0.05)"},
            "years": {"type": "number", "description": "Investment period in years"},
            "n": {"type": "integer", "description": "Times compounded per year", "default": 12}
        },
        "required": ["principal", "rate", "years"]
    },
    "output_description": "Dict with 'amount' (final value) and 'interest_earned'",
    "implementation_approach": "Use formula A = P(1 + r/n)^(nt). Validate all inputs are non-negative.",
    "required_modules": ["math"],
    "examples": [{"input": {"principal": 1000, "rate": 0.05, "years": 10}, "output": {"amount": 1647.01, "interest_earned": 647.01}}]
}
```

### Example 2 — API tool with httpx
Description: "Get current weather for a city using Open-Meteo"
```json
{
    "name": "get_weather",
    "description": "Fetch current weather for a city using the free Open-Meteo API",
    "input_schema": {
        "type": "object",
        "properties": {
            "latitude": {"type": "number", "description": "City latitude"},
            "longitude": {"type": "number", "description": "City longitude"}
        },
        "required": ["latitude", "longitude"]
    },
    "output_description": "Dict with temperature, wind_speed, and weather_code",
    "implementation_approach": "Call Open-Meteo API at https://api.open-meteo.com/v1/forecast with current_weather=true. Parse the response and return relevant fields.",
    "required_modules": ["httpx"],
    "examples": [{"input": {"latitude": 40.71, "longitude": -74.01}, "output": {"temperature": 22.5, "wind_speed": 12.3}}]
}
```

### Example 3 — Data processing
Description: "Analyse a list of numbers — mean, median, std dev, min, max"
```json
{
    "name": "analyse_numbers",
    "description": "Calculate statistical summary of a list of numbers",
    "input_schema": {
        "type": "object",
        "properties": {
            "values": {"type": "array", "items": {"type": "number"}, "description": "List of numeric values"}
        },
        "required": ["values"]
    },
    "output_description": "Dict with mean, median, stdev, min, max, count",
    "implementation_approach": "Use statistics module for mean, median, stdev. Use builtins for min, max, len. Handle empty list edge case.",
    "required_modules": ["statistics"],
    "examples": [{"input": {"values": [1, 2, 3, 4, 5]}, "output": {"mean": 3.0, "median": 3, "stdev": 1.58, "min": 1, "max": 5, "count": 5}}]
}
```

### Example 4 — User-secret API tool
Description: "Fetch my GitHub repositories"
```json
{
    "name": "list_github_repos",
    "description": "List authenticated user's GitHub repositories using their personal access token",
    "input_schema": {
        "type": "object",
        "properties": {
            "sort": {"type": "string", "description": "Sort by: created, updated, pushed, full_name", "default": "updated"},
            "per_page": {"type": "integer", "description": "Results per page (max 100)", "default": 30}
        },
        "required": []
    },
    "output_description": "Dict with repos list (name, url, description, stars, language)",
    "implementation_approach": "Read GITHUB_TOKEN from env. Call GET https://api.github.com/user/repos with auth header. Return parsed list.",
    "required_modules": ["httpx", "os"],
    "examples": [{"input": {"sort": "updated", "per_page": 5}, "output": {"repos": [{"name": "my-repo", "stars": 42}]}}]
}
```
"""

CODE_FEW_SHOTS = """\
## Code Examples

### Example 1 — Simple calculation
```python
import math

def main(principal: float, rate: float, years: float, n: int = 12) -> dict:
    \"\"\"Calculate compound interest.
    
    Args:
        principal: Initial investment amount.
        rate: Annual interest rate as decimal (e.g. 0.05 for 5%).
        years: Investment period in years.
        n: Times compounded per year (default 12).
    
    Returns:
        Dict with 'amount' and 'interest_earned'.
    \"\"\"
    if principal < 0:
        raise ValueError("Principal must be non-negative")
    if rate < 0:
        raise ValueError("Rate must be non-negative")
    if years < 0:
        raise ValueError("Years must be non-negative")
    if n <= 0:
        raise ValueError("Compounding frequency must be positive")
    
    amount = principal * math.pow(1 + rate / n, n * years)
    amount = round(amount, 2)
    return {"amount": amount, "interest_earned": round(amount - principal, 2)}
```

### Example 2 — API tool with httpx
```python
import httpx

def main(latitude: float, longitude: float) -> dict:
    \"\"\"Fetch current weather from Open-Meteo API.
    
    Args:
        latitude: City latitude.
        longitude: City longitude.
    
    Returns:
        Dict with temperature, wind_speed, and weather description.
    \"\"\"
    resp = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": True,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()
    current = data.get("current_weather", {})
    return {
        "temperature_c": current.get("temperature"),
        "wind_speed_kmh": current.get("windspeed"),
        "weather_code": current.get("weathercode"),
    }
```

### Example 3 — Data processing
```python
import statistics

def main(values: list) -> dict:
    \"\"\"Calculate statistical summary of a list of numbers.
    
    Args:
        values: List of numeric values.
    
    Returns:
        Dict with mean, median, stdev, min, max, count.
    \"\"\"
    if not values:
        return {"error": "values list is empty", "count": 0}
    
    result = {
        "mean": round(statistics.mean(values), 4),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "count": len(values),
    }
    if len(values) >= 2:
        result["stdev"] = round(statistics.stdev(values), 4)
    else:
        result["stdev"] = 0.0
    return result
```

### Example 4 — User-secret API tool
```python
import httpx
import os

def main(sort: str = "updated", per_page: int = 30) -> dict:
    \"\"\"List the authenticated user's GitHub repositories.
    
    Args:
        sort: Sort by created, updated, pushed, or full_name.
        per_page: Results per page (max 100).
    
    Returns:
        Dict with list of repos.
    \"\"\"
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {"error": "GITHUB_TOKEN not configured. Set it via PUT /v1/tools/{tool_id}/secrets"}
    
    resp = httpx.get(
        "https://api.github.com/user/repos",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        params={"sort": sort, "per_page": min(per_page, 100)},
        timeout=30.0,
    )
    resp.raise_for_status()
    repos = resp.json()
    return {
        "count": len(repos),
        "repos": [
            {
                "name": r.get("name"),
                "full_name": r.get("full_name"),
                "description": r.get("description"),
                "url": r.get("html_url"),
                "stars": r.get("stargazers_count"),
                "language": r.get("language"),
                "updated_at": r.get("updated_at"),
            }
            for r in repos
        ],
    }
```
"""
