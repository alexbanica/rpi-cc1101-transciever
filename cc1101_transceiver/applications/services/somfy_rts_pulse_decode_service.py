from __future__ import annotations

from collections.abc import Mapping, Sequence


class SomfyRtsPulseDecodeService:
    WAKEUP_HIGH_US = 9415
    WAKEUP_LOW_US = 89565
    HARDWARE_SYNC_US = 2416
    SOFTWARE_SYNC_HIGH_US = 4550
    HALF_SYMBOL_US = 604
    PAYLOAD_BITS = 56

    SYNC_TOLERANCE = 0.30
    HALF_SYMBOL_TOLERANCE = 0.35
    MIN_HARDWARE_SYNCS = 2

    def decode_obfuscated_hex(self, pulse_durations_us: Sequence[Mapping[str, object]]) -> str:
        pulses = self._normalize(pulse_durations_us)
        cursor = _PulseCursor(pulses)

        cursor.consume_exact(1, self.WAKEUP_HIGH_US, self.SYNC_TOLERANCE)
        cursor.consume_exact(0, self.WAKEUP_LOW_US, self.SYNC_TOLERANCE)

        sync_count = 0
        while (
            cursor.remaining_matches(1, self.HARDWARE_SYNC_US, self.SYNC_TOLERANCE)
            and cursor.next_remaining_matches(0, self.HARDWARE_SYNC_US, self.SYNC_TOLERANCE)
        ):
            cursor.consume_exact(1, self.HARDWARE_SYNC_US, self.SYNC_TOLERANCE)
            cursor.consume_exact(0, self.HARDWARE_SYNC_US, self.SYNC_TOLERANCE)
            sync_count += 1
        if sync_count < self.MIN_HARDWARE_SYNCS:
            raise ValueError("Somfy RTS pulse data does not contain enough hardware sync pulses")

        cursor.consume_exact(1, self.SOFTWARE_SYNC_HIGH_US, self.SYNC_TOLERANCE)
        cursor.consume_prefix(0, self.HALF_SYMBOL_US, self.HALF_SYMBOL_TOLERANCE)

        half_symbols = self._payload_half_symbols(cursor)
        if len(half_symbols) != self.PAYLOAD_BITS * 2:
            raise ValueError("Somfy RTS pulse data does not contain a 56-bit Manchester payload")

        bits = []
        for index in range(0, len(half_symbols), 2):
            pair = half_symbols[index : index + 2]
            if pair == [1, 0]:
                bits.append("1")
            elif pair == [0, 1]:
                bits.append("0")
            else:
                raise ValueError("Somfy RTS Manchester payload contains an invalid transition")

        return int("".join(bits), 2).to_bytes(7, "big").hex()

    def _normalize(self, raw_pulses: Sequence[Mapping[str, object]]) -> list[tuple[int, int]]:
        if not raw_pulses:
            raise ValueError("Somfy RTS pulse data is empty")

        pulses: list[tuple[int, int]] = []
        for item in raw_pulses:
            try:
                level = int(item["level"])
                duration_us = int(item["duration_us"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Somfy RTS pulse item must contain integer level and duration_us") from exc
            if level not in (0, 1):
                raise ValueError("Somfy RTS pulse level must be 0 or 1")
            if duration_us <= 0:
                raise ValueError("Somfy RTS pulse duration_us must be positive")
            if pulses and pulses[-1][0] == level:
                previous_level, previous_duration = pulses[-1]
                pulses[-1] = (previous_level, previous_duration + duration_us)
            else:
                pulses.append((level, duration_us))
        while pulses and pulses[0][0] == 0:
            pulses.pop(0)
        if not pulses:
            raise ValueError("Somfy RTS pulse data does not contain a high wakeup pulse")
        return pulses

    def _payload_half_symbols(self, cursor: "_PulseCursor") -> list[int]:
        half_symbols: list[int] = []
        for level, duration_us in cursor.remaining_pulses():
            half_count = round(duration_us / self.HALF_SYMBOL_US)
            if half_count < 1:
                raise ValueError("Somfy RTS payload pulse is shorter than a half-symbol")
            expected = half_count * self.HALF_SYMBOL_US
            if not _within_tolerance(duration_us, expected, self.HALF_SYMBOL_TOLERANCE):
                raise ValueError("Somfy RTS payload pulse is outside half-symbol timing tolerance")
            half_symbols.extend([level] * half_count)
            if len(half_symbols) > self.PAYLOAD_BITS * 2:
                raise ValueError("Somfy RTS pulse data contains too many payload half-symbols")
        return half_symbols


class _PulseCursor:
    def __init__(self, pulses: list[tuple[int, int]]):
        self._pulses = pulses
        self._index = 0
        self._offset_us = 0

    def remaining_matches(self, level: int, expected_us: int, tolerance: float) -> bool:
        remaining = self._remaining_at(self._index, self._offset_us)
        return remaining is not None and remaining[0] == level and _within_tolerance(remaining[1], expected_us, tolerance)

    def next_remaining_matches(self, level: int, expected_us: int, tolerance: float) -> bool:
        next_index = self._index + 1
        remaining = self._remaining_at(next_index, 0)
        return remaining is not None and remaining[0] == level and _within_tolerance(remaining[1], expected_us, tolerance)

    def consume_exact(self, level: int, expected_us: int, tolerance: float) -> None:
        remaining = self._remaining_at(self._index, self._offset_us)
        if remaining is None or remaining[0] != level or not _within_tolerance(remaining[1], expected_us, tolerance):
            raise ValueError("Somfy RTS pulse sync timing is malformed")
        self._index += 1
        self._offset_us = 0

    def consume_prefix(self, level: int, expected_us: int, tolerance: float) -> None:
        remaining = self._remaining_at(self._index, self._offset_us)
        if remaining is None or remaining[0] != level:
            raise ValueError("Somfy RTS pulse sync timing is malformed")
        if remaining[1] < expected_us * (1.0 - tolerance):
            raise ValueError("Somfy RTS pulse sync timing is malformed")
        self._offset_us += expected_us
        if self._offset_us >= self._pulses[self._index][1]:
            self._index += 1
            self._offset_us = 0

    def remaining_pulses(self) -> list[tuple[int, int]]:
        result: list[tuple[int, int]] = []
        for index in range(self._index, len(self._pulses)):
            level, duration_us = self._pulses[index]
            if index == self._index:
                duration_us -= self._offset_us
            if duration_us > 0:
                result.append((level, duration_us))
        return result

    def _remaining_at(self, index: int, offset_us: int) -> tuple[int, int] | None:
        if index >= len(self._pulses):
            return None
        level, duration_us = self._pulses[index]
        return level, duration_us - offset_us


def _within_tolerance(actual: int, expected: int, tolerance: float) -> bool:
    return expected * (1.0 - tolerance) <= actual <= expected * (1.0 + tolerance)
