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

from .exceptions import CommandFailure
from .log import logger as main_logger
from .messaging import (
    CommandCode,
    OutgoingMessage,
    check_ack_or_nak,
    format_message,
    parse_messages,
)
from .objects import (
    AllLinkMode,
    AllLinkRole,
    Identity,
    InsteonMessage,
    parse_all_link_record_response,
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
        self.on_insteon_message = Signal()

        self.on_message.connect(partial(logger.debug, "%s"))
        self.on_insteon_message.connect(partial(logger.debug, "%s"))

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
        self.__monitor_interrupt = asyncio.Event(loop=self.loop)

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
            "version: {self.firmware_version}, {self.serial_port_url})"
        ).format(self=self)

    def close(self):
        self.interrupt()
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

        check_ack_or_nak(response)
        identity = Identity(response.body[:3])
        device_category, device_subcategory = parse_device_categories(
            response.body[3:5],
        )
        firmware_version = response.body[5]

        return identity, device_category, device_subcategory, firmware_version

    async def get_all_link_records(self):
        """
        Get all controllers and responders associated to the PLM.

        :returns: A tuple (controllers, responders).
        """
        controllers = []
        responders = []

        try:
            async with self.__write_lock:
                read_command_code = CommandCode.get_first_all_link_record

                while True:
                    with self.read(
                        command_codes=[
                            read_command_code,
                            CommandCode.all_link_record_response,
                        ],
                    ) as queue:
                        self.write(read_command_code)
                        response = await queue.get()
                        check_ack_or_nak(response)

                        response = await queue.get()
                        record = parse_all_link_record_response(response.body)

                        if record.role == AllLinkRole.controller:
                            controllers.append(record)
                        else:
                            responders.append(record)

                        read_command_code = \
                            CommandCode.get_next_all_link_record
        except CommandFailure:
            # A NAK is generated to signal the end of the records.
            pass

        return sorted(controllers), sorted(responders)

    async def start_all_linking_session(self, group, mode=AllLinkMode.auto):
        """
        Start an all-linking session.

        :param group: The group to start the session for.
        :param mode: The mode to start the session as.
        """
        async with self.__write_lock:
            with self.read(
                command_codes=[CommandCode.start_all_linking],
            ) as queue:
                self.write(
                    CommandCode.start_all_linking,
                    bytes([mode.value, group]),
                )
                response = await queue.get()
                check_ack_or_nak(response)
                logger.debug(
                    "%s started all-linking session for group %s "
                    "in '%s' mode.",
                    self,
                    '%02x' % group,
                    mode,
                )

    async def cancel_all_linking_session(self):
        """
        Cancel an all-linking session.
        """
        async with self.__write_lock:
            with self.read(
                command_codes=[CommandCode.cancel_all_linking],
            ) as queue:
                self.write(CommandCode.cancel_all_linking)
                response = await queue.get()
                check_ack_or_nak(response)
                logger.debug("%s cancelled all-linking session", self)

    def all_linking_session(self, group, mode=AllLinkMode.auto):
        """
        An async context manager to start then cancel an all-linking session.

        :param group: The group to start the session for.
        :param mode: The mode to start the session as.
        """
        class AsyncContextManager(object):
            def __init__(self, plm, group, mode):
                self.plm = plm
                self.group = group
                self.mode = mode

            async def __aenter__(self):
                return await self.plm.start_all_linking_session(
                    group=self.group,
                    mode=self.mode,
                )

            async def __aexit__(self, *args):
                await self.plm.cancel_all_linking_session()

        return AsyncContextManager(plm=self, group=group, mode=mode)

    def interrupt(self):
        if not self.__monitor_interrupt.is_set():
            self.__monitor_interrupt.set()
            logger.debug("Monitoring interrupted.")

    async def monitor(self):
        self.__monitor_interrupt.clear()

        self.on_message.connect(self._monitor_message)

        try:
            await self.__monitor_interrupt.wait()
        finally:
            self.on_message.disconnect(self._monitor_message)

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

    def _monitor_message(self, message):
        # We only care about Insteon messages.
        if message.command_code not in {
            CommandCode.standard_message_received,
            CommandCode.extended_message_received,
        }:
            return

        insteon_message = InsteonMessage.from_message(message)
        self.on_insteon_message.emit(insteon_message)
