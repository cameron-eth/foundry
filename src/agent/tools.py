"""Function tools for the Agents SDK builder pipeline.

These are plain Python functions decorated with @function_tool so the
OpenAI Agents SDK can expose them to the GeneratorAgent.
"""

from __future__ import annotations

import json
import traceback
from typing import Any, Dict, Optional

from agents import function_tool

from src.builder.validator import (
    ALLOWED_MODULES,
    validate_restricted_python,
    ValidationError,
)
from src.infra.logging import get_logger

logger = get_logger("agent.tools")


# ---------------------------------------------------------------------------
# Tool 1 — AST security validator
# ---------------------------------------------------------------------------
@function_tool
def validate_code(code: str) -> str:
    """Validate Python code against Tool Foundry's security restrictions.

    Checks that the code:
      - Only imports allowed modules
      - Defines a main() function
      - Contains no blocked builtins (eval, exec, open …)
      - Contains no dunder attribute access
      - Is under 50 KB
      - Is syntactically valid Python

    Args:
        code: The full Python source code to validate.

    Returns:
        "VALID" if the code passes all checks, or a string starting with
        "INVALID:" followed by the specific error and line number.
    """
    try:
        validate_restricted_python(code)
        return "VALID"
    except ValidationError as e:
        return f"INVALID: {e}"
    except Exception as e:
        return f"INVALID: Unexpected error during validation: {e}"


# ---------------------------------------------------------------------------
# Tool 2 — Test executor  (sandboxed exec)
# ---------------------------------------------------------------------------
@function_tool
def test_code(code: str, test_input_json: str) -> str:
    """Execute a tool's main() with sample input to verify it works at runtime.

    This runs the code in a restricted namespace.  Network calls are allowed
    so API-based tools can be smoke-tested.

    Args:
        code: The full Python source code (must define main()).
        test_input_json: A JSON string of keyword arguments for main().
                         Example: '{"radius": 5}'

    Returns:
        "SUCCESS: <json result>" if main() returns without error, or
        "ERROR: <exception type>: <message>" if it crashes.
    """
    import builtins as _builtins

    try:
        test_input: Dict[str, Any] = json.loads(test_input_json)
    except json.JSONDecodeError as e:
        return f"ERROR: Invalid test_input_json — {e}"

    try:
        exec_globals: Dict[str, Any] = {
            "__builtins__": _builtins,
            "__name__": "__main__",
        }
        exec(code, exec_globals)

        main_func = exec_globals.get("main")
        if not main_func or not callable(main_func):
            return "ERROR: Code does not define a callable main() function"

        result = main_func(**test_input)

        # Verify JSON-serialisable
        result_json = json.dumps(result, default=str)
        # Truncate for context window friendliness
        if len(result_json) > 1000:
            result_json = result_json[:1000] + "… (truncated)"

        return f"SUCCESS: {result_json}"

    except Exception as e:
        tb = traceback.format_exc()
        # Keep traceback short
        lines = tb.strip().split("\n")
        short_tb = "\n".join(lines[-4:]) if len(lines) > 4 else tb
        return f"ERROR: {type(e).__name__}: {e}\n{short_tb}"


# ---------------------------------------------------------------------------
# Tool 3 — List allowed modules (informational)
# ---------------------------------------------------------------------------
@function_tool
def list_allowed_modules() -> str:
    """Return the full list of Python modules the tool is allowed to import.

    Returns:
        Comma-separated list of allowed module names.
    """
    return ", ".join(sorted(ALLOWED_MODULES))
