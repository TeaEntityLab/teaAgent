"""Core calculation module.

Contains top-level functions for arithmetic operations.
"""

TOP_LEVEL_CONSTANT = 42


def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b


def multiply(a: int, b: int) -> int:
    """Return the product of two integers."""
    return a * b


def factorial(n: int) -> int:
    """Compute n! recursively."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)


class Calculator:
    """A simple stateful calculator."""

    def __init__(self, initial: int = 0) -> None:
        self.value = initial

    def add(self, amount: int) -> int:
        self.value += amount
        return self.value

    def reset(self) -> None:
        self.value = 0
