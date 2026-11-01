import unittest

from cc1101_transceiver.applications.services.somfy_rts_pulse_decode_service import (
    SomfyRtsPulseDecodeService,
)
from cc1101_transceiver.applications.services.somfy_rts_pulse_encode_service import (
    SomfyRtsPulseEncodeService,
)

from tests.pulse_fixtures import nominal_somfy_pulses


class SomfyRtsPulseDecodeTest(unittest.TestCase):
    def setUp(self):
        self.decoder = SomfyRtsPulseDecodeService()

    def test_nominal_pulses_decode_to_obfuscated_frame(self):
        result = self.decoder.decode_obfuscated_hex(nominal_somfy_pulses())

        self.assertEqual(result, "a78e8a589b2988")

    def test_timing_tolerance_accepts_jitter(self):
        pulses = nominal_somfy_pulses()
        pulses[0] = {**pulses[0], "duration_us": 9415 + 1800}
        pulses[2] = {**pulses[2], "duration_us": 2416 - 400}

        result = self.decoder.decode_obfuscated_hex(pulses)

        self.assertEqual(result, "a78e8a589b2988")

    def test_timing_tolerance_rejects_out_of_range_sync(self):
        pulses = nominal_somfy_pulses()
        pulses[0] = {**pulses[0], "duration_us": 15000}

        with self.assertRaises(ValueError):
            self.decoder.decode_obfuscated_hex(pulses)

    def test_rejects_non_positive_duration(self):
        pulses = nominal_somfy_pulses()
        pulses[0] = {**pulses[0], "duration_us": 0}

        with self.assertRaises(ValueError):
            self.decoder.decode_obfuscated_hex(pulses)

    def test_rejects_invalid_level(self):
        pulses = nominal_somfy_pulses()
        pulses[0] = {**pulses[0], "level": 2}

        with self.assertRaises(ValueError):
            self.decoder.decode_obfuscated_hex(pulses)

    def test_rejects_short_payload(self):
        pulses = nominal_somfy_pulses()[:-4]

        with self.assertRaises(ValueError):
            self.decoder.decode_obfuscated_hex(pulses)

    def test_accepts_idle_tail_after_complete_frame(self):
        pulses = nominal_somfy_pulses()
        pulses.append({"level": 0, "duration_us": 10_000_000})

        self.assertEqual(self.decoder.decode_obfuscated_hex(pulses), "a78e8a589b2988")

    def test_accepts_idle_merged_into_final_low_payload_pulse(self):
        pulses = nominal_somfy_pulses("a78e8a589b2989")
        self.assertEqual(pulses[-1]["level"], 0)
        pulses[-1]["duration_us"] += 20000

        self.assertEqual(self.decoder.decode_obfuscated_hex(pulses), "a78e8a589b2989")

    def test_accepts_timeout_idle_merged_into_final_low_for_zero_first_bit_frame(self):
        pulses = nominal_somfy_pulses("278e8a589b2989")
        self.assertEqual(pulses[-1]["level"], 0)
        pulses[-1]["duration_us"] += 10_000_000

        self.assertEqual(self.decoder.decode_obfuscated_hex(pulses), "278e8a589b2989")

    def test_accepts_default_two_frame_encoder_output(self):
        pulses = SomfyRtsPulseEncodeService().encode_obfuscated_hex("a78e8a589b2988")

        self.assertEqual(self.decoder.decode_obfuscated_hex(pulses), "a78e8a589b2988")

    def test_accepts_complete_first_frame_before_truncated_repeat(self):
        pulses = SomfyRtsPulseEncodeService().encode_obfuscated_hex("278e8a589b2989")

        self.assertEqual(
            self.decoder.decode_obfuscated_hex(pulses[:-10]),
            "278e8a589b2989",
        )

    def test_rejects_oversized_internal_payload_pulse(self):
        pulses = nominal_somfy_pulses()
        pulses[10] = {**pulses[10], "duration_us": pulses[10]["duration_us"] + 604}

        with self.assertRaises(ValueError):
            self.decoder.decode_obfuscated_hex(pulses)

    def test_rejects_unrecognized_oversized_final_high_pulse(self):
        pulses = nominal_somfy_pulses()
        self.assertEqual(pulses[-1]["level"], 1)
        pulses[-1]["duration_us"] += 20000

        with self.assertRaises(ValueError):
            self.decoder.decode_obfuscated_hex(pulses)


if __name__ == "__main__":
    unittest.main()
