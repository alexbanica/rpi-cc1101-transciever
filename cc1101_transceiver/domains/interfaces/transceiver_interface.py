from __future__ import annotations

from typing import Protocol

from cc1101_transceiver.domains.entities.capture import CaptureFrame
from cc1101_transceiver.domains.entities.somfy_frame import EncodedSomfyFrame


class TransceiverInterface(Protocol):
    def capture(self, timeout: float, frames: int, frequency_hz: int) -> list[CaptureFrame]:
        ...

    def transmit(self, frame: EncodedSomfyFrame, frequency_hz: int) -> None:
        ...
