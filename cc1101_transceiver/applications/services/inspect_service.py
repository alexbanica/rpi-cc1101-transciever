from __future__ import annotations

from pathlib import Path

from cc1101_transceiver.infrastructures.persistences.json_capture_repository import JsonCaptureRepository
from cc1101_transceiver.infrastructures.persistences.json_profile_repository import JsonProfileRepository
from cc1101_transceiver.shared.constants.defaults import CAPTURE_FORMAT, PROFILE_FORMAT
from cc1101_transceiver.shared.exceptions import InvalidInputError


class InspectService:
    def inspect(self, path: Path) -> dict[str, object]:
        text = path.read_text(encoding="utf-8")
        if f'"format": "{CAPTURE_FORMAT}"' in text or f'"format":"{CAPTURE_FORMAT}"' in text:
            capture = JsonCaptureRepository().read(path)
            return {
                "type": "capture",
                "frequency_hz": capture.frequency_hz,
                "frames": len(capture.frames),
                "decoded_frames": sum(1 for frame in capture.frames if frame.decoded is not None),
            }
        if f'"format": "{PROFILE_FORMAT}"' in text or f'"format":"{PROFILE_FORMAT}"' in text:
            profile = JsonProfileRepository().read(path)
            return {
                "type": "profile",
                "name": profile.name,
                "address": profile.address,
                "rolling_code": profile.rolling_code,
                "frequency_hz": profile.frequency_hz,
            }
        raise InvalidInputError(f"unsupported JSON file: {path}")
