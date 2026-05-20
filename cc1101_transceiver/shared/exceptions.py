class TransceiverError(Exception):
    """Base application error."""


class InvalidInputError(TransceiverError):
    """Invalid CLI input or invalid persisted JSON."""


class OperationalError(TransceiverError):
    """Expected operational failure such as no capture or no decoded frame."""


class HardwareAccessError(TransceiverError):
    """Runtime dependency, SPI, permission, or hardware setup error."""


class ProgrammingCommandBlockedError(InvalidInputError):
    """The guarded Somfy RTS programming command was requested without approval."""
