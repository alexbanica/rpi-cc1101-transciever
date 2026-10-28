import tempfile
import unittest
from pathlib import Path

from cc1101_transceiver.applications.services.clone_profile_service import CloneProfileService
from cc1101_transceiver.applications.services.capture_service import CaptureService
from cc1101_transceiver.applications.services.decode_service import DecodeService
from cc1101_transceiver.applications.services.emit_service import EmitService
from cc1101_transceiver.applications.services.profile_initialization_service import (
    ProfileInitializationService,
)
from cc1101_transceiver.applications.services.somfy_rts_codec_service import SomfyRtsCodecService
from cc1101_transceiver.domains.entities.capture import Capture, CaptureFrame, DecodedFrame
from cc1101_transceiver.domains.entities.somfy_command import SomfyCommand
from cc1101_transceiver.infrastructures.persistences.json_capture_repository import (
    JsonCaptureRepository,
)
from cc1101_transceiver.infrastructures.persistences.json_profile_repository import (
    JsonProfileRepository,
)
from cc1101_transceiver.shared.exceptions import InvalidInputError, ProgrammingCommandBlockedError
from cc1101_transceiver.shared.exceptions import OperationalError

from tests.pulse_fixtures import nominal_somfy_pulses


class FakeTransceiver:
    def __init__(self, fail=False, capture_frames=None):
        self.fail = fail
        self.capture_frames = [] if capture_frames is None else capture_frames
        self.transmissions = []

    def capture(self, timeout, frames, frequency_hz):
        return self.capture_frames[:frames]

    def transmit(self, frame, frequency_hz):
        if self.fail:
            raise RuntimeError("hardware unavailable")
        self.transmissions.append((frame.obfuscated_hex, frequency_hz))


class PersistenceAndServicesTest(unittest.TestCase):
    def setUp(self):
        self.codec = SomfyRtsCodecService()

    def test_profile_json_read_write_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profile.json"
            service = ProfileInitializationService(JsonProfileRepository())
            profile = service.initialize(path, "A1B2C3", 1234, "blind", 433420000)

            loaded = JsonProfileRepository().read(path)

            self.assertEqual(profile.address, "a1b2c3")
            self.assertEqual(loaded.address, "a1b2c3")
            self.assertEqual(loaded.rolling_code, 1234)

    def test_capture_json_read_write_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.json"
            capture = Capture(
                frequency_hz=433420000,
                spi_bus=0,
                spi_chip_select=0,
                frames=[
                    CaptureFrame(
                        index=0,
                        captured_at="2026-05-20T00:00:00Z",
                        raw={"obfuscated_frame_hex": "a78e8a589b2988"},
                        decoded=DecodedFrame("somfy-rts", "a1b2c3", 1234, "up", True),
                    )
                ],
            )

            JsonCaptureRepository().write(path, capture)
            loaded = JsonCaptureRepository().read(path)

            self.assertEqual(loaded.frames[0].decoded.address, "a1b2c3")
            self.assertEqual(loaded.frames[0].decoded.rolling_code, 1234)

    def test_clone_profile_uses_next_rolling_code_from_decoded_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture_path = Path(tmp) / "capture.json"
            profile_path = Path(tmp) / "profile.json"
            capture = Capture(
                frequency_hz=433420000,
                spi_bus=0,
                spi_chip_select=0,
                frames=[
                    CaptureFrame(
                        index=0,
                        captured_at="2026-05-20T00:00:00Z",
                        raw={},
                        decoded=DecodedFrame("somfy-rts", "a1b2c3", 1234, "up", True),
                    )
                ],
            )
            JsonCaptureRepository().write(capture_path, capture)

            profile = CloneProfileService(JsonCaptureRepository(), JsonProfileRepository()).clone(
                capture_path,
                profile_path,
                "blind",
            )

            self.assertEqual(profile.address, "a1b2c3")
            self.assertEqual(profile.rolling_code, 1235)
            self.assertEqual(JsonProfileRepository().read(profile_path).rolling_code, 1235)

    def test_decode_falls_back_to_pulse_only_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture_path = Path(tmp) / "capture.json"
            JsonCaptureRepository().write(
                capture_path,
                Capture(
                    433420000,
                    0,
                    0,
                    [
                        CaptureFrame(
                            0,
                            "2026-05-20T00:00:00Z",
                            {
                                "capture_method": "gdo0-gpio-pulse",
                                "rx_gpio": 25,
                                "gpio_numbering": "bcm",
                                "pulse_durations_us": nominal_somfy_pulses(),
                            },
                            None,
                        )
                    ],
                ),
            )

            decoded = DecodeService(JsonCaptureRepository(), self.codec).decode(capture_path)

            self.assertEqual(decoded.frames[0].raw["obfuscated_frame_hex"], "a78e8a589b2988")
            self.assertEqual(decoded.frames[0].decoded.address, "a1b2c3")
            self.assertEqual(decoded.frames[0].decoded.rolling_code, 1234)

    def test_capture_service_does_not_write_when_adapter_returns_no_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture_path = Path(tmp) / "capture.json"

            with self.assertRaises(OperationalError):
                CaptureService(FakeTransceiver(capture_frames=[]), JsonCaptureRepository()).capture(
                    capture_path,
                    timeout=0.1,
                    frames=1,
                    frequency_hz=433420000,
                    spi_bus=0,
                    spi_chip_select=0,
                )

            self.assertFalse(capture_path.exists())

    def test_capture_service_writes_gdo0_raw_and_decoded_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture_path = Path(tmp) / "capture.json"
            frame = CaptureFrame(
                index=99,
                captured_at="2026-05-20T00:00:00Z",
                raw={
                    "capture_method": "gdo0-gpio-pulse",
                    "gdo": "GDO0",
                    "rx_gpio": 25,
                    "gpio_numbering": "bcm",
                    "pulse_durations_us": nominal_somfy_pulses(),
                    "obfuscated_frame_hex": "a78e8a589b2988",
                },
                decoded=DecodedFrame("somfy-rts", "a1b2c3", 1234, "up", True),
            )

            CaptureService(FakeTransceiver(capture_frames=[frame]), JsonCaptureRepository()).capture(
                capture_path,
                timeout=1.0,
                frames=1,
                frequency_hz=433420000,
                spi_bus=0,
                spi_chip_select=0,
            )

            loaded = JsonCaptureRepository().read(capture_path)
            self.assertEqual(loaded.frames[0].index, 0)
            self.assertEqual(loaded.frames[0].raw["capture_method"], "gdo0-gpio-pulse")
            self.assertEqual(loaded.frames[0].raw["rx_gpio"], 25)
            self.assertEqual(loaded.frames[0].decoded.address, "a1b2c3")

    def test_clone_profile_works_from_gdo0_decoded_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture_path = Path(tmp) / "capture.json"
            profile_path = Path(tmp) / "profile.json"
            JsonCaptureRepository().write(
                capture_path,
                Capture(
                    433420000,
                    0,
                    0,
                    [
                        CaptureFrame(
                            0,
                            "2026-05-20T00:00:00Z",
                            {
                                "capture_method": "gdo0-gpio-pulse",
                                "rx_gpio": 25,
                                "gpio_numbering": "bcm",
                                "pulse_durations_us": nominal_somfy_pulses(),
                                "obfuscated_frame_hex": "a78e8a589b2988",
                            },
                            DecodedFrame("somfy-rts", "a1b2c3", 1234, "up", True),
                        )
                    ],
                ),
            )

            profile = CloneProfileService(JsonCaptureRepository(), JsonProfileRepository()).clone(
                capture_path,
                profile_path,
                "blind",
            )

            self.assertEqual(profile.address, "a1b2c3")
            self.assertEqual(profile.rolling_code, 1235)

    def test_prog_safety_gating(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "profile.json"
            ProfileInitializationService(JsonProfileRepository()).initialize(
                profile_path,
                "a1b2c3",
                1234,
                "blind",
                433420000,
            )

            with self.assertRaises(ProgrammingCommandBlockedError):
                EmitService(JsonProfileRepository(), self.codec, FakeTransceiver()).send(
                    profile_path,
                    SomfyCommand.PROG,
                    dry_run=True,
                    allow_programming=False,
                )

    def test_dry_run_does_not_call_hardware_and_advances_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "profile.json"
            ProfileInitializationService(JsonProfileRepository()).initialize(
                profile_path,
                "a1b2c3",
                1234,
                "blind",
                433420000,
            )
            transceiver = FakeTransceiver()

            result = EmitService(JsonProfileRepository(), self.codec, transceiver).send(
                profile_path,
                SomfyCommand.UP,
                dry_run=True,
                allow_programming=False,
            )

            self.assertEqual(result.encoded_frame.obfuscated_hex, "a78e8a589b2988")
            self.assertEqual(transceiver.transmissions, [])
            self.assertEqual(JsonProfileRepository().read(profile_path).rolling_code, 1235)

    def test_failed_hardware_send_does_not_advance_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "profile.json"
            ProfileInitializationService(JsonProfileRepository()).initialize(
                profile_path,
                "a1b2c3",
                1234,
                "blind",
                433420000,
            )

            with self.assertRaises(RuntimeError):
                EmitService(JsonProfileRepository(), self.codec, FakeTransceiver(fail=True)).send(
                    profile_path,
                    SomfyCommand.UP,
                    dry_run=False,
                    allow_programming=False,
                )

            self.assertEqual(JsonProfileRepository().read(profile_path).rolling_code, 1234)

    def test_live_send_success_advances_profile_once_after_transmit(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "profile.json"
            ProfileInitializationService(JsonProfileRepository()).initialize(
                profile_path,
                "a1b2c3",
                1234,
                "blind",
                433420000,
            )
            transceiver = FakeTransceiver()

            result = EmitService(JsonProfileRepository(), self.codec, transceiver).send(
                profile_path,
                SomfyCommand.UP,
                dry_run=False,
                allow_programming=False,
            )

            self.assertEqual(result.encoded_frame.obfuscated_hex, "a78e8a589b2988")
            self.assertTrue(result.transmitted)
            self.assertFalse(result.dry_run)
            self.assertEqual(transceiver.transmissions, [("a78e8a589b2988", 433420000)])
            self.assertEqual(result.next_rolling_code, 1235)
            self.assertEqual(JsonProfileRepository().read(profile_path).rolling_code, 1235)

    def test_invalid_capture_without_decoded_frame_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture_path = Path(tmp) / "capture.json"
            profile_path = Path(tmp) / "profile.json"
            JsonCaptureRepository().write(
                capture_path,
                Capture(433420000, 0, 0, [CaptureFrame(0, "2026-05-20T00:00:00Z", {}, None)]),
            )

            with self.assertRaises(InvalidInputError):
                CloneProfileService(JsonCaptureRepository(), JsonProfileRepository()).clone(
                    capture_path,
                    profile_path,
                    "blind",
                )


if __name__ == "__main__":
    unittest.main()
