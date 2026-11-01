from __future__ import annotations

from pathlib import Path

from cc1101_transceiver.domains.entities.somfy_profile import SomfyProfile
from cc1101_transceiver.domains.interfaces.profile_repository_interface import ProfileRepositoryInterface
from cc1101_transceiver.shared.constants.defaults import DEFAULT_FREQUENCY_HZ


class ProfileInitializationService:
    def __init__(self, profile_repository: ProfileRepositoryInterface):
        self.profile_repository = profile_repository

    def initialize(
        self,
        profile_path: Path,
        address: str,
        rolling_code: int,
        name: str | None,
        frequency_hz: int = DEFAULT_FREQUENCY_HZ,
    ) -> SomfyProfile:
        profile = SomfyProfile(
            name=name,
            address=address,
            rolling_code=rolling_code,
            frequency_hz=frequency_hz,
            source={"type": "manual"},
        )
        self.profile_repository.write(profile_path, profile)
        return profile
