"""
Message classes.
"""

from binascii import hexlify
from enum import IntEnum

from .exceptions import (
    AcknowledgmentFailure,
    SynchronizationError,
    UnknownCommandError,
)
from .log import logger
from .objects import (
    AllLinkRecord,
    IMInfo,
    Identity,
)


PREFIX_BYTE = b'\x02'
ACK_BYTE = b'\x06'
NAK_BYTE = b'\x15'


# Message flags.
class Flags(IntEnum):
    extended = 4
    ack = 5
    all_link = 6
    broadcast = 7


MESSAGE_SIZE = 7
EXTENDED_MESSAGE_SIZE = 21


def has_bit(value, bit):
    return (value & (1 << (7 - bit))) != 0


class IndexMeta(type):
    def __new__(cls, name, bases, attrs):
        index = attrs.setdefault(
            'index',
            next(
                (
                    getattr(base, 'index', None)
                    for base in bases
                    if hasattr(base, 'index')
                ),
                {},
            ),
        )
        class_ = super().__new__(cls, name, bases, attrs)

        command = getattr(class_, 'command', None)

        if command is not None:
            existing_class = index.get(command)

            assert not existing_class, (
                "A class was already registered (%s) for command 0x%s. "
                "Cannot register class %s" % (
                    existing_class.__name__,
                    hexlify(command).decode(),
                    name,
                )
            )
            index[command] = class_

        return class_


class IndexBase(object):
    """
    Base class for all indexed classes.
    """

    @classmethod
    def get_class_for_command(cls, command):
        try:
            return cls.index[bytes(command)]
        except KeyError:
            raise UnknownCommandError(command=command)

    def __str__(self):
        return self.__class__.__name__



class Request(IndexBase, metaclass=IndexMeta):
    """
    The base class for all requests.
    """
    async def write(self, write):
        """
        Write the request.

        :param write: The write method.
        """
        await write(PREFIX_BYTE)
        await write(self.command)


class Response(IndexBase, metaclass=IndexMeta):
    """
    The base class for all responses.
    """
    @classmethod
    async def read(cls, read):
        """
        Read the response.

        :param read: The read method.
        """
        prefix_byte = await read(1)

        if not prefix_byte == PREFIX_BYTE:
            raise SynchronizationError(
                "Expected a prefix byte but got %s instead" % \
                hexlify(prefix_byte).decode(),
            )

        command = await read(1)
        class_ = cls.get_class_for_command(command)

        return await class_.read_payload(read)

    @classmethod
    async def read_ack_or_nak(cls, read):
        ack_byte = await read(1)

        if ack_byte == NAK_BYTE:
            raise AcknowledgmentFailure(command=cls.command)
        elif ack_byte != ACK_BYTE:
            raise SynchronizationError(
                "Expected an ACK or NAK byte but got %s instead" % \
                hexlify(ack_byte).decode(),
            )

    @classmethod
    async def read_flags(cls, read):
        flags_byte = (await read(1))[0]
        max_hops = flags_byte & 0x03
        hops_left = (flags_byte & 0x0c) >> 2

        flags = {
            flag for flag in Flags
            if has_bit(flags_byte, flag.value)
        }

        logger.debug(
            "Flags: %s. Hops: %s/%s.",
            ', '.join(flag.name for flag in flags),
            hops_left,
            max_hops,
        )

        return (hops_left, max_hops), flags

    @classmethod
    async def read_payload(cls, read):
        await cls.read_ack_or_nak(read)
        return cls()


class GetIMInfoRequest(Request):
    command = b'\x60'


class GetIMInfoResponse(Response):
    command = b'\x60'

    @classmethod
    async def read_payload(cls, read):
        response = await read(6)
        await cls.read_ack_or_nak(read)

        return cls(info=IMInfo(
            identity=Identity(response[:3]),
            device_category=response[3],
            device_subcategory=response[4],
            firmware_version=response[5],
        ))

    def __init__(self, info):
        self.info = info


class GetFirstAllLinkRecordRequest(Request):
    command = b'\x69'


class GetFirstAllLinkRecordResponse(Response):
    command = b'\x69'


class GetNextAllLinkRecordRequest(Request):
    command = b'\x6A'


class GetNextAllLinkRecordResponse(Response):
    command = b'\x6A'


class AllLinkRecordResponse(Response):
    command = b'\x57'

    @classmethod
    async def read_payload(cls, read):
        _, flags = await cls.read_flags(read)
        response = await read(MESSAGE_SIZE)

        return cls(record=AllLinkRecord(
            group=response[0],
            identity=Identity(response[1:4]),
            data=response[4:],
        ))

    def __init__(self, record):
        self.record = record


class StandardMessageResponse(Response):
    command = b'\x50'

    @classmethod
    async def read_payload(cls, read):
        from_ = Identity(await read(3))
        to = Identity(await read(3))

        _, flags = await cls.read_flags(read)
        response = await read(2)

        return cls(from_=from_, to=to, command_data=response)

    def __init__(self, from_, to, command_data):
        self.from_ = from_
        self.to = to
        self.command_data = command_data

    def __str__(self):
        return "Standard message from %s to %s: %s" % (
            self.from_,
            self.to,
            hexlify(self.command_data).decode(),
        )


class ExtendedMessageResponse(Response):
    command = b'\x51'

    @classmethod
    async def read_payload(cls, read):
        from_ = Identity(await read(3))
        to = Identity(await read(3))

        _, flags = await cls.read_flags(read)
        response = await read(16)

        return cls(
            from_=from_,
            to=to,
            command_data=response[:2],
            user_data=response[2:],
        )

    def __init__(self, from_, to, command_data, user_data):
        self.from_ = from_
        self.to = to
        self.command_data = command_data
        self.user_data = user_data

    def __str__(self):
        return "Extended message from %s to %s: %s, %s" % (
            self.from_,
            self.to,
            hexlify(self.command_data).decode(),
            hexlify(self.user_data).decode(),
        )
