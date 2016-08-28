"""
A controller.
"""

import asyncio

from binascii import hexlify
from serial import (
    EIGHTBITS,
    PARITY_NONE,
    STOPBITS_ONE,
    serial_for_url,
)

from .exceptions import (
    AcknowledgmentFailure,
)
from .messages import (
    AllLinkRecordResponse,
    CancelAllLinkingRequest,
    CancelAllLinkingResponse,
    GetFirstAllLinkRecordRequest,
    GetFirstAllLinkRecordResponse,
    GetIMInfoRequest,
    GetIMInfoResponse,
    GetNextAllLinkRecordRequest,
    GetNextAllLinkRecordResponse,
    MessageSendRequest,
    MessageSendResponse,
    Response,
    StartAllLinkingRequest,
    StartAllLinkingResponse,
)
from .log import logger


class Controller(object):
    def __init__(self, *, serial_port_url, loop=None):
        assert serial_port_url

        self.serial_port_url = serial_port_url
        self.loop = loop or asyncio.get_event_loop()
        self.serial = serial_for_url(
            self.serial_port_url,
            baudrate=19200,
            parity=PARITY_NONE,
            stopbits=STOPBITS_ONE,
            bytesize=EIGHTBITS,
            timeout=1,
        )
        self.flush()
        self.serial_lock = asyncio.Lock()
        self._read_buffer = bytearray()
        self._responses = []

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

                if data:
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
        if data:
            async with self.serial_lock:
                logger.debug(
                    "Sent: %s (%s byte(s))",
                    hexlify(data).decode(),
                    len(data),
                )
                self.serial.write(data)

    async def send_request(self, request):
        """
        Send a request.

        :param request: The request.
        """
        logger.debug("Sending request: %s.", request)

        await request.write(self.write)

    async def recv_response(self, expected_class=None):
        """
        Receive a response.

        :param expected_class: The class of the expected response. Any other
            received message during that time will be stored for later
            retrieval.
        :returns: A response.
        """
        if expected_class:
            logger.debug(
                "Waiting for a response of type: %s.",
                expected_class.__name__,
            )

            response = next(
                (
                    r for r in self._responses
                    if isinstance(r, expected_class)
                ),
                None,
            )

            if response:
                self._responses.remove(response)
        else:
            logger.debug("Waiting for any response.")

            if self._responses:
                return self._responses.pop(0)

        while True:
            response = await Response.read(self.read)

            assert response

            if not expected_class or isinstance(response, expected_class):
                return response

            self._responses.append(response)

    async def get_im_info(self):
        await self.send_request(GetIMInfoRequest())
        response = await self.recv_response(expected_class=GetIMInfoResponse)

        return response.info

    async def get_all_link_records(self):
        records = []

        try:
            await self.send_request(GetFirstAllLinkRecordRequest())
            await self.recv_response(
                expected_class=GetFirstAllLinkRecordResponse,
            )

            while True:
                response = await self.recv_response(
                    expected_class=AllLinkRecordResponse,
                )
                records.append(response.record)

                await self.send_request(GetNextAllLinkRecordRequest())
                await self.recv_response(
                    expected_class=GetNextAllLinkRecordResponse,
                )

        except AcknowledgmentFailure:
            pass

        return records

    async def start_all_linking_session(self, all_link_code, all_link_group):
        await self.send_request(
            StartAllLinkingRequest(
                all_link_code=all_link_code,
                all_link_group=all_link_group,
            ),
        )
        return await self.recv_response(expected_class=StartAllLinkingResponse)

    async def cancel_all_linking_session(self):
        await self.send_request(CancelAllLinkingRequest())
        return await self.recv_response(
            expected_class=CancelAllLinkingResponse,
        )

    async def send_message(
        self,
        to,
        hops,
        flags,
        command_data,
        user_data=None,
    ):
        await self.send_request(MessageSendRequest(
            to=to,
            hops=hops,
            flags=flags,
            command_data=command_data,
        ))
        return await self.recv_response(expected_class=MessageSendResponse)
