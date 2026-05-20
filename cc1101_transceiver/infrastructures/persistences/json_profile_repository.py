from __future__ import annotations

import json
import os
from pathlib import Path

from cc1101_transceiver.domains.entities.somfy_profile import SomfyProfile
from cc1101_transceiver.shared.constants.defaults import PROFILE_FORMAT, PROTOCOL_SOMFY_RTS
from cc1101_transceiver.shared.exceptions import InvalidInputError


class JsonProfileRepository:
    def read(self, path: Path) -> SomfyProfile:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("format") != PROFILE_FORMAT:
                raise InvalidInputError(f"unsupported profile format in {path}")
            if data.get("protocol") != PROTOCOL_SOMFY_RTS:
                raise InvalidInputError(f"unsupported profile protocol in {path}")
            rolling_code = data.get("rolling_code")
            if not isinstance(rolling_code, int):
                raise InvalidInputError("profile rolling_code must be an integer")
            return SomfyProfile(
                name=data.get("name"),
                address=str(data["address"]),
                rolling_code=rolling_code,
                frequency_hz=int(data["frequency_hz"]),
                source=dict(data.get("source", {"type": "manual"})),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            if isinstance(exc, InvalidInputError):
                raise
            raise InvalidInputError(f"invalid profile JSON {path}: {exc}") from exc

    def write(self, path: Path, profile: SomfyProfile) -> None:
        data = {
            "format": PROFILE_FORMAT,
            "name": profile.name,
            "protocol": profile.protocol,
            "frequency_hz": profile.frequency_hz,
            "address": profile.address,
            "rolling_code": profile.rolling_code,
            "source": profile.source,
        }
        self._atomic_write_json(path, data)

    def _atomic_write_json(self, path: Path, data: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.tmp")
        tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp_path, path)
