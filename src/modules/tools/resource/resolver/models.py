"""
Resource models.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ResourceType(Enum):

    APPLICATION = "application"

    FOLDER = "folder"

    URL = "url"

    FILE = "file"

    DRIVE = "drive"

    UNKNOWN = "unknown"


@dataclass(slots=True)
class Resource:

    type: ResourceType

    value: str
