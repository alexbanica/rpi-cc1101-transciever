import sys
import types
import unittest
from unittest.mock import patch

from cc1101_transceiver.infrastructures.cc1101.cc1101_transceiver_adapter import (
    Cc1101TransceiverAdapter,
)
from cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture import GpioPulseCapture
from cc1101_transceiver.shared.exceptions import HardwareAccessError

from tests.pulse_fixtures import nominal_somfy_pulses


class FakeCc1101:
    calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def set_base_frequency_hertz(self, value):
        self.calls.append(("set_base_frequency_hertz", value))

    def set_symbol_rate_baud(self, value):
        self.calls.append(("set_symbol_rate_baud", value))

    def _set_modulation_format(self, value):
        self.calls.append(("_set_modulation_format", value))

    def set_packet_length_mode(self, value):
        self.calls.append(("set_packet_length_mode", value))

    def set_sync_mode(self, value):
        self.calls.append(("set_sync_mode", value))

    def _set_transceive_mode(self, value):
        self.calls.append(("_set_transceive_mode", value))

    def _enable_receive_mode(self):
        self.calls.append(("_enable_receive_mode", None))


class FakePulseCapture:
    def __init__(self, rx_gpio):
        self.rx_gpio = rx_gpio

    def capture(self, timeout):
        return nominal_somfy_pulses()


class Gdo0CaptureInfrastructureTest(unittest.TestCase):
    def setUp(self):
        FakeCc1101.calls = []

    def test_adapter_requires_rx_gpio_for_live_capture(self):
        with self.assertRaises(HardwareAccessError):
            Cc1101TransceiverAdapter(0, 0).capture(0.1, 1, 433420000)

    def test_adapter_decodes_gdo0_pulses(self):
        fake_module = types.SimpleNamespace(
            CC1101=FakeCc1101,
            ModulationFormat=types.SimpleNamespace(ASK_OOK=3),
            PacketLengthMode=types.SimpleNamespace(FIXED=0),
            SyncMode=types.SimpleNamespace(NO_PREAMBLE_AND_SYNC_WORD=0),
            _TransceiveMode=types.SimpleNamespace(ASYNCHRONOUS_SERIAL=3),
        )
        with patch.dict(sys.modules, {"cc1101": fake_module}):
            with patch(
                "cc1101_transceiver.infrastructures.cc1101.cc1101_transceiver_adapter.GpioPulseCapture",
                FakePulseCapture,
            ):
                frames = Cc1101TransceiverAdapter(0, 0, rx_gpio=25).capture(0.1, 1, 433420000)

        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].raw["capture_method"], "gdo0-gpio-pulse")
        self.assertEqual(frames[0].raw["gdo"], "GDO0")
        self.assertEqual(frames[0].raw["rx_gpio"], 25)
        self.assertEqual(frames[0].raw["gpio_numbering"], "bcm")
        self.assertEqual(frames[0].raw["obfuscated_frame_hex"], "a78e8a589b2988")
        self.assertEqual(frames[0].decoded.address, "a1b2c3")
        self.assertIn(("set_base_frequency_hertz", 433420000), FakeCc1101.calls)
        self.assertIn(("_enable_receive_mode", None), FakeCc1101.calls)

    def test_adapter_returns_no_frames_for_undecodable_pulses(self):
        class BadPulseCapture:
            def __init__(self, rx_gpio):
                self.rx_gpio = rx_gpio

            def capture(self, timeout):
                return [{"level": 1, "duration_us": 100}]

        fake_module = types.SimpleNamespace(CC1101=FakeCc1101)
        with patch.dict(sys.modules, {"cc1101": fake_module}):
            with patch(
                "cc1101_transceiver.infrastructures.cc1101.cc1101_transceiver_adapter.GpioPulseCapture",
                BadPulseCapture,
            ):
                frames = Cc1101TransceiverAdapter(0, 0, rx_gpio=25).capture(0.1, 1, 433420000)

        self.assertEqual(frames, [])

    def test_gpio_loader_import_error_maps_to_hardware_error(self):
        capture = GpioPulseCapture(25, gpio_loader=lambda: (_ for _ in ()).throw(HardwareAccessError("missing")))

        with self.assertRaises(HardwareAccessError):
            capture.capture(0.1)


if __name__ == "__main__":
    unittest.main()
