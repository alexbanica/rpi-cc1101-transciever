# Reliable GDO0 receive capture implementation plan

Status: Approved

## Authority and effective specification

User approved `spec-reliable-gdo0-receive-capture.md` on 2026-10-31. The approved
file SHA-256 is `d0df284e17ccdcb7975924c04e8b794b7c5a2a0a6a862589cc507d058c416937`.
This plan implements its complete receive-only correction. It references but does
not modify the earlier approved GDO0 capture and emitter SPEC/PLAN pairs.
No source changes occur before separate PLAN approval and valid implement entry.

## Workspace, base and delivery

- Invoking checkout: `/home/alexbanica/workspace/rpi-cc1101-transciever`, branch
  `feature/cc1101-connection-test`, HEAD `9032aa8824c3502da37d96906cbabe705c23683f`.
  Its only task changes are the new specification and plan; preserve other work.
- Use isolated `/tmp/agent-worktrees/rpi-cc1101-transciever/reliable-gdo0-receive`.
- Delivery branch: `feature/reliable-gdo0-receive`; destination
  `origin/feature/reliable-gdo0-receive`. No main merge or PR creation is planned.
- Pin the existing feature baseline `9032aa8824c3502da37d96906cbabe705c23683f`,
  rather than older main, because it contains the capture/TX implementations
  under test. Before preparation refresh `origin/feature/cc1101-connection-test`
  and verify it equals that SHA. A mismatch requires reconciliation/amendment;
  never silently substitute main. `git ls-remote` confirmed that feature SHA and
  main `4523f3384c2187ce3d1df99f9a8af9d6752e7c3f` during planning.
- Before a fresh run verify delivery branch absent locally/remotely and no
  conflicting worktree state. Prepare detached pinned HEAD. Immediately before
  first authorized commit recheck branch absence and create it at verified HEAD.
  Resume an existing verified task checkpoint only from its refreshed delivery
  ref with ancestry, attachment and clean-worktree reconciliation.
- Parent manages worktree/branches, byte-verifies artifact transfer with retained
  content/index/HEAD recovery state, integrates, commits and pushes accepted
  paths. Children never perform these effects. Missing registered exact paths
  use guarded non-forced removal and verification before recreation; unsafe or
  conflicting states stop as DRAFT.
- PLAN approval plus implement entry authorizes branch commit/push of accepted
  code, tests, documentation and both new artifacts, including an evidenced
  blocked DRAFT when recovery is necessary. Verify final remote SHA, upstream,
  staging and artifact presence. Do not merge main or transmit RF.
- After verified delivery detach the clean worktree and restore only unchanged
  transferred invoking artifacts using verified recovery state; leave unrelated
  edits intact. Invoking branch/HEAD stay unchanged. Explain any cleanup gap.

## Implementation decisions and boundaries

Use only named source paths, their direct dependencies, approved artifacts and
existing evidence; do not reopen product research. If a new material fact changes
behavior, use implement's amendment procedure before affected work resumes.

Use direct `lgpio` callbacks in GPIO infrastructure, adding `lgpio>=0.2.2.0`
as an explicit dependency in both requirements.txt and setup.py; retain rpi-lgpio
for existing TX. The known Pi installation has lgpio 0.2.2.0. Discover gpiochips
through enumerated `/dev/gpiochip*`, lgpio chip information and line names. Accept
one controller exposing the requested BCM `GPIO<n>` line with a known Raspberry
Pi pin-controller label/name (bcm2835/bcm2711/pinctrl-bcm or pinctrl-rp1); reject
ambiguity, missing BCM mapping or permission failure. Claim only the chosen line.
Use injected chip/event adapters for hardware-free tests; keep filesystem and
lgpio imports outside applications/domains.

Preserve `GpioPulseCapture.capture(timeout)` as a finite measured-pulse batch
boundary and the public TransceiverInterface. Collect a continuous timestamped
batch until the bounded monotonic timeout, then scan all candidates once. This
preserves current end-of-window completion; early return at requested count is
not promised. Partition invalid edge sequences using an internal discontinuity
boundary that cannot be interpreted as a measured pulse; pass only valid runs to
extraction. This prevents joining data across lost or malformed transitions.
Watchdog notifications are ignored. Never append synthetic process-idle durations.
The internal return shape is `list[list[dict[str, int]]]`: an ordered list of
valid runs, each containing measured `{level, duration_us}` pulses. A malformed
event closes the current run and clears its previous-edge anchor; subsequent
valid edge pairs form a new run. Empty runs are omitted. No discontinuity marker
enters application pulse records or JSON. This intentionally changes only the
private infrastructure return shape; RX3 consumes it and relevant tests change.

Implement extraction as pure application logic in
`applications/services/somfy_rts_pulse_decode_service.py`, exposing an internal
candidate enumeration method with observed boundaries and decoded frame bytes.
Retain existing isolated-frame decode behavior for saved captures. Search each
run for first-frame wakeup/at-least-two-pair sync or seven-pair repeated-frame sync and
software synchronization. Validate exactly 112 Manchester half-symbols, then
checksum and supported command using the existing codec. Explicitly require
`valid_checksum is True`; a successful codec return alone is not validity.
Retain isolated wakeup captures with more than two hardware-sync pairs and add
a greater-than-two compatibility fixture. Bound allocation and
scanning to observed pulse count and fixed payload width, including adversarial
long durations; never expand an idle duration into an unbounded symbol list.
Consume only a justified final-level prefix when the measured pulse contains idle.
Store measured candidate durations without synthetic wakeups or payload repair.
Define pure application-local `PulseFrameCandidate` with `start_index`,
`end_index_exclusive` and `obfuscated_hex`, and
`iter_candidates(pulses) -> Iterator[PulseFrameCandidate]`. Indices address one
run; candidates are non-overlapping and emitted in observed order. The adapter
stores a copy of `run[start_index:end_index_exclusive]` as raw measured timing,
including the complete measured final duration even when only its payload prefix
is decoded. No reconstructed or nominal pulse lengths are persisted as observed
data. RX1 and RX2 use these fixed contracts before parallel implementation.

In the adapter use installed cc1101 3.0.0 register read/write APIs explicitly:
configure existing carrier/rate and fixed packet length behavior, ASK/OOK, no
hardware Manchester/sync, asynchronous serial and IOCFG0=0x0D before SRX. Read
back IOCFG0, PKTCTRL0 format bits and MDMCFG2 modulation/Manchester/sync fields.
Use verified driver methods `_write_burst(ConfigurationRegisterAddress, [value])`
and `_read_single_byte(ConfigurationRegisterAddress)`; `_set_transceive_mode`
and `_set_modulation_format` are available in the installed pinned driver.
Reference `ConfigurationRegisterAddress.IOCFG0` (0x02), PKTCTRL0 (0x08) and
MDMCFG2 (0x12). IOCFG0 must equal 0x0D, PKTCTRL0 & 0x30 must equal 0x30, and
MDMCFG2 & 0x7F must equal 0x30. Read-modify-write other register fields so
unrelated fields are preserved. Enter RX with `_enable_receive_mode()` only
after configuration/readback succeeds. These APIs were verified through
read-only introspection of installed cc1101 3.0.0 on pi14 during the preceding
diagnosis; local absence of that hardware dependency does not justify a fake API.
Missing capabilities/mismatches fail HardwareAccessError. Keep _configure_transmit
and TX cleanup semantics outside edit scope. Clock only session deadlines with
monotonic time; captured_at remains UTC metadata. Filter invalid candidates and
continue scanning, preserve observed order/repeats, cap returned frames and retain
nonzero partial-count success/no-file-on-empty behavior.

## Units, ownership and sequencing

All specialist assignments have verified prerequisites, artifact hashes and a
five-minute ceiling (aim three minutes). Parent dispatches bounded follow-ups
when a unit cannot fit one assignment; no deadline extension or overlap. Parent
serializes integration and shared mutations/checks. Independent initial units
may run concurrently within available slots. Checkpoints do not pause work.

| ID | Owner role and exact paths | Prerequisite | Completion and validation |
| --- | --- | --- | --- |
| RX1 | developer: infrastructures/cc1101/gpio_pulse_capture.py; tests/test_gdo0_capture_infrastructure.py GPIO-specific cases; new tests/test_timestamped_gpio_capture.py; requirements.txt; setup.py | approved artifacts, prepared baseline | timestamp/level backend, chip discovery, discontinuities, cleanup and explicit dependency; focused timestamp/backend tests |
| RX2 | developer: applications/services/somfy_rts_pulse_decode_service.py; tests/test_somfy_pulse_decode.py; tests/pulse_fixtures.py | approved artifacts, prepared baseline | observed first/repeat extraction, bounded payload processing, idle/noise/rejection recovery; focused decoder tests |
| RX3 | developer: infrastructures/cc1101/cc1101_transceiver_adapter.py; tests/test_gdo0_capture_infrastructure.py adapter cases | parent verifies RX1/RX2 contracts; RX1 releases shared test file | fail-closed radio/readback, monotonic batch orchestration/count/metadata integration; adapter tests including unchanged TX |
| RX4 | parent coordination; independent code-reviewer, contract-reviewer, security-reviewer; bounded developer corrections in original units | integrated RX1–RX3 diff and development checks | full review wave, disposition, consolidated accepted fixes and affected validation |
| RX5 | qa-agent: final QA, no source ownership; parent owns deployment and operator coordination | corrected integrated diff and review disposition | local/Pi checks plus actual capture/inspect/decode/clone/dry-run evidence; no RF TX |
| RX6 | documentation-writer: README.md only; parent: final artifact/evidence reconciliation and Git | final QA disposition | one documentation synchronization, diff checks, DoD assessment, verified branch commit/push and invoking checkout recovery |

Domain/protocol tests are written first where practical for decoder changes.
The infrastructure tests explicitly exercise timestamps despite simulated callback
delay, event-level correctness despite changed pin state, watchdogs, invalid
sequences and resource failure/cleanup; do not mirror implementation calls only.
No private real remote data is added to Git. Synthetic fixtures are labelled.

## Requirement-to-delivery trace

Anchors below refer to the approved SPEC's numbered items or named sections.

| SPEC anchor | Delivery units / paths | Evidence |
| --- | --- | --- |
| Predecessors/preserved behavior; Scope exclusions | RX1–RX6, named paths only | complete diff review; unchanged earlier artifacts, TX/CLI/profile regressions |
| Radio setup 1–3 | RX3 adapter + adapter tests | required fields/readback/failures; Pi identity/readback; no transmission |
| Edge acquisition 1–2 | RX1 backend, dependency files/tests | timestamp and reported level tests; actual Pi chip/BCM mapping |
| Edge acquisition 3–5 | RX1/RX3 backend/adapter + tests | separate clocks, discontinuities, watchdogs, callback handoff, timeout/cleanup/errors |
| Frame extraction 1–3 | RX2 decoder/fixtures/tests | noise/idle, first/repeat and concatenation, exact payload, measured final prefix, malformed/incomplete rejection |
| Frame extraction 4 | RX2/RX3 + existing codec/JSON workflow tests | checksum/command checks; raw provenance; saved capture compatibility |
| Frame extraction 5–6 | RX3 + adapter/service/CLI regressions | counts/order/repeats, nonzero partial return, quiet/rejection recovery, empty no-write, storage/index behavior |
| Acceptance deterministic and local checks | RX1–RX5 | full test and syntax/compile/diff evidence |
| Acceptance real Pi / manual coordination | RX5; no new source | actual remote capture checksum/command, inspect/decode/clone and disposable dry-run |
| Acceptance no live TX; DRAFT limitations | RX4–RX6; no TX action | scope/evidence reconciliation, exact unmet criteria if blocked |
| Documentation | RX6 README | dependency/setup, frame behavior, separate static/live evidence, no sensitive fixtures |

## Assurance profile and review scope

Select **full**: the change crosses radio/GPIO acquisition and application framing,
changes executable dependencies, and requires hardware evidence beyond unit tests.
One independent integrated code review covers the entire change and approved
criteria. Contract review covers lgpio/cc1101 interfaces and preserved CLI/JSON
compatibility. Security review covers explicit dependencies, GPIO device access,
callback/input robustness and bounded parsing; reviewers are read-only and do
not use credentials, exploit or change hardware. Parent supplies pinned diff,
artifact hashes, coverage trace, checks and known limitations. Wait for the full
wave, disposition every finding, apply one consolidated correction batch and run
affected tests before final QA. Qualifying actual failures may trigger a bounded
correction cycle under implement; speculation alone does not.

## Validation and operational authority

Development and final QA use:

```sh
python3 -m compileall cc1101_transceiver cc1101_connection_test.py
python3 -m unittest discover -s tests -p 'test_*.py'
bash -n run.sh
bash -n run_cc1101_connection_test.sh
git diff --check
```

Parent verifies Pi hostname pizero14 at pi14.pi.home, SPI0.0, BCM25 mapping, target
checkout state and absence of an active radio owner before copying accepted code.
Existing session authority covers project copying/dependency installation and
receive testing. Use rsync without --delete, exclude .git/.venv/__pycache__ and
runtime profile/capture data; stop on concurrent remote edits or unclear ownership.
Record deployed source identity with file hashes, not a Git SHA claim for an
rsynced checkout. Install into the existing project venv; no system package,
boot configuration or reboot changes are included.

Run Pi compilation/full tests with .venv Python; run the SPI diagnostic with
`.venv/bin/python cc1101_connection_test.py --chip-select 0` so installed spidev
is used. Verify receive setup/readback and the selected GPIO chip. Announce
listening only after successful setup and event registration. Coordinate one
short MY/STOP press; use a bounded 120-second QA timeout if needed for operator
latency while preserving the 10-second CLI default. Capture must contain a valid
checksum frame from that press; check receiver inspect/decode and clone-profile
against its actual file. Use a disposable profile copy for one up --dry-run;
never live transmit or run prog. Capture paths use unique /tmp names, remote
profiles remain private, and existing captures/profiles are never overwritten.

If the operator is unavailable, complete all independent work then report the
exact blocked real-capture criterion as DRAFT. A failed real capture is a QA
finding to diagnose/correct within scope, not a success. Required new behavior or
missing authority triggers amendment or a concrete blocker, never fabricated data.

## Definition of Done, recovery and documentation

Done requires integrated approved receive behavior, all review dispositions,
required validation and real Pi capture workflow evidence, README synchronization,
no sensitive fixture leakage, and verified delivery SHA/upstream/artifact presence
plus safe invoking checkout restoration. Project-level live TX remains separately
unverified; RX completion must not claim full transceiver hardware acceptance.

Missing remote connectivity/base verification, GPIO/API capabilities, operator
participation, invalid real frames or unsafe worktree/remote changes block affected
acceptance. Complete safe remaining work, record exact evidence/skips and unmet
criteria, and make only an authorized verified DRAFT delivery if safe. Worktree
transfer/cleanup failure also remains DRAFT. No force cleanup/reset/stash, history
rewrite, main merge or unrelated changes are authorized. Required automatic
implementation amendments preserve earlier artifacts and record effective scope.

## Plan assurance

Independent assurance completed on 2026-10-31 against the approved SPEC and
initial PLAN SHA-256 `ae401aafb0b8e309c647433c8ef74f21368b6bee9aff0eb7d91ceb65ebe87543`:

- Explorer `receive-plan-evidence` traced source/dependencies/validation/delivery;
  its medium finding requested concrete cc1101 register APIs and masks. Resolved
  above with the methods verified on Pi, addresses, expected masks and ordering.
- Architect `receive-plan-architecture` assessed the complete interfaces,
  sequencing, compatibility and delivery boundary. Its medium finding requested
  preserving isolated first frames with more than two sync pairs; resolved above
  with at-least-two handling and an explicit regression fixture. Its low finding
  requested concrete run/candidate representations; resolved above with fixed
  result shapes, index semantics and raw final-duration preservation.
- Architect also noted that codec success can carry valid_checksum=False;
  explicit checksum-flag acceptance is now stated. No SPEC behavior changed.
- Both handoffs were valid JSON objects with expected identities/status and
  evidence. Parent reconciled all findings; no supported planning gap remains.
  Neither review establishes hardware correctness or delivery acceptance.

## Approval

Approved by the user on 2026-10-31 with "approve" in the parent conversation.
Approval covers the complete reviewed plan whose pre-approval SHA-256 was
`19138e6ad3aa5a16692d86f0fae3a44ff7e99063e8ff0e73c470a53140c3d900`.
Implementation entry uses a new session, cleared context or explicit same-context
implementation consent; no source implementation has started.
