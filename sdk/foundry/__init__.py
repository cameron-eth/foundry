"""
Foundry SDK - Build and invoke AI-generated tools.

Usage:
    from foundry import Foundry
    
    client = Foundry()
    
    # Create a tool
    tool = client.create("Calculate compound interest with principal, rate, and time")
    
    # Invoke the tool
    result = tool.invoke(principal=1000, rate=0.05, time=10)
    
    # Chain tools
    result = (
        client.create("Search for latest AI news")
        .then(client.create("Summarize the search results"))
        .invoke()
    )
"""

from .client import Foundry, Tool, ToolChain
from .exceptions import FoundryError, ToolCreationError, ToolInvocationError

__version__ = "0.1.0"
__all__ = [
    "Foundry",
    "Tool",
    "ToolChain",
    "FoundryError",
    "ToolCreationError",
    "ToolInvocationError",
]
