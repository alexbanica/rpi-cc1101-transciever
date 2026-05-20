from __future__ import annotations

from pathlib import Path

from cc1101_transceiver.applications.services.somfy_rts_codec_service import SomfyRtsCodecService
from cc1101_transceiver.applications.services.somfy_rts_pulse_decode_service import SomfyRtsPulseDecodeService
from cc1101_transceiver.domains.entities.capture import Capture, CaptureFrame, DecodedFrame
from cc1101_transceiver.domains.interfaces.capture_repository_interface import CaptureRepositoryInterface
from cc1101_transceiver.shared.constants.defaults import PROTOCOL_SOMFY_RTS
from cc1101_transceiver.shared.exceptions import OperationalError


class DecodeService:
    def __init__(self, capture_repository: CaptureRepositoryInterface, codec: SomfyRtsCodecService):
        self.capture_repository = capture_repository
        self.codec = codec
        self.pulse_decoder = SomfyRtsPulseDecodeService()

    def decode(self, capture_path: Path) -> Capture:
        capture = self.capture_repository.read(capture_path)
        decoded_frames: list[CaptureFrame] = []
        for frame in capture.frames:
            decoded = frame.decoded
            raw_hex = frame.raw.get("obfuscated_frame_hex")
            raw = dict(frame.raw)
            if decoded is None and not isinstance(raw_hex, str):
                pulses = raw.get("pulse_durations_us")
                if isinstance(pulses, list):
                    raw_hex = self.pulse_decoder.decode_obfuscated_hex(pulses)
                    raw["obfuscated_frame_hex"] = raw_hex
            if decoded is None and isinstance(raw_hex, str):
                somfy = self.codec.decode_obfuscated_hex(raw_hex)
                decoded = DecodedFrame(
                    PROTOCOL_SOMFY_RTS,
                    somfy.address,
                    somfy.rolling_code,
                    somfy.command,
                    somfy.valid_checksum,
                )
            decoded_frames.append(CaptureFrame(frame.index, frame.captured_at, raw, decoded))
        result = Capture(capture.frequency_hz, capture.spi_bus, capture.spi_chip_select, decoded_frames)
        if not any(frame.decoded is not None for frame in result.frames):
            raise OperationalError("capture does not contain decodable Somfy RTS frame data")
        return result
