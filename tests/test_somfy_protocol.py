import unittest

from cc1101_transceiver.applications.services.somfy_rts_codec_service import SomfyRtsCodecService
from cc1101_transceiver.domains.entities.somfy_command import SomfyCommand
from cc1101_transceiver.domains.entities.somfy_profile import SomfyProfile


class SomfyRtsProtocolTest(unittest.TestCase):
    def setUp(self):
        self.codec = SomfyRtsCodecService()

    def test_command_mapping(self):
        self.assertEqual(SomfyCommand.from_label("up").control_nibble, 0x2)
        self.assertEqual(SomfyCommand.from_label("down").control_nibble, 0x4)
        self.assertEqual(SomfyCommand.from_label("my").control_nibble, 0x1)
        self.assertEqual(SomfyCommand.from_label("prog").control_nibble, 0x8)
        with self.assertRaises(ValueError):
            SomfyCommand.from_label("stop")

    def test_checksum_and_obfuscation_round_trip(self):
        profile = SomfyProfile(
            name="blind",
            address="a1b2c3",
            rolling_code=1234,
            frequency_hz=433420000,
        )
        encoded = self.codec.encode(profile, SomfyCommand.UP)

        self.assertEqual(encoded.plain_frame[0], 0xA7)
        self.assertTrue(self.codec.is_checksum_valid(encoded.plain_frame))
        self.assertEqual(
            self.codec.deobfuscate(encoded.obfuscated_frame),
            encoded.plain_frame,
        )
        self.assertEqual(
            self.codec.obfuscate(encoded.plain_frame),
            encoded.obfuscated_frame,
        )

    def test_decode_known_fixture_frame(self):
        decoded = self.codec.decode_obfuscated_hex("a78e8a589b2988")

        self.assertEqual(decoded.address, "a1b2c3")
        self.assertEqual(decoded.rolling_code, 1234)
        self.assertEqual(decoded.command, "up")
        self.assertTrue(decoded.valid_checksum)

    def test_encode_from_profile_and_command_is_deterministic(self):
        profile = SomfyProfile(
            name="blind",
            address="a1b2c3",
            rolling_code=1234,
            frequency_hz=433420000,
        )

        encoded = self.codec.encode(profile, SomfyCommand.UP)

        self.assertEqual(encoded.plain_hex, "a72904d2c3b2a1")
        self.assertEqual(encoded.obfuscated_hex, "a78e8a589b2988")


if __name__ == "__main__":
    unittest.main()
