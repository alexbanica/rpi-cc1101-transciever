# rpi-cc1101-transciever

## CC1101 SPI Connection Test

`cc1101_connection_test.py` is a standalone Raspberry Pi diagnostic for checking
whether a CC1101 module is reachable over SPI. It reads the CC1101 `PARTNUM` and
`VERSION` identity registers only. It does not configure radio registers,
transmit RF packets, validate antenna performance, or verify optional GDO wiring.

Run it directly on the Pi:

```sh
python3 cc1101_connection_test.py
```

By default, the script probes `/dev/spidev0.0` and `/dev/spidev0.1`. To select a
specific chip-select:

```sh
python3 cc1101_connection_test.py --chip-select 0
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
