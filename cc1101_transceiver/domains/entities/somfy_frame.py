from __future__ import annotations

from dataclasses import dataclass

from cc1101_transceiver.domains.entities.somfy_command import SomfyCommand


@dataclass(frozen=True)
class EncodedSomfyFrame:
    command: SomfyCommand
    address: str
    rolling_code: int
    plain_frame: bytes
    obfuscated_frame: bytes
    frequency_hz: int

    @property
    def plain_hex(self) -> str:
        return self.plain_frame.hex()

    @property
    def obfuscated_hex(self) -> str:
        return self.obfuscated_frame.hex()


@dataclass(frozen=True)
class DecodedSomfyFrame:
    address: str
    rolling_code: int
    command: str
    valid_checksum: bool
    plain_frame: bytes
    obfuscated_frame: bytes

    @property
    def plain_hex(self) -> str:
        return self.plain_frame.hex()

    @property
    def obfuscated_hex(self) -> str:
        return self.obfuscated_frame.hex()
