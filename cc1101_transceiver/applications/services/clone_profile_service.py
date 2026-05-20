from __future__ import annotations

from pathlib import Path

from cc1101_transceiver.domains.entities.somfy_profile import SomfyProfile
from cc1101_transceiver.domains.interfaces.capture_repository_interface import CaptureRepositoryInterface
from cc1101_transceiver.domains.interfaces.profile_repository_interface import ProfileRepositoryInterface
from cc1101_transceiver.shared.constants.defaults import PROTOCOL_SOMFY_RTS
from cc1101_transceiver.shared.exceptions import InvalidInputError


class CloneProfileService:
    def __init__(
        self,
        capture_repository: CaptureRepositoryInterface,
        profile_repository: ProfileRepositoryInterface,
    ):
        self.capture_repository = capture_repository
        self.profile_repository = profile_repository

    def clone(self, capture_path: Path, profile_path: Path, name: str | None) -> SomfyProfile:
        capture = self.capture_repository.read(capture_path)
        decoded = next(
            (
                frame.decoded
                for frame in capture.frames
                if frame.decoded is not None
                and frame.decoded.protocol == PROTOCOL_SOMFY_RTS
                and frame.decoded.valid_checksum
            ),
            None,
        )
        if decoded is None:
            raise InvalidInputError("capture does not contain a valid decoded Somfy RTS frame")

        profile = SomfyProfile(
            name=name,
            address=decoded.address,
            rolling_code=decoded.rolling_code + 1,
            frequency_hz=capture.frequency_hz,
            source={"type": "capture", "capture_file": str(capture_path)},
        )
        self.profile_repository.write(profile_path, profile)
        return profile
