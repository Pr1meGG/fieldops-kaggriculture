from dataclasses import dataclass
from typing import Any

@dataclass
class Event:
    turn: int
    event_type: str
    details: dict
