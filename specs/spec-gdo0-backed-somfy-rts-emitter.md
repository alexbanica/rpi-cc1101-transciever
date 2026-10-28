# GDO0-Backed Somfy RTS Emitter

Status: Approved

## Purpose

Implement live Somfy RTS RF emission through the existing Raspberry Pi and CC1101 hardware so a profile derived from an authorized remote capture can send future `up`, `down`, `my`, and guarded `prog` commands.

The intended workflow remains clone-oriented: capture and decode an authorized Somfy RTS remote, create a local clone profile with the next rolling code, then transmit deterministic Somfy RTS frames from that profile.

## Problem Statement

The repository can currently encode Somfy RTS frames and advance clone-profile rolling-code state in `--dry-run` mode. Live `emitter send` without `--dry-run` is intentionally blocked with a hardware/API limitation because raw timed TX over CC1101 `GDO0` has not been specified or validated.

To make the emitter usable, the project needs a specified transmit timing path that converts the existing encoded 7-byte Somfy RTS frame into the Somfy RTS OOK pulse waveform, drives CC1101 asynchronous TX using `GDO0`, and advances profile state only after successful transmission.

## Scope

- Implement live `emitter send` without `--dry-run` for Somfy RTS profiles.
- Reuse the existing profile JSON format and rolling-code behavior.
- Reuse the existing deterministic Somfy RTS encoder for the 7-byte obfuscated frame.
- Add deterministic Somfy RTS pulse generation from an encoded frame.
- Configure the CC1101 for ASK/OOK asynchronous TX at the profile frequency.
- Drive the CC1101 `GDO0` line from Raspberry Pi BCM GPIO `25` during TX.
- Preserve existing `emitter send --dry-run` behavior as hardware-free.
- Preserve `prog` command safety gating with `--allow-programming`.
- Add live-TX validation and documentation for the required GDO0 wiring.
- Preserve receive capture, decode, clone-profile, profile persistence, and the standalone CC1101 connection diagnostic.

## Out Of Scope

- Raw RF replay of captured pulses as the primary control path.
- Brute forcing or bypassing Somfy RTS rolling-code state.
- Supporting non-Somfy RF protocols.
- Supporting encrypted or non-RTS Somfy protocols such as io-homecontrol.
- Pairing the Pi as a new RTS remote except where the existing guarded `prog` command is intentionally invoked by the user.
- Guaranteeing clone reliability if the original physical remote continues to advance the receiver's rolling-code state.
- Automatic blind-position tracking.
- HTTP, daemon, MQTT, HomeKit/Homebridge, scheduler, or UI integration.
- Automatic system package installation.
- Live RF transmit from tests running off the Raspberry Pi.

## Definitions

- Live emission: `emitter send` without `--dry-run`, causing the CC1101 to transmit RF.
- TX GPIO: Raspberry Pi BCM GPIO used to drive the CC1101 `GDO0` data input while the CC1101 is in asynchronous TX mode.
- Pulse plan: deterministic ordered high/low durations generated from an encoded Somfy RTS frame before GPIO output.
- Frame repeat: a repeated Somfy RTS transmission of the same encoded frame within one button-command emission.

## Inputs And Constraints

- Existing target hardware remains `pi14.pi.home`.
- Existing CC1101 SPI defaults remain bus `0`, chip-select `0`.
- Existing Somfy RTS carrier default remains `433420000` Hz.
- Existing GDO0 wiring is CC1101 `GDO0` to Raspberry Pi physical pin `22` / BCM GPIO `25`.
- Live TX uses BCM GPIO numbering.
- `--tx-gpio` must default to `25` and be available on `emitter send` for advanced wiring overrides.
- Documentation and QA must use `--tx-gpio 25` or the default equivalent.
- GPIO access must fail with hardware exit code `2` when dependencies, permissions, platform support, or device access are unavailable.
- CC1101 setup failures must fail with hardware exit code `2`.
- Invalid profile, invalid command, invalid rolling code, or missing `--allow-programming` for `prog` must fail with usage exit code `64`.
- Failed live transmission must not advance the stored profile rolling code.
- Successful live transmission must advance the stored profile rolling code exactly once per `emitter send` invocation, not once per frame repeat.
- The implementation must not report fake live transmit success.

## Timing Model

Somfy RTS live emission uses the same timing model already used by GDO0-backed receive capture:

- Carrier and modulation: `433.42 MHz` ASK/OOK.
- Payload: 56-bit obfuscated Somfy RTS frame.
- Encoding: Manchester-coded payload.
- Half-symbol width: approximately `604 us`.
- Symbol width: approximately `1208 us`.
- First frame wakeup pulse: approximately `9415 us` high followed by approximately `89565 us` low.
- Hardware sync pulse: approximately `2416 us` high followed by approximately `2416 us` low.
- Software sync pulse: approximately `4550 us` high followed by one half-symbol low before payload.
- First frame hardware sync count: `2`.
- Repeated frame hardware sync count: `7`.
- Default frame repeat count: `2` total frames per command emission.

The pulse generator must use integer microsecond durations with deterministic constants. The initial implementation may expose no CLI timing-tuning options beyond `--frequency-hz`, `--symbol-rate`, and `--tx-gpio`; timing constants must be documented in code and covered by tests.

## CLI Behavior

`emitter send` must support:

```bash
./run.sh emitter send --profile profiles/blind.json --command up
./run.sh emitter send --profile profiles/blind.json --command down
./run.sh emitter send --profile profiles/blind.json --command my
./run.sh emitter send --profile profiles/blind.json --command prog --allow-programming
```

Additional behavior:

- `--dry-run` keeps existing behavior and does not touch CC1101 or GPIO.
- `--tx-gpio <bcm>` selects the BCM GPIO that drives CC1101 `GDO0` during live TX. Default: `25`.
- Existing `--spi-bus`, `--spi-chip-select`, `--frequency-hz`, and `--symbol-rate` options remain available.
- Command output must continue to include command, address, rolling code, obfuscated frame, dry-run status, transmit status, and next rolling code.
- On live TX success, `transmitted=true`.
- On dry-run success, `transmitted=false`.

## Deterministic Behavior

1. `emitter send --dry-run` remains hardware-free, encodes the RTS frame, prints the frame fields, and advances the profile rolling code according to existing approved behavior.
2. `emitter send` without `--dry-run` reads the profile, encodes one Somfy RTS frame from the current rolling code, generates a deterministic pulse plan, configures CC1101 asynchronous TX, drives the pulse plan through TX GPIO, and exits `0` only after the transmit operation completes without reported error.
3. Live TX must advance and persist the profile rolling code only after successful CC1101 setup and pulse-plan output.
4. Live TX failure must leave the profile file unchanged.
5. The profile rolling code advances by exactly `1` for one `emitter send` invocation, regardless of the number of repeated frames transmitted.
6. The emitted pulse plan contains one first-frame waveform followed by repeated-frame waveforms according to the configured/default repeat count.
7. The first frame includes the wakeup pulse, two hardware sync pulses, software sync, and Manchester payload.
8. Each repeated frame omits the wakeup pulse, uses seven hardware sync pulses, then software sync and the same Manchester payload.
9. Manchester payload generation maps the encoded obfuscated frame bits deterministically using the same bit order accepted by the existing pulse decoder fixtures.
10. `prog` fails unless `--allow-programming` is supplied.
11. Live `prog` with `--allow-programming` is permitted by the CLI but must be documented as a programming operation that can affect device pairing/configuration.
12. Missing GPIO or CC1101 dependencies, unsupported platform behavior, permission errors, SPI errors, and GPIO output failures map to hardware exit code `2`.
13. The implementation must not use raw captured pulses for live control when a decoded profile is available.
14. The standalone `cc1101_connection_test.py` diagnostic remains non-transmitting.

## Assumptions

- The user is authorized to transmit commands to their own Somfy RTS device.
- The connected Somfy receiver accepts standard 56-bit Somfy RTS timing.
- CC1101 asynchronous TX can use `GDO0` as serial TX data input while in TX mode.
- The existing physical GDO0 connection to BCM GPIO `25` can be driven by the Pi during TX after being used as an input during RX.
- Two total transmitted frames per command is sufficient for initial live validation; if empirical QA shows otherwise, the spec must be amended before changing repeat behavior.
- Local unit tests can validate pulse generation and orchestration with fakes; live RF effectiveness requires manual Pi QA.

## Impact And Regression Considerations

- This change intentionally removes the live-TX block for `emitter send`.
- Incorrect pulse timing can fail to move the blind or can desynchronize rolling-code state if the profile advances after a bad RF transmission that the receiver did not accept.
- To reduce false success risk, QA must include live observation of at least one non-programming command against the authorized Somfy device.
- GPIO direction changes must not break receive capture in subsequent commands.
- The CC1101 adapter must keep GPIO, SPI, and CC1101 dependencies in infrastructure code.
- Domain/application code must remain deterministic and hardware-free except for calls through interfaces.
- Dry-run behavior must remain safe for local validation and automated tests.
- Documentation must make clear that using the original remote after cloning can desynchronize the profile.

## Validation Plan

Local validation:

- `python3 -m compileall cc1101_transceiver cc1101_connection_test.py`
- `python3 -m unittest discover -s tests -p 'test_*.py'`
- `bash -n run.sh`
- `bash -n run_cc1101_connection_test.sh`
- `git diff --check`

Required automated test coverage:

- Pulse generation from `a78e8a589b2988` produces a pulse plan that the existing pulse decoder can decode back to the same obfuscated frame.
- First-frame timing includes wakeup, two hardware sync pulses, software sync, and 56-bit Manchester payload.
- Repeated-frame timing omits wakeup and uses seven hardware sync pulses.
- Pulse generator uses deterministic integer microsecond durations and valid GPIO levels.
- Live `EmitService` success calls transceiver transmit once and advances the profile once.
- Live `EmitService` failure does not advance the profile.
- `emitter send --dry-run` remains hardware-free.
- CLI accepts `--tx-gpio` on `emitter send` and passes it to the infrastructure adapter.
- Missing GPIO/CC1101 dependency paths map to exit code `2`.
- `prog` remains blocked without `--allow-programming`.
- Existing capture, decode, clone-profile, persistence, and connection diagnostic tests continue passing.

Pi live-TX QA on `pi14.pi.home`:

- Deploy with `rsync`.
- Install dependencies in `.venv`.
- Run compile validation.
- Run unit tests.
- Run `./run_cc1101_connection_test.sh --chip-select 0`.
- Run `./run.sh --help`.
- Capture an authorized remote press:
  `./run.sh receiver capture --rx-gpio 25 --out-file /tmp/cc1101_gdo0_capture.json --timeout 10 --frames 1`
- Decode and inspect the capture.
- Clone a profile:
  `./run.sh emitter clone-profile --capture /tmp/cc1101_gdo0_capture.json --profile /tmp/cc1101_gdo0_profile.json --name qa-gdo0`
- Run a dry-run send and confirm encoded output.
- Run one live non-programming command against the authorized device, preferably `my` when that is the least disruptive observable command:
  `./run.sh emitter send --profile /tmp/cc1101_gdo0_profile.json --command my`
- Confirm by observation whether the authorized device reacts.
- Do not run live `prog` during QA unless a separate explicit user instruction authorizes programming-mode testing.

## Documentation Requirements

- Update `README.md` to state that live TX is supported when CC1101 `GDO0` is wired to BCM GPIO `25`.
- Document `--tx-gpio`, its default, and BCM numbering.
- Document live emitter examples separately from dry-run examples.
- Document the live RF risk and the `prog` programming risk.
- Document that failed live TX does not advance profile state, while successful live TX advances it once.
- Update `AGENTS.md` operational constraints so future agents know live TX has a specified timing path after this spec is implemented and validated.

## Research Notes

- Existing approved baseline spec: `specs/spec-cc1101-somfy-rts-transceiver.md`.
- Existing approved capture spec: `specs/spec-gdo0-backed-pulse-capture.md`.
- The pinned project dependency is `cc1101==3.0.0`.
- PyPI and the upstream `python-cc1101` README state that `GDO0` is used by `.asynchronous_transmission()` for data input.
- The TI CC1101 datasheet states that in synchronous and asynchronous serial modes, `GDO0` is used as serial TX data input while in transmit mode.
- PushStack's Somfy RTS notes describe the timing model, including wakeup pulse, hardware sync, software sync, and repeat-frame hardware sync behavior.
