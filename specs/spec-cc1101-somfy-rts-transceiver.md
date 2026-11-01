# CC1101 Somfy RTS Transceiver

Status: Approved

## Purpose

Implement a Python 3 CC1101 transceiver project that can capture, decode, persist, and emit Somfy RTS-compatible frames for a Somfy Situo 1 RTS Pure II NE 1870404A remote-control workflow.

The first product goal is cloning-oriented operation: observe an existing remote, derive a local profile from captured RTS frames, and emit future RTS commands using that cloned transmitter identity and rolling-code state. The project must not require pairing the Raspberry Pi as a new Somfy RTS remote.

## Problem Statement

The repository currently contains only a standalone CC1101 SPI reachability diagnostic. The CC1101 is reachable on `pi14.pi.home` through `/dev/spidev0.0`, but there is no reusable Python package, no receiver/emitter CLI, no Somfy RTS encoder/decoder, no persistence for cloned remote state, and no DDD/onion project structure.

## Scope

- Convert the repository into a Python 3 project with DDD + Onion architecture.
- Keep the existing CC1101 connection diagnostic available.
- Add a repository-local `run.sh` wrapper that can run receiver and emitter workflows.
- Add a `cc1101_transceiver` Python package with:
  - domain entities, DTOs, and interfaces
  - application services for capture, inspect, clone-profile creation, and emission orchestration
  - infrastructure adapters for CC1101 access and JSON persistence
  - CLI controllers and request/response DTOs
  - shared constants for defaults, JSON keys, exit codes, and static CLI text
- Add receiver functionality:
  - raw capture mode for CC1101/Somfy RF timing observations
  - inspect mode for saved capture/profile files
  - decode mode for Somfy RTS frame extraction where captured data is decodable
- Add emitter functionality:
  - initialize a profile manually
  - clone a profile from a decoded capture
  - send RTS commands using a profile
  - update and persist rolling-code state after successful command generation
- Support Somfy RTS commands:
  - `up`
  - `down`
  - `my`
  - `prog`
- Gate `prog` behind an explicit safety flag.
- Add unit tests for deterministic protocol, persistence, CLI parsing, and application orchestration boundaries because live motor/blind QA is intentionally deferred.
- Add manual Pi QA that does not send real blind-control commands.

## Out Of Scope

- Pairing the Pi as a new RTS remote.
- Live transmission against the real motor/blind during initial QA.
- Guaranteeing indefinite cloned-control reliability when the original physical remote is also used after cloning.
- Brute forcing, bypassing, or defeating unknown rolling-code state beyond captured/decoded Somfy RTS semantics.
- Supporting non-Somfy RF protocols.
- Supporting encrypted or non-RTS Somfy protocols such as io-homecontrol.
- Building an HTTP API, daemon, MQTT bridge, scheduler, or HomeKit/Homebridge integration.
- Automatic system package installation from `run.sh`.
- Requiring unit tests for the pre-existing standalone connection diagnostic beyond syntax/import validation.

## Definitions

- CC1101: TI sub-1 GHz transceiver connected to Raspberry Pi SPI.
- RTS: Somfy Radio Technology Somfy protocol used by the target Situo remote.
- Clone profile: a JSON file containing a remote identity and rolling-code state derived from capture or supplied manually.
- Raw capture: persisted RF/timing data that may or may not decode into a Somfy RTS frame.
- Decoded frame: structured Somfy RTS fields extracted from a raw capture.
- Rolling code: monotonically advancing Somfy RTS value accepted by a receiver only within its expected future window.
- Emitter: CLI mode that encodes and transmits Somfy RTS commands through CC1101.
- Receiver: CLI mode that captures, decodes, or inspects RF data.
- Programming command: Somfy RTS `prog` command used for programming workflows and therefore guarded from accidental emission.

## Inputs And Constraints

- Target remote: Somfy Situo 1 RTS Pure II NE 1870404A.
- Target Pi for QA: `pi14.pi.home`.
- Known successful CC1101 SPI path: `/dev/spidev0.0`.
- Current wiring:
  - VCC to Pi physical pin `1`
  - GND to Pi physical pin `6`
  - MOSI to Pi physical pin `19`
  - MISO to Pi physical pin `21`
  - SCK to Pi physical pin `23`
  - CSN to Pi physical pin `24`
- No GDO pin is currently specified as wired.
- Default SPI bus is `0`.
- Default SPI chip-select is `0`.
- Default Somfy RTS carrier frequency is `433420000` Hz.
- Python runtime is Python 3.
- The implementation should use the published Python `cc1101` package where it supports the required CC1101 operations cleanly.
- The infrastructure layer may add a project-local low-level CC1101 adapter only for behavior not exposed by the `cc1101` package.
- The public `cc1101` package documents Raspberry Pi SPI wiring matching the current SPI wiring and notes that `GDO0` is used for asynchronous transmission.
- Because no GDO wiring is specified, the first implementation must not require live asynchronous GDO-based transmission or capture for automated QA.
- If implementation research proves that required raw Somfy RTS transmit or receive behavior cannot be supported over SPI alone, the implementation must stop and request a spec update that adds GDO wiring requirements instead of silently changing behavior.

## Architecture Requirements

The project must follow the DDD + Onion style used by nearby Raspberry Pi RF projects.

Expected package layout:

```text
cc1101_transceiver/
  applications/
    services/
  controllers/
    requests/
    responses/
  domains/
    dtos/
    entities/
    interfaces/
  infrastructures/
    cc1101/
    persistences/
  shared/
    constants/
```

Layering rules:

- `domains` contains pure entities, DTOs, and interfaces.
- `applications` contains business services and orchestration.
- `infrastructures` contains CC1101, SPI, filesystem, JSON, and runtime adapter implementations.
- `controllers` contains CLI parsing, CLI request/response DTOs, and command coordination.
- `shared/constants` contains defaults, JSON keys, format names, exit codes, and static CLI text.
- Dependencies point inward.
- Domain code must not import CLI parsing, filesystem persistence, CC1101 libraries, SPI libraries, Raspberry Pi GPIO libraries, subprocess, SSH, or `rsync`.
- Interfaces use the `Interface` suffix.
- Keep one primary class per file where practical.

## CLI Behavior

`run.sh` must:

- resolve the repository root from its own location
- prefer `.venv/bin/python` when executable
- otherwise use `python3`
- run `python -m cc1101_transceiver "$@"`
- forward all arguments unchanged
- preserve the module CLI exit code

Receiver commands:

```bash
./run.sh receiver capture --out-file situo_capture.json
./run.sh receiver inspect situo_capture.json
./run.sh receiver decode situo_capture.json
```

Emitter commands:

```bash
./run.sh emitter init-profile --profile profiles/blind.json --address <hex> --rolling-code <int>
./run.sh emitter clone-profile --capture situo_capture.json --profile profiles/blind.json --name <name>
./run.sh emitter send --profile profiles/blind.json --command up
./run.sh emitter send --profile profiles/blind.json --command down
./run.sh emitter send --profile profiles/blind.json --command my
./run.sh emitter send --profile profiles/blind.json --command prog --allow-programming
```

Common RF/CC1101 options:

- `--spi-bus`, default `0`
- `--spi-chip-select`, default `0`
- `--frequency-hz`, default `433420000`
- `--symbol-rate`, default chosen by the implementation from Somfy RTS timing requirements and documented in README
- `--dry-run`, available for emitter `send`, encodes and prints/persists the frame without transmitting

Receiver capture options:

- `--out-file`, required for capture
- `--timeout`, default `10.0`
- `--frames`, default `1`
- `--store-mode`, allowed `selected` or `all`, default `selected`
- `--select-index`, default `0`
- `--rx-gpio`, optional and only meaningful when a GDO-backed adapter is implemented

Emitter profile options:

- `--profile`, required
- `--name`, optional user label
- `--address`, required for manual profile creation
- `--rolling-code`, required for manual profile creation unless an explicit implementation-supported default is documented
- `--command`, one of `up`, `down`, `my`, `prog`
- `--allow-programming`, required when `--command prog`

## Persistence Formats

Raw capture JSON format:

```json
{
  "format": "cc1101-somfy-rts-capture-v1",
  "frequency_hz": 433420000,
  "spi_bus": 0,
  "spi_chip_select": 0,
  "frames": [
    {
      "index": 0,
      "captured_at": "2026-05-20T00:00:00Z",
      "raw": {},
      "decoded": {
        "protocol": "somfy-rts",
        "address": "a1b2c3",
        "rolling_code": 1234,
        "command": "up",
        "valid_checksum": true
      }
    }
  ]
}
```

Clone profile JSON format:

```json
{
  "format": "cc1101-somfy-rts-profile-v1",
  "name": "living-room-blind",
  "protocol": "somfy-rts",
  "frequency_hz": 433420000,
  "address": "a1b2c3",
  "rolling_code": 1235,
  "source": {
    "type": "capture",
    "capture_file": "situo_capture.json"
  }
}
```

Persistence invariants:

- `format` must exactly identify the schema version.
- Profile address must be stored as a stable lowercase hexadecimal string.
- Profile rolling code must be stored as an integer.
- Emission must increment and persist the rolling code only after the frame is encoded and either transmitted successfully or intentionally persisted in dry-run mode according to the command output.
- Failed validation or failed CC1101 access must not advance the stored rolling code.

## Deterministic Behavior

1. The CLI exits with deterministic status codes:
   - `0` success
   - `1` no capture, no decoded frame, or command could not be completed for expected operational reasons
   - `2` runtime dependency, CC1101 access, permission, SPI, or hardware setup error
   - `64` invalid CLI arguments or invalid input file
2. `receiver capture` writes a capture file only when at least one capture frame is obtained.
3. `receiver capture` must not write partial or invalid JSON if capture fails.
4. `receiver inspect` reads capture/profile JSON without touching hardware.
5. `receiver decode` reads capture JSON and prints decoded Somfy RTS frame fields where available.
6. `emitter init-profile` writes a profile from manually supplied address and rolling code.
7. `emitter clone-profile` selects a decoded Somfy RTS frame from a capture and writes a clone profile with the captured address and the next rolling code.
8. `emitter clone-profile` fails deterministically when the capture has no valid decoded Somfy RTS frame.
9. `emitter send --dry-run` encodes the RTS frame and reports the frame fields without transmitting RF.
10. `emitter send` without `--dry-run` attempts CC1101 transmission through the infrastructure adapter.
11. `emitter send --command prog` fails unless `--allow-programming` is supplied.
12. Somfy RTS command encoding and decoding must be implemented in deterministic domain/application code and covered by unit tests.
13. The implementation must preserve a generic command/profile naming mechanism; generated files and command labels are user-supplied and not hard-coded to one blind or room.
14. Raw RF replay is not the primary control path. The control path is decoded Somfy RTS profile state plus deterministic frame generation.
15. The README must explicitly warn that using the original physical remote after cloning can advance rolling-code state and may desynchronize the clone profile.

## Assumptions

- The user is authorized to capture and control their own Somfy RTS device.
- The Situo 1 RTS Pure II uses Somfy RTS at `433.42 MHz`.
- The desired clone behavior is for authorized local device automation, not unauthorized access.
- Capturing at least one valid frame from the original remote is acceptable input for clone-profile creation.
- Unit tests are acceptable and now required for protocol and orchestration validation because live motor/blind QA is deferred.
- Pi hardware QA can verify SPI access, dependency installation, CLI help, dry-run encode, JSON persistence, and non-emitting inspection paths on `pi14.pi.home`.

## Impact And Regression Considerations

- The existing connection diagnostic should remain runnable.
- Introducing a package structure must not remove the ability to perform a simple CC1101 identity check.
- Adding `cc1101` as a dependency may require Raspberry Pi OS packages such as `python3-spidev`.
- The published `cc1101` package is GPL-3.0-or-later; dependency/license implications must be documented if it is added to project requirements.
- Real RF transmission may affect nearby Somfy RTS receivers, so live command transmission is excluded from first QA.
- Rolling-code state must be handled carefully to avoid creating a profile that immediately desynchronizes from the receiver.
- If the CC1101 cannot perform required Somfy RTS raw timing behavior without GDO wiring, the implementation must not fake support; it must surface the blocker clearly.

## Validation Plan

Local validation:

- `python3 -m compileall cc1101_transceiver cc1101_connection_test.py`
- `python3 -m unittest discover -s tests -p 'test_*.py'`
- `bash -n run.sh`
- `bash -n run_cc1101_connection_test.sh`
- `git diff --check`

Required unit-test coverage:

- Somfy RTS command mapping.
- Somfy RTS checksum validation.
- Somfy RTS frame obfuscation/deobfuscation.
- Decode of known captured/fixture frame bytes.
- Encode from profile and command.
- Clone-profile rolling-code selection from decoded capture.
- Profile JSON read/write validation.
- Capture JSON read/write validation.
- CLI argument parsing and exit-code mapping.
- `prog` safety gating.
- Dry-run emission does not touch CC1101 hardware adapter.

Pi QA on `pi14.pi.home`:

- Deploy with `rsync`.
- Create or reuse a virtual environment.
- Install project dependencies.
- Run compile validation.
- Run unit tests.
- Run `./run_cc1101_connection_test.sh --chip-select 0`.
- Run `./run.sh --help`.
- Run `./run.sh receiver inspect` against fixture/sample capture files without hardware transmission.
- Run `./run.sh emitter init-profile` into `/tmp` or a QA profile path.
- Run `./run.sh emitter send --profile <qa-profile> --command up --dry-run`.
- Do not send live `up`, `down`, `my`, or `prog` RF commands during initial QA.

## Documentation Requirements

- Update README with:
  - hardware wiring
  - required dependencies
  - project structure
  - `run.sh` usage
  - receiver capture/inspect/decode examples
  - emitter init-profile/clone-profile/send examples
  - profile and capture JSON examples
  - dry-run QA workflow
  - warning about Somfy RTS rolling-code desynchronization
  - warning that live `prog` is guarded and should not be sent accidentally
- Add or update repository-level `AGENTS.md` with the DDD/onion layout, layer boundaries, defaults, validation commands, and QA target for future agents.

## Research Notes

- The existing project diagnostic has already shown `pi14.pi.home` can reach the CC1101 on `/dev/spidev0.0`.
- PyPI documents `cc1101` version `3.0.0`, released May 4, 2023, as a Python library and CLI for CC1101 transceivers.
- The `cc1101` package documents direct Raspberry Pi SPI wiring that matches the current SPI pins and states that `GDO0` is used by asynchronous transmission.
- The implementation must inspect the installed `cc1101` API during implementation before deciding whether to use it directly for all RF behavior or wrap it with a narrower infrastructure adapter.
