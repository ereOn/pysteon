"""
Message-parsing/producing utilities.

Implemented according to:
http://cache.insteon.com/developer/2413dev-042007-en.pdf
"""

from enum import IntEnum

from .exceptions import CommandFailure
from .log import logger


MESSAGE_START_BYTE = 0x02


class CommandCode(IntEnum):
    """
    Implements the command codes as defined in the Insteon's Modem Developer's
    Guide (page 12).
    """

    # Messages sent from IM to host.
    #
    # If you add commands here you MUST also update the `BODY_SIZES` dictionary
    # below. Failure to do so will result in a crash upon reception of those
    # messages.
    standard_message_received = 0x50
    extended_message_received = 0x51
    x10_received = 0x52
    all_linking_completed = 0x53
    button_event_report = 0x54
    user_reset_detected = 0x55
    all_link_cleanup_failure_report = 0x56
    all_link_record_response = 0x57
    all_link_cleanup_status_report = 0x58

    # Messages sent from host to IM.
    #
    # If you add commands here you MUST also update the `BODY_SIZES` dictionary
    # below with the size for the RESPONSE messages, not the REQUESTS. Failure
    # to do so will result in a crash upon reception of those responses.
    get_im_info = 0x60
    send_all_link_command = 0x61
    send_standard_or_extended_message = 0x62
    send_x10 = 0x63
    start_all_linking = 0x64
    cancel_all_linking = 0x65
    set_host_device_category = 0x66
    reset_im = 0x67
    set_ack_message_byte = 0x68
    get_first_all_link_record = 0x69
    get_next_all_link_record = 0x6a
    set_im_configuration = 0x6b
    get_all_link_record_for_sender = 0x6c
    led_on = 0x6d
    led_off = 0x6e
    manage_all_link_record = 0x6f
    set_nak_message_byte = 0x70
    set_nak_message_two_bytes = 0x71
    rf_sleep = 0x72
    get_im_configuration = 0x73


BODY_SIZES = {
    # Messages sent from IM to host.
    CommandCode.standard_message_received: 9,
    CommandCode.extended_message_received: 23,
    CommandCode.x10_received: 2,
    CommandCode.all_linking_completed: 8,
    CommandCode.button_event_report: 1,
    CommandCode.user_reset_detected: 0,
    CommandCode.all_link_cleanup_failure_report: 5,
    CommandCode.all_link_record_response: 8,
    CommandCode.all_link_cleanup_status_report: 1,

    # Messages response sent from IM.
    CommandCode.get_im_info: 7,
    CommandCode.get_first_all_link_record: 1,
    CommandCode.get_next_all_link_record: 1,
}


class BaseMessage(object):
    """
    Base class for messages.
    """
    def __init__(self, command_code, body=b''):
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


class IncomingMessage(BaseMessage):
    """
    Represents an incoming message.
    """

    def __str__(self):
        if self.body:
            return "[<<<] 0x%02x: %s" % (
                self.command_code.value,
                self.body.hex(),
            )
        else:
            return "[<<<] 0x%02x" % self.command_code.value


class OutgoingMessage(BaseMessage):
    """
    Represents an outgoing message.
    """

    def __str__(self):
        if self.body:
            return "[>>>] 0x%02x: %s" % (
                self.command_code.value,
                self.body.hex(),
            )
        else:
            return "[>>>] 0x%02x" % self.command_code.value


def check_ack_or_nak(message):
    """
    Check that the command was acknowledged.

    :param message: The incoming message. If the message was not acknowledged,
        a `CommandFailure` is raised.
    """
    value = message.body[-1]

    if value == 0x06:
        return
    elif value == 0x15:
        raise CommandFailure(command_code=message.command_code)
    else:
        raise RuntimeError("Unexpected ACK/NAK value (0x%02x)" % value)


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
    if body is None:
        return None, expected

    return (
        IncomingMessage(command_code=command_code, body=body),
        max(2 - len(buffer), 1),
    )


def format_message(command_code, body=b''):
    """
    Format a message for writing on the PLM.

    :param command_code: The command code.
    :param body: An optional body to send with the command.
    :returns: The formatted buffer, ready to be sent.
    """
    return bytes([MESSAGE_START_BYTE, command_code.value]) + body


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
        buffer[:len(discarded_bytes)] = []
        discarded_bytes = discarded_bytes.lstrip(b'\x00')

        if discarded_bytes:
            logger.warning(
                "Discarding %s unexpected byte(s): %s",
                len(discarded_bytes),
                discarded_bytes.hex(),
            )


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
