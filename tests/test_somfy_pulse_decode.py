import unittest

from cc1101_transceiver.applications.services.somfy_rts_pulse_decode_service import (
    SomfyRtsPulseDecodeService,
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


if __name__ == "__main__":
    unittest.main()
