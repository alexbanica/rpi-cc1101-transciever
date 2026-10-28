from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cc1101_transceiver.domains.entities.capture import Capture, CaptureFrame
from cc1101_transceiver.domains.interfaces.capture_repository_interface import CaptureRepositoryInterface
from cc1101_transceiver.domains.interfaces.transceiver_interface import TransceiverInterface
from cc1101_transceiver.shared.exceptions import OperationalError


class CaptureService:
    def __init__(
        self,
        transceiver: TransceiverInterface,
        capture_repository: CaptureRepositoryInterface,
    ):
        self.transceiver = transceiver
        self.capture_repository = capture_repository

    def capture(
        self,
        out_file: Path,
        timeout: float,
        frames: int,
        frequency_hz: int,
        spi_bus: int,
        spi_chip_select: int,
    ) -> Capture:
        captured = self.transceiver.capture(timeout, frames, frequency_hz)
        if not captured:
            raise OperationalError("no capture frames were obtained")
        normalized = [
            CaptureFrame(
                index=index,
                captured_at=frame.captured_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                raw=frame.raw,
                decoded=frame.decoded,
            )
            for index, frame in enumerate(captured)
        ]
        capture = Capture(frequency_hz, spi_bus, spi_chip_select, normalized)
        self.capture_repository.write(out_file, capture)
        return capture
