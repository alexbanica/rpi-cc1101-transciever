from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cc1101_transceiver.applications.services.somfy_rts_codec_service import SomfyRtsCodecService
from cc1101_transceiver.domains.entities.somfy_command import SomfyCommand
from cc1101_transceiver.domains.entities.somfy_frame import EncodedSomfyFrame
from cc1101_transceiver.domains.interfaces.profile_repository_interface import ProfileRepositoryInterface
from cc1101_transceiver.domains.interfaces.transceiver_interface import TransceiverInterface
from cc1101_transceiver.shared.exceptions import ProgrammingCommandBlockedError


@dataclass(frozen=True)
class EmitResult:
    encoded_frame: EncodedSomfyFrame
    dry_run: bool
    transmitted: bool
    next_rolling_code: int


class EmitService:
    def __init__(
        self,
        profile_repository: ProfileRepositoryInterface,
        codec: SomfyRtsCodecService,
        transceiver: TransceiverInterface,
    ):
        self.profile_repository = profile_repository
        self.codec = codec
        self.transceiver = transceiver

    def send(
        self,
        profile_path: Path,
        command: SomfyCommand,
        dry_run: bool,
        allow_programming: bool,
    ) -> EmitResult:
        if command is SomfyCommand.PROG and not allow_programming:
            raise ProgrammingCommandBlockedError("prog requires --allow-programming")
        profile = self.profile_repository.read(profile_path)
        encoded = self.codec.encode(profile, command)
        if not dry_run:
            self.transceiver.transmit(encoded, profile.frequency_hz)
        next_profile = profile.with_rolling_code(profile.rolling_code + 1)
        self.profile_repository.write(profile_path, next_profile)
        return EmitResult(encoded, dry_run=dry_run, transmitted=not dry_run, next_rolling_code=next_profile.rolling_code)
