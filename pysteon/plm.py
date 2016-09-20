"""
PowerLine Modem interface.
"""

import asyncio

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
    def __init__(self, serial_port_url, loop=None):
        assert serial_port_url

        self.serial_port_url = serial_port_url
        self.loop = loop or asyncio.get_event_loop()
        self.on_event = Signal()
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
        self.__messages = []
        self.__has_new_messages = asyncio.Event(loop=self.loop)

    def close(self):
        self.__must_stop.set()
        self.__thread.join()
        self.__thread = None
        self._serial.close()
        self._serial = None

    def write(self, message):
        """
        Write a command to the PLM.

        :param message: A message to send.
        """
        logger.debug("%s", message)

        self._serial.write(
            format_message(
                command_code=message.command_code,
                body=message.body,
            ),
        )

    async def read(self, command_codes=None):
        """
        Read from the PLM.

        :param command_codes: An optional list of command codes to filter
            messages.
        :returns: The first message, that optionally matches on of the command
            codes.
        """
        while True:
            message = next(
                (
                    m for m in self.__messages
                    if m.command_code in command_codes or not command_codes
                ),
                None,
            )

            if message:
                self.__messages.remove(message)
                return message

            await self.__has_new_messages.wait()
            self.__has_new_messages.clear()

    async def get_info(self):
        self.write(OutgoingMessage(command_code=CommandCode.get_im_info))
        response = await self.read(command_codes={
            CommandCode.get_im_info,
        })
        identity = Identity(response.body[:3])
        devcat, subcat = parse_device_categories(response.body[3:5])
        firmware_version = response.body[5]
        check_ack_or_nak(CommandCode.get_im_info, response.body[-1])
        return identity, devcat, subcat, firmware_version

    # Private methods below.

    def _flush(self):
        self._serial.flushInput()
        self._serial.flushOutput()

    def _make_messages_ready(self, messages):
        for message in messages:
            logger.debug("%s", message)

        self.__messages.extend(messages)
        self.__has_new_messages.set()

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

                    if messages:
                        self.loop.call_soon_threadsafe(
                            self._make_messages_ready,
                            messages,
                        )
