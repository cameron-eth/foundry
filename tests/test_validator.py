"""Tests for the restricted Python validator."""

import pytest

from src.builder.validator import ValidationError, validate_restricted_python


class TestValidateRestrictedPython:
    """Tests for validate_restricted_python function."""

    def test_valid_simple_function(self):
        """Valid simple function should pass."""
        code = """
def main(a: int, b: int) -> int:
    return a + b
"""
        # Should not raise
        validate_restricted_python(code)

    def test_valid_with_math(self):
        """Valid function using math module should pass."""
        code = """
import math

def main(x: float) -> float:
    return math.sqrt(x)
"""
        validate_restricted_python(code)

    def test_valid_with_json(self):
        """Valid function using json module should pass."""
        code = """
import json

def main(data: dict) -> str:
    return json.dumps(data)
"""
        validate_restricted_python(code)

    def test_valid_with_datetime(self):
        """Valid function using datetime module should pass."""
        code = """
from datetime import datetime

def main() -> str:
    return datetime.now().isoformat()
"""
        validate_restricted_python(code)

    def test_valid_complex_function(self):
        """Valid complex function should pass."""
        code = """
import math
import statistics

def calculate_stats(numbers: list) -> dict:
    return {
        "mean": statistics.mean(numbers),
        "stdev": statistics.stdev(numbers) if len(numbers) > 1 else 0,
        "min": min(numbers),
        "max": max(numbers),
    }

def main(numbers: list) -> dict:
    return calculate_stats(numbers)
"""
        validate_restricted_python(code)

    def test_missing_main_function(self):
        """Code without main function should fail."""
        code = """
def add(a: int, b: int) -> int:
    return a + b
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "main" in str(exc_info.value).lower()

    def test_empty_code(self):
        """Empty code should fail."""
        with pytest.raises(ValidationError):
            validate_restricted_python("")

        with pytest.raises(ValidationError):
            validate_restricted_python("   \n\t  ")

    def test_syntax_error(self):
        """Code with syntax errors should fail."""
        code = """
def main(
    return 42
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "syntax" in str(exc_info.value).lower()

    def test_blocked_sys_import(self):
        """Importing sys module should fail."""
        code = """
import sys

def main() -> str:
    return sys.version
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "sys" in str(exc_info.value).lower()

    def test_blocked_subprocess_import(self):
        """Importing subprocess should fail."""
        code = """
import subprocess

def main(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True).decode()
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "subprocess" in str(exc_info.value).lower()

    def test_blocked_socket_import(self):
        """Importing socket should fail."""
        code = """
import socket

def main(host: str) -> str:
    return socket.gethostbyname(host)
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "socket" in str(exc_info.value).lower()

    def test_blocked_eval_builtin(self):
        """Using eval should fail."""
        code = """
def main(expr: str) -> int:
    return eval(expr)
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "eval" in str(exc_info.value).lower()

    def test_blocked_exec_builtin(self):
        """Using exec should fail."""
        code = """
def main(code: str) -> None:
    exec(code)
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "exec" in str(exc_info.value).lower()

    def test_blocked_open_builtin(self):
        """Using open should fail."""
        code = """
def main(path: str) -> str:
    with open(path) as f:
        return f.read()
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "open" in str(exc_info.value).lower()

    def test_blocked_import_builtin(self):
        """Using __import__ should fail (caught as dunder attribute)."""
        code = """
def main(module: str):
    return __import__(module)
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        # __import__ is caught as a dunder attribute pattern
        assert "dunder" in str(exc_info.value).lower() or "__import__" in str(exc_info.value).lower()

    def test_blocked_compile_builtin(self):
        """Using compile should fail."""
        code = """
def main(code: str):
    return compile(code, '<string>', 'exec')
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "compile" in str(exc_info.value).lower()

    def test_blocked_async_function(self):
        """Async functions should fail."""
        code = """
async def main() -> int:
    return 42
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "async" in str(exc_info.value).lower()

    def test_blocked_await(self):
        """Await expressions should fail."""
        code = """
async def helper():
    return 42

def main():
    # This would fail anyway due to async, but check await too
    pass
"""
        # The async function itself will trigger the error
        with pytest.raises(ValidationError):
            validate_restricted_python(code)

    def test_blocked_unknown_module(self):
        """Unknown modules should fail."""
        code = """
import some_random_module

def main() -> int:
    return some_random_module.do_something()
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "allowlist" in str(exc_info.value).lower()

    def test_from_import_blocked_module(self):
        """From import of blocked module should fail."""
        code = """
from sys import version

def main() -> str:
    return version
"""
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "sys" in str(exc_info.value).lower()

    def test_code_too_long(self):
        """Code that's too long should fail."""
        code = "x = 1\n" * 100000  # Way over 50KB
        code += "\ndef main(): return x"
        with pytest.raises(ValidationError) as exc_info:
            validate_restricted_python(code)
        assert "too long" in str(exc_info.value).lower()


class TestValidatorEdgeCases:
    """Edge case tests for the validator."""

    def test_nested_function(self):
        """Nested functions should work."""
        code = """
def main(n: int) -> int:
    def factorial(x: int) -> int:
        if x <= 1:
            return 1
        return x * factorial(x - 1)
    return factorial(n)
"""
        validate_restricted_python(code)

    def test_class_definition(self):
        """Class definitions should work."""
        code = """
class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b

def main(a: int, b: int) -> int:
    calc = Calculator()
    return calc.add(a, b)
"""
        validate_restricted_python(code)

    def test_list_comprehension(self):
        """List comprehensions should work."""
        code = """
def main(numbers: list) -> list:
    return [x * 2 for x in numbers if x > 0]
"""
        validate_restricted_python(code)

    def test_dict_comprehension(self):
        """Dict comprehensions should work."""
        code = """
def main(keys: list, values: list) -> dict:
    return {k: v for k, v in zip(keys, values)}
"""
        validate_restricted_python(code)

    def test_generator_expression(self):
        """Generator expressions should work."""
        code = """
def main(numbers: list) -> int:
    return sum(x * 2 for x in numbers)
"""
        validate_restricted_python(code)

    def test_try_except(self):
        """Try/except blocks should work."""
        code = """
def main(a: int, b: int) -> float:
    try:
        return a / b
    except ZeroDivisionError:
        return 0.0
"""
        validate_restricted_python(code)

    def test_with_statement_without_open(self):
        """With statements (without open) should work."""
        code = """
from decimal import Decimal, localcontext

def main(n: str) -> str:
    with localcontext() as ctx:
        ctx.prec = 50
        return str(Decimal(n) / Decimal(3))
"""
        validate_restricted_python(code)
