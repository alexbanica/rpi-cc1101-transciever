# Implementation Plan: GDO0-Backed Somfy RTS Emitter

Status: Approved

Approved spec: `specs/spec-gdo0-backed-somfy-rts-emitter.md`

## Target Branch

- Continue from the current branch `feature/cc1101-connection-test` unless the implementation command finds the branch has changed.
- If implementation starts from another branch, create or switch to a dedicated branch named `feature/gdo0-backed-somfy-rts-emitter` before production changes.

## Scope

Implement live Somfy RTS emission for `emitter send` without `--dry-run` by generating the approved Somfy RTS pulse plan from the existing encoded frame, configuring CC1101 asynchronous TX, driving CC1101 `GDO0` through BCM GPIO `25`, updating documentation, and validating with local tests plus one authorized non-programming live command on `pi14.pi.home`.

## Architecture And Files

Update likely files:

- `AGENTS.md`
- `README.md`
- `cc1101_transceiver/controllers/cli.py`
- `cc1101_transceiver/shared/constants/defaults.py`
- `cc1101_transceiver/domains/interfaces/transceiver_interface.py`
- `cc1101_transceiver/applications/services/emit_service.py` only if the interface shape must carry TX options
- New application service, likely `cc1101_transceiver/applications/services/somfy_rts_pulse_encode_service.py`
- `cc1101_transceiver/infrastructures/cc1101/cc1101_transceiver_adapter.py`
- New infrastructure module, likely `cc1101_transceiver/infrastructures/cc1101/gpio_pulse_transmitter.py`
- Tests under `tests/`
- `tests/pulse_fixtures.py` if shared fixture helpers need TX pulse-plan assertions

Preserve:

- Existing profile JSON format.
- Existing capture JSON format.
- Existing Somfy RTS byte encoder/decoder behavior.
- Existing GDO0-backed receive capture behavior.
- Existing `emitter send --dry-run` hardware-free behavior.
- Existing `prog` guard.
- Existing `cc1101_connection_test.py` non-transmitting diagnostic.

## Implementation Steps

1. Add test-first pulse-plan coverage.
   - Add tests for generating a pulse plan from encoded frame `a78e8a589b2988`.
   - Assert the first frame contains wakeup, two hardware sync pulses, software sync, and 56-bit Manchester payload.
   - Assert repeated frames omit wakeup and use seven hardware sync pulses.
   - Assert generated payload pulses decode back to the same obfuscated frame through the existing pulse decoder.
   - Assert all generated pulse items have level `0` or `1` and positive integer `duration_us`.

2. Add deterministic Somfy RTS pulse generation.
   - Create a hardware-free application service that accepts `EncodedSomfyFrame` or obfuscated frame bytes and returns ordered pulse durations.
   - Use approved constants:
     - wakeup high `9415 us`
     - wakeup low `89565 us`
     - hardware sync high/low `2416 us`
     - software sync high `4550 us`
     - half-symbol `604 us`
     - first-frame hardware sync count `2`
     - repeated-frame hardware sync count `7`
     - default total frame count `2`
   - Generate Manchester payload bits in the same bit order used by `tests.pulse_fixtures.nominal_somfy_pulses`.
   - Keep this service free of GPIO, SPI, CC1101 imports, filesystem, and CLI parsing.

3. Extend the transceiver interface and CLI TX options.
   - Add `--tx-gpio` to `emitter send`, defaulting to BCM GPIO `25`.
   - Add a default constant for TX GPIO.
   - Pass the TX GPIO to the infrastructure adapter without affecting receive `--rx-gpio`.
   - If the existing `TransceiverInterface.transmit(frame, frequency_hz)` cannot carry TX GPIO cleanly, update the adapter constructor to accept `tx_gpio` while preserving tests with fakes.

4. Add GPIO pulse transmit infrastructure.
   - Add a `GpioPulseTransmitter` that uses `RPi.GPIO`/`rpi-lgpio` through a loader pattern similar to `GpioPulseCapture`.
   - Use BCM numbering.
   - Configure the TX GPIO as output and drive ordered pulse levels for the specified microsecond durations.
   - Use monotonic timing for pulse duration loops.
   - Ensure the GPIO is left low and cleaned up after success or failure.
   - Map missing dependency, permission, unsupported platform, and GPIO errors to `HardwareAccessError`.
   - Unit-test with a fake GPIO loader and fake monotonic/sleep behavior rather than real hardware.

5. Implement CC1101 asynchronous TX adapter behavior.
   - During implementation, inspect the installed `cc1101==3.0.0` API on the Pi or in the project virtualenv before choosing the exact call sequence.
   - Prefer the upstream `cc1101.CC1101.asynchronous_transmission()` API if it is available and can expose a context/session suitable for GPIO-driven data input.
   - If the public method is unavailable or insufficient, use the narrowest project-local adapter code necessary to configure ASK/OOK asynchronous TX with GDO0 data input.
   - Configure the requested base frequency and symbol rate where the selected API supports it.
   - Keep CC1101/SPI/GPIO imports inside infrastructure.
   - Convert CC1101 setup/runtime failures to `HardwareAccessError`.
   - Do not claim success until the pulse transmitter completes.

6. Preserve application service state semantics.
   - Keep dry-run behavior unchanged: no hardware access, print encoded fields, advance rolling code.
   - For live send, call `transceiver.transmit` before persisting the next rolling code.
   - Preserve the existing invariant that failed hardware send leaves the profile rolling code unchanged.
   - Ensure one `emitter send` invocation advances the profile by exactly one rolling code even though the pulse plan transmits repeated frames.

7. Update documentation and agent guidance.
   - Update `README.md` to document live TX support, `--tx-gpio`, wiring, examples, risk, `prog` guard, and profile advancement behavior.
   - Separate dry-run examples from live transmit examples.
   - Update validation/QA instructions to include one authorized live non-programming command.
   - Update `AGENTS.md` defaults and operational constraints so future agents know live TX has a specified path after implementation and validation.

8. Review and QA.
   - Review layer boundaries: pulse generation is application-level and hardware-free; GPIO/CC1101 access remains infrastructure-only.
   - Review rolling-code persistence on success/failure.
   - Review `prog` safety and CLI exit-code behavior.
   - Run local validation.
   - Run Pi QA including capture, clone-profile, dry-run, and one live non-programming command against the authorized device.

## Test-First Work

Write or update tests before production implementation for:

- Somfy RTS pulse-plan generation for first frame and repeated frames.
- Round-trip generated pulse plan through the existing pulse decoder.
- Deterministic integer timings and valid GPIO levels.
- GPIO pulse transmitter success path with fake GPIO.
- GPIO pulse transmitter cleanup and low-output behavior on failure.
- Missing GPIO dependency maps to `HardwareAccessError`.
- CC1101 adapter live transmit uses pulse generation and GPIO transmitter with fakes.
- Live `EmitService` success advances profile exactly once.
- Live `EmitService` failure does not advance profile.
- `emitter send --dry-run` remains hardware-free.
- CLI parses `--tx-gpio` and constructs the adapter with the selected BCM GPIO.
- Hardware errors from live send map to exit code `2`.
- `prog` remains blocked without `--allow-programming`.
- Existing capture/decode/clone-profile/persistence/diagnostic tests continue passing.

Do not require real GPIO or RF hardware for unit tests.

## Validation Commands

Run locally:

```bash
python3 -m compileall cc1101_transceiver cc1101_connection_test.py
python3 -m unittest discover -s tests -p 'test_*.py'
bash -n run.sh
bash -n run_cc1101_connection_test.sh
git diff --check
```

Run Pi QA on `pi14.pi.home`:

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
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh emitter send --profile /tmp/cc1101_gdo0_profile.json --command my'
```

The `receiver capture` QA command requires pressing the authorized Somfy RTS remote once during the timeout window.

The live `my` command requires observing the authorized Somfy device. If `my` is not a safe observable command for the device, use one explicit user-approved non-programming command such as `up` or `down`.

Do not run live `prog` during QA unless the user separately authorizes programming-mode testing.

## Code Review Expectations

Review against the approved spec:

- Live TX uses the existing decoded profile and encoded Somfy frame, not raw replay.
- TX GPIO default is BCM GPIO `25`.
- GPIO numbering is BCM everywhere user-visible or persisted.
- Pulse generation is deterministic and hardware-free.
- GPIO and CC1101 dependencies stay in infrastructure.
- Dry-run does not touch hardware.
- Live TX only advances profile after transmit success.
- Failed live TX leaves profile state unchanged.
- Profile advances once per command, not once per repeated frame.
- `prog` remains guarded.
- Existing receive capture and connection diagnostic behavior remain intact.
- README and `AGENTS.md` reflect the changed operational constraint.

## QA Expectations

- Local compile, unit tests, shell syntax checks, and `git diff --check` must pass.
- Pi QA must verify dependency installation, unit tests, CC1101 identity check, CLI help, GDO0 capture from an authorized remote press, inspect/decode, clone-profile, dry-run send, and one live non-programming command.
- If live TX does not produce observable device reaction, delivery must be marked draft unless the implementation can prove RF output independently and the remaining issue is explicitly documented.
- If the `cc1101` API or hardware prevents asynchronous TX, delivery must be marked draft and the exact blocker documented.

## Documentation Expectations

- README update is required.
- `AGENTS.md` update is required.
- No OpenAPI, HTTP fixtures, service unit files, Docker docs, MQTT docs, or UI docs are applicable.

## Commit And Push Expectations

- After implementation, review, QA, validation, documentation, and final acceptance, commit accepted changes.
- Use a non-draft commit only if required local validation and Pi live-TX QA pass.
- Use a `DRAFT` commit message if dependency installation, CC1101 asynchronous TX, GPIO transmit, tests, live device reaction, review, documentation, or Pi QA are blocked or failing.
- Push the implementation branch if repository access allows it.

## No-Research Constraint For Implementation

Implementation may inspect only:

- The approved spec.
- This approved plan.
- Affected repository files listed above.
- The installed `cc1101` API needed to execute the specified asynchronous TX behavior.
- Minimal official/upstream `cc1101` or TI CC1101 documentation only if the local installed API is insufficiently self-describing.

Implementation must not expand product scope, add integrations, change protocol support, or alter capture behavior beyond what the approved spec requires.

## Implementation Boundary

This plan is for the implementation command. After approval, implementation must start only in a fresh session, after explicitly clearing context, or after explicit user confirmation that continuing in this same context is intentional.
