# rpi-cc1101-transciever

Planned Raspberry Pi/CC1101 transceiver project. The repository is currently an
unimplemented scaffold: it has no radio driver, GPIO/SPI integration, command
line interface, service, configuration schema, dependency metadata, or runtime
entrypoint.

## Undefined behavior

No current contract selects a Raspberry Pi model, CC1101 board revision, pinout,
SPI bus, interrupt wiring, carrier frequency, regulatory region, modulation,
data rate, packet format, transmit power, receive/transmit workflow, retry or
timeout rules, persistence, or external API. These choices require an explicit
approved design before implementation; they must not be guessed from the
repository name.

## Verification status

No software build, automated domain behavior, loopback exchange, over-the-air
communication, range, interference, antenna, power, thermal, regulatory, or
long-running reliability behavior has been implemented or verified. Future
hardware claims must be checked on the exact Raspberry Pi, CC1101 module,
antenna, wiring, supply, frequency band, and deployment environment.
