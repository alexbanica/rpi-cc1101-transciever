from __future__ import annotations

HALF_SYMBOL_US = 604
SYMBOL_US = 1208
WAKEUP_HIGH_US = 9415
WAKEUP_LOW_US = 89565
HARDWARE_SYNC_US = 2416
SOFTWARE_SYNC_HIGH_US = 4550


def nominal_somfy_pulses(obfuscated_hex: str = "a78e8a589b2988") -> list[dict[str, int]]:
    samples: list[tuple[int, int]] = [
        (1, WAKEUP_HIGH_US),
        (0, WAKEUP_LOW_US),
    ]
    for _ in range(2):
        samples.append((1, HARDWARE_SYNC_US))
        samples.append((0, HARDWARE_SYNC_US))
    samples.append((1, SOFTWARE_SYNC_HIGH_US))
    samples.append((0, HALF_SYMBOL_US))

    bits = "".join(f"{byte:08b}" for byte in bytes.fromhex(obfuscated_hex))
    for bit in bits:
        samples.extend([(1, HALF_SYMBOL_US), (0, HALF_SYMBOL_US)] if bit == "1" else [(0, HALF_SYMBOL_US), (1, HALF_SYMBOL_US)])

    return _merge(samples)


def _merge(samples: list[tuple[int, int]]) -> list[dict[str, int]]:
    merged: list[dict[str, int]] = []
    for level, duration_us in samples:
        if merged and merged[-1]["level"] == level:
            merged[-1]["duration_us"] += duration_us
        else:
            merged.append({"level": level, "duration_us": duration_us})
    return merged
