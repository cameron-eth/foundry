"""Tests for the Tool Foundry API."""

import pytest
from fastapi.testclient import TestClient

from src.api.routes import get_registry, web_app


@pytest.fixture
def client():
    """Create a test client."""
    # Clear registry before each test
    get_registry().clear()
    return TestClient(web_app)


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Health check should return healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "tool-foundry"


class TestCreateTool:
    """Tests for tool creation endpoint."""

    def test_create_simple_tool(self, client):
        """Should create a simple tool successfully."""
        response = client.post(
            "/v1/tools",
            json={
                "name": "add_numbers",
                "description": "Add two numbers",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                    },
                    "required": ["a", "b"],
                },
                "implementation": "def main(a: float, b: float) -> float:\n    return a + b",
                "org_id": "test-org",
                "conversation_id": "test-conv",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["tool_id"].startswith("tool-")
        assert "manifest_url" in data
        assert "invoke_url" in data

    def test_create_tool_with_math(self, client):
        """Should create a tool using math module."""
        response = client.post(
            "/v1/tools",
            json={
                "name": "sqrt",
                "description": "Calculate square root",
                "input_schema": {
                    "type": "object",
                    "properties": {"x": {"type": "number"}},
                    "required": ["x"],
                },
                "implementation": "import math\n\ndef main(x: float) -> float:\n    return math.sqrt(x)",
                "org_id": "test-org",
                "conversation_id": "test-conv",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_create_tool_blocked_module(self, client):
        """Should fail when using blocked module."""
        response = client.post(
            "/v1/tools",
            json={
                "name": "bad_tool",
                "description": "Uses subprocess module",
                "input_schema": {"type": "object"},
                "implementation": "import subprocess\n\ndef main() -> str:\n    return subprocess.check_output(['ls'])",
                "org_id": "test-org",
                "conversation_id": "test-conv",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "subprocess" in data["message"].lower()

    def test_create_tool_no_main(self, client):
        """Should fail when main function is missing."""
        response = client.post(
            "/v1/tools",
            json={
                "name": "no_main",
                "description": "Missing main",
                "input_schema": {"type": "object"},
                "implementation": "def add(a, b):\n    return a + b",
                "org_id": "test-org",
                "conversation_id": "test-conv",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "main" in data["message"].lower()

    def test_create_tool_syntax_error(self, client):
        """Should fail with syntax error."""
        response = client.post(
            "/v1/tools",
            json={
                "name": "syntax_error",
                "description": "Has syntax error",
                "input_schema": {"type": "object"},
                "implementation": "def main(\n    return 42",
                "org_id": "test-org",
                "conversation_id": "test-conv",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "syntax" in data["message"].lower()


class TestInvokeTool:
    """Tests for tool invocation endpoint."""

    def test_invoke_simple_tool(self, client):
        """Should invoke a simple tool successfully."""
        # Create tool first
        create_response = client.post(
            "/v1/tools",
            json={
                "name": "add",
                "description": "Add numbers",
                "input_schema": {"type": "object"},
                "implementation": "def main(a: float, b: float) -> float:\n    return a + b",
                "org_id": "test-org",
                "conversation_id": "test-conv",
            },
        )
        tool_id = create_response.json()["tool_id"]

        # Invoke it
        response = client.post(
            f"/v1/tools/{tool_id}:invoke",
            json={"input": {"a": 5, "b": 3}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result_type"] == "number"
        assert data["result"]["number"] == 8.0
        assert data["raw_result"] == 8  # Backward compat
        assert data["execution_time_ms"] >= 0

    def test_invoke_tool_with_math(self, client):
        """Should invoke a tool using math module."""
        # Create tool
        create_response = client.post(
            "/v1/tools",
            json={
                "name": "circle_area",
                "description": "Calculate circle area",
                "input_schema": {"type": "object"},
                "implementation": "import math\n\ndef main(radius: float) -> float:\n    return math.pi * radius ** 2",
                "org_id": "test-org",
                "conversation_id": "test-conv",
            },
        )
        tool_id = create_response.json()["tool_id"]

        # Invoke
        response = client.post(
            f"/v1/tools/{tool_id}:invoke",
            json={"input": {"radius": 2}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result_type"] == "number"
        assert abs(data["result"]["number"] - 12.566370614359172) < 0.0001

    def test_invoke_tool_with_json(self, client):
        """Should invoke a tool using json module."""
        # Create tool
        create_response = client.post(
            "/v1/tools",
            json={
                "name": "to_json",
                "description": "Convert to JSON",
                "input_schema": {"type": "object"},
                "implementation": "import json\n\ndef main(data: dict) -> str:\n    return json.dumps(data, sort_keys=True)",
                "org_id": "test-org",
                "conversation_id": "test-conv",
            },
        )
        tool_id = create_response.json()["tool_id"]

        # Invoke
        response = client.post(
            f"/v1/tools/{tool_id}:invoke",
            json={"input": {"data": {"b": 2, "a": 1}}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result_type"] == "text"
        assert data["result"]["text"] == '{"a": 1, "b": 2}'

    def test_invoke_nonexistent_tool(self, client):
        """Should return 404 for nonexistent tool."""
        response = client.post(
            "/v1/tools/tool-nonexistent:invoke",
            json={"input": {}},
        )
        assert response.status_code == 404

    def test_invoke_tool_runtime_error(self, client):
        """Should handle runtime errors gracefully."""
        # Create tool that will fail
        create_response = client.post(
            "/v1/tools",
            json={
                "name": "divide",
                "description": "Divide numbers",
                "input_schema": {"type": "object"},
                "implementation": "def main(a: float, b: float) -> float:\n    return a / b",
                "org_id": "test-org",
                "conversation_id": "test-conv",
            },
        )
        tool_id = create_response.json()["tool_id"]

        # Invoke with zero denominator
        response = client.post(
            f"/v1/tools/{tool_id}:invoke",
            json={"input": {"a": 5, "b": 0}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "division" in data["error"].lower() or "zero" in data["error"].lower()


class TestGetTool:
    """Tests for getting tool metadata."""

    def test_get_tool(self, client):
        """Should get tool metadata."""
        # Create tool
        create_response = client.post(
            "/v1/tools",
            json={
                "name": "test_tool",
                "description": "A test tool",
                "input_schema": {"type": "object", "properties": {"x": {"type": "number"}}},
                "implementation": "def main(x: int) -> int:\n    return x * 2",
                "org_id": "test-org",
                "conversation_id": "test-conv",
            },
        )
        tool_id = create_response.json()["tool_id"]

        # Get tool
        response = client.get(f"/v1/tools/{tool_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["tool_id"] == tool_id
        assert data["name"] == "test_tool"
        assert data["description"] == "A test tool"
        assert data["status"] == "ready"

    def test_get_nonexistent_tool(self, client):
        """Should return 404 for nonexistent tool."""
        response = client.get("/v1/tools/tool-nonexistent")
        assert response.status_code == 404


class TestDeleteTool:
    """Tests for deleting tools."""

    def test_delete_tool(self, client):
        """Should delete a tool."""
        # Create tool
        create_response = client.post(
            "/v1/tools",
            json={
                "name": "to_delete",
                "description": "Will be deleted",
                "input_schema": {"type": "object"},
                "implementation": "def main() -> int:\n    return 42",
                "org_id": "test-org",
                "conversation_id": "test-conv",
            },
        )
        tool_id = create_response.json()["tool_id"]

        # Delete
        response = client.delete(f"/v1/tools/{tool_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify it's gone
        response = client.get(f"/v1/tools/{tool_id}")
        assert response.status_code == 404

    def test_delete_nonexistent_tool(self, client):
        """Should return 404 for nonexistent tool."""
        response = client.delete("/v1/tools/tool-nonexistent")
        assert response.status_code == 404


class TestListTools:
    """Tests for listing tools."""

    def test_list_empty(self, client):
        """Should return empty list when no tools."""
        response = client.get("/v1/tools")
        assert response.status_code == 200
        assert response.json()["tools"] == []

    def test_list_tools(self, client):
        """Should list all tools."""
        # Create two tools
        client.post(
            "/v1/tools",
            json={
                "name": "tool1",
                "description": "First tool",
                "input_schema": {"type": "object"},
                "implementation": "def main() -> int:\n    return 1",
                "org_id": "org1",
                "conversation_id": "conv1",
            },
        )
        client.post(
            "/v1/tools",
            json={
                "name": "tool2",
                "description": "Second tool",
                "input_schema": {"type": "object"},
                "implementation": "def main() -> int:\n    return 2",
                "org_id": "org2",
                "conversation_id": "conv2",
            },
        )

        # List all
        response = client.get("/v1/tools")
        assert response.status_code == 200
        tools = response.json()["tools"]
        assert len(tools) == 2

    def test_list_tools_filtered_by_org(self, client):
        """Should filter tools by org_id."""
        # Create tools for different orgs
        client.post(
            "/v1/tools",
            json={
                "name": "tool1",
                "description": "Org1 tool",
                "input_schema": {"type": "object"},
                "implementation": "def main() -> int:\n    return 1",
                "org_id": "org1",
                "conversation_id": "conv1",
            },
        )
        client.post(
            "/v1/tools",
            json={
                "name": "tool2",
                "description": "Org2 tool",
                "input_schema": {"type": "object"},
                "implementation": "def main() -> int:\n    return 2",
                "org_id": "org2",
                "conversation_id": "conv2",
            },
        )

        # Filter by org1
        response = client.get("/v1/tools?org_id=org1")
        assert response.status_code == 200
        tools = response.json()["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "tool1"
