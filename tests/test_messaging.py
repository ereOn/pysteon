"""
Tests for the messaging functions.
"""


from pysteon.messaging import (
    CommandCode,
    IncomingMessage,
    parse_message,
    parse_messages,
)


def test_parse_messages():
    messages = list(parse_messages(
        bytearray(
            b'\x02\x50\x0a\x0b\x0c\x01\x02\x03\xe0\x0a\x0b'
            b'\x02\x51\x0a\x0b\x0c\x01\x02\x03\xe0\x0a\x0b'
            b'\x01\x02\x03\x04\x05\x06\x07'
            b'\x01\x02\x03\x04\x05\x06\x07'
        ),
    ))

    assert messages == [
        IncomingMessage(
            command_code=CommandCode.standard_message_received,
            body=(
                b'\x0a\x0b\x0c\x01\x02\x03\xe0\x0a\x0b'
            ),
        ),
        IncomingMessage(
            command_code=CommandCode.extended_message_received,
            body=(
                b'\x0a\x0b\x0c\x01\x02\x03\xe0\x0a\x0b'
                b'\x01\x02\x03\x04\x05\x06\x07'
                b'\x01\x02\x03\x04\x05\x06\x07'
            ),
        ),
    ]


def test_parse_message_too_short():
    assert parse_message(bytearray(b'\x02')) is None


def test_parse_message_unknown_command_code():
    assert parse_message(bytearray(b'\x02\x00')) is None


def test_parse_message_incomplete_standard_message_received():
    assert parse_message(bytearray(b'\x02\x50\x0a')) is None


def test_parse_message_standard_message_received():
    message = parse_message(
        bytearray(b'\x02\x50\x0a\x0b\x0c\x01\x02\x03\xe0\x0a\x0b'),
    )

    assert message == IncomingMessage(
        command_code=CommandCode.standard_message_received,
        body=b'\x0a\x0b\x0c\x01\x02\x03\xe0\x0a\x0b',
    )


def test_parse_message_standard_message_received_padding():
    buffer = bytearray(b'\xff\x02\x50\x0a\x0b\x0c\x01\x02\x03\xe0\x0a\x0b\x55')
    message = parse_message(buffer)

    assert message == IncomingMessage(
        command_code=CommandCode.standard_message_received,
        body=b'\x0a\x0b\x0c\x01\x02\x03\xe0\x0a\x0b',
    )
    assert buffer == b'\x55'


def test_parse_message_invalid():
    assert parse_message(bytearray(b'\x01\x03')) is None
