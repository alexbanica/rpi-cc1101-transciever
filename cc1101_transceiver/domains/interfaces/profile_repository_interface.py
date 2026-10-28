from __future__ import annotations

from pathlib import Path
from typing import Protocol

from cc1101_transceiver.domains.entities.somfy_profile import SomfyProfile


class ProfileRepositoryInterface(Protocol):
    def read(self, path: Path) -> SomfyProfile:
        ...

    def write(self, path: Path, profile: SomfyProfile) -> None:
        ...
