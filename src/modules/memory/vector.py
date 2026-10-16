"""
Vector utilities.
"""

from __future__ import annotations

import math


def cosine_similarity(
    a: list[float],
    b: list[float],
) -> float:
    """
    Compute cosine similarity between two vectors.
    """

    if len(a) != len(b):
        raise ValueError("Vector dimensions do not match.")

    dot = sum(x * y for x, y in zip(a, b))

    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)
