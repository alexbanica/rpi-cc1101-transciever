# GDO0-Backed Somfy RTS Pulse Capture

Status: Approved

## Purpose

Add hardware-backed receive capture for Somfy RTS by using the now-known CC1101 `GDO0` wiring to capture GPIO edge timing, decode Somfy RTS timing into a 56-bit frame, and persist the result in the existing `cc1101-somfy-rts-capture-v1` JSON format.

## Problem Statement

The approved Somfy RTS transceiver spec intentionally left live raw timing capture blocked because no GDO wiring was specified. The wiring is now known: CC1101 `GDO0` is connected to Raspberry Pi physical pin `22`, which is BCM GPIO `25`. The next behavior change is to replace the current explicit capture limitation with a real receive path when `receiver capture --rx-gpio 25` is used.

## Scope

- Document CC1101 `GDO0` to Raspberry Pi physical pin `22` / BCM GPIO `25`.
- Implement GPIO edge capture for `receiver capture --rx-gpio 25`.
- Configure the CC1101 receive path for Somfy RTS carrier reception at the existing default `433420000` Hz.
- Convert captured GDO0 level durations into Somfy RTS frame timing.
- Decode captured Somfy RTS timing into the existing capture JSON format:
  - pulse timing data in each frame's `raw` object
  - obfuscated frame bytes in `raw.obfuscated_frame_hex`
  - decoded Somfy RTS fields in the existing `decoded` object
- Preserve `receiver inspect`, `receiver decode`, `emitter clone-profile`, and profile persistence behavior against the existing capture format.
- Keep live transmission blocked unless `--dry-run` is used.
- Preserve the standalone `cc1101_connection_test.py` diagnostic.

## Out Of Scope

- Live Somfy RTS transmission.
- TX GDO timing validation.
- Pairing the Pi as a new RTS remote.
- Supporting protocols other than Somfy RTS.
- Supporting Somfy RTS 80-bit step-wheel variants.
- Replacing the existing capture JSON schema version.
- Guaranteeing capture of every repeated frame from one remote button press.
- Hardware setup automation, pull-up/down configuration outside the process, or permanent Pi GPIO configuration.

## Definitions

- `GDO0`: CC1101 general digital output pin used here as the receive signal output.
- `rx_gpio`: Raspberry Pi BCM GPIO number used by the CLI to read GDO0 transitions.
- Pulse duration: one contiguous high or low GPIO level duration measured in microseconds.
- Capture session: one invocation of `receiver capture`.
- Candidate frame: a contiguous set of pulse durations that matches Somfy RTS preamble/sync/data timing closely enough to attempt decode.
- Decoded capture frame: an existing `CaptureFrame` whose `decoded` object contains Somfy RTS address, rolling code, command, and checksum validity.

## Inputs And Constraints

- CC1101 `GDO0` is wired to Raspberry Pi physical pin `22`, BCM GPIO `25`.
- The approved default Somfy RTS carrier remains `433420000` Hz.
- The approved default capture timeout remains `10.0` seconds.
- The approved default capture frame count remains `1`.
- `receiver capture --rx-gpio 25` is the supported GDO-backed receive command.
- `--rx-gpio` values other than `25` are accepted only as explicit advanced input and must be recorded in capture JSON; documentation and QA use `25`.
- GPIO capture must use BCM numbering, not physical-board numbering.
- GPIO capture depends on Raspberry Pi-compatible GPIO access and must fail with hardware exit code `2` when required GPIO dependencies, permissions, or device access are unavailable.
- The implementation must not report fake capture success. It writes a capture file only after at least one decoded or raw candidate frame is obtained.
- The implementation must not transmit RF during capture.
- `emitter send` without `--dry-run` remains blocked with an explicit hardware/API limitation until TX timing is separately specified, implemented, and validated.

## Timing Model

Somfy RTS capture decode uses the following timing model derived from passive reverse-engineering references and validated by repository tests/fixtures:

- Carrier and modulation: `433.42 MHz` ASK/OOK.
- Encoding: Manchester-coded payload.
- Standard payload length: `56` bits.
- Symbol width: approximately `1208 us`.
- Half-symbol width: approximately `604 us`.
- First-frame wakeup pulse: approximately `9415 us` high followed by approximately `89565 us` low.
- Hardware sync pulse: approximately `2416 us` high followed by approximately `2416 us` low.
- Software sync pulse: approximately `4550 us` high followed by approximately one half-symbol low before payload edge decoding.

The decoder must use deterministic tolerances rather than exact equality. The implementation plan may tune the tolerance value, but the implementation must document it in code or constants and cover accepted/rejected boundaries with unit tests.

## Persistence Format

The capture file keeps the existing top-level `cc1101-somfy-rts-capture-v1` format. GDO0 capture adds fields inside `raw` without changing the schema version:

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
      "raw": {
        "capture_method": "gdo0-gpio-pulse",
        "gdo": "GDO0",
        "rx_gpio": 25,
        "gpio_numbering": "bcm",
        "pulse_durations_us": [
          {"level": 1, "duration_us": 9415},
          {"level": 0, "duration_us": 89565}
        ],
        "obfuscated_frame_hex": "a78e8a589b2988"
      },
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

Persistence invariants:

- `pulse_durations_us` stores ordered contiguous durations as positive integer microseconds.
- Each pulse item stores `level` as `0` or `1`.
- `rx_gpio` stores the BCM GPIO number used by capture.
- `gpio_numbering` must be `bcm`.
- `obfuscated_frame_hex` stores the decoded 7-byte Somfy RTS obfuscated frame as 14 lowercase hexadecimal characters.
- `decoded` uses the existing decoded-frame object and must not introduce a new decoded schema.

## Deterministic Behavior

1. `receiver capture --rx-gpio 25 --out-file <path>` configures capture for BCM GPIO `25`, waits up to `--timeout`, and attempts to collect up to `--frames` Somfy RTS frames.
2. If at least one Somfy RTS frame is decoded from GDO0 pulse timing, the command writes the existing capture JSON format and exits `0`.
3. If GDO0 edges are observed but no candidate decodes to a valid Somfy RTS frame, the command exits `1` and does not overwrite the output file with invalid JSON.
4. If no GDO0 pulse activity is observed before timeout, the command exits `1` and does not write a capture file.
5. If GPIO or CC1101 receive setup fails because of missing dependencies, permissions, SPI errors, GPIO access errors, or unsupported platform behavior, the command exits `2`.
6. If `--rx-gpio` is omitted, `receiver capture` keeps the existing explicit limitation path and exits `2` rather than pretending SPI-only raw timing capture works.
7. `receiver decode <capture>` can decode captures containing `raw.obfuscated_frame_hex` and can also decode captures containing only `raw.pulse_durations_us` when those pulses match the Somfy RTS timing model.
8. `receiver inspect <capture>` reports capture/profile summary without hardware access and counts decoded frames from GDO0 captures the same way it counts existing decoded fixtures.
9. `emitter clone-profile` accepts a GDO0-decoded capture and creates the profile from the first valid decoded Somfy RTS frame.
10. `emitter send --dry-run` remains hardware-free, encodes the frame, prints frame fields, and advances the profile rolling code according to the approved baseline behavior.
11. `emitter send` without `--dry-run` remains blocked and must not attempt live GDO0/TX timing.
12. The standalone `cc1101_connection_test.py` remains a non-transmitting SPI identity diagnostic and does not require GDO0.

## Assumptions

- The user is authorized to capture their own Somfy RTS remote.
- The target Situo remote emits the standard 56-bit Somfy RTS timing variant.
- BCM GPIO `25` receives a digital demodulated signal suitable for edge timing after CC1101 receive configuration.
- A first implementation may depend on a Pi-only GPIO library for live capture, while unit tests use fake pulse sources and do not require GPIO hardware.
- Existing capture JSON readers tolerate additional `raw` keys and do not require a schema-version bump for this additive raw data.

## Impact And Regression Considerations

- The infrastructure adapter changes from a capture stub to a hardware-backed capture path when `--rx-gpio` is provided.
- Domain and application protocol decoding must remain hardware-free and deterministic.
- GPIO libraries must stay out of domain/application layers.
- Timing tolerance mistakes could produce false positives or reject valid captures; tests must cover accepted nominal timing, tolerated jitter, and rejection cases.
- Capture failure must preserve the existing output-file safety invariant.
- Live transmit remains intentionally unavailable, so this change must not weaken the dry-run-only TX guard.
- README and `AGENTS.md` must be updated because the repository's previous documentation says no GDO pin is specified.

## Validation Plan

Local validation:

- `python3 -m compileall cc1101_transceiver cc1101_connection_test.py`
- `python3 -m unittest discover -s tests -p 'test_*.py'`
- `bash -n run.sh`
- `bash -n run_cc1101_connection_test.sh`
- `git diff --check`

Required automated test coverage:

- GPIO pulse-duration normalization with deterministic fake edge events.
- Somfy RTS pulse timing decode to a 7-byte obfuscated frame.
- Manchester decode of nominal 56-bit Somfy RTS timing.
- Timing tolerance accept/reject boundaries.
- `receiver capture --rx-gpio 25` writes capture JSON with `raw.capture_method`, `raw.rx_gpio`, `raw.gpio_numbering`, `raw.pulse_durations_us`, `raw.obfuscated_frame_hex`, and `decoded`.
- Capture timeout/no-frame path does not write invalid or partial JSON.
- Missing GPIO dependency or permission path maps to hardware exit code `2`.
- `receiver decode` handles pulse-only raw capture fixtures when `obfuscated_frame_hex` is absent.
- `emitter clone-profile` works from a GDO0-decoded capture fixture.
- `emitter send --dry-run` remains hardware-free.
- `emitter send` without `--dry-run` remains blocked.
- Existing Somfy codec, persistence, CLI, and connection diagnostic tests continue to pass.

Pi no-live-transmit QA on `pi14.pi.home`:

- Deploy with `rsync`.
- Install dependencies in `.venv`.
- Run compile validation.
- Run unit tests.
- Run `./run_cc1101_connection_test.sh --chip-select 0`.
- Run `./run.sh --help`.
- Run `./run.sh receiver capture --rx-gpio 25 --out-file /tmp/cc1101_gdo0_capture.json --timeout 10 --frames 1` while pressing the authorized Somfy RTS remote once.
- Run `./run.sh receiver inspect /tmp/cc1101_gdo0_capture.json`.
- Run `./run.sh receiver decode /tmp/cc1101_gdo0_capture.json`.
- Run `./run.sh emitter clone-profile --capture /tmp/cc1101_gdo0_capture.json --profile /tmp/cc1101_gdo0_profile.json --name qa-gdo0`.
- Run `./run.sh emitter send --profile /tmp/cc1101_gdo0_profile.json --command up --dry-run`.

Do not run live `emitter send` without `--dry-run` during this implementation.

## Documentation Requirements

- Update `README.md` hardware wiring with `GDO0` to physical pin `22` / BCM GPIO `25`.
- Update receiver capture examples to show `--rx-gpio 25`.
- Update JSON format examples with GDO0 pulse raw data.
- Update validation/QA instructions with the GDO0 capture flow.
- Update `AGENTS.md` defaults/operational constraints so future agents know GDO0 wiring is specified and TX remains dry-run-only.

## Research Notes

- Existing approved repository spec: `specs/spec-cc1101-somfy-rts-transceiver.md`.
- Existing approved implementation plan: `specs/plan-cc1101-somfy-rts-transceiver.md`.
- The prior approved spec stated that no GDO pin was specified and required a spec update before GDO-backed behavior.
- PushStack's passive Somfy RTS reverse-engineering notes describe `433.42 MHz` ASK/OOK, Manchester encoding, 56-bit payloads, and the timing values used by this proposed spec: https://pushstack.wordpress.com/somfy-rts-protocol/
