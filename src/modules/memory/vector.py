"""
Vector utilities.
"""

from __future__ import annotations

import math


def cosine_similarity(
    a: list[float],
    b: list[float],
    *,
    norm_a: float | None = None,
    norm_b: float | None = None,
) -> float:
    """
    Compute cosine similarity between two vectors.

    ``norm_a`` / ``norm_b`` let a caller that compares one vector against
    many others pass in a precomputed magnitude, so it isn't recomputed on
    every call (see ``SQLiteMemoryStore.search``). They are optional and
    default to being computed here, so existing call sites are unaffected.
    """

    if len(a) != len(b):
        raise ValueError("Vector dimensions do not match.")

    dot = sum(x * y for x, y in zip(a, b))

    if norm_a is None:
        norm_a = math.sqrt(sum(x * x for x in a))

    if norm_b is None:
        norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)
