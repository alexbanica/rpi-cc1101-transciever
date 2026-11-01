from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cc1101_transceiver.controllers.cli import main
from cc1101_transceiver.domains.entities.capture import Capture, CaptureFrame, DecodedFrame
from cc1101_transceiver.domains.entities.somfy_profile import SomfyProfile
from cc1101_transceiver.shared.constants.defaults import CAPTURE_FORMAT, PROFILE_FORMAT


class FakeCaptureRepository:
    def __init__(self, capture: Capture):
        self.capture = capture
        self.read_paths: list[Path] = []

    def read(self, path: Path) -> Capture:
        self.read_paths.append(path)
        return self.capture


class FakeProfileRepository:
    def __init__(self, profile: SomfyProfile):
        self.profile = profile
        self.read_paths: list[Path] = []

    def read(self, path: Path) -> SomfyProfile:
        self.read_paths.append(path)
        return self.profile


class InspectServiceTest(unittest.TestCase):
    def setUp(self):
        self.capture = Capture(
            frequency_hz=433420000,
            spi_bus=0,
            spi_chip_select=0,
            frames=[
                CaptureFrame(1, "now", {}, DecodedFrame("somfy-rts", "a1b2c3", 1234, "up", True)),
                CaptureFrame(2, "later", {}, None),
            ],
        )
        self.profile = SomfyProfile("hall", "a1b2c3", 1234)
        self.capture_repository = FakeCaptureRepository(self.capture)
        self.profile_repository = FakeProfileRepository(self.profile)

    def test_inspects_capture_using_injected_repository(self):
        from cc1101_transceiver.applications.services.inspect_service import InspectService

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            path.write_text('{"format": "' + CAPTURE_FORMAT + '"}', encoding="utf-8")

            summary = InspectService(self.capture_repository, self.profile_repository).inspect(path)

        self.assertEqual(
            summary,
            {"type": "capture", "frequency_hz": 433420000, "frames": 2, "decoded_frames": 1},
        )
        self.assertEqual(self.capture_repository.read_paths, [path])
        self.assertEqual(self.profile_repository.read_paths, [])

    def test_inspects_profile_using_injected_repository(self):
        from cc1101_transceiver.applications.services.inspect_service import InspectService

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text('{"format":"' + PROFILE_FORMAT + '"}', encoding="utf-8")

            summary = InspectService(self.capture_repository, self.profile_repository).inspect(path)

        self.assertEqual(
            summary,
            {
                "type": "profile",
                "name": "hall",
                "address": "a1b2c3",
                "rolling_code": 1234,
                "frequency_hz": 433420000,
            },
        )
        self.assertEqual(self.capture_repository.read_paths, [])
        self.assertEqual(self.profile_repository.read_paths, [path])

    def test_cli_wires_persistence_adapters_into_inspect_service(self):
        capture_adapter = object()
        profile_adapter = object()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            path.write_text('{"format": "' + CAPTURE_FORMAT + '"}', encoding="utf-8")
            with (
                patch("cc1101_transceiver.controllers.cli.JsonCaptureRepository", return_value=capture_adapter),
                patch("cc1101_transceiver.controllers.cli.JsonProfileRepository", return_value=profile_adapter),
                patch("cc1101_transceiver.controllers.cli.InspectService") as service_class,
            ):
                service_class.return_value.inspect.return_value = {"type": "capture", "frames": 0}
                result = main(["receiver", "inspect", str(path)])

        self.assertEqual(result, 0)
        service_class.assert_called_once_with(capture_adapter, profile_adapter)
        service_class.return_value.inspect.assert_called_once_with(path)


if __name__ == "__main__":
    unittest.main()
