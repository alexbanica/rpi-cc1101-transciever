from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import time
from typing import Iterator

from cc1101_transceiver.applications.services.somfy_rts_codec_service import SomfyRtsCodecService
from cc1101_transceiver.applications.services.somfy_rts_pulse_decode_service import SomfyRtsPulseDecodeService
from cc1101_transceiver.applications.services.somfy_rts_pulse_encode_service import SomfyRtsPulseEncodeService
from cc1101_transceiver.domains.entities.capture import CaptureFrame
from cc1101_transceiver.domains.entities.capture import DecodedFrame
from cc1101_transceiver.domains.entities.somfy_frame import EncodedSomfyFrame
from cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture import GpioPulseCapture
from cc1101_transceiver.infrastructures.cc1101.gpio_pulse_transmitter import GpioPulseTransmitter
from cc1101_transceiver.shared.constants.defaults import DEFAULT_SYMBOL_RATE, DEFAULT_TX_GPIO_BCM, PROTOCOL_SOMFY_RTS
from cc1101_transceiver.shared.exceptions import HardwareAccessError


class Cc1101TransceiverAdapter:
    def __init__(
        self,
        spi_bus: int,
        spi_chip_select: int,
        rx_gpio: int | None = None,
        tx_gpio: int = DEFAULT_TX_GPIO_BCM,
        symbol_rate: int = DEFAULT_SYMBOL_RATE,
    ):
        self.spi_bus = spi_bus
        self.spi_chip_select = spi_chip_select
        self.rx_gpio = rx_gpio
        self.tx_gpio = tx_gpio
        self.symbol_rate = symbol_rate
        self.codec = SomfyRtsCodecService()
        self.pulse_decoder = SomfyRtsPulseDecodeService()

    def capture(self, timeout: float, frames: int, frequency_hz: int) -> list[CaptureFrame]:
        if self.rx_gpio is None:
            raise HardwareAccessError(
                "live capture requires --rx-gpio for GDO0-backed raw timing; SPI-only capture is not supported"
            )
        if frames < 1:
            return []

        deadline = time.monotonic() + max(0.0, timeout)
        captured: list[CaptureFrame] = []
        with self._receive_session(frequency_hz):
            pulse_capture = GpioPulseCapture(self.rx_gpio)
            remaining = max(0.0, deadline - time.monotonic())
            runs = pulse_capture.capture(remaining) if remaining else []
            for run in runs:
                try:
                    candidates = list(self.pulse_decoder.iter_candidates(run))
                except ValueError:
                    continue
                for candidate in candidates:
                    try:
                        somfy = self.codec.decode_obfuscated_hex(candidate.obfuscated_hex)
                    except ValueError:
                        continue
                    if somfy.valid_checksum is not True:
                        continue
                    captured.append(
                        CaptureFrame(
                            index=len(captured),
                            captured_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                            raw={
                                "capture_method": "gdo0-gpio-pulse",
                                "gdo": "GDO0",
                                "rx_gpio": self.rx_gpio,
                                "gpio_numbering": "bcm",
                                "pulse_durations_us": list(run[candidate.start_index:candidate.end_index_exclusive]),
                                "obfuscated_frame_hex": candidate.obfuscated_hex,
                            },
                            decoded=DecodedFrame(
                                PROTOCOL_SOMFY_RTS, somfy.address, somfy.rolling_code,
                                somfy.command, somfy.valid_checksum,
                            ),
                        )
                    )
                    if len(captured) >= frames:
                        return captured
        return captured

    def transmit(self, frame: EncodedSomfyFrame, frequency_hz: int) -> None:
        pulses = SomfyRtsPulseEncodeService().encode_obfuscated_hex(frame.obfuscated_hex)
        with self._transmit_session(frequency_hz):
            pulse_transmitter = GpioPulseTransmitter(self.tx_gpio)
            pulse_transmitter.transmit(pulses)

    @contextmanager
    def _transmit_session(self, frequency_hz: int) -> Iterator[object]:
        try:
            import cc1101  # type: ignore[import-not-found]
        except ImportError as exc:
            raise HardwareAccessError("missing Python dependency 'cc1101'; install requirements on the Pi") from exc

        transceiver_class = getattr(cc1101, "CC1101", None)
        if transceiver_class is None:
            raise HardwareAccessError("installed cc1101 package does not expose CC1101")

        try:
            with transceiver_class() as transceiver:
                self._configure_transmit(cc1101, transceiver, frequency_hz)
                async_session = getattr(transceiver, "asynchronous_transmission", None)
                if not callable(async_session):
                    raise HardwareAccessError("CC1101 asynchronous TX API is unavailable")
                with async_session():
                    yield transceiver
        except HardwareAccessError:
            raise
        except (OSError, RuntimeError, PermissionError, AttributeError, TypeError) as exc:
            raise HardwareAccessError(f"CC1101 transmit setup failed: {exc}") from exc

    @contextmanager
    def _receive_session(self, frequency_hz: int) -> Iterator[object]:
        try:
            import cc1101  # type: ignore[import-not-found]
        except ImportError as exc:
            raise HardwareAccessError("missing Python dependency 'cc1101'; install requirements on the Pi") from exc

        transceiver_class = getattr(cc1101, "CC1101", None)
        if transceiver_class is None:
            raise HardwareAccessError("installed cc1101 package does not expose CC1101")

        try:
            with transceiver_class() as transceiver:
                self._configure_receive(cc1101, transceiver, frequency_hz)
                yield transceiver
        except HardwareAccessError:
            raise
        except (OSError, RuntimeError, PermissionError, AttributeError, TypeError) as exc:
            raise HardwareAccessError(f"CC1101 receive setup failed: {exc}") from exc

    def _configure_receive(self, cc1101_module: object, transceiver: object, frequency_hz: int) -> None:
        self._require_call(transceiver, "set_base_frequency_hertz", frequency_hz)
        self._require_call(transceiver, "set_symbol_rate_baud", DEFAULT_SYMBOL_RATE)
        modulation_format = getattr(getattr(cc1101_module, "ModulationFormat", object), "ASK_OOK", None)
        if modulation_format is None:
            raise HardwareAccessError("CC1101 ASK/OOK modulation is unavailable")
        self._require_call(transceiver, "_set_modulation_format", modulation_format)
        packet_length_mode = getattr(getattr(cc1101_module, "PacketLengthMode", object), "FIXED", None)
        if packet_length_mode is None:
            raise HardwareAccessError("CC1101 fixed packet length mode is unavailable")
        self._require_call(transceiver, "set_packet_length_mode", packet_length_mode)
        sync_mode = getattr(getattr(cc1101_module, "SyncMode", object), "NO_PREAMBLE_AND_SYNC_WORD", None)
        if sync_mode is None:
            raise HardwareAccessError("CC1101 no-sync mode is unavailable")
        self._require_call(transceiver, "set_sync_mode", sync_mode)
        transceive_mode = getattr(getattr(cc1101_module, "_TransceiveMode", object), "ASYNCHRONOUS_SERIAL", None)
        if transceive_mode is None:
            raise HardwareAccessError("CC1101 asynchronous serial RX mode is unavailable")
        self._require_call(transceiver, "_set_transceive_mode", transceive_mode)
        addresses = getattr(cc1101_module, "ConfigurationRegisterAddress", None)
        if addresses is None:
            raise HardwareAccessError("CC1101 register address API is unavailable")
        iocfg, pktctrl, mdmcfg = (getattr(addresses, name, None) for name in ("IOCFG0", "PKTCTRL0", "MDMCFG2"))
        if any(address is None for address in (iocfg, pktctrl, mdmcfg)):
            raise HardwareAccessError("CC1101 required RX register addresses are unavailable")
        self._require_call(transceiver, "_write_burst", iocfg, [0x0D])
        self._set_register_bits(transceiver, pktctrl, 0x30, 0x30)
        self._set_register_bits(transceiver, mdmcfg, 0x7F, 0x30)
        for address, mask, expected, label in ((iocfg, 0xFF, 0x0D, "IOCFG0"), (pktctrl, 0x30, 0x30, "PKTCTRL0"), (mdmcfg, 0x7F, 0x30, "MDMCFG2")):
            value = self._read_register(transceiver, address)
            if value & mask != expected:
                raise HardwareAccessError(f"CC1101 {label} readback mismatch")
        self._require_call(transceiver, "_enable_receive_mode")

    def _read_register(self, transceiver: object, address: object) -> int:
        value = self._require_call(transceiver, "_read_single_byte", address)
        if not isinstance(value, int) or not 0 <= value <= 255:
            raise HardwareAccessError("CC1101 register read returned an invalid byte")
        return value

    def _set_register_bits(self, transceiver: object, address: object, mask: int, expected: int) -> None:
        value = self._read_register(transceiver, address)
        self._require_call(transceiver, "_write_burst", address, [(value & ~mask) | expected])

    def _require_call(self, target: object, name: str, *args: object) -> object:
        method = getattr(target, name, None)
        if not callable(method):
            raise HardwareAccessError(f"CC1101 required API {name} is unavailable")
        return method(*args)

    def _configure_transmit(self, cc1101_module: object, transceiver: object, frequency_hz: int) -> None:
        self._call_if_present(transceiver, "set_base_frequency_hertz", frequency_hz)
        self._call_if_present(transceiver, "set_symbol_rate_baud", self.symbol_rate)
        modulation_format = getattr(getattr(cc1101_module, "ModulationFormat", object), "ASK_OOK", None)
        if modulation_format is not None:
            self._call_if_present(transceiver, "_set_modulation_format", modulation_format)
        packet_length_mode = getattr(getattr(cc1101_module, "PacketLengthMode", object), "FIXED", None)
        if packet_length_mode is not None:
            self._call_if_present(transceiver, "set_packet_length_mode", packet_length_mode)
        sync_mode = getattr(getattr(cc1101_module, "SyncMode", object), "NO_PREAMBLE_AND_SYNC_WORD", None)
        if sync_mode is not None:
            self._call_if_present(transceiver, "set_sync_mode", sync_mode)
        transceive_mode = getattr(getattr(cc1101_module, "_TransceiveMode", object), "ASYNCHRONOUS_SERIAL", None)
        if transceive_mode is None:
            raise HardwareAccessError("CC1101 asynchronous serial TX mode is unavailable")
        set_transceive_mode = getattr(transceiver, "_set_transceive_mode", None)
        if not callable(set_transceive_mode):
            raise HardwareAccessError("CC1101 asynchronous serial TX mode cannot be selected")
        set_transceive_mode(transceive_mode)

    def _call_if_present(self, target: object, name: str, *args: object) -> None:
        method = getattr(target, name, None)
        if callable(method):
            method(*args)
