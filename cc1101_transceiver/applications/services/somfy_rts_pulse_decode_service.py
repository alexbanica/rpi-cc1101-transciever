from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from cc1101_transceiver.applications.services.somfy_rts_codec_service import SomfyRtsCodecService


@dataclass(frozen=True)
class PulseFrameCandidate:
    start_index: int
    end_index_exclusive: int
    obfuscated_hex: str


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

    def __init__(self) -> None:
        self.codec = SomfyRtsCodecService()

    def decode_obfuscated_hex(self, pulse_durations_us: Sequence[Mapping[str, object]]) -> str:
        # Offline diagnostic decoding intentionally reports syntactically decoded
        # bytes even when checksum/command validation fails; callers surface that
        # metadata. Live capture uses iter_candidates' stricter acceptance.
        pulses, _ = self._normalize_with_spans(pulse_durations_us)
        for index in range(len(pulses)):
            parsed = self._parse_at(pulses, index)
            if parsed is not None:
                return parsed[1]
        raise ValueError("Somfy RTS pulse data contains no complete 56-bit frame")

    def iter_candidates(self, pulse_durations_us: Sequence[Mapping[str, object]]) -> Iterator[PulseFrameCandidate]:
        """Yield complete, syntactically valid observed frames in pulse-index order."""
        pulses, spans = self._normalize_with_spans(pulse_durations_us)
        index = 0
        while index < len(pulses):
            parsed = self._parse_at(pulses, index)
            if parsed is None:
                index += 1
                continue
            end, frame = parsed
            try:
                decoded = self.codec.decode_obfuscated_hex(frame)
            except ValueError:
                index += 1
                continue
            if decoded.valid_checksum is not True:
                index += 1
                continue
            yield PulseFrameCandidate(spans[index][0], spans[end - 1][1], frame)
            index = end

    def _parse_at(self, pulses: list[tuple[int, int]], start: int) -> tuple[int, str] | None:
        cursor = start
        if not self._matches(pulses, cursor, 1, self.WAKEUP_HIGH_US):
            # Repeats have no wakeup and always start with seven high/low pairs.
            sync_end = self._sync_end(pulses, cursor, exact_pairs=7)
            if sync_end is None:
                return None
            cursor = sync_end
        else:
            if cursor + 1 >= len(pulses) or not self._matches(pulses, cursor + 1, 0, self.WAKEUP_LOW_US):
                return None
            cursor += 2
            sync_end = self._sync_end(pulses, cursor, minimum_pairs=self.MIN_HARDWARE_SYNCS)
            if sync_end is None:
                return None
            cursor = sync_end
        if not self._matches(pulses, cursor, 1, self.SOFTWARE_SYNC_HIGH_US):
            return None
        cursor += 1
        if cursor >= len(pulses) or pulses[cursor][0] != 0 or pulses[cursor][1] < self.HALF_SYMBOL_US * (1 - self.HALF_SYMBOL_TOLERANCE):
            return None
        # The low half of software sync is part of the Manchester stream.
        symbols: list[int] = []
        first_duration = pulses[cursor][1]
        first_half_count = _round_half_symbols(first_duration, self.HALF_SYMBOL_US)
        if first_half_count < 1 or first_half_count > 2 or not _within_tolerance(first_duration, first_half_count * self.HALF_SYMBOL_US, self.HALF_SYMBOL_TOLERANCE):
            return None
        cursor += 1
        # If the first data half is also low it is coalesced with the software
        # sync low by edge measurement. Preserve only the measured remainder.
        extra = max(0, first_half_count - 1)
        if extra > 0:
            if not _within_tolerance(first_duration, (extra + 1) * self.HALF_SYMBOL_US, self.HALF_SYMBOL_TOLERANCE):
                return None
            symbols.extend([0] * min(extra, self.PAYLOAD_BITS * 2))
        remaining = self.PAYLOAD_BITS * 2 - len(symbols)
        while remaining > 0 and cursor < len(pulses):
            level, duration = pulses[cursor]
            count = _round_half_symbols(duration, self.HALF_SYMBOL_US)
            if count < 1:
                return None
            # Bound work by the fixed payload size, even for adversarial durations.
            if count > remaining:
                # The final observed level may continue into idle. Consume only the
                # prefix justified by the remaining payload width.
                needed_duration = remaining * self.HALF_SYMBOL_US
                if duration < needed_duration * (1 - self.HALF_SYMBOL_TOLERANCE):
                    return None
                symbols.extend([level] * remaining)
                remaining = 0
                cursor += 1
                break
            expected = count * self.HALF_SYMBOL_US
            if not _within_tolerance(duration, expected, self.HALF_SYMBOL_TOLERANCE):
                return None
            symbols.extend([level] * count)
            remaining -= count
            cursor += 1
        if remaining:
            return None
        bits: list[str] = []
        for offset in range(0, len(symbols), 2):
            pair = symbols[offset:offset + 2]
            if pair == [1, 0]:
                bits.append("1")
            elif pair == [0, 1]:
                bits.append("0")
            else:
                return None
        return cursor, int("".join(bits), 2).to_bytes(7, "big").hex()

    def _sync_end(self, pulses: list[tuple[int, int]], start: int, *, minimum_pairs: int | None = None, exact_pairs: int | None = None) -> int | None:
        count = 0
        cursor = start
        while cursor + 1 < len(pulses) and self._matches(pulses, cursor, 1, self.HARDWARE_SYNC_US) and self._matches(pulses, cursor + 1, 0, self.HARDWARE_SYNC_US):
            count += 1
            cursor += 2
            if exact_pairs is not None and count == exact_pairs:
                return cursor
        if exact_pairs is not None:
            return None
        return cursor if count >= (minimum_pairs or self.MIN_HARDWARE_SYNCS) else None

    def _matches(self, pulses: list[tuple[int, int]], index: int, level: int, duration: int) -> bool:
        return index < len(pulses) and pulses[index][0] == level and _within_tolerance(pulses[index][1], duration, self.SYNC_TOLERANCE)

    def _normalize_with_spans(self, raw_pulses: Sequence[Mapping[str, object]]) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
        pulses: list[tuple[int, int]] = []
        spans: list[tuple[int, int]] = []
        for source_index, item in enumerate(raw_pulses):
            try:
                level, duration = int(item["level"]), int(item["duration_us"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Somfy RTS pulse item must contain integer level and duration_us") from exc
            if level not in (0, 1) or duration <= 0:
                raise ValueError("Somfy RTS pulse level and duration_us must be valid")
            if pulses and pulses[-1][0] == level:
                pulses[-1] = (level, pulses[-1][1] + duration)
                spans[-1] = (spans[-1][0], source_index + 1)
            else:
                pulses.append((level, duration))
                spans.append((source_index, source_index + 1))
        return pulses, spans

    def _normalize(self, raw_pulses: Sequence[Mapping[str, object]]) -> list[tuple[int, int]]:
        return self._normalize_with_spans(raw_pulses)[0]


def _within_tolerance(actual: int, expected: int, tolerance: float) -> bool:
    return expected * (1.0 - tolerance) <= actual <= expected * (1.0 + tolerance)


def _round_half_symbols(duration_us: int, half_symbol_us: int) -> int:
    # Integer-only rounding keeps arbitrary saved durations from overflowing
    # during conversion to float. Callers cap the resulting count before use.
    return (duration_us + half_symbol_us // 2) // half_symbol_us
