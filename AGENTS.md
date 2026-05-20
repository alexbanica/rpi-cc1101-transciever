# Repository Agent Guidance

## Architecture

This repository uses a Python 3 DDD + Onion layout for the Somfy RTS transceiver package:

```text
cc1101_transceiver/
  applications/services/
  controllers/
  controllers/requests/
  controllers/responses/
  domains/dtos/
  domains/entities/
  domains/interfaces/
  infrastructures/cc1101/
  infrastructures/persistences/
  shared/constants/
```

Layer dependencies must point inward:

- `domains` contains pure entities, DTOs, and interfaces.
- `applications` contains orchestration and deterministic protocol/application services.
- `infrastructures` contains CC1101, SPI, filesystem, JSON, and runtime adapters.
- `controllers` contains CLI parsing and command coordination.
- `shared/constants` contains defaults, format names, and exit codes.

Domain code must not import CLI parsing, filesystem persistence, CC1101 libraries, SPI libraries, GPIO libraries, subprocess, SSH, or `rsync`. Domain-facing interfaces use the `Interface` suffix.

## Defaults

- Default SPI bus: `0`
- Default SPI chip-select: `0`
- Default Somfy RTS carrier: `433420000` Hz
- Default symbol rate: `4800`
- Default capture timeout: `10.0`
- Default capture frame count: `1`
- Capture JSON format: `cc1101-somfy-rts-capture-v1`
- Profile JSON format: `cc1101-somfy-rts-profile-v1`

## Validation

Run these before delivery:

```bash
python3 -m compileall cc1101_transceiver cc1101_connection_test.py
python3 -m unittest discover -s tests -p 'test_*.py'
bash -n run.sh
bash -n run_cc1101_connection_test.sh
git diff --check
```

No-live-transmit Raspberry Pi QA target:

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

Do not run live `emitter send` without `--dry-run` unless a new approved spec explicitly allows live RF transmission.

## Operational Constraints

The existing `cc1101_connection_test.py` diagnostic must remain runnable. The Somfy RTS adapter must not fake live capture or transmission success. Current wiring does not specify GDO, and raw Somfy RTS timing capture/transmission must report an explicit hardware/API limitation until GDO-backed behavior is validated.
