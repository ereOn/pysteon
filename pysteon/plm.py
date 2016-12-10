"""
PowerLine Modem interface.
"""

import asyncio

from contextlib import contextmanager
from functools import partial
from itertools import chain
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
    MessageFailure,
    OutgoingMessage,
    check_ack_or_nak,
    format_message,
    parse_messages,
)
from .objects import (
    AllLinkMode,
    AllLinkRole,
    DeviceInfo,
    Identity,
    InsteonMessage,
    InsteonMessageFlag,
    parse_all_link_record_response,
    parse_device_categories,
)
from .units import (
    led_brightness_from_percent,
    led_brightness_to_percent,
    on_level_from_percent,
    on_level_to_percent,
    ramp_rate_from_seconds,
    ramp_rate_to_seconds,
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
        self.on_message.connect(self._handle_message)
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

        info = self.loop.run_until_complete(self.get_info())
        self.identity = info['identity']
        self.device_category = info['category']
        self.device_subcategory = info['subcategory']
        self.firmware_version = info['firmware_version']

        self.on_all_linking_completed = Signal()
        self.on_all_linking_completed.connect(
            self._handle_all_linking_completed,
        )

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
        self._serial.flushOutput()

    @contextmanager
    def read(self, command_codes=None, handle_failures=False):
        """
        Read from the PLM.

        :param command_codes: An optional list of command codes to filter
            messages.
        :yields: A queue of messages that were read.
        """
        queue = asyncio.Queue(loop=self.loop)

        def read_one(message):
            if handle_failures and isinstance(message, Exception):
                queue.put_nowait(message)
            elif command_codes is None or message.command_code in command_codes:
                queue.put_nowait(message)

        self.on_message.connect(read_one)

        try:
            yield queue
        finally:
            self.on_message.disconnect(read_one)

    async def write_read(
        self,
        *,
        command_code,
        body=None,
        command_codes=None,
        retry_delay=0.5
    ):
        """
        Perform a write-read sequence with automatic retry on failure.

        :param command_code: The command code to write.
        :param body: The body to send.
        :param command_codes: An optional list of command codes to accept as
            responses.
        :returns: The first response.
        """
        async with self.__write_lock:
            try:
                with self.read(
                    command_codes=command_codes,
                    handle_failures=True,
                ) as queue:
                    response = None

                    while not response:
                        self.write(command_code=command_code, body=body or b'')
                        response = await queue.get()

                        if isinstance(response, MessageFailure):
                            logger.debug("Write operation failed. Retrying...")
                            response = None
                            await asyncio.sleep(retry_delay)
            except Exception:
                self._flush()
                raise

        return response

    @contextmanager
    def read_insteon_messages(self):
        """
        Context manager that reads Insteon messages.
        """
        async def read_queue(queue, insteon_queue):
            while True:
                response = await queue.get()
                insteon_message = InsteonMessage.from_message_body(
                    response.body,
                )
                insteon_queue.put_nowait(insteon_message)

        insteon_queue = asyncio.Queue(loop=self.loop)

        with self.read(
            command_codes=[
                CommandCode.standard_message_received,
                CommandCode.extended_message_received,
            ],
        ) as queue:
            read_queue_task = asyncio.ensure_future(
                read_queue(queue, insteon_queue),
            )

            try:
                yield insteon_queue
            finally:
                read_queue_task.cancel()

    async def get_info(self):
        """
        Get the PLM information.

        :returns: A 4-tuple (identity, device category, device subcategory,
            firmware version).
        """
        response = await self.write_read(
            command_code=CommandCode.get_im_info,
            command_codes=[CommandCode.get_im_info],
        )

        check_ack_or_nak(response)
        identity = Identity(response.body[:3])
        category, subcategory = parse_device_categories(
            response.body[3:5],
        )
        firmware_version = response.body[5]

        return {
            'identity': identity,
            'category': category,
            'subcategory': subcategory,
            'firmware_version': firmware_version,
        }

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
        response = await self.write_read(
            command_code=CommandCode.start_all_linking,
            body=bytes([mode.value, group]),
            command_codes=[CommandCode.start_all_linking],
        )
        check_ack_or_nak(response)
        logger.debug(
            "%s started all-linking session for group %s "
            "in '%s' mode.",
            self,
            hex(group),
            mode,
        )

    async def cancel_all_linking_session(self):
        """
        Cancel an all-linking session.
        """
        response = await self.write_read(
            command_code=CommandCode.cancel_all_linking,
            command_codes=[CommandCode.cancel_all_linking],
        )
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

    def wait_all_linking_completed(self):
        """
        Wait for an all-linking completed event.
        """
        future = asyncio.Future(loop=self.loop)

        def handler_func(
            future,
            identity,
            group,
            mode,
            category,
            subcategory,
            firmware_version,
        ):
            future.set_result({
                'identity': identity,
                'group': group,
                'mode': mode,
                'category': category,
                'subcategory': subcategory,
                'firmware_version': firmware_version,
            })

        handler = partial(handler_func, future)

        @future.add_done_callback
        def on_done(f):
            self.on_all_linking_completed.disconnect(handler)

        self.on_all_linking_completed.connect(handler)

        return future

    async def send_standard_or_extended_message(self, message):
        """
        Send a standard or extended message to the specified device.

        :param message: The Insteon message to send.
        """
        response = await self.write_read(
            command_code=CommandCode.send_standard_or_extended_message,
            body=message.to_message_body(),
            command_codes=[CommandCode.send_standard_or_extended_message],
        )
        check_ack_or_nak(response)

        return response

    async def id_request(self, identity):
        """
        Send an ID request to the specified device.

        :param identity: The device identity.
        """
        with self.read_insteon_messages() as queue:
            await self.send_standard_or_extended_message(
                message=InsteonMessage(
                    sender=self.identity,
                    target=identity,
                    hops_left=2,
                    max_hops=3,
                    flags=set(),
                    command_bytes=b'\x10\x00',
                    user_data=b'',
                )
            )

            while True:
                insteon_message = await queue.get()

                if insteon_message.sender == identity and \
                        insteon_message.target != self.identity:
                    category, subcategory = parse_device_categories(
                        insteon_message.target[0:2],
                    )
                    firmware_version = insteon_message.target[2]

                    return {
                        'identity': identity,
                        'category': category,
                        'subcategory': subcategory,
                        'firmware_version': firmware_version,
                    }

    async def light_on(self, identity, level=100.0, instant=False):
        """
        Send a light ON request to the specified device.

        :param identity: The device identity.
        :param level: The level to turn the light on to.
        :param instant: A flag that if set, cause the light level to change
            instantly.
        :returns: The effective level.
        """
        byte_value = on_level_from_percent(level)

        await self.send_standard_or_extended_message(
            message=InsteonMessage(
                sender=self.identity,
                target=identity,
                hops_left=2,
                max_hops=3,
                flags=set(),
                command_bytes=bytes([
                    0x12 if instant else 0x11,
                    byte_value,
                ]),
                user_data=b'',
            )
        )

        return on_level_to_percent(byte_value)

    async def light_off(self, identity, instant=False):
        """
        Send a light OFF request to the specified device.

        :param identity: The device identity.
        :param level: The level to turn the light off to.
        :param instant: A flag that if set, cause the light level to change
            instantly.
        """
        await self.send_standard_or_extended_message(
            message=InsteonMessage(
                sender=self.identity,
                target=identity,
                hops_left=2,
                max_hops=3,
                flags=set(),
                command_bytes=bytes([
                    0x14 if instant else 0x13,
                    0x00,
                ]),
                user_data=b'',
            )
        )

        return 0

    async def remote_enter_linking(self, identity, group=0x01):
        """
        Tell a remote device to enter linking mode.

        :param identity: The device identity.
        :param group: A group to enter remote linking into.
        """
        command_bytes = bytes([0x09, group])
        user_data = bytes([0x00] * 14)
        user_data = self._checksum(command_bytes, user_data)

        await self.send_standard_or_extended_message(
            message=InsteonMessage(
                sender=self.identity,
                target=identity,
                hops_left=2,
                max_hops=3,
                flags={InsteonMessageFlag.extended},
                command_bytes=command_bytes,
                user_data=user_data,
            )
        )

    async def remote_enter_unlinking(self, identity, group=0x01):
        """
        Tell a remote device to enter unlinking mode.

        :param identity: The device identity.
        :param group: A group to enter remote unlinking into.
        """
        command_bytes = bytes([0x0A, group])
        user_data = bytes([0x00] * 14)
        user_data = self._checksum(command_bytes, user_data)

        await self.send_standard_or_extended_message(
            message=InsteonMessage(
                sender=self.identity,
                target=identity,
                hops_left=2,
                max_hops=3,
                flags=set(),
                command_bytes=command_bytes,
                user_data=b'',
            )
        )

    async def remote_set(self, identity):
        """
        Emulates a remote tap of a set button.

        :param identity: The device identity.
        """
        command_bytes = bytes([0x25, 0x00])

        await self.send_standard_or_extended_message(
            message=InsteonMessage(
                sender=self.identity,
                target=identity,
                hops_left=2,
                max_hops=3,
                flags=set(),
                command_bytes=command_bytes,
                user_data=b'',
            )
        )

    async def beep(self, identity):
        """
        Emulates a remote tap of a set button.

        :param identity: The device identity.
        """
        command_bytes = bytes([0x30, 0x00])

        await self.send_standard_or_extended_message(
            message=InsteonMessage(
                sender=self.identity,
                target=identity,
                hops_left=2,
                max_hops=3,
                flags=set(),
                command_bytes=command_bytes,
                user_data=b'',
            )
        )

    async def get_device_info(self, identity):
        """
        Get device information.

        :param identity: The device identity.
        :return: The device information dict.
        """
        command_bytes = bytes([0x2e, 0x00])
        user_data = bytes([0x00] * 14)

        with self.read_insteon_messages() as queue:
            await self.send_standard_or_extended_message(
                message=InsteonMessage(
                    sender=self.identity,
                    target=identity,
                    hops_left=2,
                    max_hops=3,
                    flags={InsteonMessageFlag.extended},
                    command_bytes=command_bytes,
                    user_data=user_data,
                )
            )

            # First message is an ack.
            response = await queue.get()
            assert InsteonMessageFlag.ack in response.flags

            # Second one is the actual answer.
            response = await queue.get()
            return {
                'x10_house_code': response.user_data[4],
                'x10_unit_code': response.user_data[5],
                'ramp_rate': ramp_rate_to_seconds(response.user_data[6]),
                'on_level': on_level_to_percent(response.user_data[7]),
                'led_level': led_brightness_to_percent(
                    response.user_data[8],
                ),
            }

    async def set_device_info(self, identity, device_info, value):
        """
        Set device information.

        :param identity: The device identity.
        :param device_info: The device information to set.
        :param value: The value.
        :return: The used value.
        """
        command_bytes = bytes([0x2e, 0x00])

        if device_info == DeviceInfo.ramp_rate:
            device_info_byte_index = 2
            device_info_byte_value = ramp_rate_from_seconds(value)
            value = ramp_rate_to_seconds(device_info_byte_value)
        elif device_info == DeviceInfo.led_brightness:
            device_info_byte_index = 2
            device_info_byte_value = led_brightness_from_percent(value)
            value = led_brightness_to_percent(device_info_byte_value)
        elif device_info == DeviceInfo.on_level:
            device_info_byte_index = 2
            device_info_byte_value = on_level_from_percent(value)
            value = on_level_to_percent(device_info_byte_value)
        elif device_subcategory == DeviceInfo.x10_address:
            return 0
        else:
            raise RuntimeError(
                "Command %s is not supported for this device." % device_info,
            )

        user_data = bytes(chain(
            [0, device_info.value],
            [
                device_info_byte_value if i == device_info_byte_index else 0x00
                for i in range(2, 14)
            ],
        ))
        user_data = self._checksum(command_bytes, user_data)

        with self.read_insteon_messages() as queue:
            await self.send_standard_or_extended_message(
                message=InsteonMessage(
                    sender=self.identity,
                    target=identity,
                    hops_left=2,
                    max_hops=3,
                    flags={InsteonMessageFlag.extended},
                    command_bytes=command_bytes,
                    user_data=user_data,
                )
            )

            # First message is an ack.
            response = await queue.get()
            assert InsteonMessageFlag.ack in response.flags

        return value


    # Private methods below.

    @staticmethod
    def _checksum(command_bytes, user_data):
        assert len(command_bytes) == 2
        assert len(user_data) == 14

        s = sum(chain(command_bytes, user_data[:-1]))
        return bytes(chain(user_data[:-1], [((0xff ^ s) + 1) & 0xff]))

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

    def _handle_message(self, message):
        if message.command_code == CommandCode.all_linking_completed:
            try:
                mode = AllLinkMode(message.body[0])
            except ValueError:
                mode = None

            group = message.body[1]
            identity = Identity(message.body[2:5])
            category, subcategory = parse_device_categories(
                message.body[5:7],
            )
            firmware_version = message.body[7]

            self.on_all_linking_completed.emit(
                identity=identity,
                group=group,
                mode=mode,
                category=category,
                subcategory=subcategory,
                firmware_version=firmware_version,
            )
        elif message.command_code in {
            CommandCode.standard_message_received,
            CommandCode.extended_message_received,
        }:
            insteon_message = InsteonMessage.from_message_body(message.body)
            self.on_insteon_message.emit(insteon_message)

    def _monitor_message(self, message):
        pass

    def _handle_all_linking_completed(
        self,
        identity,
        group,
        mode,
        category,
        subcategory,
        firmware_version,
    ):
        if mode is None:
            logger.debug(
                "All linking deletion failed with device %s-%s (%s) as no "
                "existing entry was found.",
                identity,
                '%02x' % group,
                subcategory,
            )
        else:
            logger.debug(
                "All linking with device %s-%s (%s) in mode %s is complete.",
                identity,
                '%02x' % group,
                subcategory,
                mode,
            )
