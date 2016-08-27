"""
A controller.
"""

import asyncio

from binascii import hexlify
from collections import defaultdict
from io import (
    SEEK_END,
    SEEK_SET,
)
from serial import (
    EIGHTBITS,
    PARITY_NONE,
    STOPBITS_ONE,
    serial_for_url,
)
from serial.aio import create_serial_connection

from .exceptions import (
    AcknowledgmentFailure,
    ReadTimeout,
    SynchronizationError,
)
from .log import logger
from .objects import (
    AllLinkRecord,
    Identity,
    IMInfo,
)


def get_bit(value, bit):
    return (value & (1 << bit)) != 0


class Controller(object):
    PREFIX_BYTE = b'\x02'
    ACK_BYTE = b'\x06'
    NAK_BYTE = b'\x15'

    # Commands.
    GET_IM_INFO = b'\x60'
    GET_FIRST_ALL_LINK_RECORD = b'\x69'
    GET_NEXT_ALL_LINK_RECORD = b'\x6A'
    ALL_LINK_RECORD_RESPONSE = b'\x57'

    def __init__(self, *, serial_port_url, read_timeout=0.5, loop=None):
        assert serial_port_url

        self.serial_port_url = serial_port_url
        self.loop = loop or asyncio.get_event_loop()
        self.serial = serial_for_url(
            self.serial_port_url,
            baudrate=19200,
            parity=PARITY_NONE,
            stopbits=STOPBITS_ONE,
            bytesize=EIGHTBITS,
            timeout=read_timeout,
        )
        self.flush()
        self.serial_lock = asyncio.Lock()
        self._read_buffer = bytearray()
        self._messages = defaultdict(list)

    def flush(self):
        self.serial.flushInput()
        self.serial.flushOutput()

    def close(self):
        if self.serial:
            self.serial.close()
            self.serial = None

    async def read(self, cnt):
        """
        Read on the controller until cnt bytes were fetched.

        :param cnt: The number of bytes to wait for.
        :returns: The bytes read.
        """
        async with self.serial_lock:
            while len(self._read_buffer) < cnt:
                data = await self.loop.run_in_executor(
                    None,
                    self.serial.read,
                    cnt,
                )

                if not data:
                    raise ReadTimeout(
                        expected_size=cnt,
                        data=self._read_buffer,
                    )

                logger.debug(
                    "Read: %s (%s byte(s))",
                    hexlify(data).decode(),
                    len(data),
                )

                self._read_buffer.extend(data)

            result = self._read_buffer[:cnt]
            self._read_buffer[:] = self._read_buffer[cnt:]

            return result

    async def write(self, data):
        """
        Write data on the controller.

        :param data: The data to write.
        """
        async with self.serial_lock:
            logger.debug(
                "Sent: %s (%s byte(s))",
                hexlify(data).decode(),
                len(data),
            )
            self.serial.write(data)

    async def communicate(self, command, params=b'', expected_size=0):
        """
        Send a command and wait for a response of the specified size or fail.

        :param command: The command to send, without any prefix.
        :param expected_size: The expected size of the response, without its
            prefix or suffix.
        :returns: The response, without any prefix or suffix.
        """
        logger.debug(
            "Sending command: %s (%s). Expecting %s byte(s) back.",
            hexlify(command).decode(),
            hexlify(params).decode(),
            expected_size,
        )
        await self.write(self.PREFIX_BYTE)
        await self.write(command)

        prefix_byte = await self.read(1)

        if not prefix_byte == self.PREFIX_BYTE:
            raise SynchronizationError(
                "Expected a prefix byte but got %s instead" % \
                hexlify(prefix_byte).decode(),
            )

        command_byte = await self.read(1)

        if not command_byte == command:
            raise SynchronizationError(
                "Expected a command byte but got %s instead" % \
                hexlify(command_byte).decode(),
            )

        response = await self.read(expected_size)

        ack_byte = await self.read(1)

        if ack_byte == self.NAK_BYTE:
            raise AcknowledgmentFailure(command=command)
        elif ack_byte != self.ACK_BYTE:
            raise SynchronizationError(
                "Expected an ACK byte but got %s instead" % \
                hexlify(ack_byte).decode(),
            )

        logger.debug("Received response: %s.", hexlify(response).decode())

        return response

    async def read_message(self, command=None):
        """
        Wait for a message to arrive.

        :param command: The expected command to receive. If not specified, the
            first received command will be returned.
        """
        if command:
            logger.debug(
                "Waiting for a message of type: %s.",
                hexlify(command).decode(),
            )

            if self._messages.get(command):
                return self._messages[command].pop(0)
        else:
            logger.debug("Waiting for any message.")

        response = None

        while not response:
            prefix_byte = await self.read(1)

            if not prefix_byte == self.PREFIX_BYTE:
                raise SynchronizationError(
                    "Expected a prefix byte but got %s instead" % \
                    hexlify(prefix_byte).decode(),
                )

            command_byte = await self.read(1)
            flags_byte = (await self.read(1))[0]
            max_hops = flags_byte & 0x03
            hops_left = (flags_byte & 0x0c) >> 2

            flags = dict(
                extended=get_bit(flags_byte, 4),
                ack=get_bit(flags_byte, 5),
                all_link=get_bit(flags_byte, 6),
                broadcast=get_bit(flags_byte, 7),
            )
            expected_size = 21 if flags['extended'] else 7

            response = await self.read(expected_size)

            logger.debug(
                "Received message of type %s: %s. Info: %d/%d hops. Flags: %s",
                hexlify(command_byte).decode(),
                hexlify(response).decode(),
                hops_left,
                max_hops,
                ', '.join(
                    flag for flag, is_set in flags.items() if is_set
                ),
            )

            if command is not None and command_byte != command:
                self._messages[command_byte].append(response)
                response = None

        return response

    async def get_im_info(self):
        response = await self.communicate(
            command=self.GET_IM_INFO,
            expected_size=6,
        )

        return IMInfo(
            identity=Identity(response[:3]),
            device_category=response[3],
            device_subcategory=response[4],
            firmware_version=response[5],
        )

    async def get_all_link_records(self):
        records = []

        try:
            await self.communicate(command=self.GET_FIRST_ALL_LINK_RECORD)

            while True:
                response = await self.read_message(
                    command=self.ALL_LINK_RECORD_RESPONSE,
                )
                records.append(AllLinkRecord(
                    group=response[0],
                    identity=Identity(response[1:4]),
                    data=response[4:],
                ))

                await self.communicate(command=self.GET_NEXT_ALL_LINK_RECORD)

        except AcknowledgmentFailure:
            pass

        return records
