from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    model: str = "turbo"
    device: str = "auto"
    language: str | None = None
    sample_rate: int = 16000
    first_window: float = 1.5
    interval: float = 1.0
    overlap: float = 2.0
    mutable_tail: float = 5.0
    max_window: float = 24.0
    max_backlog: float = 120.0

    def __post_init__(self):
        if self.device not in {"auto", "cuda", "cpu"}:
            raise ValueError("device must be auto, cuda or cpu")
        if self.sample_rate != 16000:
            raise ValueError("Whisper input must be 16 kHz")
        if not (0 < self.overlap < self.mutable_tail < self.max_window < self.max_backlog):
            raise ValueError("Invalid audio window configuration")
        if self.first_window <= 0 or self.interval <= 0:
            raise ValueError("Timing intervals must be positive")
