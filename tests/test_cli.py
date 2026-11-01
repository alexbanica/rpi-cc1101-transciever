import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cc1101_transceiver.applications.services.emit_service import EmitResult
from cc1101_transceiver.controllers.cli import main
from cc1101_transceiver.domains.entities.somfy_command import SomfyCommand
from cc1101_transceiver.domains.entities.somfy_frame import EncodedSomfyFrame
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

    def test_live_send_hardware_error_maps_to_2_and_does_not_advance_profile(self):
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
            with patch(
                "cc1101_transceiver.infrastructures.cc1101.cc1101_transceiver_adapter.Cc1101TransceiverAdapter.transmit",
                side_effect=HardwareAccessError("GPIO unavailable"),
            ):
                self.assertEqual(
                    main(
                        [
                            "emitter",
                            "send",
                            "--profile",
                            str(profile),
                            "--command",
                            "up",
                        ]
                    ),
                    2,
                )

            with open(profile, encoding="utf-8") as handle:
                self.assertIn('"rolling_code": 1234', handle.read())

    def test_send_parses_tx_gpio_and_passes_it_to_adapter(self):
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
            encoded = EncodedSomfyFrame(
                SomfyCommand.UP,
                "a1b2c3",
                1234,
                bytes.fromhex("a72004d2c3b2a1"),
                bytes.fromhex("a78e8a589b2988"),
                433420000,
            )
            result = EmitResult(encoded, dry_run=False, transmitted=True, next_rolling_code=1235)

            with patch("cc1101_transceiver.controllers.cli.Cc1101TransceiverAdapter") as adapter_class:
                with patch("cc1101_transceiver.controllers.cli.EmitService") as service_class:
                    service_class.return_value.send.return_value = result
                    self.assertEqual(
                        main(
                            [
                                "emitter",
                                "send",
                                "--profile",
                                str(profile),
                                "--command",
                                "up",
                                "--tx-gpio",
                                "26",
                            ]
                        ),
                        0,
                    )

            adapter_class.assert_called_once_with(0, 0, tx_gpio=26, symbol_rate=4800)

    def test_send_parses_symbol_rate_and_passes_it_to_adapter(self):
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
            encoded = EncodedSomfyFrame(
                SomfyCommand.UP,
                "a1b2c3",
                1234,
                bytes.fromhex("a72004d2c3b2a1"),
                bytes.fromhex("a78e8a589b2988"),
                433420000,
            )
            result = EmitResult(encoded, dry_run=False, transmitted=True, next_rolling_code=1235)

            with patch("cc1101_transceiver.controllers.cli.Cc1101TransceiverAdapter") as adapter_class:
                with patch("cc1101_transceiver.controllers.cli.EmitService") as service_class:
                    service_class.return_value.send.return_value = result
                    self.assertEqual(
                        main(
                            [
                                "emitter",
                                "send",
                                "--profile",
                                str(profile),
                                "--command",
                                "up",
                                "--symbol-rate",
                                "2400",
                            ]
                        ),
                        0,
                    )

            adapter_class.assert_called_once_with(0, 0, tx_gpio=25, symbol_rate=2400)

    def test_prog_without_allow_programming_maps_to_usage(self):
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
                        "prog",
                    ]
                ),
                64,
            )

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
