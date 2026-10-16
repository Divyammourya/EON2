from dataclasses import dataclass


@dataclass(slots=True)
class Capability:
    name: str
    description: str
