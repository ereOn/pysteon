"""
Message-parsing/producing utilities.

Implemented according to:
http://cache.insteon.com/developer/2413dev-042007-en.pdf
"""

from enum import IntEnum

from .log import logger


MESSAGE_START_BYTE = 0x02

class CommandCode(IntEnum):
    standard_message_received = 0x50
    extended_message_received = 0x51


BODY_SIZES = {
    CommandCode.standard_message_received: 9,
    CommandCode.extended_message_received: 23,
}


class IncomingMessage(object):
    """
    Represents an incoming message.
    """

    def __init__(self, command_code, body):
        self.command_code = command_code
        self.body = bytearray(body)

    def __eq__(self, value):
        if not isinstance(value, IncomingMessage):
            return NotImplemented

        return self.command_code == value.command_code and \
            self.body == value.body

    def __bytes__(self):
        return bytes([self.command_code.value]) + self.body

    def __repr__(self):
        return repr(bytes(self))

    def __str__(self):
        return "[<<<] 0x%02x: %s" % (self.command_code.value, self.body.hex())


def parse_messages(buffer):
    """
    Parses all messages found in `buffer`.

    :param buffer: The buffer to extract the message from. If a message is
        found, it will be removed from `buffer`.
    :returns: A tuple (messages, expected).
    """
    messages = []
    message, expected = parse_message(buffer)

    while message:
        messages.append(message)
        message, expected = parse_message(buffer)

    return messages, expected


def parse_message(buffer):
    """
    Parse a message from the buffer.

    :param buffer: The buffer to extract the message from. If a message is
        found, it will be removed from `buffer`.
    :returns: A tuple (message, expected). Message is `None` if no complete
        message can be read. `expected` is the minimum number of bytes to read
        next.
    """
    _discard_until_message_start(buffer)

    # It takes at least 2 bytes to move forward.
    if len(buffer) < 2:
        return None, 2 - len(buffer)

    try:
        command_code = CommandCode(buffer[1])
    except ValueError:
        logger.warning(
            "Unrecognized command code (0x%02x). Ignoring invalid data.",
            buffer[1],
        )
        buffer[:2] = []

        return None, 2

    body, expected = _extract_body(buffer, BODY_SIZES[command_code])

    # Not enough bytes to process the message. Let's wait for more.
    if not body:
        return None, expected

    return (
        IncomingMessage(command_code=command_code, body=body),
        max(2 - len(buffer), 1),
    )


# Private functions below.


def _discard_until_message_start(buffer):
    """
    Discard unexpected bytes until a message start or the buffer end is found.

    :param buffer: The buffer to extract invalid bytes from.
    """
    discarded_bytes = bytearray()

    for index, c in enumerate(buffer):
        if c != MESSAGE_START_BYTE:
            discarded_bytes.append(c)
        else:
            break

    if discarded_bytes:
        logger.warning(
            "Discarding %s unexpected byte(s): %s",
            len(discarded_bytes),
            discarded_bytes.hex(),
        )
        buffer[:len(discarded_bytes)] = []


def _extract_body(buffer, size):
    """
    Extracts the body of a specified `size` from `buffer`.

    :param buffer: The buffer to extract the body from.
    :param size: The size of the body to extract. The message start and command
        code bytes are *NOT* part of size but will be removed nonetheless.
    :returns: A tuple (body, expected). The body iss a bytearray or `None` if
        not enough bytes are available. In the latter case, no bytes are
        extracted from `buffer`. `expected` is the next minimum number of bytes
        to read.
    """
    # We account for the message start and command code bytes, hence the +2.
    if len(buffer) < size + 2:
        return None, size + 2 - len(buffer)

    body = buffer[2:size + 2]
    buffer[:size + 2] = []

    return body, 0
