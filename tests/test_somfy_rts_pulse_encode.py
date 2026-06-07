import unittest

from cc1101_transceiver.applications.services.somfy_rts_pulse_decode_service import (
    SomfyRtsPulseDecodeService,
)
from cc1101_transceiver.applications.services.somfy_rts_pulse_encode_service import (
    SomfyRtsPulseEncodeService,
)

from tests.pulse_fixtures import (
    HALF_SYMBOL_US,
    HARDWARE_SYNC_US,
    SOFTWARE_SYNC_HIGH_US,
    WAKEUP_HIGH_US,
    WAKEUP_LOW_US,
)


class SomfyRtsPulseEncodeTest(unittest.TestCase):
    def test_first_frame_round_trips_through_existing_decoder(self):
        pulses = SomfyRtsPulseEncodeService(total_frames=1).encode_obfuscated_hex("a78e8a589b2988")

        decoded = SomfyRtsPulseDecodeService().decode_obfuscated_hex(pulses)

        self.assertEqual(decoded, "a78e8a589b2988")

    def test_first_frame_timing_shape_is_deterministic(self):
        pulses = SomfyRtsPulseEncodeService(total_frames=1).encode_obfuscated_hex("a78e8a589b2988")

        self.assertEqual(
            pulses[:8],
            [
                {"level": 1, "duration_us": WAKEUP_HIGH_US},
                {"level": 0, "duration_us": WAKEUP_LOW_US},
                {"level": 1, "duration_us": HARDWARE_SYNC_US},
                {"level": 0, "duration_us": HARDWARE_SYNC_US},
                {"level": 1, "duration_us": HARDWARE_SYNC_US},
                {"level": 0, "duration_us": HARDWARE_SYNC_US},
                {"level": 1, "duration_us": SOFTWARE_SYNC_HIGH_US},
                {"level": 0, "duration_us": HALF_SYMBOL_US},
            ],
        )
        self.assertEqual(len(pulses), 120)
        self.assertEqual(pulses[8:], _manchester_pulses("a78e8a589b2988"))

    def test_repeated_frame_omits_wakeup_and_uses_seven_hardware_syncs(self):
        pulses = SomfyRtsPulseEncodeService(total_frames=2).encode_obfuscated_hex("a78e8a589b2988")
        repeated_frame = pulses[120:]

        expected_sync = []
        for _ in range(7):
            expected_sync.extend(
                [
                    {"level": 1, "duration_us": HARDWARE_SYNC_US},
                    {"level": 0, "duration_us": HARDWARE_SYNC_US},
                ]
            )
        self.assertEqual(repeated_frame[:14], expected_sync)
        self.assertEqual(
            repeated_frame[14:16],
            [
                {"level": 1, "duration_us": SOFTWARE_SYNC_HIGH_US},
                {"level": 0, "duration_us": HALF_SYMBOL_US},
            ],
        )
        self.assertEqual(repeated_frame[16:], _manchester_pulses("a78e8a589b2988"))
        self.assertEqual(len(pulses), 248)

    def test_pulse_items_use_valid_levels_and_positive_integer_durations(self):
        pulses = SomfyRtsPulseEncodeService(total_frames=2).encode_obfuscated_hex("a78e8a589b2988")

        self.assertGreater(len(pulses), 0)
        for pulse in pulses:
            self.assertIn(pulse["level"], (0, 1))
            self.assertIs(type(pulse["duration_us"]), int)
            self.assertGreater(pulse["duration_us"], 0)


def _manchester_pulses(obfuscated_hex):
    pulses = []
    bits = "".join(f"{byte:08b}" for byte in bytes.fromhex(obfuscated_hex))
    for bit in bits:
        if bit == "1":
            pulses.extend(
                [
                    {"level": 1, "duration_us": HALF_SYMBOL_US},
                    {"level": 0, "duration_us": HALF_SYMBOL_US},
                ]
            )
        else:
            pulses.extend(
                [
                    {"level": 0, "duration_us": HALF_SYMBOL_US},
                    {"level": 1, "duration_us": HALF_SYMBOL_US},
                ]
            )
    return pulses


if __name__ == "__main__":
    unittest.main()
