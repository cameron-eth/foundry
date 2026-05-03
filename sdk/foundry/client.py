"""Foundry SDK client."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

import httpx

from .exceptions import (
    ChainError,
    FoundryError,
    ToolCreationError,
    ToolInvocationError,
    ToolNotReadyError,
)


@dataclass
class ToolManifest:
    """Tool manifest containing metadata and schema."""
    
    tool_id: str
    name: str
    description: str
    input_schema: Dict[str, Any]
    status: str
    invoke_url: str
    manifest_url: str
    created_at: Optional[str] = None
    expires_at: Optional[str] = None


@dataclass
class InvocationResult:
    """Result of a tool invocation."""
    
    success: bool
    result: Any
    result_type: Optional[str] = None
    raw_result: Any = None
    error: Optional[str] = None
    execution_time_ms: Optional[int] = None
    
    def __repr__(self) -> str:
        if self.success:
            return f"InvocationResult(success=True, result={self.result!r})"
        return f"InvocationResult(success=False, error={self.error!r})"


class Tool:
    """
    A Foundry tool that can be invoked.
    
    Example:
        tool = client.create("Calculate factorial")
        result = tool.invoke(n=10)
        print(result.result)  # 3628800
    """
    
    def __init__(
        self,
        client: "Foundry",
        manifest: ToolManifest,
    ):
        self._client = client
        self._manifest = manifest
    
    @property
    def tool_id(self) -> str:
        return self._manifest.tool_id
    
    @property
    def name(self) -> str:
        return self._manifest.name
    
    @property
    def description(self) -> str:
        return self._manifest.description
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return self._manifest.input_schema
    
    @property
    def status(self) -> str:
        return self._manifest.status
    
    @property
    def is_ready(self) -> bool:
        return self._manifest.status == "ready"
    
    def invoke(self, **kwargs) -> InvocationResult:
        """
        Invoke the tool with the given arguments.
        
        Args:
            **kwargs: Arguments matching the tool's input schema.
            
        Returns:
            InvocationResult containing the result or error.
            
        Raises:
            ToolNotReadyError: If the tool isn't ready yet.
            ToolInvocationError: If the invocation fails.
        """
        if not self.is_ready:
            raise ToolNotReadyError(f"Tool {self.tool_id} is not ready (status: {self.status})")
        
        return self._client._invoke_tool(self._manifest.invoke_url, kwargs)
    
    def then(self, next_tool: Union["Tool", "ToolChain", Callable]) -> "ToolChain":
        """
        Chain this tool with another tool or function.
        
        Args:
            next_tool: The next tool, chain, or function to execute.
            
        Returns:
            A ToolChain that will execute both tools in sequence.
        """
        chain = ToolChain(self._client)
        chain.add(self)
        
        if isinstance(next_tool, ToolChain):
            for step in next_tool._steps:
                chain.add(step)
        else:
            chain.add(next_tool)
        
        return chain
    
    def refresh(self) -> "Tool":
        """Refresh the tool's manifest from the server."""
        self._manifest = self._client._get_manifest(self._manifest.manifest_url)
        return self
    
    def wait_until_ready(self, timeout: float = 60.0, poll_interval: float = 1.0) -> "Tool":
        """
        Wait until the tool is ready.
        
        Args:
            timeout: Maximum time to wait in seconds.
            poll_interval: Time between status checks in seconds.
            
        Returns:
            Self for chaining.
            
        Raises:
            TimeoutError: If the tool doesn't become ready in time.
        """
        start = time.time()
        while time.time() - start < timeout:
            self.refresh()
            if self.is_ready:
                return self
            if self.status == "failed":
                raise ToolCreationError(f"Tool creation failed: {self.tool_id}")
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Tool {self.tool_id} did not become ready within {timeout}s")
    
    def __repr__(self) -> str:
        return f"Tool(id={self.tool_id!r}, name={self.name!r}, status={self.status!r})"


class ToolChain:
    """
    A chain of tools that execute in sequence.
    
    Each tool receives the output of the previous tool as input.
    
    Example:
        chain = (
            client.create("Search for news about AI")
            .then(client.create("Summarize the articles"))
            .then(client.create("Translate to Spanish"))
        )
        result = chain.invoke()
    """
    
    def __init__(self, client: "Foundry"):
        self._client = client
        self._steps: List[Union[Tool, Callable]] = []
    
    def add(self, step: Union[Tool, Callable]) -> "ToolChain":
        """Add a step to the chain."""
        self._steps.append(step)
        return self
    
    def then(self, next_step: Union[Tool, "ToolChain", Callable]) -> "ToolChain":
        """Add the next step to the chain."""
        if isinstance(next_step, ToolChain):
            for step in next_step._steps:
                self._steps.append(step)
        else:
            self._steps.append(next_step)
        return self
    
    def invoke(self, **initial_input) -> InvocationResult:
        """
        Execute the chain with the given initial input.
        
        Args:
            **initial_input: Arguments for the first tool in the chain.
            
        Returns:
            InvocationResult from the final tool in the chain.
        """
        if not self._steps:
            raise ChainError("Cannot invoke empty chain")
        
        current_input = initial_input
        last_result: Optional[InvocationResult] = None
        
        for i, step in enumerate(self._steps):
            try:
                if isinstance(step, Tool):
                    # If we have a previous result, pass it as input
                    if last_result is not None:
                        # Try to intelligently map the output to input
                        if isinstance(last_result.raw_result, dict):
                            current_input = last_result.raw_result
                        else:
                            current_input = {"input": last_result.raw_result}
                    
                    last_result = step.invoke(**current_input)
                    
                    if not last_result.success:
                        raise ChainError(
                            f"Step {i + 1} failed: {last_result.error}",
                            step=i + 1,
                            tool_id=step.tool_id
                        )
                elif callable(step):
                    # It's a transform function
                    if last_result is not None:
                        transformed = step(last_result.raw_result)
                        last_result = InvocationResult(
                            success=True,
                            result=transformed,
                            result_type=type(transformed).__name__,
                            raw_result=transformed,
                        )
                    else:
                        transformed = step(current_input)
                        last_result = InvocationResult(
                            success=True,
                            result=transformed,
                            result_type=type(transformed).__name__,
                            raw_result=transformed,
                        )
            except ChainError:
                raise
            except Exception as e:
                raise ChainError(
                    f"Step {i + 1} raised exception: {e}",
                    step=i + 1,
                    tool_id=step.tool_id if isinstance(step, Tool) else None
                )
        
        return last_result
    
    def __repr__(self) -> str:
        steps_repr = " -> ".join(
            s.name if isinstance(s, Tool) else s.__name__
            for s in self._steps
        )
        return f"ToolChain([{steps_repr}])"


class Foundry:
    """
    Foundry API client.
    
    Example:
        from foundry import Foundry
        
        client = Foundry()
        
        # Create a tool from a description
        tool = client.create("Calculate the Fibonacci sequence up to n terms")
        
        # Invoke the tool
        result = tool.invoke(n=10)
        print(result.result)
        
        # Get an existing tool
        existing = client.get("tool-abc123")
        
        # Chain tools together
        chain = (
            client.create("Search for Python tutorials")
            .then(client.create("Extract the top 5 results"))
            .then(client.create("Format as markdown list"))
        )
        result = chain.invoke(query="python async tutorial")
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        org_id: Optional[str] = None,
        timeout: float = 120.0,
    ):
        """
        Initialize the Foundry client.
        
        Args:
            base_url: API base URL. Defaults to FOUNDRY_API_URL env var or production.
            api_key: API key. Defaults to FOUNDRY_API_KEY env var.
            org_id: Organization ID for namespacing tools. Defaults to "default".
            timeout: Request timeout in seconds.
        """
        self.base_url = (
            base_url
            or os.environ.get("FOUNDRY_API_URL")
            or "http://localhost:8000"
        ).rstrip("/")
        
        self.api_key = api_key or os.environ.get("FOUNDRY_API_KEY")
        self.org_id = org_id or os.environ.get("FOUNDRY_ORG_ID", "default")
        self.timeout = timeout
        
        self._client = httpx.Client(timeout=timeout)
    
    def _headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers
    
    def create(
        self,
        capability_description: str,
        conversation_id: Optional[str] = None,
        wait: bool = True,
        timeout: float = 60.0,
    ) -> Tool:
        """
        Create a new tool from a capability description.
        
        Args:
            capability_description: Natural language description of what the tool should do.
            conversation_id: Optional conversation ID for context.
            wait: If True, wait for the tool to be ready before returning.
            timeout: How long to wait for the tool to be ready.
            
        Returns:
            The created Tool.
            
        Raises:
            ToolCreationError: If tool creation fails.
        """
        import uuid
        
        payload = {
            "capability_description": capability_description,
            "org_id": self.org_id,
            "conversation_id": conversation_id or f"sdk-{uuid.uuid4().hex[:12]}",
            "async_build": not wait,
        }
        
        response = self._client.post(
            f"{self.base_url}/v1/construct",
            headers=self._headers(),
            json=payload,
        )
        
        if response.status_code != 200:
            raise ToolCreationError(f"Failed to create tool: {response.text}")
        
        data = response.json()
        
        if data.get("status") == "failed":
            raise ToolCreationError(
                data.get("message", "Tool creation failed"),
                request_id=data.get("request_id"),
            )
        
        # Fetch the full manifest
        manifest = self._get_manifest(data["manifest_url"])
        tool = Tool(self, manifest)
        
        if wait and not tool.is_ready:
            tool.wait_until_ready(timeout=timeout)
        
        return tool
    
    def get(self, tool_id: str) -> Tool:
        """
        Get an existing tool by ID.
        
        Args:
            tool_id: The tool ID.
            
        Returns:
            The Tool.
            
        Raises:
            FoundryError: If the tool doesn't exist.
        """
        manifest = self._get_manifest(f"{self.base_url}/v1/tools/{tool_id}")
        return Tool(self, manifest)
    
    def _get_manifest(self, url: str) -> ToolManifest:
        """Fetch a tool manifest."""
        response = self._client.get(url, headers=self._headers())
        
        if response.status_code == 404:
            raise FoundryError(f"Tool not found: {url}")
        if response.status_code != 200:
            raise FoundryError(f"Failed to get tool manifest: {response.text}")
        
        data = response.json()
        
        return ToolManifest(
            tool_id=data["tool_id"],
            name=data["name"],
            description=data["description"],
            input_schema=data["input_schema"],
            status=data["status"],
            invoke_url=data["invoke_url"],
            manifest_url=url,  # Use the URL we fetched from
            created_at=data.get("created_at"),
            expires_at=data.get("expires_at"),
        )
    
    def _invoke_tool(self, url: str, inputs: Dict[str, Any]) -> InvocationResult:
        """Invoke a tool at the given URL."""
        response = self._client.post(
            url,
            headers=self._headers(),
            json={"input": inputs},
        )
        
        if response.status_code != 200:
            raise ToolInvocationError(f"Failed to invoke tool: {response.text}")
        
        data = response.json()
        
        return InvocationResult(
            success=data.get("success", False),
            result=data.get("result"),
            result_type=data.get("result_type"),
            raw_result=data.get("raw_result"),
            error=data.get("error"),
            execution_time_ms=data.get("execution_time_ms"),
        )
    
    def search(
        self,
        query: str,
        num_results: int = 10,
        num_searches: int = 1,
        optimize_query: bool = True,
    ) -> Dict[str, Any]:
        """
        Search the web using Foundry's search API.
        
        Args:
            query: The search query.
            num_results: Number of results to return.
            num_searches: Number of parallel searches to perform.
            optimize_query: Whether to optimize the query with LLM.
            
        Returns:
            Search results dictionary.
        """
        response = self._client.post(
            f"{self.base_url}/v1/search",
            headers=self._headers(),
            json={
                "query": query,
                "num_results": num_results,
                "num_searches": num_searches,
                "optimize_query": optimize_query,
            },
        )
        
        if response.status_code != 200:
            raise FoundryError(f"Search failed: {response.text}")
        
        return response.json()
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self) -> "Foundry":
        return self
    
    def __exit__(self, *args):
        self.close()
    
    def __repr__(self) -> str:
        return f"Foundry(base_url={self.base_url!r}, org_id={self.org_id!r})"
