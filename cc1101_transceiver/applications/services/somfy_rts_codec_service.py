from __future__ import annotations

from cc1101_transceiver.domains.entities.somfy_command import SomfyCommand
from cc1101_transceiver.domains.entities.somfy_frame import DecodedSomfyFrame, EncodedSomfyFrame
from cc1101_transceiver.domains.entities.somfy_profile import SomfyProfile


class SomfyRtsCodecService:
    encryption_key = 0xA7

    def encode(self, profile: SomfyProfile, command: SomfyCommand) -> EncodedSomfyFrame:
        address_bytes = bytes.fromhex(profile.address)
        frame = bytearray(
            [
                self.encryption_key,
                command.control_nibble << 4,
                (profile.rolling_code >> 8) & 0xFF,
                profile.rolling_code & 0xFF,
                address_bytes[2],
                address_bytes[1],
                address_bytes[0],
            ]
        )
        frame[1] |= self.calculate_checksum(frame)
        plain = bytes(frame)
        obfuscated = self.obfuscate(plain)
        return EncodedSomfyFrame(command, profile.address, profile.rolling_code, plain, obfuscated, profile.frequency_hz)

    def decode_obfuscated_hex(self, value: str) -> DecodedSomfyFrame:
        obfuscated = bytes.fromhex(value)
        if len(obfuscated) != 7:
            raise ValueError("Somfy RTS frame must be exactly 7 bytes")
        plain = self.deobfuscate(obfuscated)
        command = self._command_from_control_nibble((plain[1] >> 4) & 0x0F)
        rolling_code = (plain[2] << 8) | plain[3]
        address = bytes([plain[6], plain[5], plain[4]]).hex()
        return DecodedSomfyFrame(
            address=address,
            rolling_code=rolling_code,
            command=command.label,
            valid_checksum=self.is_checksum_valid(plain),
            plain_frame=plain,
            obfuscated_frame=obfuscated,
        )

    def calculate_checksum(self, plain_frame_with_zeroed_checksum: bytes | bytearray) -> int:
        checksum = 0
        frame = bytearray(plain_frame_with_zeroed_checksum)
        frame[1] &= 0xF0
        for byte in frame:
            checksum ^= byte
            checksum ^= byte >> 4
        return checksum & 0x0F

    def is_checksum_valid(self, plain_frame: bytes | bytearray) -> bool:
        expected = self.calculate_checksum(plain_frame)
        return (plain_frame[1] & 0x0F) == expected

    def obfuscate(self, plain_frame: bytes | bytearray) -> bytes:
        if len(plain_frame) != 7:
            raise ValueError("Somfy RTS frame must be exactly 7 bytes")
        obfuscated = bytearray(plain_frame)
        for index in range(1, len(obfuscated)):
            obfuscated[index] ^= obfuscated[index - 1]
        return bytes(obfuscated)

    def deobfuscate(self, obfuscated_frame: bytes | bytearray) -> bytes:
        if len(obfuscated_frame) != 7:
            raise ValueError("Somfy RTS frame must be exactly 7 bytes")
        plain = bytearray(obfuscated_frame)
        for index in range(len(plain) - 1, 0, -1):
            plain[index] ^= plain[index - 1]
        return bytes(plain)

    def _command_from_control_nibble(self, control_nibble: int) -> SomfyCommand:
        for command in SomfyCommand:
            if command.control_nibble == control_nibble:
                return command
        raise ValueError(f"unsupported Somfy RTS control nibble: {control_nibble}")
