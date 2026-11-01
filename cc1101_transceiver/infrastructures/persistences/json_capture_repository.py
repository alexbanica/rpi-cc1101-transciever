from __future__ import annotations

import json
import os
from pathlib import Path

from cc1101_transceiver.domains.entities.capture import Capture, CaptureFrame, DecodedFrame
from cc1101_transceiver.shared.constants.defaults import CAPTURE_FORMAT, PROTOCOL_SOMFY_RTS
from cc1101_transceiver.shared.exceptions import InvalidInputError


class JsonCaptureRepository:
    def read(self, path: Path) -> Capture:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("format") != CAPTURE_FORMAT:
                raise InvalidInputError(f"unsupported capture format in {path}")
            frames = [self._frame_from_dict(item) for item in data["frames"]]
            return Capture(
                frequency_hz=int(data["frequency_hz"]),
                spi_bus=int(data["spi_bus"]),
                spi_chip_select=int(data["spi_chip_select"]),
                frames=frames,
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            if isinstance(exc, InvalidInputError):
                raise
            raise InvalidInputError(f"invalid capture JSON {path}: {exc}") from exc

    def write(self, path: Path, capture: Capture) -> None:
        data = {
            "format": CAPTURE_FORMAT,
            "frequency_hz": capture.frequency_hz,
            "spi_bus": capture.spi_bus,
            "spi_chip_select": capture.spi_chip_select,
            "frames": [self._frame_to_dict(frame) for frame in capture.frames],
        }
        self._atomic_write_json(path, data)

    def _frame_from_dict(self, data: dict[str, object]) -> CaptureFrame:
        decoded_data = data.get("decoded")
        decoded = None
        if decoded_data is not None:
            if not isinstance(decoded_data, dict):
                raise InvalidInputError("capture decoded frame must be an object")
            if decoded_data.get("protocol") != PROTOCOL_SOMFY_RTS:
                raise InvalidInputError("capture decoded frame protocol must be somfy-rts")
            decoded = DecodedFrame(
                protocol=str(decoded_data["protocol"]),
                address=str(decoded_data["address"]).lower(),
                rolling_code=int(decoded_data["rolling_code"]),
                command=str(decoded_data["command"]),
                valid_checksum=bool(decoded_data["valid_checksum"]),
            )
        raw = data.get("raw", {})
        if not isinstance(raw, dict):
            raise InvalidInputError("capture raw field must be an object")
        return CaptureFrame(index=int(data["index"]), captured_at=str(data["captured_at"]), raw=raw, decoded=decoded)

    def _frame_to_dict(self, frame: CaptureFrame) -> dict[str, object]:
        decoded = None
        if frame.decoded is not None:
            decoded = {
                "protocol": frame.decoded.protocol,
                "address": frame.decoded.address.lower(),
                "rolling_code": frame.decoded.rolling_code,
                "command": frame.decoded.command,
                "valid_checksum": frame.decoded.valid_checksum,
            }
        return {
            "index": frame.index,
            "captured_at": frame.captured_at,
            "raw": frame.raw,
            "decoded": decoded,
        }

    def _atomic_write_json(self, path: Path, data: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.tmp")
        tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp_path, path)
