import unittest
import time
from unittest.mock import patch

from cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture import GpioPulseCapture


class FakeCallback:
    def cancel(self):
        calls.append("cancel")


calls = []


class FakeLgpio:
    BOTH_EDGES = 3
    TIMEOUT = 2

    def gpiochip_open(self, index):
        calls.append(("open", index))
        return 40 + index

    def gpio_get_chip_info(self, chip):
        return (0, 30, "gpiochip4", "pinctrl-rp1")

    def gpio_get_line_info(self, chip, line):
        return (0, line, 0, f"GPIO{25}" if line == 25 else f"line{line}", "")

    def gpio_claim_alert(self, chip, line, edge):
        calls.append(("claim", line))
        return 0

    def callback(self, chip, line, edge, function):
        # Callback delay and later pin state are irrelevant; event clock and levels win.
        time.sleep(0.01)
        function(chip, line, 1, 1_000_000)
        function(chip, line, 0, 1_600_000)
        function(chip, line, self.TIMEOUT, 1_700_000)
        function(chip, line, 1, 2_100_000)
        function(chip, line, 0, 2_900_000)
        return FakeCallback()

    def gpio_free(self, chip, line):
        calls.append(("free", line))

    def gpiochip_close(self, chip):
        calls.append(("close", chip))


class TimestampedGpioCaptureTest(unittest.TestCase):
    def test_uses_event_levels_and_timestamps_ignores_watchdog_and_releases_resources(self):
        calls.clear()
        with patch("cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture.glob.glob", return_value=["/dev/gpiochip4"]):
            runs = GpioPulseCapture(25, gpio_loader=FakeLgpio).capture(0.03)
        self.assertEqual(runs, [[{"level": 1, "duration_us": 600}, {"level": 0, "duration_us": 500}, {"level": 1, "duration_us": 800}]])
        self.assertIn(("claim", 25), calls)
        self.assertIn(("free", 25), calls)
        self.assertIn("cancel", calls)
        self.assertIn(("close", 44), calls)

    def test_bad_transition_splits_runs_and_reanchors_on_next_edge(self):
        fake = FakeLgpio()
        events = [(1, 1_000_000), (0, 2_000_000), (0, 3_000_000), (1, 4_000_000), (0, 4_500_000)]
        def callback(chip, line, edge, function):
            for level, stamp in events:
                function(chip, line, level, stamp)
            return FakeCallback()
        fake.callback = callback
        with patch("cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture.glob.glob", return_value=["/dev/gpiochip4"]):
            runs = GpioPulseCapture(25, gpio_loader=lambda: fake).capture(0.03)
        self.assertEqual(runs, [[{"level": 1, "duration_us": 1000}], [{"level": 1, "duration_us": 500}]])

    def test_gpiochip_symlink_alias_is_discovered_once(self):
        calls.clear()
        with patch("cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture.glob.glob", return_value=["/dev/gpiochip0", "/dev/gpiochip4"]):
            with patch("cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture.os.path.realpath", return_value="/dev/gpiochip0"):
                runs = GpioPulseCapture(25, gpio_loader=FakeLgpio).capture(0.03)
        self.assertEqual(runs[0][0], {"level": 1, "duration_us": 600})
        self.assertEqual([call for call in calls if isinstance(call, tuple) and call[0] == "open"], [("open", 0)])

    def test_gpio25_does_not_match_gpio2_and_invalid_levels_or_timestamps_split_runs(self):
        fake = FakeLgpio()
        def line_info(chip, line):
            if line == 2:
                return (0, 2, 0, "GPIO2", "")
            return (0, line, 0, "GPIO25" if line == 25 else f"line{line}", "")
        fake.gpio_get_line_info = line_info
        def callback(chip, line, edge, function):
            for level, stamp in [(1, 1000000), (0, 2000000), (7, 2500000), (1, 3000000), (0, 2900000), (1, 4000000), (0, 4500000)]:
                function(chip, line, level, stamp)
            return FakeCallback()
        fake.callback = callback
        with patch("cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture.glob.glob", return_value=["/dev/gpiochip4"]):
            runs = GpioPulseCapture(25, gpio_loader=lambda: fake).capture(0.03)
        self.assertEqual(runs, [[{"level": 1, "duration_us": 1000}], [{"level": 1, "duration_us": 500}]])

    def test_chip_access_failure_fails_closed(self):
        class PermissionDenied(FakeLgpio):
            def gpiochip_open(self, index):
                raise PermissionError("denied")
        with patch("cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture.glob.glob", return_value=["/dev/gpiochip4"]):
            with self.assertRaisesRegex(Exception, "failed to inspect GPIO controller"):
                GpioPulseCapture(25, gpio_loader=PermissionDenied).capture(0.03)

    def test_error_cleanup_releases_claimed_line_and_chip(self):
        class CallbackFailure(FakeLgpio):
            def callback(self, *args):
                raise OSError("callback registration failed")
        calls.clear()
        with patch("cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture.glob.glob", return_value=["/dev/gpiochip4"]):
            with self.assertRaises(Exception):
                GpioPulseCapture(25, gpio_loader=CallbackFailure).capture(0.03)
        self.assertIn(("free", 25), calls)
        self.assertIn(("close", 44), calls)

    def test_discovery_time_consumes_capture_timeout_without_registering_callback(self):
        fake = FakeLgpio()
        now = [100.0]
        callback_calls = []
        def discover(_capture, gpio, requested):
            now[0] = 103.0
            return 44, 25
        fake.callback = lambda *args: callback_calls.append(args)
        with patch("cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture.time.monotonic", side_effect=lambda: now[0]):
            with patch.object(GpioPulseCapture, "_find_gpio_line", discover):
                result = GpioPulseCapture(25, gpio_loader=lambda: fake).capture(1.0)
        self.assertEqual(result, [])
        self.assertEqual(callback_calls, [])

    def test_nonselected_chip_close_failure_releases_selected_handle(self):
        class CloseFailure(FakeLgpio):
            def gpio_get_chip_info(self, chip):
                return (0, 30, "gpiochip", "pinctrl-rp1" if chip == 40 else "other-controller")
            def gpiochip_close(self, chip):
                calls.append(("close", chip))
                if chip == 41:
                    raise OSError("close failed")
        calls.clear()
        fake = CloseFailure()
        with patch("cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture.glob.glob", return_value=["/dev/gpiochip0", "/dev/gpiochip1"]):
            with patch("cc1101_transceiver.infrastructures.cc1101.gpio_pulse_capture.os.path.realpath", side_effect=lambda p: p):
                with self.assertRaisesRegex(Exception, "release an unselected"):
                    GpioPulseCapture(25, gpio_loader=lambda: fake).capture(0.03)
        self.assertIn(("close", 40), calls)
