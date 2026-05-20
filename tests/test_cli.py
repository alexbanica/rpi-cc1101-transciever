import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cc1101_transceiver.controllers.cli import main
from cc1101_transceiver.shared.exceptions import HardwareAccessError


class CliTest(unittest.TestCase):
    def test_help_exits_successfully(self):
        self.assertEqual(main(["--help"]), 0)

    def test_invalid_arguments_map_to_64(self):
        self.assertEqual(main(["emitter", "send", "--command", "up"]), 64)

    def test_capture_hardware_error_maps_to_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / "capture.json"
            with patch(
                "cc1101_transceiver.infrastructures.cc1101.cc1101_transceiver_adapter.Cc1101TransceiverAdapter.capture",
                side_effect=HardwareAccessError("missing GPIO access"),
            ):
                self.assertEqual(
                    main(["receiver", "capture", "--rx-gpio", "25", "--out-file", str(capture)]),
                    2,
                )
            self.assertFalse(capture.exists())

    def test_init_profile_and_dry_run_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile.json"

            self.assertEqual(
                main(
                    [
                        "emitter",
                        "init-profile",
                        "--profile",
                        str(profile),
                        "--address",
                        "a1b2c3",
                        "--rolling-code",
                        "1234",
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "emitter",
                        "send",
                        "--profile",
                        str(profile),
                        "--command",
                        "up",
                        "--dry-run",
                    ]
                ),
                0,
            )

    def test_run_sh_help_wrapper(self):
        result = subprocess.run(
            ["bash", "run.sh", "--help"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("receiver", result.stdout)
        self.assertIn("emitter", result.stdout)


if __name__ == "__main__":
    unittest.main()
