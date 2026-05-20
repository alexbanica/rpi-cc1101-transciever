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
- GDO0 to physical pin `22` / BCM GPIO `25`

Default SPI path is `/dev/spidev0.0`, default bus is `0`, default chip-select is
`0`, and default Somfy RTS carrier is `433420000` Hz.

GDO0-backed receive capture uses BCM GPIO numbering. Live RTS transmission is
still intentionally conservative and reports an explicit hardware/API limitation
unless `--dry-run` is used.

## Dependencies

Install Python dependencies in a virtual environment on the Pi:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` includes the published `cc1101` package, `spidev`, and
`rpi-lgpio` for the `RPi.GPIO`-compatible BCM GPIO edge capture path. Raspberry
Pi OS may also require system packages for SPI and GPIO access. The published
`cc1101` package is GPL-3.0-or-later, so downstream redistribution should
account for that dependency license.

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
./run.sh receiver capture --rx-gpio 25 --out-file situo_capture.json
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

Receiver arguments:

- `receiver capture`: captures RF/timing observations and writes a capture JSON
  file only when at least one GDO0 pulse-timing frame decodes successfully.
- `--out-file`: required output path for capture JSON.
- `--timeout`: capture wait time in seconds. Default: `10.0`.
- `--frames`: number of frames to collect. Default: `1`.
- `--store-mode`: capture storage mode, either `selected` or `all`. Default:
  `selected`.
- `--select-index`: selected frame index when storing a single frame. Default:
  `0`.
- `--rx-gpio`: optional receive GDO pin as a BCM GPIO number. Use `25` for the
  documented GDO0 wiring. Omitting it keeps the explicit SPI-only capture
  limitation.
- `receiver inspect <path>`: reads a capture or profile JSON file and prints a
  compact summary without touching hardware.
- `receiver decode <capture>`: reads capture JSON and prints decoded Somfy RTS
  fields when the capture already contains decoded data, raw obfuscated frame
  bytes under `raw.obfuscated_frame_hex`, or GDO0 pulse timing under
  `raw.pulse_durations_us`.

Emitter arguments:

- `emitter init-profile`: creates a manual Somfy RTS profile JSON.
- `--profile`: required path to the profile JSON to write or read.
- `--address`: required 3-byte Somfy RTS remote address as 6 hexadecimal
  characters, for example `a1b2c3`. Values are stored lowercase.
- `--rolling-code`: required current rolling-code integer for manual profile
  creation. It must fit in an unsigned 16-bit value.
- `--name`: optional human-readable profile label.
- `emitter clone-profile`: creates a profile from the first valid decoded Somfy
  RTS frame in a capture.
- `--capture`: required capture JSON path used by `clone-profile`.
- `emitter send`: encodes and optionally transmits a command using a profile.
- `--command`: required Somfy RTS command. Allowed values are `up`, `down`,
  `my`, and `prog`.
- `--dry-run`: encode, print, and persist the next rolling code without
  transmitting RF or touching the CC1101 adapter.
- `--allow-programming`: required with `--command prog`; without it, `prog`
  fails as invalid input.

Common RF/CC1101 arguments:

- `--spi-bus`: SPI bus number. Default: `0`.
- `--spi-chip-select`: SPI chip-select number. Default: `0`.
- `--frequency-hz`: RF carrier frequency in Hz. Default: `433420000`.
- `--symbol-rate`: intended symbol rate setting for future hardware-backed RF
  adapters. Default: `4800`.

`prog` is guarded and fails unless `--allow-programming` is supplied.

Dry-run emission encodes the frame, prints the frame fields, does not touch the
CC1101 adapter, and advances the profile rolling code. Failed validation or
failed hardware access does not advance the rolling code.

Using the original physical remote after cloning can advance the receiver's
rolling-code state and desynchronize the local clone profile.

## JSON Formats

GDO0-backed raw capture:

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
          {
            "level": 1,
            "duration_us": 9415
          },
          {
            "level": 0,
            "duration_us": 89565
          }
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
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh receiver capture --rx-gpio 25 --out-file /tmp/cc1101_gdo0_capture.json --timeout 10 --frames 1'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh receiver inspect /tmp/cc1101_gdo0_capture.json'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh receiver decode /tmp/cc1101_gdo0_capture.json'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh emitter clone-profile --capture /tmp/cc1101_gdo0_capture.json --profile /tmp/cc1101_gdo0_profile.json --name qa-gdo0'
ssh pi14.pi.home 'cd ~/rpi-cc1101-transciever && . .venv/bin/activate && ./run.sh emitter send --profile /tmp/cc1101_gdo0_profile.json --command up --dry-run'
```

Press the authorized Somfy RTS remote once during the `receiver capture`
timeout window.

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
