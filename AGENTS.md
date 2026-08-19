# AGENTS

Repository guidance for rpi-cc1101-transciever.

## Project status

- This repository is currently a documentation-only scaffold. It contains no
  transceiver source code, runtime configuration, package metadata, executable,
  or defined public interface.
- Do not infer radio frequency, modulation, packet encoding, GPIO/SPI wiring,
  board variant, transmit power, regulatory region, retry behavior, CLI, daemon,
  or service contract from the repository name.
- Any implementation must first define its intended hardware, electrical and
  radio constraints, runtime interface, failure behavior, and acceptance checks.
- Hardware behavior requires validation on the exact Raspberry Pi, CC1101
  module, antenna, wiring, power supply, frequency band, and operating region;
  static checks or mocks are not physical RF validation.

## Specs and plans

- `specs/` is for active work, not completed-work history.
- Remove completed spec/plan pairs after their durable behavior and outstanding
  limitations are consolidated into maintained documentation.

## Domain-only test policy

- Automated tests of any kind, including unit, integration, contract, snapshot,
  workflow, and configuration tests, may be created or maintained only for
  deterministic domain source logic in this project.
- Do not create or maintain tests for anything outside domain source logic,
  including application orchestration, infrastructure and adapters,
  presentation, UI and controllers, Docker or container files, GitHub Actions
  or other CI/CD workflows, deployment and configuration, packaging and release
  scripts, tooling, or other operational code.
- Validate non-domain changes with appropriate static, syntax, lint, type,
  structural, build, dry-run, smoke, runtime, or operator checks instead of
  automated tests.
- If this project has no domain source logic, automated testing and test-first
  work are not applicable.
- This policy supersedes any more general testing or validation wording
  elsewhere in this file.
