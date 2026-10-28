import unittest

from cc1101_transceiver.infrastructures.cc1101.gpio_pulse_transmitter import GpioPulseTransmitter
from cc1101_transceiver.shared.exceptions import HardwareAccessError


class FakeClock:
    def __init__(self):
        self.now_ns = 0

    def monotonic_ns(self):
        self.now_ns += 1_000_000
        return self.now_ns

    def sleep(self, seconds):
        self.now_ns += int(seconds * 1_000_000_000)


class FakeGpio:
    BCM = "BCM"
    OUT = "OUT"

    def __init__(self, fail_on_output_index=None):
        self.fail_on_output_index = fail_on_output_index
        self.outputs = []
        self.calls = []

    def setmode(self, mode):
        self.calls.append(("setmode", mode))

    def setup(self, pin, mode, initial=None):
        self.calls.append(("setup", pin, mode, initial))

    def output(self, pin, level):
        self.calls.append(("output", pin, level))
        self.outputs.append((pin, level))
        if self.fail_on_output_index is not None and len(self.outputs) == self.fail_on_output_index:
            raise RuntimeError("GPIO write failed")

    def cleanup(self, pin):
        self.calls.append(("cleanup", pin))


class GpioPulseTransmitterTest(unittest.TestCase):
    def test_transmit_drives_pulses_then_leaves_gpio_low_and_cleans_up(self):
        gpio = FakeGpio()
        clock = FakeClock()
        transmitter = GpioPulseTransmitter(
            25,
            gpio_loader=lambda: gpio,
            monotonic_ns=clock.monotonic_ns,
            sleep=clock.sleep,
        )

        transmitter.transmit(
            [
                {"level": 1, "duration_us": 604},
                {"level": 0, "duration_us": 604},
                {"level": 1, "duration_us": 1208},
            ]
        )

        self.assertEqual(gpio.calls[0], ("setmode", gpio.BCM))
        self.assertEqual(gpio.calls[1], ("setup", 25, gpio.OUT, 0))
        self.assertEqual(gpio.outputs[:3], [(25, 1), (25, 0), (25, 1)])
        self.assertEqual(gpio.outputs[-1], (25, 0))
        self.assertEqual(gpio.calls[-1], ("cleanup", 25))

    def test_transmit_failure_leaves_gpio_low_and_cleans_up(self):
        gpio = FakeGpio(fail_on_output_index=2)
        clock = FakeClock()
        transmitter = GpioPulseTransmitter(
            25,
            gpio_loader=lambda: gpio,
            monotonic_ns=clock.monotonic_ns,
            sleep=clock.sleep,
        )

        with self.assertRaises(HardwareAccessError):
            transmitter.transmit(
                [
                    {"level": 1, "duration_us": 604},
                    {"level": 0, "duration_us": 604},
                ]
            )

        self.assertEqual(gpio.outputs[-1], (25, 0))
        self.assertEqual(gpio.calls[-1], ("cleanup", 25))

    def test_missing_gpio_dependency_maps_to_hardware_error(self):
        transmitter = GpioPulseTransmitter(
            25,
            gpio_loader=lambda: (_ for _ in ()).throw(HardwareAccessError("missing GPIO")),
        )

        with self.assertRaises(HardwareAccessError):
            transmitter.transmit([{"level": 1, "duration_us": 604}])


if __name__ == "__main__":
    unittest.main()
