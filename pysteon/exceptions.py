"""
Exceptions classes.
"""

from binascii import hexlify


class PysteonError(RuntimeError):
    """
    The base class for all Pysteon-specific errors.
    """


class SynchronizationError(PysteonError):
    """
    A synchronization error was detected.
    """


class UnknownCommandError(PysteonError):
    """
    An unknown command was received.
    """
    def __init__(self, command):
        super().__init__(
            "Received unknown command: 0x%s" % hexlify(command).decode(),
        )
        self.command = command


class AcknowledgmentFailure(PysteonError):
    """
    A command was not acknowledged by the recipient device.
    """
    def __init__(self, command):
        super().__init__(
            "Received NAK for command: 0x%s" % hexlify(command).decode(),
        )
        self.command = command
