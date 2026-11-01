# Implementation Plan: GDO0-Backed Somfy RTS Pulse Capture

Status: Approved

Approved spec: `specs/spec-gdo0-backed-pulse-capture.md`

## Target Branch

- Continue from the current branch `feature/cc1101-connection-test` unless the implementation command finds the branch has changed.
- If implementation starts from another branch, create or switch to a dedicated branch named `feature/gdo0-backed-pulse-capture` before production changes.

## Scope

Implement GDO0-backed receive capture for Somfy RTS using BCM GPIO `25`, decode captured pulse timing into the existing capture JSON format, update documentation, and keep live transmit unavailable except for `--dry-run`.

## Architecture And Files

Update likely files:

- `AGENTS.md`
- `README.md`
- `requirements.txt` if a GPIO dependency is required
- `cc1101_transceiver/controllers/cli.py`
- `cc1101_transceiver/applications/services/capture_service.py`
- `cc1101_transceiver/applications/services/decode_service.py`
- `cc1101_transceiver/applications/services/somfy_rts_codec_service.py`
- `cc1101_transceiver/domains/entities/capture.py` only if structured pulse DTOs are needed
- `cc1101_transceiver/domains/interfaces/transceiver_interface.py`
- `cc1101_transceiver/infrastructures/cc1101/cc1101_transceiver_adapter.py`
- New infrastructure module for GPIO edge capture if useful
- New deterministic application/domain service for Somfy RTS pulse timing decode
- `cc1101_transceiver/infrastructures/persistences/json_capture_repository.py` only if validation/normalization needs to be tightened
- `tests/`
- `tests/fixtures/`

Preserve:

- Existing `cc1101-somfy-rts-capture-v1` schema version.
- Existing decoded-frame object shape.
- Existing profile, clone, inspect, dry-run, and connection-test behavior.
- Live TX block in `Cc1101TransceiverAdapter.transmit`.

## Implementation Steps

1. Add test fixtures and pulse helpers first.
   - Create deterministic fixture pulse durations representing a nominal 56-bit Somfy RTS frame.
   - Include a pulse-only capture fixture with `raw.pulse_durations_us` and no `raw.obfuscated_frame_hex`.
   - Include rejected/noise timing examples for negative tests.

2. Add deterministic Somfy RTS pulse timing decode.
   - Add a hardware-free service that converts ordered pulse durations into Somfy RTS bits and a 7-byte obfuscated frame.
   - Keep timing constants and tolerances in application/domain-level code with clear names.
   - Support nominal wakeup, hardware sync, software sync, Manchester payload, and 56-bit payload decode.
   - Reject malformed sync, invalid payload length, impossible pulse levels, non-positive durations, and out-of-tolerance timing deterministically.
   - Feed the resulting `obfuscated_frame_hex` through the existing Somfy frame decoder for decoded fields.

3. Extend `receiver decode`.
   - Preserve existing `raw.obfuscated_frame_hex` decode behavior.
   - Add fallback decode from `raw.pulse_durations_us` when `obfuscated_frame_hex` is absent.
   - Keep decode hardware-free.
   - Ensure decoded captures are written back through the existing capture repository as today.

4. Implement GPIO pulse capture infrastructure.
   - Add a GPIO edge capture adapter scoped to infrastructure code.
   - Use BCM numbering and record `rx_gpio` and `gpio_numbering` in raw capture data.
   - Select a Raspberry Pi-compatible GPIO library based on installed/available dependencies during implementation; document the dependency choice.
   - Map missing dependency, permission, unsupported platform, SPI, and GPIO setup failures to `HardwareAccessError`.
   - Return no frames on timeout/no activity so the existing application service maps it to operational failure without writing output.

5. Update CC1101 receive adapter.
   - When `rx_gpio` is omitted, preserve the current explicit SPI-only capture limitation.
   - When `rx_gpio` is provided, configure CC1101 receive mode for the requested frequency and Somfy RTS-compatible ASK/OOK receive settings supported by the selected CC1101 API.
   - Capture GDO0 pulse durations until a decoded frame is obtained, the requested frame count is reached, or timeout expires.
   - Populate each `CaptureFrame.raw` with:
     - `capture_method: "gdo0-gpio-pulse"`
     - `gdo: "GDO0"`
     - `rx_gpio`
     - `gpio_numbering: "bcm"`
     - `pulse_durations_us`
     - `obfuscated_frame_hex` when decode succeeds
   - Populate `decoded` when decode succeeds.
   - Do not transmit RF.

6. Preserve and harden application behavior.
   - Ensure `CaptureService` writes only when frames are returned.
   - Ensure no invalid or partial capture JSON is written on timeout, undecodable pulses, or hardware failure.
   - Keep CLI exit-code mappings unchanged.
   - Keep `emitter send --dry-run` hardware-free.
   - Keep `emitter send` without `--dry-run` blocked with an explicit TX timing limitation.

7. Update documentation.
   - Update `README.md` hardware wiring with `GDO0` to physical pin `22` / BCM GPIO `25`.
   - Update receiver capture examples to include `--rx-gpio 25`.
   - Update JSON capture examples with GDO0 pulse raw data.
   - Update validation and Pi QA steps with the manual remote-press capture flow.
   - Update `AGENTS.md` defaults/operational constraints to reflect known GDO0 wiring and dry-run-only TX.

8. Review and QA.
   - Review layer boundaries: GPIO and CC1101 access must remain infrastructure-only.
   - Review timing decode determinism and failure modes.
   - Review output-file safety on failure paths.
   - Run local validation.
   - Run no-live-transmit Pi QA, including a manual `receiver capture --rx-gpio 25` while pressing the authorized remote.

## Test-First Work

Write or update tests before production implementation for:

- Pulse-duration validation and normalization.
- Nominal Somfy RTS pulse timing decode to `obfuscated_frame_hex`.
- Manchester decode for a 56-bit payload.
- Timing tolerance accept/reject boundaries.
- Rejection of malformed sync, short/long payloads, invalid pulse levels, and non-positive durations.
- `receiver decode` fallback from `raw.pulse_durations_us`.
- Capture service does not write output when adapter returns no frames.
- CLI/hardware error mapping for missing GPIO dependency or permission path.
- `receiver capture --rx-gpio 25` with a fake adapter writes expected raw and decoded fields.
- `emitter clone-profile` works from a GDO0-decoded capture fixture.
- `emitter send --dry-run` does not touch hardware.
- `emitter send` without `--dry-run` remains blocked.
- Existing Somfy codec, persistence, CLI, and diagnostic tests remain passing.

Do not require GPIO hardware for unit tests. Use fakes for GPIO edge events, CC1101 access, transceiver boundaries, and time.

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
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh receiver capture --rx-gpio 25 --out-file /tmp/cc1101_gdo0_capture.json --timeout 10 --frames 1'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh receiver inspect /tmp/cc1101_gdo0_capture.json'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh receiver decode /tmp/cc1101_gdo0_capture.json'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh emitter clone-profile --capture /tmp/cc1101_gdo0_capture.json --profile /tmp/cc1101_gdo0_profile.json --name qa-gdo0'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh emitter send --profile /tmp/cc1101_gdo0_profile.json --command up --dry-run'
```

The `receiver capture` QA command requires pressing the authorized Somfy RTS remote once during the timeout window.

Do not run live `emitter send` without `--dry-run`.

## Worker Splits

This plan can be implemented by the main agent without implementation workers. If the implementation command chooses to delegate, use disjoint write scopes:

- Test-focused worker: tests and fixtures only.
- Pulse decode worker: deterministic pulse decode service only.
- Infrastructure worker: GPIO/CC1101 receive adapter only.
- Documentation worker: README and `AGENTS.md` only.

Workers must not manage branches, commit, push, or alter behavior outside this approved spec.

## Code Review Expectations

Review against the approved spec:

- `GDO0` wiring is documented as physical pin `22` / BCM GPIO `25`.
- GPIO numbering is BCM everywhere user-visible or persisted.
- Domain/application decode logic is deterministic and hardware-free.
- GPIO and CC1101 dependencies stay in infrastructure.
- Capture JSON keeps the existing schema version and decoded-frame shape.
- Output files are not written on timeout, undecodable pulses, or hardware failure.
- `receiver decode` handles both `raw.obfuscated_frame_hex` and pulse-only raw captures.
- `emitter clone-profile` works from decoded GDO0 captures.
- Live TX remains blocked; `--dry-run` remains hardware-free.
- Existing connection diagnostic remains runnable.

## QA Expectations

- Local compile, unit tests, shell syntax checks, and `git diff --check` must pass.
- Pi QA must verify dependency installation, unit tests, CC1101 identity check, CLI help, GDO0 capture from an authorized remote press, inspect/decode of the captured JSON, clone-profile from the captured JSON, and dry-run send.
- Live motor/blind commands remain explicitly unvalidated.
- If GPIO or CC1101 receive API support blocks live capture, mark delivery draft and document the exact blocker.

## Documentation Expectations

- README update is required.
- `AGENTS.md` update is required.
- No OpenAPI, HTTP fixtures, service unit files, or Docker docs are applicable.

## Commit And Push Expectations

- After implementation, review, QA, validation, documentation, and final acceptance, commit accepted changes.
- Use a non-draft commit only if required local validation and no-live-transmit Pi QA pass.
- Use a `DRAFT` commit message if dependency installation, GPIO capture, CC1101 receive configuration, tests, or Pi QA are blocked or failing.
- Push the implementation branch if repository access allows it.

## Implementation Boundary

This plan is for the implementation command. After approval, implementation must start only in a fresh session, after explicitly clearing context, or after explicit user confirmation that continuing in this same context is intentional.
