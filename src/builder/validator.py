"""Restricted Python validator for tool implementations.

This module validates that user-provided Python code only uses allowed
modules and patterns, preventing access to dangerous functionality.
"""

from __future__ import annotations

import ast
import re
from typing import Final

# Modules that are safe to import
ALLOWED_MODULES: Final[frozenset[str]] = frozenset(
    {
        # Standard library - safe subset
        "math",
        "datetime",
        "json",
        "re",
        "typing",
        "collections",
        "itertools",
        "functools",
        "dataclasses",
        "enum",
        "decimal",
        "fractions",
        "statistics",
        "random",
        "uuid",
        "hashlib",
        "base64",
        "urllib.parse",
        "html",
        "string",
        "textwrap",
        "copy",
        "operator",
        "numbers",
        "abc",
        # Allowed third-party packages
        "pydantic",
        "numpy",
        "pandas",
        "scipy",
        "sklearn",
        "matplotlib",
        # Utilities for data handling
        "io",
        # Network access (for API tools)
        "httpx",
        "requests",
        # Limited os access (for environment variables)
        "os",
    }
)

# Modules that are explicitly blocked (even if they might appear safe)
BLOCKED_MODULES: Final[frozenset[str]] = frozenset(
    {
        # "os" - now allowed for os.environ.get() only
        "sys",
        "subprocess",
        "shutil",
        "pathlib",
        "socket",
        "http",
        "urllib.request",
        "ftplib",
        "smtplib",
        "telnetlib",
        "ssl",
        "asyncio",
        "threading",
        "multiprocessing",
        "concurrent",
        "ctypes",
        "importlib",
        "builtins",
        "pickle",
        "marshal",
        "shelve",
        "dbm",
        "sqlite3",
        "code",
        "codeop",
        "compileall",
        "dis",
        "inspect",
        "gc",
        "traceback",
        "tracemalloc",
        "warnings",
        "atexit",
        "signal",
        "resource",
        "pwd",
        "grp",
        "fcntl",
        "termios",
        "pty",
        "tty",
    }
)

# Builtins that are blocked
BLOCKED_BUILTINS: Final[frozenset[str]] = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",
        "input",
        "breakpoint",
        "globals",
        "locals",
        "vars",
        "dir",
        "getattr",
        "setattr",
        "delattr",
        "hasattr",
        "memoryview",
        "bytearray",
        "bytes",  # Can be used for code execution
    }
)

# Patterns that indicate dangerous code
BLOCKED_PATTERNS: Final[list[tuple[str, str]]] = [
    (r"__\w+__", "Dunder attributes are not allowed"),
    (r"lambda\s*:", "Lambda expressions are not allowed (use def instead)"),
]


class ValidationError(ValueError):
    """Raised when code validation fails."""

    def __init__(self, message: str, line: int | None = None, col: int | None = None):
        self.line = line
        self.col = col
        location = f" at line {line}" if line else ""
        super().__init__(f"{message}{location}")


class RestrictedPythonValidator(ast.NodeVisitor):
    """AST visitor that validates Python code against security restrictions."""

    def __init__(self):
        self.errors: list[ValidationError] = []
        self.has_main_function = False

    def visit_Import(self, node: ast.Import) -> None:
        """Check that imported modules are allowed."""
        for alias in node.names:
            module = alias.name.split(".")[0]
            if module in BLOCKED_MODULES:
                self.errors.append(
                    ValidationError(
                        f"Module '{module}' is not allowed",
                        line=node.lineno,
                        col=node.col_offset,
                    )
                )
            elif module not in ALLOWED_MODULES:
                self.errors.append(
                    ValidationError(
                        f"Module '{module}' is not in the allowlist",
                        line=node.lineno,
                        col=node.col_offset,
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check that imported modules are allowed."""
        if node.module:
            module = node.module.split(".")[0]
            if module in BLOCKED_MODULES:
                self.errors.append(
                    ValidationError(
                        f"Module '{module}' is not allowed",
                        line=node.lineno,
                        col=node.col_offset,
                    )
                )
            elif module not in ALLOWED_MODULES:
                self.errors.append(
                    ValidationError(
                        f"Module '{module}' is not in the allowlist",
                        line=node.lineno,
                        col=node.col_offset,
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check for blocked builtin calls."""
        if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_BUILTINS:
            self.errors.append(
                ValidationError(
                    f"Builtin '{node.func.id}()' is not allowed",
                    line=node.lineno,
                    col=node.col_offset,
                )
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Check for access to blocked module attributes."""
        # Check for access to blocked modules via attribute
        if isinstance(node.value, ast.Name) and node.value.id in BLOCKED_MODULES:
            self.errors.append(
                ValidationError(
                    f"Access to '{node.value.id}' module is not allowed",
                    line=node.lineno,
                    col=node.col_offset,
                )
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function definitions, looking for main()."""
        if node.name == "main":
            self.has_main_function = True
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Block async function definitions."""
        self.errors.append(
            ValidationError(
                "Async functions are not allowed",
                line=node.lineno,
                col=node.col_offset,
            )
        )
        self.generic_visit(node)

    def visit_Await(self, node: ast.Await) -> None:
        """Block await expressions."""
        self.errors.append(
            ValidationError(
                "Await expressions are not allowed",
                line=node.lineno,
                col=node.col_offset,
            )
        )
        self.generic_visit(node)


def validate_restricted_python(code: str) -> None:
    """
    Validate that Python code follows security restrictions.

    Args:
        code: The Python source code to validate.

    Raises:
        ValidationError: If the code violates any security restrictions.
    """
    # Check for empty code
    if not code or not code.strip():
        raise ValidationError("Implementation code cannot be empty")

    # Check code length (prevent DOS)
    if len(code) > 50_000:  # 50KB limit
        raise ValidationError("Implementation code is too long (max 50KB)")

    # Check for blocked patterns via regex
    for pattern, message in BLOCKED_PATTERNS:
        if re.search(pattern, code):
            # Find the line number
            for i, line in enumerate(code.split("\n"), 1):
                if re.search(pattern, line):
                    raise ValidationError(message, line=i)
            raise ValidationError(message)

    # Parse the AST
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValidationError(f"Invalid Python syntax: {e.msg}", line=e.lineno) from e

    # Run the AST validator
    validator = RestrictedPythonValidator()
    validator.visit(tree)

    # Check for errors
    if validator.errors:
        # Raise the first error
        raise validator.errors[0]

    # Check for main function
    if not validator.has_main_function:
        raise ValidationError("Implementation must define a 'main' function")


def get_allowed_modules() -> list[str]:
    """Return list of allowed modules for documentation."""
    return sorted(ALLOWED_MODULES)


def get_blocked_builtins() -> list[str]:
    """Return list of blocked builtins for documentation."""
    return sorted(BLOCKED_BUILTINS)
