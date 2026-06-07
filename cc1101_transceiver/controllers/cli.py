from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

from cc1101_transceiver.applications.services.capture_service import CaptureService
from cc1101_transceiver.applications.services.clone_profile_service import CloneProfileService
from cc1101_transceiver.applications.services.decode_service import DecodeService
from cc1101_transceiver.applications.services.emit_service import EmitService
from cc1101_transceiver.applications.services.inspect_service import InspectService
from cc1101_transceiver.applications.services.profile_initialization_service import ProfileInitializationService
from cc1101_transceiver.applications.services.somfy_rts_codec_service import SomfyRtsCodecService
from cc1101_transceiver.domains.entities.somfy_command import SomfyCommand
from cc1101_transceiver.infrastructures.cc1101.cc1101_transceiver_adapter import Cc1101TransceiverAdapter
from cc1101_transceiver.infrastructures.persistences.json_capture_repository import JsonCaptureRepository
from cc1101_transceiver.infrastructures.persistences.json_profile_repository import JsonProfileRepository
from cc1101_transceiver.shared.constants.defaults import (
    DEFAULT_CAPTURE_FRAMES,
    DEFAULT_CAPTURE_SELECT_INDEX,
    DEFAULT_CAPTURE_STORE_MODE,
    DEFAULT_CAPTURE_TIMEOUT,
    DEFAULT_FREQUENCY_HZ,
    DEFAULT_SPI_BUS,
    DEFAULT_SPI_CHIP_SELECT,
    DEFAULT_SYMBOL_RATE,
    DEFAULT_TX_GPIO_BCM,
)
from cc1101_transceiver.shared.constants.exit_codes import EXIT_HARDWARE, EXIT_OPERATIONAL, EXIT_SUCCESS, EXIT_USAGE
from cc1101_transceiver.shared.exceptions import HardwareAccessError, InvalidInputError, OperationalError


class FriendlyArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise InvalidInputError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = FriendlyArgumentParser(prog="cc1101-transceiver")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    receiver = subparsers.add_parser("receiver")
    receiver_sub = receiver.add_subparsers(dest="receiver_command", required=True)
    capture = receiver_sub.add_parser("capture")
    capture.add_argument("--out-file", required=True)
    capture.add_argument("--timeout", type=float, default=DEFAULT_CAPTURE_TIMEOUT)
    capture.add_argument("--frames", type=int, default=DEFAULT_CAPTURE_FRAMES)
    capture.add_argument("--store-mode", choices=["selected", "all"], default=DEFAULT_CAPTURE_STORE_MODE)
    capture.add_argument("--select-index", type=int, default=DEFAULT_CAPTURE_SELECT_INDEX)
    capture.add_argument("--rx-gpio", type=int)
    add_rf_options(capture)
    inspect = receiver_sub.add_parser("inspect")
    inspect.add_argument("path")
    decode = receiver_sub.add_parser("decode")
    decode.add_argument("capture")

    emitter = subparsers.add_parser("emitter")
    emitter_sub = emitter.add_subparsers(dest="emitter_command", required=True)
    init_profile = emitter_sub.add_parser("init-profile")
    init_profile.add_argument("--profile", required=True)
    init_profile.add_argument("--address", required=True)
    init_profile.add_argument("--rolling-code", type=int, required=True)
    init_profile.add_argument("--name")
    add_rf_options(init_profile)
    clone_profile = emitter_sub.add_parser("clone-profile")
    clone_profile.add_argument("--capture", required=True)
    clone_profile.add_argument("--profile", required=True)
    clone_profile.add_argument("--name")
    send = emitter_sub.add_parser("send")
    send.add_argument("--profile", required=True)
    send.add_argument("--command", choices=SomfyCommand.labels(), required=True)
    send.add_argument("--allow-programming", action="store_true")
    send.add_argument("--dry-run", action="store_true")
    send.add_argument("--tx-gpio", type=int, default=DEFAULT_TX_GPIO_BCM)
    add_rf_options(send)
    return parser


def add_rf_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--spi-bus", type=int, default=DEFAULT_SPI_BUS)
    parser.add_argument("--spi-chip-select", type=int, default=DEFAULT_SPI_CHIP_SELECT)
    parser.add_argument("--frequency-hz", type=int, default=DEFAULT_FREQUENCY_HZ)
    parser.add_argument("--symbol-rate", type=int, default=DEFAULT_SYMBOL_RATE)


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
        return dispatch(args)
    except SystemExit as exc:
        return int(exc.code)
    except (InvalidInputError, ValueError) as exc:
        print(f"invalid input: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except OperationalError as exc:
        print(f"operation failed: {exc}", file=sys.stderr)
        return EXIT_OPERATIONAL
    except HardwareAccessError as exc:
        print(f"hardware error: {exc}", file=sys.stderr)
        return EXIT_HARDWARE


def dispatch(args: argparse.Namespace) -> int:
    capture_repository = JsonCaptureRepository()
    profile_repository = JsonProfileRepository()
    codec = SomfyRtsCodecService()

    if args.mode == "receiver":
        if args.receiver_command == "capture":
            adapter = Cc1101TransceiverAdapter(args.spi_bus, args.spi_chip_select, args.rx_gpio)
            capture = CaptureService(adapter, capture_repository).capture(
                Path(args.out_file),
                args.timeout,
                args.frames,
                args.frequency_hz,
                args.spi_bus,
                args.spi_chip_select,
            )
            print(f"capture_file={args.out_file} frames={len(capture.frames)} frequency_hz={capture.frequency_hz}")
            return EXIT_SUCCESS
        if args.receiver_command == "inspect":
            summary = InspectService().inspect(Path(args.path))
            print(" ".join(f"{key}={value}" for key, value in summary.items()))
            return EXIT_SUCCESS
        if args.receiver_command == "decode":
            capture = DecodeService(capture_repository, codec).decode(Path(args.capture))
            for frame in capture.frames:
                if frame.decoded is None:
                    continue
                decoded = frame.decoded
                print(
                    " ".join(
                        [
                            f"index={frame.index}",
                            f"protocol={decoded.protocol}",
                            f"address={decoded.address}",
                            f"rolling_code={decoded.rolling_code}",
                            f"command={decoded.command}",
                            f"valid_checksum={str(decoded.valid_checksum).lower()}",
                        ]
                    )
                )
            return EXIT_SUCCESS

    if args.mode == "emitter":
        if args.emitter_command == "init-profile":
            profile = ProfileInitializationService(profile_repository).initialize(
                Path(args.profile),
                args.address,
                args.rolling_code,
                args.name,
                args.frequency_hz,
            )
            print(f"profile={args.profile} address={profile.address} rolling_code={profile.rolling_code}")
            return EXIT_SUCCESS
        if args.emitter_command == "clone-profile":
            profile = CloneProfileService(capture_repository, profile_repository).clone(
                Path(args.capture),
                Path(args.profile),
                args.name,
            )
            print(f"profile={args.profile} address={profile.address} rolling_code={profile.rolling_code}")
            return EXIT_SUCCESS
        if args.emitter_command == "send":
            adapter = Cc1101TransceiverAdapter(
                args.spi_bus,
                args.spi_chip_select,
                tx_gpio=args.tx_gpio,
                symbol_rate=args.symbol_rate,
            )
            result = EmitService(profile_repository, codec, adapter).send(
                Path(args.profile),
                SomfyCommand.from_label(args.command),
                args.dry_run,
                args.allow_programming,
            )
            print(
                " ".join(
                    [
                        f"command={result.encoded_frame.command.label}",
                        f"address={result.encoded_frame.address}",
                        f"rolling_code={result.encoded_frame.rolling_code}",
                        f"frame={result.encoded_frame.obfuscated_hex}",
                        f"dry_run={str(result.dry_run).lower()}",
                        f"transmitted={str(result.transmitted).lower()}",
                        f"next_rolling_code={result.next_rolling_code}",
                    ]
                )
            )
            return EXIT_SUCCESS

    raise InvalidInputError("unsupported command")
