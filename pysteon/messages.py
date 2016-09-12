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


class IMButtonEvent(IntEnum):
    set_button_tapped = 0x02
    set_button_hold = 0x03
    set_button_released = 0x04


class AllLinkCode(IntEnum):
    responder = 0x00
    controller = 0x01
    auto = 0x03
    unknown = 0xfe
    delete = 0xff


def has_bit(value, bit):
    return (value & (1 << bit)) != 0


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

    async def write_flags(self, write, hops, flags):
        hops_left, max_hops = hops
        flags_byte = (hops_left & 0x03) << 2 | (max_hops & 0x03)

        for flag in flags:
            flags_byte |= (1 << flag.value)

        await write(flags_byte.to_bytes(1, 'big'))


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
        response = await read(8)

        return cls(record=AllLinkRecord(
            flags=response[0],
            group=response[1],
            identity=Identity(response[2:5]),
            data=response[5:],
        ))

    def __init__(self, record):
        self.record = record


class MessageSendRequest(Request):
    command = b'\x62'

    def __init__(self, to, hops, flags, command_data, user_data=None):
        self.to = to
        self.hops = hops
        self.flags = flags
        self.command_data = command_data
        self.user_data = user_data

        assert len(hops) == 2, "hops must be a 2-tuple"
        assert len(command_data) == 2

        if self.user_data is None:
            self.flags.discard(Flags.extended)
        else:
            self.flags.add(Flags.extended)
            assert len(user_data) == 14

    async def write(self, write):
        await super().write(write)
        await write(self.to.value)
        await self.write_flags(write, self.hops, self.flags)
        await write(self.command_data)

        if self.user_data:
            await write(self.user_data)


class MessageSendResponse(Response):
    command = b'\x62'

    @classmethod
    async def read_payload(cls, read):
        to = Identity(await read(3))
        hops, flags = await cls.read_flags(read)
        command_data = await read(2)

        if Flags.extended in flags:
            user_data = await read(14)
        else:
            user_data = None

        await cls.read_ack_or_nak(read)

        return cls(
            to=to,
            hops=hops,
            flags=flags,
            command_data=command_data,
            user_data=user_data,
        )

    def __init__(self, to, hops, flags, command_data, user_data):
        self.to = to
        self.hops = hops
        self.flags = flags
        self.command_data = command_data
        self.user_data = user_data

    def __str__(self):
        return "Standard message sent to %s: %s, %s" % (
            self.to,
            hexlify(self.command_data).decode(),
            hexlify(self.user_data).decode()
            if self.user_data else '<no user data>',
        )


class StandardMessageReceivedResponse(Response):
    command = b'\x50'

    @classmethod
    async def read_payload(cls, read):
        from_ = Identity(await read(3))
        to = Identity(await read(3))

        hops, flags = await cls.read_flags(read)
        response = await read(2)

        return cls(
            from_=from_,
            to=to,
            hops=hops,
            flags=flags,
            command_data=response,
        )

    def __init__(self, from_, to, hops, flags, command_data):
        self.from_ = from_
        self.to = to
        self.hops = hops
        self.flags = flags
        self.command_data = command_data

    def __str__(self):
        return "Standard message from %s to %s: %s" % (
            self.from_,
            self.to,
            hexlify(self.command_data).decode(),
        )


class ExtendedMessageReceivedResponse(Response):
    command = b'\x51'

    @classmethod
    async def read_payload(cls, read):
        from_ = Identity(await read(3))
        to = Identity(await read(3))

        hops, flags = await cls.read_flags(read)
        response = await read(2)

        return cls(
            from_=from_,
            to=to,
            hops=hops,
            flags=flags,
            command_data=response[:2],
            user_data=response[2:],
        )

    def __init__(self, from_, to, hops, flags, command_data, user_data):
        self.from_ = from_
        self.to = to
        self.hops = hops
        self.flags = flags
        self.command_data = command_data
        self.user_data = user_data

    def __str__(self):
        return "Extended message from %s to %s: %s, %s" % (
            self.from_,
            self.to,
            hexlify(self.command_data).decode(),
            hexlify(self.user_data).decode(),
        )


class ResetRequest(Request):
    command = b'\x67'


class ResetResponse(Response):
    command = b'\x67'


class UserResetDetectedResponse(Response):
    command = b'\x55'

    def __str__(self):
        return "Insteon Modem was reset from user action"


class ButtonEventReportResponse(Response):
    command = b'\x54'

    @classmethod
    async def read_payload(cls, read):
        response = await read(1)

        return cls(event=IMButtonEvent(response[0]))

    def __init__(self, event):
        self.event = event

    def __str__(self):
        return "Insteon Modem button event report: %s" % self.event.name


class StartAllLinkingRequest(Request):
    command = b'\x64'

    def __init__(self, all_link_code, all_link_group):
        """
        Start an all-linking session.

        :param all_link_code: The link code enumeration value.
        :param all_link_group: The all-link group, as bytes.
        """
        self.all_link_code = all_link_code
        self.all_link_group = all_link_group

    async def write(self, write):
        await super().write(write)
        await write(self.all_link_code.value.to_bytes(1, 'big'))
        await write(self.all_link_group)


class StartAllLinkingResponse(Response):
    command = b'\x64'

    @classmethod
    async def read_payload(cls, read):
        response = await read(2)
        await cls.read_ack_or_nak(read)

        return cls(
            all_link_code=AllLinkCode(response[0]),
            all_link_group=response[1:],
        )

    def __init__(self, all_link_code, all_link_group):
        self.all_link_code = all_link_code
        self.all_link_group = all_link_group

    def __str__(self):
        return (
            "Insteon Modem all-linking session for group %s started in "
            "mode: %s"
        ) % (
            hexlify(self.all_link_group).decode(),
            self.all_link_code.name,
        )


class CancelAllLinkingRequest(Request):
    command = b'\x65'


class CancelAllLinkingResponse(Response):
    command = b'\x65'

    def __str__(self):
        return "Insteon Modem all-linking session was cancelled."


class AllLinkingCompleteResponse(Response):
    command = b'\x53'

    @classmethod
    async def read_payload(cls, read):
        response = await read(8)

        return cls(
            all_link_code=AllLinkCode(response[0]),
            all_link_group=response[1:2],
            identity=Identity(response[2:5]),
            device_category=response[5],
            device_subcategory=response[6],
            firmware_version=response[7],
        )

    def __init__(
        self,
        all_link_code,
        all_link_group,
        identity,
        device_category,
        device_subcategory,
        firmware_version,
    ):
        self.all_link_code = all_link_code
        self.all_link_group = all_link_group
        self.identity = identity
        self.device_category = device_category
        self.device_subcategory = device_subcategory
        self.firmware_version = firmware_version

    def __str__(self):
        return (
            "Insteon Modem all-linking complete with %s for group %s in "
            "mode: %s"
        ) % (
            self.identity,
            hexlify(self.all_link_group).decode(),
            self.all_link_code.name,
        )
