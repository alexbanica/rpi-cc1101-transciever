import unittest

from cc1101_transceiver.applications.services.somfy_rts_pulse_decode_service import (
    SomfyRtsPulseDecodeService,
)

from tests.pulse_fixtures import nominal_somfy_pulses, repeated_somfy_pulses


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

    def test_candidate_extraction_skips_idle_noise_and_finds_later_frame(self):
        noisy = [{"level": 1, "duration_us": 1500}, {"level": 0, "duration_us": 50000}]
        noisy += nominal_somfy_pulses()
        found = list(self.decoder.iter_candidates(noisy))
        self.assertEqual([item.obfuscated_hex for item in found], ["a78e8a589b2988"])
        self.assertEqual(found[0].start_index, 2)

    def test_repeat_without_wakeup_is_extracted(self):
        found = list(self.decoder.iter_candidates(repeated_somfy_pulses()))
        self.assertEqual([item.obfuscated_hex for item in found], ["a78e8a589b2988"])

    def test_concatenated_first_and_repeat_are_both_extracted(self):
        found = list(self.decoder.iter_candidates(nominal_somfy_pulses() + [{"level": 0, "duration_us": 2500}] + repeated_somfy_pulses()))
        self.assertEqual([item.obfuscated_hex for item in found], ["a78e8a589b2988", "a78e8a589b2988"])

    def test_invalid_checksum_candidate_does_not_hide_later_valid_frame(self):
        corrupted = bytearray.fromhex("a78e8a589b2988")
        corrupted[-1] ^= 1
        pulses = nominal_somfy_pulses(corrupted.hex()) + [{"level": 0, "duration_us": 3000}] + nominal_somfy_pulses()
        found = list(self.decoder.iter_candidates(pulses))
        self.assertEqual([item.obfuscated_hex for item in found], ["a78e8a589b2988"])

    def test_offline_decode_preserves_invalid_checksum_diagnostic_bytes(self):
        corrupted = bytearray.fromhex("a78e8a589b2988")
        corrupted[-1] ^= 1
        self.assertEqual(self.decoder.decode_obfuscated_hex(nominal_somfy_pulses(corrupted.hex())), corrupted.hex())
        self.assertEqual(list(self.decoder.iter_candidates(nominal_somfy_pulses(corrupted.hex()))), [])

    def test_first_frame_accepts_more_than_two_sync_pairs(self):
        pulses = nominal_somfy_pulses()
        insert_at = next(i for i, pulse in enumerate(pulses) if pulse["duration_us"] == 4550)
        pulses[insert_at:insert_at] = [{"level": 1, "duration_us": 2416}, {"level": 0, "duration_us": 2416}] * 3
        self.assertEqual(list(self.decoder.iter_candidates(pulses))[0].obfuscated_hex, "a78e8a589b2988")

    def test_coalesced_halves_and_final_idle_are_handled_with_original_indices(self):
        pulses = nominal_somfy_pulses()
        expanded = []
        for pulse in pulses:
            duration = pulse["duration_us"]
            if duration > 5000:
                expanded.append(dict(pulse))
            else:
                while duration > 1208:
                    expanded.append({"level": pulse["level"], "duration_us": 604})
                    duration -= 604
                expanded.append({"level": pulse["level"], "duration_us": duration})
        expanded[-1]["duration_us"] += 12000
        found = list(self.decoder.iter_candidates(expanded))
        self.assertEqual(found[0].start_index, 0)
        self.assertEqual(found[0].end_index_exclusive, len(expanded))

    def test_adversarial_long_idle_does_not_create_unbounded_symbol_expansion(self):
        pulses = [{"level": 0, "duration_us": 10**18}] + nominal_somfy_pulses()
        found = list(self.decoder.iter_candidates(pulses))
        self.assertEqual([item.obfuscated_hex for item in found], ["a78e8a589b2988"])

    def test_arbitrarily_huge_final_idle_and_software_sync_low_are_bounded(self):
        final_idle = nominal_somfy_pulses()
        final_idle[-1]["duration_us"] = 10**1000
        self.assertEqual(list(self.decoder.iter_candidates(final_idle))[0].obfuscated_hex, "a78e8a589b2988")

        malformed = nominal_somfy_pulses()
        software_sync = next(i for i, pulse in enumerate(malformed) if pulse["duration_us"] == 4550)
        malformed[software_sync + 1]["duration_us"] = 10**1000
        self.assertEqual(list(self.decoder.iter_candidates(malformed)), [])


if __name__ == "__main__":
    unittest.main()
