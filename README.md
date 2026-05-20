# rpi-cc1101-transciever

Python 3 tooling for a Raspberry Pi connected to a CC1101 transceiver. The
repository keeps the original SPI reachability diagnostic and adds a DDD/onion
Somfy RTS transceiver package for clone-oriented capture, decode, profile, and
dry-run emission workflows.

## Hardware

Known QA target: `pi14.pi.home`.

Current CC1101 wiring:

- VCC to Raspberry Pi physical pin `1`
- GND to physical pin `6`
- MOSI to physical pin `19`
- MISO to physical pin `21`
- SCK to physical pin `23`
- CSN to physical pin `24`

Default SPI path is `/dev/spidev0.0`, default bus is `0`, default chip-select is
`0`, and default Somfy RTS carrier is `433420000` Hz.

No GDO pin is currently specified as wired. Live raw timing capture and live RTS
transmission are intentionally conservative and report explicit hardware/API
limitations instead of pretending to work. Initial QA uses `--dry-run` only.

## Dependencies

Install Python dependencies in a virtual environment on the Pi:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` includes the published `cc1101` package and `spidev`.
Raspberry Pi OS may also require system packages for SPI access. The published
`cc1101` package is GPL-3.0-or-later, so downstream redistribution should account
for that dependency license.

## Project Structure

```text
cc1101_transceiver/
  applications/services/
  controllers/
  domains/entities/
  domains/interfaces/
  infrastructures/cc1101/
  infrastructures/persistences/
  shared/constants/
```

Domain code is hardware-free. Application services orchestrate deterministic
Somfy RTS encoding, decoding, profile state, and persistence. Infrastructure
adapters own JSON files and CC1101 runtime access. Controllers own CLI parsing.

## Somfy RTS CLI

Use the module wrapper:

```sh
./run.sh --help
```

The wrapper resolves the repository root, prefers `.venv/bin/python`, falls back
to `python3`, and executes `python -m cc1101_transceiver "$@"`.

Receiver examples:

```sh
./run.sh receiver capture --out-file situo_capture.json
./run.sh receiver inspect situo_capture.json
./run.sh receiver decode situo_capture.json
```

Emitter examples:

```sh
./run.sh emitter init-profile --profile profiles/blind.json --address a1b2c3 --rolling-code 1234
./run.sh emitter clone-profile --capture situo_capture.json --profile profiles/blind.json --name living-room-blind
./run.sh emitter send --profile profiles/blind.json --command up --dry-run
./run.sh emitter send --profile profiles/blind.json --command down --dry-run
./run.sh emitter send --profile profiles/blind.json --command my --dry-run
./run.sh emitter send --profile profiles/blind.json --command prog --allow-programming --dry-run
```

`prog` is guarded and fails unless `--allow-programming` is supplied.

Dry-run emission encodes the frame, prints the frame fields, does not touch the
CC1101 adapter, and advances the profile rolling code. Failed validation or
failed hardware access does not advance the rolling code.

Using the original physical remote after cloning can advance the receiver's
rolling-code state and desynchronize the local clone profile.

## JSON Formats

Raw capture:

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

Clone profile:

```json
{
  "format": "cc1101-somfy-rts-profile-v1",
  "name": "living-room-blind",
  "protocol": "somfy-rts",
  "frequency_hz": 433420000,
  "address": "a1b2c3",
  "rolling_code": 1235,
  "source": {
    "type": "capture",
    "capture_file": "situo_capture.json"
  }
}
```

## Validation

Local validation:

```sh
python3 -m compileall cc1101_transceiver cc1101_connection_test.py
python3 -m unittest discover -s tests -p 'test_*.py'
bash -n run.sh
bash -n run_cc1101_connection_test.sh
git diff --check
```

No-live-transmit Pi QA:

```sh
rsync -az --delete --exclude .git --exclude .venv ./ pi14.pi.home:~/rpi-cc1101-transciever/
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && python -m compileall cc1101_transceiver cc1101_connection_test.py'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && python -m unittest discover -s tests -p "test_*.py"'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && ./run_cc1101_connection_test.sh --chip-select 0'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh --help'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh emitter init-profile --profile /tmp/cc1101_qa_profile.json --address a1b2c3 --rolling-code 1234'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh emitter send --profile /tmp/cc1101_qa_profile.json --command up --dry-run'
```

Do not run live `emitter send` without `--dry-run` during initial QA.

## CC1101 SPI Connection Test

`cc1101_connection_test.py` is a standalone Raspberry Pi diagnostic for checking
whether a CC1101 module is reachable over SPI. It reads the CC1101 `PARTNUM` and
`VERSION` identity registers only. It does not configure radio registers,
transmit RF packets, validate antenna performance, or verify optional GDO wiring.

Run it directly on the Pi:

```sh
python3 cc1101_connection_test.py
```

Or use the local wrapper from this checkout:

```sh
./run_cc1101_connection_test.sh
```

By default, the script probes `/dev/spidev0.0` and `/dev/spidev0.1`. To select a
specific chip-select:

```sh
./run_cc1101_connection_test.sh --chip-select 0
```

Copy and run it from this development machine:

```sh
HOST=pi14.pi.home
rsync -az cc1101_connection_test.py "$HOST:/tmp/cc1101_connection_test.py"
ssh "$HOST" 'python3 /tmp/cc1101_connection_test.py'
```

Exit codes:

- `0`: at least one SPI candidate returned a plausible CC1101 identity response.
- `1`: SPI communication completed, but no candidate returned a plausible
  CC1101 identity response.
- `2`: the script could not perform meaningful probing because of a missing
  dependency, permission problem, or selected missing SPI device node.
