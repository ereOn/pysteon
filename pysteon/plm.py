"""
PowerLine Modem interface.
"""

import asyncio

from contextlib import contextmanager
from functools import partial
from pyslot.thread_safe_signal import ThreadSafeSignal as Signal
from serial import (
    EIGHTBITS,
    PARITY_NONE,
    STOPBITS_ONE,
    serial_for_url,
)
from threading import (
    Event,
    Thread,
)

from .log import logger as main_logger
from .messaging import (
    CommandCode,
    OutgoingMessage,
    check_ack_or_nak,
    format_message,
    parse_messages,
)
from .objects import (
    Identity,
    parse_device_categories,
)

logger = main_logger.getChild('serial')


class PowerLineModem(object):
    """
    Represents a PowerLine Modem that responds and controls Insteon devices.
    """
    def __init__(self, serial_port_url, on_message=None, loop=None):
        assert serial_port_url

        self.serial_port_url = serial_port_url
        self.loop = loop or asyncio.get_event_loop()
        self.on_message = Signal()

        self.on_message.connect(partial(logger.debug, "%s"))

        if on_message:
            self.on_message.connect(on_message)

        self._serial = serial_for_url(
            self.serial_port_url,
            baudrate=19200,
            parity=PARITY_NONE,
            stopbits=STOPBITS_ONE,
            bytesize=EIGHTBITS,
            timeout=1,
        )
        self._flush()
        self.__must_stop = Event()
        self.__thread = Thread(target=self._run)
        self.__thread.daemon = True
        self.__thread.start()
        self.__write_lock = asyncio.Lock(loop=self.loop)

        logger.debug("Querying PLM's information...")
        (
            self.identity,
            self.device_category,
            self.device_subcategory,
            self.firmware_version,
        ) = self.loop.run_until_complete(self.get_info())

    def __str__(self):
        return (
            "{self.device_subcategory.title} ({self.identity}, firmware "
            "version: {self.firmware_version})"
        ).format(self=self)

    def close(self):
        self.__must_stop.set()
        self.__thread.join()
        self.__thread = None
        self._serial.close()
        self._serial = None

    def write(self, *args, **kwargs):
        """
        Write a command to the PLM.

        :param args: The arguments to pass to the `OutgoingMessage`
            constructor.
        """
        message = OutgoingMessage(*args, **kwargs)
        logger.debug("%s", message)

        self._serial.write(
            format_message(
                command_code=message.command_code,
                body=message.body,
            ),
        )

    @contextmanager
    def read(self, command_codes=None):
        """
        Read from the PLM.

        :param command_codes: An optional list of command codes to filter
            messages.
        :yields: A queue of messages that were read.
        """
        queue = asyncio.Queue(loop=self.loop)

        def read_one(message):
            if command_codes is None or message.command_code in command_codes:
                queue.put_nowait(message)

        self.on_message.connect(read_one)

        try:
            yield queue
        finally:
            self.on_message.disconnect(read_one)

    async def get_info(self):
        """
        Get the PLM information.

        :returns: A 4-tuple (identity, device category, device subcategory,
            firmware version).
        """
        async with self.__write_lock:
            with self.read(command_codes=[CommandCode.get_im_info]) as queue:
                self.write(command_code=CommandCode.get_im_info)
                response = await queue.get()

        identity = Identity(response.body[:3])
        device_category, device_subcategory = parse_device_categories(
            response.body[3:5],
        )
        firmware_version = response.body[5]
        check_ack_or_nak(CommandCode.get_im_info, response.body[-1])

        return identity, device_category, device_subcategory, firmware_version

    # Private methods below.

    def _flush(self):
        self._serial.flushInput()
        self._serial.flushOutput()

    def _run(self):
        buffer = bytearray()
        expected = 2

        while not self.__must_stop.is_set():
            try:
                data = self._serial.read(expected)
            except Exception:
                logger.exception(
                    "Unexpected error while reading from serial port.",
                )
            else:
                if data:
                    buffer.extend(data)

                    messages, expected = parse_messages(buffer)

                    for message in messages:
                        self.loop.call_soon_threadsafe(
                            self.on_message.emit,
                            message,
                        )
