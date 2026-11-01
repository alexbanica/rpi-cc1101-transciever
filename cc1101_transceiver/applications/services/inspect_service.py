from __future__ import annotations

from pathlib import Path

from cc1101_transceiver.domains.interfaces.capture_repository_interface import CaptureRepositoryInterface
from cc1101_transceiver.domains.interfaces.profile_repository_interface import ProfileRepositoryInterface
from cc1101_transceiver.shared.constants.defaults import CAPTURE_FORMAT, PROFILE_FORMAT
from cc1101_transceiver.shared.exceptions import InvalidInputError


class InspectService:
    def __init__(
        self,
        capture_repository: CaptureRepositoryInterface,
        profile_repository: ProfileRepositoryInterface,
    ) -> None:
        self._capture_repository = capture_repository
        self._profile_repository = profile_repository

    def inspect(self, path: Path) -> dict[str, object]:
        text = path.read_text(encoding="utf-8")
        if f'"format": "{CAPTURE_FORMAT}"' in text or f'"format":"{CAPTURE_FORMAT}"' in text:
            capture = self._capture_repository.read(path)
            return {
                "type": "capture",
                "frequency_hz": capture.frequency_hz,
                "frames": len(capture.frames),
                "decoded_frames": sum(1 for frame in capture.frames if frame.decoded is not None),
            }
        if f'"format": "{PROFILE_FORMAT}"' in text or f'"format":"{PROFILE_FORMAT}"' in text:
            profile = self._profile_repository.read(path)
            return {
                "type": "profile",
                "name": profile.name,
                "address": profile.address,
                "rolling_code": profile.rolling_code,
                "frequency_hz": profile.frequency_hz,
            }
        raise InvalidInputError(f"unsupported JSON file: {path}")
