#!/usr/bin/env python3
"""Check whether a CC1101 is reachable over Raspberry Pi SPI.

This diagnostic reads identity registers only. It does not configure the radio
or transmit RF.

>>> spi_path(0, 1)
'/dev/spidev0.1'
>>> classify_identity(0x00, 0x14)
(True, 'plausible CC1101 identity response')
>>> classify_identity(0x00, 0x00)
(False, 'all-zero identity response')
>>> classify_identity(0xff, 0xff)
(False, 'all-0xff identity response')
>>> decide_exit_code([CandidateResult('/dev/spidev0.0', True, None, None, 'ok')])
0
>>> decide_exit_code([CandidateResult('/dev/spidev0.0', False, 0, 0, 'all-zero identity response')])
1
>>> decide_exit_code([CandidateResult('/dev/spidev0.0', False, None, None, 'missing SPI device node', operational_error=True)])
2
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
from dataclasses import asdict, dataclass
from typing import Iterable


CC1101_PARTNUM = 0x30
CC1101_VERSION = 0x31
CC1101_READ_BURST = 0xC0
DEFAULT_BUS = 0
DEFAULT_CHIP_SELECTS = (0, 1)
DEFAULT_SPEED_HZ = 500_000


@dataclass(frozen=True)
class Candidate:
    bus: int
    chip_select: int

    @property
    def path(self) -> str:
        return spi_path(self.bus, self.chip_select)


@dataclass(frozen=True)
class CandidateResult:
    path: str
    passed: bool
    partnum: int | None
    version: int | None
    reason: str
    operational_error: bool = False


def positive_int(value: str) -> int:
    parsed = int(value, 10)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value, 10)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read CC1101 PARTNUM and VERSION registers over SPI. "
            "No configuration registers are written and no RF is transmitted."
        )
    )
    parser.add_argument("--bus", type=non_negative_int, default=DEFAULT_BUS)
    parser.add_argument(
        "--chip-select",
        type=non_negative_int,
        help="probe only this chip-select; defaults to probing 0 and 1",
    )
    parser.add_argument(
        "--speed-hz",
        type=positive_int,
        default=DEFAULT_SPEED_HZ,
        help=f"SPI speed in Hz; default {DEFAULT_SPEED_HZ}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print a machine-readable JSON summary after the text report",
    )
    return parser.parse_args(list(argv))


def spi_path(bus: int, chip_select: int) -> str:
    return f"/dev/spidev{bus}.{chip_select}"


def build_candidates(bus: int, chip_select: int | None) -> list[Candidate]:
    chip_selects = (chip_select,) if chip_select is not None else DEFAULT_CHIP_SELECTS
    return [Candidate(bus, cs) for cs in chip_selects]


def classify_identity(partnum: int, version: int) -> tuple[bool, str]:
    if partnum == 0x00 and version == 0x00:
        return False, "all-zero identity response"
    if partnum == 0xFF and version == 0xFF:
        return False, "all-0xff identity response"
    return True, "plausible CC1101 identity response"


def decide_exit_code(results: Iterable[CandidateResult]) -> int:
    result_list = list(results)
    if any(result.passed for result in result_list):
        return 0
    if any(result.operational_error for result in result_list):
        return 2
    return 1


def read_register(spi: object, address: int) -> int:
    # CC1101 status registers 0x30-0x3d require the burst bit to distinguish
    # them from command strobes. PARTNUM and VERSION are status registers.
    response = spi.xfer2([CC1101_READ_BURST | address, 0x00])
    if len(response) < 2:
        raise OSError(f"short SPI response: {response!r}")
    return int(response[1]) & 0xFF


def probe_candidate(candidate: Candidate, speed_hz: int, spidev_module: object) -> CandidateResult:
    path = candidate.path
    if not os.path.exists(path):
        return CandidateResult(path, False, None, None, "missing SPI device node", operational_error=True)

    spi = spidev_module.SpiDev()
    try:
        spi.open(candidate.bus, candidate.chip_select)
        spi.mode = 0
        spi.max_speed_hz = speed_hz
        partnum = read_register(spi, CC1101_PARTNUM)
        version = read_register(spi, CC1101_VERSION)
    except PermissionError as exc:
        return CandidateResult(path, False, None, None, f"permission error: {exc}", operational_error=True)
    except OSError as exc:
        return CandidateResult(path, False, None, None, f"SPI error: {exc}", operational_error=True)
    finally:
        close = getattr(spi, "close", None)
        if callable(close):
            close()

    passed, reason = classify_identity(partnum, version)
    return CandidateResult(path, passed, partnum, version, reason)


def import_spidev() -> object:
    try:
        import spidev  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "missing Python dependency 'spidev'; install it on the Raspberry Pi, "
            "for example with apt or the environment's package manager"
        ) from exc
    return spidev


def format_hex(value: int | None) -> str:
    return "n/a" if value is None else f"0x{value:02x}"


def print_report(results: list[CandidateResult], speed_hz: int, exit_code: int) -> None:
    print("CC1101 SPI connection test")
    print(f"Host: {socket.gethostname()}")
    print(f"Platform: {platform.platform()}")
    print(f"SPI mode: 0")
    print(f"SPI speed: {speed_hz} Hz")
    print()

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{result.path}: {status}")
        print(f"  PARTNUM: {format_hex(result.partnum)}")
        print(f"  VERSION: {format_hex(result.version)}")
        print(f"  Reason: {result.reason}")

    print()
    if exit_code == 0:
        print("Final result: PASS - at least one candidate returned a plausible CC1101 identity.")
    elif exit_code == 1:
        print("Final result: FAIL - SPI completed, but no candidate returned a plausible CC1101 identity.")
    else:
        print("Final result: ERROR - dependency, permission, or selected device availability blocked probing.")


def result_to_json(result: CandidateResult) -> dict[str, object]:
    return asdict(result)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    candidates = build_candidates(args.bus, args.chip_select)

    try:
        spidev_module = import_spidev()
    except RuntimeError as exc:
        results = [
            CandidateResult(candidate.path, False, None, None, str(exc), operational_error=True)
            for candidate in candidates
        ]
        print_report(results, args.speed_hz, 2)
        if args.json:
            print(json.dumps({"exit_code": 2, "results": [result_to_json(r) for r in results]}, indent=2))
        return 2

    results = [probe_candidate(candidate, args.speed_hz, spidev_module) for candidate in candidates]

    if args.chip_select is None and any(not result.operational_error for result in results):
        downgraded_results = []
        for result in results:
            if result.reason == "missing SPI device node":
                downgraded_results.append(
                    CandidateResult(result.path, False, None, None, result.reason, operational_error=False)
                )
            else:
                downgraded_results.append(result)
        results = downgraded_results

    exit_code = decide_exit_code(results)
    print_report(results, args.speed_hz, exit_code)
    if args.json:
        print(json.dumps({"exit_code": exit_code, "results": [result_to_json(r) for r in results]}, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
