"""Calculator: exact arithmetic, so the model never has to guess a number.

Why this exists
---------------
A 3B model cannot do arithmetic reliably. Ask it "what's 18% of 4500" and
it will produce a confident, wrong number. Arithmetic has exactly one
right answer and it is trivially computable, so EON should never ask the
model for it.

This module recognises an arithmetic question in a message, evaluates it
with Python's own parser, and returns the answer as a sentence. Anything
it doesn't recognise returns ``None`` and the message falls through to the
normal chat path.

Safety
------
Nothing here uses ``eval``. The expression is parsed with ``ast`` and only
a whitelist of node types is walked, so no attribute access, call, name
lookup or import can reach the interpreter. Exponents are capped, since
``9 ** 9 ** 9`` is a denial-of-service you can type by accident.

Requires: Python 3.12+
"""

from __future__ import annotations

import ast
import math
import operator
import re

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPERATORS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# "9 ** 9 ** 9" is huge and slow. Nobody asking a voice assistant for
# arithmetic means anything near this, so refuse rather than compute it.
_MAX_EXPONENT = 100

# A candidate must be nothing but digits, spaces and operators — this is
# what stops prose like "10 km in miles" being handed to the evaluator.
_ARITHMETIC_ONLY = re.compile(r"^[\d\s+\-*/%().]+$")
_HAS_OPERATOR = re.compile(r"[+\-*/%]")
_HAS_DIGIT = re.compile(r"\d")

_PERCENT_OF = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:%|percent)\s*of\s*(-?\d+(?:\.\d+)?)",
    re.I,
)

_LEADING_WAKE = re.compile(r"^\s*(?:hey\s+)?eon[,:\s]+", re.I)

_FILLER = re.compile(
    r"^\s*(?:what(?:'s| is)|whats|how much is|how many is|calculate|compute|"
    r"evaluate|solve|work out|tell me|give me|the answer to)\s+",
    re.I,
)

_SPOKEN_OPERATORS = (
    (r"\bplus\b", "+"),
    (r"\bminus\b", "-"),
    (r"\bmultiplied by\b", "*"),
    (r"\btimes\b", "*"),
    (r"\bdivided by\b", "/"),
    (r"\bover\b", "/"),
    (r"\bmodulo\b", "%"),
    (r"\bto the power of\b", "**"),
)


def format_number(value: float) -> str:
    """Renders a result without trailing zeros or thousands separators."""
    if not math.isfinite(value):
        return "undefined"

    if value == int(value) and abs(value) < 1e15:
        return str(int(value))

    return f"{value:.6f}".rstrip("0").rstrip(".")


def _evaluate_node(node: ast.AST) -> float:
    """Walks a whitelisted arithmetic tree. Raises on anything else."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise TypeError("only numbers are allowed")
        return node.value

    if isinstance(node, ast.UnaryOp):
        unary = _UNARY_OPERATORS.get(type(node.op))
        if unary is None:
            raise TypeError("unsupported unary operator")
        return unary(_evaluate_node(node.operand))

    if isinstance(node, ast.BinOp):
        binary = _BINARY_OPERATORS.get(type(node.op))
        if binary is None:
            raise TypeError("unsupported operator")

        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)

        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise ValueError("exponent too large")

        return binary(left, right)

    raise TypeError("unsupported expression")


def safe_evaluate(expression: str) -> float | None:
    """Evaluates a pure arithmetic expression, or returns None.

    Never raises: a malformed or disallowed expression is simply not
    something this module can answer.
    """
    if len(expression) > 200:
        return None

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return None

    try:
        return float(_evaluate_node(tree.body))
    except (TypeError, ValueError, ZeroDivisionError, OverflowError):
        return None


def _strip_question_words(text: str) -> str:
    """Removes the wake word and any leading "what is ..." phrasing."""
    candidate = _LEADING_WAKE.sub("", text.strip())

    previous = None
    while previous != candidate:
        previous = candidate
        candidate = _FILLER.sub("", candidate)

    return candidate.strip().strip("?.!=").strip()


def _to_expression(text: str) -> str | None:
    """Turns a spoken arithmetic question into an expression, or None."""
    candidate = _strip_question_words(text)

    for pattern, replacement in _SPOKEN_OPERATORS:
        candidate = re.sub(pattern, replacement, candidate, flags=re.I)

    # "3 x 4" — only when standing alone, so words containing x survive.
    candidate = re.sub(r"\s+x\s+", " * ", candidate)

    if not _ARITHMETIC_ONLY.match(candidate):
        return None
    if not _HAS_DIGIT.search(candidate):
        return None
    if not _HAS_OPERATOR.search(candidate):
        return None

    return candidate


def answer(text: str) -> str | None:
    """Answers an arithmetic question in ``text``, or returns None.

    Handles percentages first, since "18% of 4500" is not valid
    arithmetic syntax and would otherwise be rejected.
    """
    percentage = _PERCENT_OF.search(text)

    if percentage:
        percent = float(percentage.group(1))
        whole = float(percentage.group(2))
        result = percent / 100 * whole
        return (
            f"{format_number(percent)}% of {format_number(whole)} "
            f"is {format_number(result)}."
        )

    expression = _to_expression(text)

    if expression is None:
        return None

    value = safe_evaluate(expression)

    if value is None:
        return None

    return f"{expression} = {format_number(value)}"
