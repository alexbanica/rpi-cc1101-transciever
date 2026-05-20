# Implementation Plan: CC1101 Somfy RTS Transceiver

Status: Approved

Approved spec: `specs/spec-cc1101-somfy-rts-transceiver.md`

## Target Branch

- Continue from the current feature branch unless the implementation command finds the branch has changed.
- If implementation starts from another branch, create or switch to a dedicated branch named `feature/cc1101-somfy-rts-transceiver` before production changes.

## Scope

Implement the approved clone-oriented Somfy RTS transceiver project using Python 3, DDD + Onion architecture, a `run.sh` module wrapper, JSON capture/profile persistence, deterministic Somfy RTS encode/decode services, receiver/emitter CLIs, unit tests, code review, and no-live-transmit Raspberry Pi QA.

## Architecture And Files

Add/update:

- `AGENTS.md`
- `README.md`
- `requirements.txt`
- `setup.py` or `pyproject.toml`, choosing the simplest packaging style consistent with the nearby Raspberry Pi projects
- `run.sh`
- `cc1101_transceiver/__init__.py`
- `cc1101_transceiver/__main__.py`
- `cc1101_transceiver/domains/entities/`
- `cc1101_transceiver/domains/dtos/`
- `cc1101_transceiver/domains/interfaces/`
- `cc1101_transceiver/applications/services/`
- `cc1101_transceiver/infrastructures/cc1101/`
- `cc1101_transceiver/infrastructures/persistences/`
- `cc1101_transceiver/controllers/`
- `cc1101_transceiver/controllers/requests/`
- `cc1101_transceiver/controllers/responses/`
- `cc1101_transceiver/shared/constants/`
- `cc1101_transceiver/shared/exceptions.py`
- `tests/`
- fixture files under `tests/fixtures/` or `examples/` when needed for deterministic decode/profile validation

Preserve:

- `cc1101_connection_test.py`
- `run_cc1101_connection_test.sh`
- existing approved connection-test spec and plan

## Implementation Steps

1. Add repository agent guidance.
   - Document DDD/onion layering.
   - Document package layout, naming standards, defaults, validation commands, and `pi14.pi.home` no-live-transmit QA.

2. Add packaging/runtime scaffolding.
   - Add dependency metadata for Python 3 and the `cc1101` package.
   - Include `spidev` dependency guidance where appropriate.
   - Add `run.sh` that resolves repo root, prefers `.venv/bin/python`, falls back to `python3`, runs `python -m cc1101_transceiver "$@"`, forwards arguments unchanged, and preserves exit code.

3. Build domain model.
   - Add Somfy command entity/value definitions for `up`, `down`, `my`, `prog`.
   - Add RTS frame/profile/capture entities and DTOs.
   - Add domain-facing interfaces with `Interface` suffix for transceiver access and persistence boundaries.
   - Keep domain code pure and independent of CLI, filesystem, SPI, and CC1101 libraries.

4. Implement Somfy RTS protocol services.
   - Encode deterministic RTS frames from profile state and command.
   - Decode known RTS frame bytes/timing fixtures into address, rolling code, command, and checksum validity.
   - Implement checksum, obfuscation/deobfuscation, and command mapping in deterministic code.
   - Keep raw timing modulation specifics behind domain/application DTOs so the CC1101 adapter can evolve if GDO wiring becomes necessary.

5. Implement persistence.
   - Add JSON capture reader/writer for `cc1101-somfy-rts-capture-v1`.
   - Add JSON profile reader/writer for `cc1101-somfy-rts-profile-v1`.
   - Validate required fields, address format, rolling-code type, format version, and decoded-frame presence for clone-profile.
   - Write files atomically or in a way that avoids partial invalid JSON on failure.

6. Implement application services.
   - `CaptureService`: orchestrates receiver capture through a transceiver interface and persistence.
   - `InspectService`: inspects capture/profile JSON without hardware access.
   - `DecodeService`: decodes capture content and reports decoded fields.
   - `CloneProfileService`: creates a profile from selected decoded capture data and advances to next rolling code.
   - `ProfileInitializationService`: creates manual profiles from address and rolling code.
   - `EmitService`: validates profile/command, gates `prog`, encodes frames, supports dry-run, calls transceiver adapter only when not dry-run, and persists rolling-code advancement only after successful encode/transmit/dry-run according to spec.

7. Implement infrastructure adapters.
   - Add a narrow CC1101 adapter wrapping the published `cc1101` package for base-frequency and transmit operations that are actually supported.
   - Add an explicit runtime error path if the requested RF operation requires GDO wiring or unsupported CC1101-library behavior.
   - Do not fake live capture/transmission success.
   - Keep receive/capture adapter behavior conservative until implementation confirms the installed `cc1101` API can support it.

8. Implement CLI controllers.
   - Add top-level subcommands:
     - `receiver capture`
     - `receiver inspect`
     - `receiver decode`
     - `emitter init-profile`
     - `emitter clone-profile`
     - `emitter send`
   - Implement approved arguments and defaults.
   - Map validation/runtime/no-capture errors to approved exit codes.
   - Print concise, parseable summaries with enough detail for QA.

9. Update README.
   - Document wiring, dependency installation, project structure, CLI examples, JSON formats, dry-run workflow, rolling-code desynchronization warning, `prog` guard, and no-live-transmit initial QA.

10. Preserve connection diagnostic.
   - Keep the existing diagnostic scripts runnable.
   - Optionally document both old diagnostic and new package CLI side by side.

## Test-First Work

Unit tests are required despite the user's initial note because live blind-control QA is deferred and the approved spec requires deterministic tests.

Create tests before or alongside production implementation for:

- Somfy RTS command mapping.
- Somfy RTS checksum validation.
- Somfy RTS frame obfuscation/deobfuscation.
- Decode of known fixture frame bytes.
- Encode from profile and command.
- Clone-profile rolling-code selection from decoded capture.
- Profile JSON read/write validation.
- Capture JSON read/write validation.
- CLI argument parsing and exit-code mapping.
- `prog` safety gating.
- Dry-run emission does not call CC1101 hardware adapter.
- Failed hardware/runtime paths do not advance the rolling code.
- `run.sh` help or wrapper behavior where practical without relying on hardware.

Do not require live CC1101 hardware for unit tests. Use fakes for transceiver, persistence, clock, and hardware boundaries.

## Validation Commands

Run locally:

```bash
python3 -m compileall cc1101_transceiver cc1101_connection_test.py
python3 -m unittest discover -s tests -p 'test_*.py'
bash -n run.sh
bash -n run_cc1101_connection_test.sh
git diff --check
```

Run no-live-transmit Pi QA on `pi14.pi.home`:

```bash
rsync -az --delete --exclude .git --exclude .venv ./ pi14.pi.home:~/rpi-cc1101-transciever/
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && python -m compileall cc1101_transceiver cc1101_connection_test.py'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && python -m unittest discover -s tests -p "test_*.py"'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && ./run_cc1101_connection_test.sh --chip-select 0'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh --help'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh emitter init-profile --profile /tmp/cc1101_qa_profile.json --address a1b2c3 --rolling-code 1234'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh emitter send --profile /tmp/cc1101_qa_profile.json --command up --dry-run'
```

Do not run live `emitter send` without `--dry-run` during this implementation unless the spec is amended and reapproved.

## Code Review Expectations

Review against the approved spec and plan:

- Layer dependencies point inward.
- Domain/protocol code is deterministic and hardware-free.
- Interfaces use `Interface` suffix.
- Profile rolling-code advancement is correct and failure-safe.
- `prog` cannot be emitted without `--allow-programming`.
- Dry-run does not touch the CC1101 adapter.
- Receiver/decoder failures are deterministic and do not write invalid output.
- Unsupported CC1101/GDO behavior is reported explicitly instead of faked.
- Existing connection diagnostic still works.
- README and `AGENTS.md` match implemented behavior.

## QA Expectations

- Local unit and compile validation must pass.
- Pi QA must verify dependency installation, unit tests, CC1101 identity check, CLI help, manual profile creation, and dry-run emission.
- Live motor/blind commands are explicitly unvalidated in this delivery.
- If the published `cc1101` package or hardware wiring blocks real capture/transmit implementation, mark delivery draft and document the exact blocker and required wiring/API change.

## Documentation Expectations

- README update is required.
- `AGENTS.md` update is required.
- No OpenAPI or `.http` artifacts are applicable.

## Commit And Push Expectations

- After implementation, review, QA, validation, and documentation, commit the accepted changes.
- Use a non-draft commit only if required local validation and no-live-transmit Pi QA pass.
- Use a `DRAFT` commit message if dependency installation, CC1101 adapter validation, unit tests, or Pi QA are blocked or failing.
- Push the implementation branch if repository access allows it.

## Implementation Boundary

This plan is for the implementation command. After approval, implementation must start only in a fresh session, after explicitly clearing context, or after explicit user confirmation that continuing in this same context is intentional.
