from __future__ import annotations

from enum import Enum


class SomfyCommand(Enum):
    MY = ("my", 0x1)
    UP = ("up", 0x2)
    DOWN = ("down", 0x4)
    PROG = ("prog", 0x8)

    def __init__(self, label: str, control_nibble: int):
        self.label = label
        self.control_nibble = control_nibble

    @classmethod
    def from_label(cls, label: str) -> "SomfyCommand":
        normalized = label.lower()
        for command in cls:
            if command.label == normalized:
                return command
        raise ValueError(f"unsupported Somfy RTS command: {label}")

    @classmethod
    def labels(cls) -> list[str]:
        return [command.label for command in cls]
