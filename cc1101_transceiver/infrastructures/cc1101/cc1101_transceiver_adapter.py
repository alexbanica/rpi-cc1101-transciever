from __future__ import annotations

from cc1101_transceiver.domains.entities.capture import CaptureFrame
from cc1101_transceiver.domains.entities.somfy_frame import EncodedSomfyFrame
from cc1101_transceiver.shared.exceptions import HardwareAccessError


class Cc1101TransceiverAdapter:
    def __init__(self, spi_bus: int, spi_chip_select: int, rx_gpio: int | None = None):
        self.spi_bus = spi_bus
        self.spi_chip_select = spi_chip_select
        self.rx_gpio = rx_gpio

    def capture(self, timeout: float, frames: int, frequency_hz: int) -> list[CaptureFrame]:
        raise HardwareAccessError(
            "live capture requires GDO-backed raw timing support; current adapter does not fake capture success"
        )

    def transmit(self, frame: EncodedSomfyFrame, frequency_hz: int) -> None:
        try:
            import cc1101  # type: ignore[import-not-found]
        except ImportError as exc:
            raise HardwareAccessError("missing Python dependency 'cc1101'; install requirements on the Pi") from exc

        transceiver_class = getattr(cc1101, "CC1101", None)
        if transceiver_class is None:
            raise HardwareAccessError("installed cc1101 package does not expose CC1101")
        raise HardwareAccessError(
            "Somfy RTS raw timed transmission requires validated GDO0/asynchronous support; "
            "use --dry-run until wiring/API support is added"
        )
