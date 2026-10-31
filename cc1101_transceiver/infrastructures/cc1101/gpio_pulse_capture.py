from __future__ import annotations

import glob
import os
import threading
import time
from collections.abc import Callable

from cc1101_transceiver.shared.exceptions import HardwareAccessError


class GpioPulseCapture:
    """Capture measured edge-to-edge runs using lgpio's event clock."""

    def __init__(self, rx_gpio: int, gpio_loader: Callable[[], object] | None = None):
        self.rx_gpio = rx_gpio
        self._gpio_loader = gpio_loader or self._load_gpio

    def capture(self, timeout: float) -> list[list[dict[str, int]]]:
        deadline = time.monotonic() + max(0.0, timeout)
        gpio = self._gpio_loader()
        chip = None
        callback = None
        claimed = False
        lock = threading.Lock()
        runs: list[list[dict[str, int]]] = []
        current: list[dict[str, int]] = []
        previous: tuple[int, int] | None = None
        accepting = True
        cleanup_errors: list[Exception] = []

        def on_edge(_chip: int, _line: int, level: int, timestamp_ns: int) -> None:
            nonlocal previous, current
            with lock:
                if not accepting:
                    return
                if time.monotonic() >= deadline:
                    return
                if level == getattr(gpio, "TIMEOUT", 2):
                    return
                if level not in (0, 1) or timestamp_ns <= 0:
                    self._close_run(runs, current)
                    current = []
                    previous = None
                    return
                if previous is None:
                    previous = (level, timestamp_ns)
                    return
                old_level, old_time = previous
                if timestamp_ns <= old_time or level == old_level:
                    self._close_run(runs, current)
                    current = []
                    previous = None
                    return
                duration = max(1, round((timestamp_ns - old_time) / 1000))
                current.append({"level": old_level, "duration_us": duration})
                previous = (level, timestamp_ns)

        try:
            chip, line = self._find_gpio_line(gpio, self.rx_gpio)
            result = gpio.gpio_claim_alert(chip, line, gpio.BOTH_EDGES)
            if result < 0:
                raise OSError(f"gpio_claim_alert returned {result}")
            claimed = True
            # Setup consumes the same bounded session budget as edge collection.
            if time.monotonic() < deadline:
                callback = gpio.callback(chip, line, gpio.BOTH_EDGES, on_edge)
            while time.monotonic() < deadline:
                time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
            if callback is not None:
                callback.cancel()
                callback = None
            with lock:
                accepting = False
                self._close_run(runs, current)
                result = [list(run) for run in runs]
            return result
        except HardwareAccessError:
            raise
        except (OSError, RuntimeError, PermissionError, AttributeError, TypeError) as exc:
            raise HardwareAccessError(f"GPIO capture failed on BCM GPIO {self.rx_gpio}: {exc}") from exc
        finally:
            if callback is not None:
                try:
                    callback.cancel()
                except Exception as exc:
                    cleanup_errors.append(exc)
            if claimed:
                try:
                    gpio.gpio_free(chip, line)
                except Exception as exc:
                    cleanup_errors.append(exc)
            if chip is not None:
                try:
                    gpio.gpiochip_close(chip)
                except Exception as exc:
                    cleanup_errors.append(exc)
            if cleanup_errors:
                raise HardwareAccessError(f"GPIO capture cleanup failed: {cleanup_errors[0]}") from cleanup_errors[0]

    @staticmethod
    def _close_run(runs: list[list[dict[str, int]]], run: list[dict[str, int]]) -> None:
        if run:
            runs.append(list(run))

    def _find_gpio_line(self, gpio: object, requested: int) -> tuple[int, int]:
        matches: list[tuple[int, int]] = []
        seen_devices: set[str] = set()
        opened: list[int] = []
        for device in sorted(glob.glob("/dev/gpiochip*")):
            physical_device = os.path.realpath(device)
            if physical_device in seen_devices:
                continue
            seen_devices.add(physical_device)
            handle = None
            try:
                index = int(device.rsplit("gpiochip", 1)[1])
                handle = gpio.gpiochip_open(index)
                opened.append(handle)
                info = gpio.gpio_get_chip_info(handle)
                details = " ".join(str(value) for value in info).lower()
                if not any(marker in details for marker in ("bcm2835", "bcm2711", "pinctrl-bcm", "pinctrl-rp1")):
                    continue
                if len(info) < 4 or not isinstance(info[0], int) or info[0] < 0:
                    raise HardwareAccessError(f"lgpio could not read chip information for {device}")
                line_count = info[1]
                if not isinstance(line_count, int) or line_count < 0:
                    raise HardwareAccessError(f"invalid gpiochip information for {device}")
                for line in range(line_count):
                    line_info = gpio.gpio_get_line_info(handle, line)
                    if not line_info or not isinstance(line_info[0], int) or line_info[0] < 0:
                        raise HardwareAccessError(f"lgpio could not read line {line} information on {device}")
                    name = str(line_info[3]).strip().upper() if len(line_info) > 3 else ""
                    if name == f"GPIO{requested}":
                        matches.append((handle, line))
            except HardwareAccessError:
                self._close_discovery_handles(gpio, opened)
                raise
            except (OSError, RuntimeError, TypeError, ValueError, IndexError) as exc:
                self._close_discovery_handles(gpio, opened)
                raise HardwareAccessError(f"failed to inspect GPIO controller {device}: {exc}") from exc
        if len(matches) != 1:
            self._close_discovery_handles(gpio, opened)
            raise HardwareAccessError(f"could not uniquely identify BCM GPIO {requested} on a Raspberry Pi gpiochip")
        selected = matches[0]
        try:
            for handle in opened:
                if handle != selected[0]:
                    gpio.gpiochip_close(handle)
        except (OSError, RuntimeError) as exc:
            self._close_discovery_handles(gpio, opened)
            raise HardwareAccessError(f"failed to release an unselected GPIO controller: {exc}") from exc
        return selected

    @staticmethod
    def _close_discovery_handles(gpio: object, handles: list[int]) -> None:
        for handle in handles:
            try:
                gpio.gpiochip_close(handle)
            except Exception:
                pass

    def _load_gpio(self) -> object:
        try:
            import lgpio  # type: ignore[import-not-found]
        except ImportError as exc:
            raise HardwareAccessError("missing GPIO dependency 'lgpio'; install requirements on the Pi") from exc
        return lgpio
