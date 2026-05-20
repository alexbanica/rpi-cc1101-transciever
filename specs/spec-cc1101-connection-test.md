# CC1101 Connection Test Script

Status: Approved

## Purpose

Provide a deterministic one-file Python script that can be copied to a Raspberry Pi Zero and run there to verify whether a CC1101 transceiver connected through the Raspberry Pi header is reachable over SPI.

## Problem Statement

The CC1101 module is physically wired to the Raspberry Pi header, but the wiring may be incorrect. The repository currently has no diagnostic tool for confirming whether the Pi can communicate with the transceiver.

## Scope

- Add a standalone one-file Python connection-test script intended to run on Raspberry Pi OS.
- Probe the Pi's enabled SPI device nodes.
- Attempt CC1101 SPI communication on both `/dev/spidev0.0` and `/dev/spidev0.1` unless the user explicitly selects one.
- Report enough diagnostic detail to distinguish:
  - SPI device nodes missing.
  - Permission or dependency failure.
  - No plausible CC1101 response on either chip-select.
  - Plausible CC1101 response on one or more chip-selects.
- Support QA by copying the script to a hostname supplied as an argument to the QA command or helper flow, then running it there.

## Out Of Scope

- Transmitting or receiving RF packets.
- Validating antenna quality, frequency calibration, RF range, or modulation settings.
- Proving that every optional CC1101 GPIO signal is wired correctly.
- Permanently changing Raspberry Pi boot configuration, kernel overlays, or user group membership.
- Installing system packages automatically.

## Definitions

- CC1101: The TI CC1101 sub-1 GHz transceiver accessed through SPI.
- SPI device node: A Linux character device such as `/dev/spidev0.0` or `/dev/spidev0.1`.
- Plausible CC1101 response: A register read sequence that returns values consistent with a responding CC1101-compatible chip rather than an all-zero, all-one, permission, timeout, or open failure.
- Chip-select: The SPI chip-select line represented by the final component of a spidev path, for example `0` in `/dev/spidev0.0`.

## Inputs And Constraints

- Target host: supplied by argument during QA; the known current target is `pi14.pi.home`.
- Target OS observed during planning: Raspberry Pi OS Bookworm on Linux `6.12.87+rpt-rpi-v6`, `armv6l`.
- Target user observed during planning: `alexbanica`, member of `spi` and `gpio`.
- Target SPI nodes observed during planning:
  - `/dev/spidev0.0`
  - `/dev/spidev0.1`
- Target Python libraries observed during planning:
  - `spidev`
  - `RPi.GPIO`
  - `lgpio`
  - `gpiozero`
- The first implementation should be a single Python 3 file using the installed `spidev` package.
- The script must not require root when device permissions allow the current user to access SPI.
- The script must be safe to run repeatedly.

## Deterministic Behavior

1. The script prints a concise diagnostic report and exits with a deterministic status code.
2. By default, the script probes `/dev/spidev0.0` and `/dev/spidev0.1` when they exist.
3. The script supports selecting a specific SPI bus and chip-select through command-line options.
4. The script verifies that the selected spidev path exists before attempting communication.
5. The script opens each candidate SPI device with conservative CC1101-compatible defaults:
   - SPI mode `0`.
   - Maximum speed no higher than `500000` Hz unless overridden by option.
6. For each candidate SPI device, the script reads CC1101 identity and status registers using CC1101 SPI register-read semantics.
7. The minimum register set must include `PARTNUM` and `VERSION`.
8. The script treats the connection as passing when at least one candidate returns a plausible CC1101 identity response.
9. The script treats all-zero and all-`0xff` identity responses as failures because they commonly indicate missing MISO, missing power, wrong chip-select, or no responding device.
10. The script prints the raw register values for each candidate, even when the candidate fails.
11. The script exits:
    - `0` when at least one candidate passes.
    - `1` when SPI communication completes but no candidate returns a plausible CC1101 response.
    - `2` when the script cannot run because of missing dependencies, missing selected SPI device nodes, or permission errors.
12. The script must avoid writing CC1101 configuration registers during the basic connection test.
13. The script may issue CC1101 command strobes only if they are required to recover from an unusable state, and any such behavior must be explicitly documented in script help text.

## Assumptions

- A correct SPI wiring check is the first useful diagnostic because it confirms power, ground, SCLK, MOSI, MISO, and chip-select well enough for register reads.
- Optional CC1101 GDO pins are not required for this initial connection test.
- Probing both chip-selects is acceptable because both `/dev/spidev0.0` and `/dev/spidev0.1` are enabled on the target Pi.
- A one-file standalone script is preferable for the initial repo state because there is no package structure yet.

## Impact And Regression Considerations

- This is an additive diagnostic utility and should not affect existing runtime behavior because the repository currently has no application code.
- The script must not create persistent state on the Pi.
- The script should avoid RF transmission to prevent regulatory and environment-specific side effects.
- The script should be written so future automation can parse its exit code without depending on exact prose output.

## Validation Plan

- Add deterministic local tests for pure parsing/classification logic where practical.
- Run Python syntax validation locally.
- Copy the script to a hostname supplied as a command argument with `rsync`; use `pi14.pi.home` for initial QA unless another hostname is supplied.
- Run the script on that host against the default candidate devices.
- Record which SPI device, if any, returns plausible CC1101 register values.
- Run at least one negative-path validation when practical, such as selecting a nonexistent chip-select and verifying exit code `2`.
- Run `git diff --check`.

## Documentation Requirements

- Update `README.md` with:
  - How to run the connection test locally on the Pi.
  - How to copy and run it from the development machine using a hostname argument.
  - Expected success and failure meanings.
  - A note that the test validates SPI reachability, not RF performance or optional GPIO wiring.
