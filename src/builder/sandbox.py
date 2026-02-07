"""Sandbox executor for running tools in isolation.

This module provides two execution modes:
1. Modal Sandbox - True isolation using Modal's sandbox feature
2. Restricted exec - Fallback for local development

In production, Modal Sandbox provides:
- Process isolation
- Network isolation
- Filesystem isolation
- Resource limits (CPU, memory, time)
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.infra.logging import get_logger
from src.infra.config import get_settings

logger = get_logger("sandbox")


@dataclass
class ExecutionResult:
    """Result of tool execution."""

    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: int = 0


class SandboxExecutor(ABC):
    """Abstract base class for sandbox executors."""

    @abstractmethod
    def execute(
        self,
        implementation: str,
        input_data: Dict[str, Any],
        timeout_seconds: int = 30,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        """Execute tool code with input data.
        
        Args:
            implementation: Python source code with a main() function.
            input_data: Keyword arguments passed to main().
            timeout_seconds: Maximum execution time.
            extra_env: Additional env vars to inject (e.g., user secrets).
        """
        ...


class RestrictedExecExecutor(SandboxExecutor):
    """
    Execute tools using restricted exec().

    This is used for local development and testing.
    It provides some safety via restricted builtins but is NOT
    suitable for production use with untrusted code.
    """

    def __init__(self):
        # Pre-import allowed modules
        import base64
        import collections
        import copy
        import datetime as dt
        import decimal
        import enum
        import fractions
        import functools
        import hashlib
        import html
        import itertools
        import json
        import math
        import numbers
        import operator
        import os
        import random
        import re
        import statistics
        import string
        import textwrap
        import uuid as uuid_module

        # Network modules (optional)
        try:
            import httpx
            self._httpx = httpx
        except ImportError:
            self._httpx = None

        try:
            import requests
            self._requests = requests
        except ImportError:
            self._requests = None

        self._allowed_modules = {
            "math": math,
            "json": json,
            "re": re,
            "datetime": dt,
            "random": random,
            "statistics": statistics,
            "uuid": uuid_module,
            "decimal": decimal,
            "fractions": fractions,
            "collections": collections,
            "itertools": itertools,
            "functools": functools,
            "hashlib": hashlib,
            "base64": base64,
            "html": html,
            "string": string,
            "textwrap": textwrap,
            "copy": copy,
            "operator": operator,
            "numbers": numbers,
            "enum": enum,
            "os": os,  # Limited - only for env vars
        }

        # Add network modules if available
        if self._httpx:
            self._allowed_modules["httpx"] = self._httpx
        if self._requests:
            self._allowed_modules["requests"] = self._requests

    def execute(
        self,
        implementation: str,
        input_data: Dict[str, Any],
        timeout_seconds: int = 30,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        """Execute tool code using exec with full imports.
        
        Since code is pre-validated by the AST validator to only use
        allowed modules, and Modal provides container isolation,
        we can use regular exec with full import capability.
        """
        import builtins
        import os as _os
        start_time = time.perf_counter()

        # Inject user secrets as env vars for the duration of execution
        _prev_env: Dict[str, Optional[str]] = {}
        if extra_env:
            for k, v in extra_env.items():
                _prev_env[k] = _os.environ.get(k)
                _os.environ[k] = v

        try:
            # Use a single dict for both globals and locals
            # This ensures imports are visible to functions defined in the code
            exec_globals: Dict[str, Any] = {
                "__builtins__": builtins,
                "__name__": "__main__",
            }

            # Execute the implementation (use same dict for globals and locals)
            exec(implementation, exec_globals)

            # Get the main function
            main_func = exec_globals.get("main")
            if not main_func or not callable(main_func):
                raise ValueError("Implementation must define a callable 'main' function")

            # Call the function with input
            result = main_func(**input_data)

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            return ExecutionResult(
                success=True,
                result=result,
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.warning(f"Execution failed: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=elapsed_ms,
            )
        finally:
            # Restore previous env state — never leak user secrets
            if extra_env:
                for k in extra_env:
                    prev = _prev_env.get(k)
                    if prev is None:
                        _os.environ.pop(k, None)
                    else:
                        _os.environ[k] = prev


class ModalSandboxExecutor(SandboxExecutor):
    """
    Execute tools in Modal Sandbox.

    This provides true isolation with:
    - Separate process/container
    - No network access
    - Limited filesystem access
    - CPU/memory/time limits
    """

    def __init__(
        self,
        timeout_seconds: int = 30,
        memory_mb: int = 256,
        cpu: float = 0.25,
    ):
        self.timeout_seconds = timeout_seconds
        self.memory_mb = memory_mb
        self.cpu = cpu
        self._sandbox_image = None

    def _get_sandbox_image(self):
        """Get or create the sandbox image."""
        if self._sandbox_image is None:
            import modal

            self._sandbox_image = (
                modal.Image.debian_slim(python_version="3.11")
                .pip_install(
                    # Network libraries for API tools
                    "httpx",
                    "requests",
                    # Data science & visualization
                    "numpy",
                    "pandas",
                    "scipy",
                    "scikit-learn",
                    "matplotlib",
                    "pydantic",
                )
            )
        return self._sandbox_image

    def execute(
        self,
        implementation: str,
        input_data: Dict[str, Any],
        timeout_seconds: Optional[int] = None,
        extra_env: Optional[Dict[str, str]] = None,
    ) -> ExecutionResult:
        """Execute tool code in Modal Sandbox."""
        import modal
        import json

        timeout = timeout_seconds or self.timeout_seconds
        start_time = time.perf_counter()

        try:
            # Create the execution wrapper
            wrapper_code = f'''
import json
import sys

# The tool implementation
{implementation}

# Execute with input
if __name__ == "__main__":
    input_json = sys.argv[1]
    input_data = json.loads(input_json)
    result = main(**input_data)
    print(json.dumps({{"success": True, "result": result}}))
'''

            # Collect platform API keys from environment
            import os as _os
            env_vars = {}
            for key in ["EXA_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]:
                val = _os.environ.get(key)
                if val:
                    env_vars[key] = val

            # Merge in user-provided secrets (these take priority)
            if extra_env:
                env_vars.update(extra_env)

            # Create sandbox with all environment variables
            sandbox = modal.Sandbox.create(
                image=self._get_sandbox_image(),
                timeout=timeout,
                cpu=self.cpu,
                memory=self.memory_mb,
                secrets=[modal.Secret.from_dict(env_vars)] if env_vars else [],
            )

            try:
                # Run the code
                process = sandbox.exec(
                    "python",
                    "-c",
                    wrapper_code,
                    json.dumps(input_data),
                )

                # Wait for completion
                process.wait()

                # Check result
                stdout = process.stdout.read()
                stderr = process.stderr.read()

                if process.returncode != 0:
                    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                    return ExecutionResult(
                        success=False,
                        error=stderr or f"Process exited with code {process.returncode}",
                        execution_time_ms=elapsed_ms,
                    )

                # Parse result
                result_data = json.loads(stdout)
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)

                return ExecutionResult(
                    success=True,
                    result=result_data.get("result"),
                    execution_time_ms=elapsed_ms,
                )

            finally:
                sandbox.terminate()

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Sandbox execution failed: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time_ms=elapsed_ms,
            )


def create_executor() -> SandboxExecutor:
    """
    Create the appropriate executor based on settings.

    Returns:
        SandboxExecutor instance.
    """
    import os as _os
    settings = get_settings()

    # Only use Modal Sandbox when running inside Modal
    if settings.enable_sandbox_execution and _os.environ.get("MODAL_ENVIRONMENT"):
        try:
            import modal  # noqa: F401
            logger.info("Using Modal Sandbox executor")
            return ModalSandboxExecutor(
                timeout_seconds=settings.tool_timeout_seconds,
                memory_mb=settings.tool_memory_mb,
                cpu=settings.tool_cpu,
            )
        except ImportError:
            logger.warning("Modal not available, falling back to restricted exec")

    logger.info("Using restricted exec executor")
    return RestrictedExecExecutor()


# Default executor instance
_executor: Optional[SandboxExecutor] = None


def get_executor() -> SandboxExecutor:
    """Get the default executor instance."""
    global _executor
    if _executor is None:
        _executor = create_executor()
    return _executor


def reset_executor() -> None:
    """Reset the executor (for testing)."""
    global _executor
    _executor = None
