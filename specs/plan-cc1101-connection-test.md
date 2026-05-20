# Implementation Plan: CC1101 Connection Test Script

Status: Proposed

Approved spec: `specs/spec-cc1101-connection-test.md`

## Target Branch

- Use a dedicated implementation branch: `feature/cc1101-connection-test`.
- Create it from the current base branch only after implementation starts.

## Scope

Implement the approved one-file Python CC1101 SPI connection diagnostic and the minimal documentation needed to run and QA it.

## Files To Change

- Add `cc1101_connection_test.py`.
- Update `README.md`.
- Keep `specs/spec-cc1101-connection-test.md` as the approved behavior source.
- Keep this implementation plan as the approved execution source after plan approval.

## Test-First Work

1. Add testable pure functions inside `cc1101_connection_test.py` before hardware-specific behavior:
   - CLI argument parsing helpers where practical.
   - SPI path selection from bus/chip-select arguments.
   - CC1101 identity response classification.
   - Exit-code decision from candidate results.
2. Add a lightweight local test file only if the implementation remains simple without introducing package scaffolding. If a test file would add unnecessary structure for this initial one-file utility, validate pure functions through `python3 -m doctest cc1101_connection_test.py` or equivalent inline deterministic checks.

## Implementation Steps

1. Create `cc1101_connection_test.py` as a standalone Python 3 executable script.
2. Implement command-line options:
   - `--bus`, default `0`.
   - `--chip-select`, optional; when omitted, probe chip-selects `0` and `1`.
   - `--speed-hz`, default `500000`, constrained to positive integers.
   - `--json`, optional machine-readable summary if it can be added without complicating the script.
3. Implement candidate device handling:
   - Build `/dev/spidev<bus>.<chip_select>` paths.
   - Check existence before opening.
   - Treat selected missing paths as exit code `2`.
   - For default probing, report missing candidates and continue when at least one candidate exists.
4. Implement SPI access:
   - Import `spidev`; on import failure, print actionable diagnostic and exit `2`.
   - Open each candidate with SPI mode `0` and `max_speed_hz <= 500000` by default.
   - Read CC1101 `PARTNUM` and `VERSION` using CC1101 register-read semantics.
   - Avoid writing config registers and avoid RF transmit behavior.
5. Implement classification:
   - Pass when at least one candidate returns plausible non-all-zero, non-all-`0xff` identity values.
   - Fail with exit `1` when all reachable candidates return implausible values.
   - Fail with exit `2` for dependency, permission, or selected-device availability problems that prevent meaningful probing.
6. Print a concise report:
   - Host/device context where available.
   - Each candidate path.
   - Raw `PARTNUM` and `VERSION` values when read.
   - Candidate pass/fail reason.
   - Final result.
7. Update `README.md` with:
   - Run command on the Pi.
   - Copy-and-run command using a hostname argument, for example with `rsync`.
   - Exit-code meanings.
   - Scope limitation: SPI reachability only, not RF performance or optional GDO wiring.

## Validation Commands

Run locally:

```sh
python3 -m py_compile cc1101_connection_test.py
python3 -m doctest cc1101_connection_test.py
git diff --check
```

Run hardware QA against a supplied host, initially `pi14.pi.home`:

```sh
HOST=pi14.pi.home
rsync -az cc1101_connection_test.py "$HOST:/tmp/cc1101_connection_test.py"
ssh "$HOST" 'python3 /tmp/cc1101_connection_test.py'
ssh "$HOST" 'python3 /tmp/cc1101_connection_test.py --chip-select 99'; test "$?" -eq 2
```

If shell quoting or exit-code capture needs to be adjusted during implementation, preserve the same validation intent.

## Review And QA Expectations

- Review script behavior against every deterministic behavior item in the approved spec.
- Confirm the script remains a single Python file.
- Confirm no RF transmit or persistent Pi configuration changes are introduced.
- Confirm README instructions use a hostname variable or argument rather than hard-coding only `pi14.pi.home`.
- Record hardware QA output in the completion report.

## Documentation Expectations

- README update is required because the new script changes repository usage.
- No additional architecture documentation is required for this one-file utility.

## Commit And Push Expectations

- After implementation, review, QA, and validation, commit the approved spec, approved plan, script, README changes, and any focused tests.
- Use a non-draft commit only if local validation and hardware QA complete successfully.
- Use a `DRAFT` commit message if hardware QA or required validation is blocked or failing.
- Push the implementation branch if repository access allows it.
