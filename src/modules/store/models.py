"""
Store models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class StoreDecision:
    """
    Decision whether something should be stored.
    """

    should_store: bool

    content: str = ""

    reason: str = ""
