from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecodedFrame:
    protocol: str
    address: str
    rolling_code: int
    command: str
    valid_checksum: bool


@dataclass(frozen=True)
class CaptureFrame:
    index: int
    captured_at: str
    raw: dict[str, object]
    decoded: DecodedFrame | None


@dataclass(frozen=True)
class Capture:
    frequency_hz: int
    spi_bus: int
    spi_chip_select: int
    frames: list[CaptureFrame]
