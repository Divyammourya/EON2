"""
Identity Profile.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class IdentityProfile:
    name: str
    creator: str
    version: str
    description: str
    location: str
    company: str | None = None
