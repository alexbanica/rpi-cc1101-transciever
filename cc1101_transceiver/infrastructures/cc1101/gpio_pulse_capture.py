from __future__ import annotations

import time
from collections.abc import Callable

from cc1101_transceiver.shared.exceptions import HardwareAccessError


class GpioPulseCapture:
    def __init__(self, rx_gpio: int, gpio_loader: Callable[[], object] | None = None):
        self.rx_gpio = rx_gpio
        self._gpio_loader = gpio_loader or self._load_gpio

    def capture(self, timeout: float) -> list[dict[str, int]]:
        gpio = self._gpio_loader()
        pulses: list[dict[str, int]] = []
        state = {"last_level": None, "last_ns": time.monotonic_ns(), "saw_edge": False}

        try:
            gpio.setmode(gpio.BCM)
            gpio.setup(self.rx_gpio, gpio.IN)
            state["last_level"] = int(gpio.input(self.rx_gpio))

            def on_edge(channel: int) -> None:
                now_ns = time.monotonic_ns()
                next_level = int(gpio.input(channel))
                previous_level = state["last_level"]
                previous_ns = state["last_ns"]
                if previous_level in (0, 1):
                    duration_us = max(1, round((now_ns - previous_ns) / 1000))
                    self._append_pulse(pulses, int(previous_level), duration_us)
                state["last_level"] = next_level
                state["last_ns"] = now_ns
                state["saw_edge"] = True

            gpio.add_event_detect(self.rx_gpio, gpio.BOTH, callback=on_edge)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))

            if state["saw_edge"] and state["last_level"] in (0, 1):
                duration_us = max(1, round((time.monotonic_ns() - state["last_ns"]) / 1000))
                self._append_pulse(pulses, int(state["last_level"]), duration_us)
            return pulses
        except HardwareAccessError:
            raise
        except (OSError, RuntimeError, PermissionError) as exc:
            raise HardwareAccessError(f"GPIO capture failed on BCM GPIO {self.rx_gpio}: {exc}") from exc
        finally:
            try:
                gpio.remove_event_detect(self.rx_gpio)
            except Exception:
                pass
            try:
                gpio.cleanup(self.rx_gpio)
            except Exception:
                pass

    def _load_gpio(self) -> object:
        try:
            import RPi.GPIO as gpio  # type: ignore[import-not-found]
        except ImportError as exc:
            raise HardwareAccessError(
                "missing Raspberry Pi GPIO dependency 'rpi-lgpio'/'RPi.GPIO'; install requirements on the Pi"
            ) from exc
        return gpio

    def _append_pulse(self, pulses: list[dict[str, int]], level: int, duration_us: int) -> None:
        if pulses and pulses[-1]["level"] == level:
            pulses[-1]["duration_us"] += duration_us
        else:
            pulses.append({"level": level, "duration_us": duration_us})
