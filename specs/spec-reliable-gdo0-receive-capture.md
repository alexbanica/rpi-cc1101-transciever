# Reliable GDO0 receive capture

Status: Approved

## Request and purpose

On 2026-10-31 the user requested "correct them" after investigation identified
incorrect GDO0 signal selection, callback-time pulse measurement, and failure to
extract individual Somfy RTS frames from a listening window. This specification
covers those receive corrections. It does not claim implementation or approval.

## Predecessors and preserved behavior

This is new corrective work referencing `spec-gdo0-backed-pulse-capture.md` and
`plan-gdo0-backed-pulse-capture.md`. Both remain unchanged. Their receive intent,
defaults, BCM GPIO25 / physical pin22 wiring, 433420000-Hz carrier, 10-second
default timeout, CLI arguments, capture/profile JSON formats, and inward layer
dependencies remain applicable. The later approved emitter specification and
plan remain authoritative for TX; this change does not restore the earlier TX
restriction or change emission, rolling-code persistence, or programming guards.
The standalone connection diagnostic remains runnable.

## Evidence and limitations

At source HEAD `9032aa8824c3502da37d96906cbabe705c23683f`, receive setup selects
asynchronous serial mode but leaves IOCFG0 at the installed driver's FIFO-status
default. Pi register reads found IOCFG0=0x01, PKTCTRL0=0x34, MDMCFG2=0x30 and
MARCSTATE=0x0d. TI's CC1101 datasheet defines GDO serial data output as signal
0x0D, asynchronous packet format as 3, and ASK/OOK modulation as 3:
<https://www.ti.com/lit/ds/symlink/cc1101.pdf>, asynchronous operation and GDO
signal-selection sections / Table 41.

A session-only IOCFG0=0x0D correction was read back. A subsequent 120-second
recording containing a user-confirmed MY press retained 325 intervals, including
repeated sync-like groups, but yielded no validated frame. The recording uses
callback execution timestamps and current input sampling, so it cannot prove
edge timing accuracy or missing edges. Installed lgpio callbacks expose the
reported edge level and nanosecond timestamp; its documentation warns that the
current pin state may have changed before a callback runs. Physical wiring was
confirmed by the user, not independently measured.

## Scope and definitions

An edge event carries its reported GPIO level and event timestamp. A measured
pulse is the elapsed time between two consecutive valid edge events at the
previous event's level. A candidate is a contiguous observed segment with Somfy
hardware/software synchronization and a possible 56-bit Manchester payload.
A valid frame must satisfy timing, Manchester encoding, supported command, and
checksum validation. Repeated transmissions are distinct observed candidates;
no missing data may be fabricated to create a valid frame.

Scope is runtime RX radio setup, timestamp-preserving GPIO acquisition,
deterministic frame extraction, focused regression tests, and matching receive
documentation. No TX changes, pairing, programming-mode testing, new protocols,
80-bit variants, automatic inversion, unrelated CLI redesign, or permanent Pi
boot/pin configuration is included.

## Required behavior

### Radio setup

1. Every receive session explicitly selects ASK/OOK, asynchronous serial format,
   no hardware Manchester decoding and no preamble/sync qualification, the
   existing carrier and symbol-rate settings, and non-inverted GDO0 serial data
   output (IOCFG0=0x0D). Set configuration before entering receive mode.
2. Read back the required register fields (IOCFG0, asynchronous format and modem
   modulation/Manchester/sync fields) before starting GPIO capture. Missing
   required driver capabilities, failed writes/readback or mismatched fields
   produce the existing hardware error result; setup must not silently skip
   required configuration. Do not alter TX setup as part of this change.
3. Receiver capture does not transmit RF and does not report setup as capture
   success.

### Edge acquisition

1. Use the installed lgpio event timestamp and event-reported level directly,
   without obtaining event levels from a later gpio_read/input call or measuring
   durations from callback execution times. Direct lgpio use belongs to the
   infrastructure adapter; declare its runtime dependency explicitly.
2. Resolve the GPIO chip for the supported Pi's BCM-numbered pins from available
   chip information rather than assuming the same gpiochip index on all Pi
   models. Fail clearly when an appropriate chip cannot be established.
3. Compute microsecond durations only between actual edge events in one clock
   domain. Do not combine event timestamps with time.monotonic_ns() or create a
   leading/trailing pulse duration from process start or timeout. Use a separate
   monotonic deadline only for controlling the session timeout.
4. Ignore watchdog notifications as non-edge events. Reject invalid levels,
   non-increasing timestamps and consecutive same-level events as an unusable
   sequence rather than inventing intervening transitions; resume candidate
   collection only after a new valid sequence can be established.
5. Protect callback/consumer handoff, unregister callbacks and release claimed
   lines/chips on completion or error. Do not disturb GPIO lines outside the
   selected receive line. Missing dependencies and access failures retain the
   existing hardware-error exit behavior.

### Frame extraction and decoding

1. Search the observed stream for candidate boundaries instead of requiring
   the entire timeout window to be one frame. Ignore leading idle/noise and
   trailing idle outside each candidate. An invalid candidate must not prevent
   a later valid candidate from being considered in the same capture.
2. Recognize the first-frame wakeup plus hardware/software synchronization and
   repeated-frame hardware/software synchronization without requiring a
   synthetic wakeup. Preserve the existing first-frame timing model and
   tolerances; repeated frames use seven hardware-sync pairs followed by the
   existing software sync and 56-bit payload. Do not widen timing tolerances
   merely to force the damaged callback-time recording to decode.
3. Decode exactly 56 Manchester payload bits; surrounding repeat frames or idle
   must not be consumed as extra payload. A final payload level may share an
   observed duration with the following idle; consume only the required
   Manchester prefix when synchronization and the preceding bits determine the
   boundary. Do not invent unobserved edges, payload bits, or checksum validity.
4. Accept only checksum-valid supported frames. Retain observed candidate timing
   in each frame's raw pulse data, existing metadata, obfuscated frame bytes,
   decoded fields and schema version. An isolated previously supported valid
   first-frame capture remains decodable. Offline decode of existing saved
   captures and all profile workflows remain compatible.
5. Collect valid observed frames in order, up to --frames, within the single
   monotonic session timeout. Quiet periods and rejected candidates must not
   prematurely end the remaining listening window. Recognition of repeats does
   not guarantee reception of every transmitted repeat. Repeated valid RF frames may satisfy this count; do not
   deduplicate them into invented reception results. A smaller nonzero number
   at timeout keeps existing partial-count success behavior. Zero valid frames
   produces the existing operational error and no successful capture file.
6. Preserve storage selection (--store-mode / --select-index), index
   normalization and existing controller/service responsibilities.

## Acceptance and validation

- Deterministic tests demonstrate callback scheduling delays and later pin
  changes cannot alter durations computed from supplied event timestamps/levels;
  cover malformed sequences, watchdogs, chip discovery failure and cleanup.
- Radio-adapter tests verify actual required configuration and readback failure
  handling, not just presence of optional method calls. Preserve TX regressions.
- Decoder tests include isolated first frames, repeated frames without wakeup,
  leading/trailing idle and noise, concatenated frames, invalid candidate followed
  by a valid one, final-level/idle boundary, corrupted checksum, malformed timing,
  incomplete payload and requested frame counts. Fixtures must distinguish
  synthetic protocol tests from actual RF evidence.
- Run Python compileall, the full unittest suite, both shell syntax checks, and
  git diff --check as required by AGENTS.md.
- On pi14.pi.home, verify dependency installation, compilation/unit tests, SPI
  identity and RX configuration readback. A coordinated real remote press must
  produce a valid frame before claiming real capture/decode success. Inspect,
  decode and clone-profile must work on that real capture. Use a disposable
  profile copy for dry-run checks because dry-run advances its rolling code.
- No live TX is required for acceptance of this RX correction. It remains a
  separately outstanding project-level hardware outcome, not an excluded failure
  disguised as complete end-to-end transceiver validation.
- If manual pressing is unavailable or hardware decoding fails, report missing
  evidence and DRAFT status; never substitute synthetic test output for RF proof.

## Documentation

Update README receive dependency/setup and capture behavior as needed, explain
hardware-timestamp acquisition and frame extraction, and keep local versus real
RF validation outcomes distinct. Do not commit raw captures containing the user's
remote identity or rolling-code state as public fixtures.

## Approval

Approved by the user on 2026-10-31 with "approve" in the parent conversation.
Approval covers the complete proposed revision whose pre-approval SHA-256 was
`15707e727786ee028127a9dfa09795e53520f3f9de4c2ad7518dec652dba8c35`.
PLAN approval and valid implementation entry remain separate gates; this record
does not authorize new live transmission.
