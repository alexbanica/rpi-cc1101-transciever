from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from cc1101_transceiver.shared.exceptions import HardwareAccessError


class GpioPulseTransmitter:
    def __init__(
        self,
        tx_gpio: int,
        gpio_loader: Callable[[], object] | None = None,
        monotonic_ns: Callable[[], int] | None = None,
        sleep: Callable[[float], None] | None = None,
    ):
        self.tx_gpio = tx_gpio
        self._gpio_loader = gpio_loader or self._load_gpio
        self._monotonic_ns = monotonic_ns or time.monotonic_ns
        self._sleep = sleep or time.sleep

    def transmit(self, pulses: Sequence[dict[str, int]]) -> None:
        gpio = self._load_runtime_gpio()
        setup_complete = False
        try:
            gpio.setmode(gpio.BCM)
            gpio.setup(self.tx_gpio, gpio.OUT, initial=0)
            setup_complete = True
            for pulse in pulses:
                level = self._pulse_level(pulse)
                duration_us = self._pulse_duration_us(pulse)
                gpio.output(self.tx_gpio, level)
                self._wait_duration_us(duration_us)
        except HardwareAccessError:
            raise
        except (OSError, RuntimeError, PermissionError, AttributeError, TypeError, ValueError) as exc:
            raise HardwareAccessError(f"GPIO transmit failed on BCM GPIO {self.tx_gpio}: {exc}") from exc
        finally:
            if setup_complete:
                try:
                    gpio.output(self.tx_gpio, 0)
                except Exception:
                    pass
            try:
                gpio.cleanup(self.tx_gpio)
            except Exception:
                pass

    def _load_runtime_gpio(self) -> object:
        try:
            return self._gpio_loader()
        except HardwareAccessError:
            raise
        except ImportError as exc:
            raise HardwareAccessError(
                "missing Raspberry Pi GPIO dependency 'rpi-lgpio'/'RPi.GPIO'; install requirements on the Pi"
            ) from exc
        except (OSError, RuntimeError, PermissionError) as exc:
            raise HardwareAccessError(f"GPIO transmit setup failed on BCM GPIO {self.tx_gpio}: {exc}") from exc

    def _load_gpio(self) -> object:
        try:
            import RPi.GPIO as gpio  # type: ignore[import-not-found]
        except ImportError as exc:
            raise HardwareAccessError(
                "missing Raspberry Pi GPIO dependency 'rpi-lgpio'/'RPi.GPIO'; install requirements on the Pi"
            ) from exc
        return gpio

    def _wait_duration_us(self, duration_us: int) -> None:
        deadline_ns = self._monotonic_ns() + duration_us * 1000
        while True:
            remaining_ns = deadline_ns - self._monotonic_ns()
            if remaining_ns <= 0:
                return
            if remaining_ns > 200_000:
                self._sleep(min(remaining_ns / 1_000_000_000, 0.0001))

    def _pulse_level(self, pulse: dict[str, int]) -> int:
        level = int(pulse["level"])
        if level not in (0, 1):
            raise ValueError("pulse level must be 0 or 1")
        return level

    def _pulse_duration_us(self, pulse: dict[str, int]) -> int:
        duration_us = int(pulse["duration_us"])
        if duration_us <= 0:
            raise ValueError("pulse duration_us must be positive")
        return duration_us
