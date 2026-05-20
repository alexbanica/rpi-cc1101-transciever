from __future__ import annotations

from dataclasses import dataclass, field

from cc1101_transceiver.shared.constants.defaults import DEFAULT_FREQUENCY_HZ, PROTOCOL_SOMFY_RTS


@dataclass(frozen=True)
class SomfyProfile:
    name: str | None
    address: str
    rolling_code: int
    frequency_hz: int = DEFAULT_FREQUENCY_HZ
    protocol: str = PROTOCOL_SOMFY_RTS
    source: dict[str, object] = field(default_factory=lambda: {"type": "manual"})

    def __post_init__(self):
        normalized = self.address.lower()
        if len(normalized) != 6:
            raise ValueError("profile address must be exactly 3 bytes of hexadecimal text")
        int(normalized, 16)
        if self.rolling_code < 0 or self.rolling_code > 0xFFFF:
            raise ValueError("rolling_code must fit in an unsigned 16-bit integer")
        object.__setattr__(self, "address", normalized)

    def with_rolling_code(self, rolling_code: int) -> "SomfyProfile":
        return SomfyProfile(
            name=self.name,
            address=self.address,
            rolling_code=rolling_code,
            frequency_hz=self.frequency_hz,
            protocol=self.protocol,
            source=dict(self.source),
        )
