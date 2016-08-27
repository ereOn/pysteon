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


class AcknowledgmentFailure(PysteonError):
    """
    A command was not acknowledged by the recipient device.
    """
    def __init__(self, command):
        super().__init__(
            "Received NAK for command: %s" % hexlify(command).decode(),
        )
        self.command = command


class ReadTimeout(PysteonError):
    """
    A read operation timed-out.
    """
    def __init__(self, expected_size, data):
        super().__init__(
            "A read operation timed out. Expected %s byte(s) but got only %s."
            " Received data: %s" % (
                expected_size,
                len(data),
                hexlify(data).decode(),
            )
        )
        self.expected_size = expected_size
        self.data = data
