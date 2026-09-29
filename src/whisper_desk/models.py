from dataclasses import dataclass
from enum import Enum


class State(str, Enum):
    LOADING = "loading"
    READY = "ready"
    STARTING = "starting"
    RECORDING = "recording"
    FINALIZING = "finalizing"
    ERROR = "error"
    CLOSED = "closed"


@dataclass(frozen=True)
class Word:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Event:
    kind: str
    value: object
