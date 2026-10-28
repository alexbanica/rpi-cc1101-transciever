from __future__ import annotations

from pathlib import Path
from typing import Protocol

from cc1101_transceiver.domains.entities.capture import Capture


class CaptureRepositoryInterface(Protocol):
    def read(self, path: Path) -> Capture:
        ...

    def write(self, path: Path, capture: Capture) -> None:
        ...
