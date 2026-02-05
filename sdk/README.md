# Foundry SDK

Python SDK for [Foundry](https://foundry.ai) - Build AI-powered tools from natural language descriptions.

## Installation

```bash
pip install foundry-sdk
```

## Quick Start

```python
from foundry import Foundry

# Initialize the client
client = Foundry()

# Create a tool from a description
tool = client.create("Calculate compound interest given principal, rate, and time")

# Invoke the tool
result = tool.invoke(principal=1000, rate=0.05, time=10)
print(result.result)  # {'final_amount': 1628.89, ...}
```

## Features

### Create Tools

Generate tools from natural language:

```python
# Math tools
factorial = client.create("Calculate factorial of a number")
result = factorial.invoke(n=10)

# Data processing
parser = client.create("Parse CSV data and return as list of dictionaries")
result = parser.invoke(csv_data="name,age\nAlice,30\nBob,25")

# Web search (requires Exa API key)
searcher = client.create("Search the web for recent news about a topic")
result = searcher.invoke(query="AI developments 2025")

# Prediction markets (Polymarket)
markets = client.create("Get current prediction market odds for an event")
result = markets.invoke(search_term="2024 election")
```

### Tool Chaining

Chain multiple tools together:

```python
# Create a pipeline
chain = (
    client.create("Search for news about {topic}")
    .then(client.create("Extract the main points from search results"))
    .then(client.create("Summarize the points in 3 bullet points"))
)

result = chain.invoke(topic="artificial intelligence")
```

### Custom Transforms

Add custom Python functions to chains:

```python
def format_as_markdown(data):
    return f"# Results\n\n{data}"

chain = (
    client.create("Search for Python tutorials")
    .then(format_as_markdown)
)

result = chain.invoke(query="async python")
```

### Get Existing Tools

Retrieve and reuse previously created tools:

```python
# Get a tool by ID
tool = client.get("tool-abc123")

# Check status
print(tool.status)  # "ready"
print(tool.input_schema)  # JSON schema

# Invoke it
result = tool.invoke(x=42)
```

### Web Search

Use Foundry's built-in search API:

```python
results = client.search(
    query="How do I learn Python?",
    num_results=10,
    num_searches=3,  # Generates 3 related queries
    optimize_query=True,  # LLM optimizes your query
)

for r in results["results"]:
    print(f"- {r['title']}: {r['url']}")
```

## Configuration

### Environment Variables

```bash
export FOUNDRY_API_URL="https://your-deployment.modal.run"
export FOUNDRY_API_KEY="your-api-key"  # Optional
export FOUNDRY_ORG_ID="your-org"
```

### Client Options

```python
client = Foundry(
    base_url="https://custom-deployment.modal.run",
    api_key="sk-...",
    org_id="my-org",
    timeout=120.0,
)
```

## Async Support

For async applications:

```python
import asyncio
from foundry import Foundry

async def main():
    client = Foundry()
    
    # Create runs synchronously (building happens server-side)
    tool = client.create("Calculate prime numbers up to n")
    
    # Invoke
    result = tool.invoke(n=100)
    print(result.result)

asyncio.run(main())
```

## Error Handling

```python
from foundry import Foundry, ToolCreationError, ToolInvocationError

client = Foundry()

try:
    tool = client.create("Impossible task that will fail")
except ToolCreationError as e:
    print(f"Failed to create tool: {e}")
    print(f"Request ID: {e.request_id}")

try:
    result = tool.invoke(bad_param="invalid")
except ToolInvocationError as e:
    print(f"Invocation failed: {e}")
    print(f"Tool ID: {e.tool_id}")
```

## Examples

### Financial Calculator

```python
tool = client.create("""
    Calculate loan amortization schedule.
    Given principal, annual interest rate, and loan term in months,
    return monthly payment and total interest paid.
""")

result = tool.invoke(
    principal=250000,
    annual_rate=0.065,
    term_months=360,
)
print(result.result)
# {'monthly_payment': 1580.17, 'total_interest': 318861.20, ...}
```

### Data Analysis Pipeline

```python
chain = (
    client.create("Fetch stock data for a ticker symbol")
    .then(client.create("Calculate 20-day moving average"))
    .then(client.create("Generate a buy/sell signal based on price vs MA"))
)

result = chain.invoke(ticker="AAPL")
print(result.result)  # {'signal': 'BUY', 'price': 185.50, 'ma_20': 182.30}
```

### Polymarket Integration

```python
# Get prediction market data
tool = client.create("""
    Query Polymarket for prediction markets matching a search term.
    Return the top 5 markets with their current probabilities.
""")

result = tool.invoke(search_term="AI")
for market in result.result["markets"]:
    print(f"{market['question']}: {market['probability']}%")
```

## License

MIT
