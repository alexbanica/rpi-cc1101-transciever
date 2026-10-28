from __future__ import annotations


class SomfyRtsPulseEncodeService:
    WAKEUP_HIGH_US = 9415
    WAKEUP_LOW_US = 89565
    HARDWARE_SYNC_US = 2416
    SOFTWARE_SYNC_HIGH_US = 4550
    HALF_SYMBOL_US = 604
    PAYLOAD_BYTES = 7

    FIRST_FRAME_HARDWARE_SYNCS = 2
    REPEATED_FRAME_HARDWARE_SYNCS = 7
    DEFAULT_TOTAL_FRAMES = 2

    def __init__(self, total_frames: int = DEFAULT_TOTAL_FRAMES):
        if total_frames < 1:
            raise ValueError("Somfy RTS pulse encoding requires at least one frame")
        self.total_frames = total_frames

    def encode_obfuscated_hex(self, obfuscated_hex: str) -> list[dict[str, int]]:
        payload = bytes.fromhex(obfuscated_hex)
        if len(payload) != self.PAYLOAD_BYTES:
            raise ValueError("Somfy RTS obfuscated frame must be exactly 7 bytes")

        pulses: list[dict[str, int]] = []
        pulses.extend(self._frame_pulses(payload, include_wakeup=True, hardware_syncs=self.FIRST_FRAME_HARDWARE_SYNCS))
        for _ in range(self.total_frames - 1):
            pulses.extend(
                self._frame_pulses(payload, include_wakeup=False, hardware_syncs=self.REPEATED_FRAME_HARDWARE_SYNCS)
            )
        return pulses

    def _frame_pulses(self, payload: bytes, include_wakeup: bool, hardware_syncs: int) -> list[dict[str, int]]:
        pulses: list[dict[str, int]] = []
        if include_wakeup:
            pulses.append({"level": 1, "duration_us": self.WAKEUP_HIGH_US})
            pulses.append({"level": 0, "duration_us": self.WAKEUP_LOW_US})

        for _ in range(hardware_syncs):
            pulses.append({"level": 1, "duration_us": self.HARDWARE_SYNC_US})
            pulses.append({"level": 0, "duration_us": self.HARDWARE_SYNC_US})

        pulses.append({"level": 1, "duration_us": self.SOFTWARE_SYNC_HIGH_US})
        pulses.append({"level": 0, "duration_us": self.HALF_SYMBOL_US})
        pulses.extend(self._manchester_payload_pulses(payload))
        return pulses

    def _manchester_payload_pulses(self, payload: bytes) -> list[dict[str, int]]:
        pulses: list[dict[str, int]] = []
        bits = "".join(f"{byte:08b}" for byte in payload)
        for bit in bits:
            if bit == "1":
                pulses.append({"level": 1, "duration_us": self.HALF_SYMBOL_US})
                pulses.append({"level": 0, "duration_us": self.HALF_SYMBOL_US})
            else:
                pulses.append({"level": 0, "duration_us": self.HALF_SYMBOL_US})
                pulses.append({"level": 1, "duration_us": self.HALF_SYMBOL_US})
        return pulses
