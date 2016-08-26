"""
A controller.
"""

import asyncio
import os

from io import (
    BytesIO,
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


class Controller(object):
    def __init__(self, *, serial_port_url=None, loop=None):
        # TODO: Move this higher in the chain. That's too much logic for here.
        self.serial_port_url = serial_port_url or os.environ.get(
            'PYSTEON_SERIAL_PORT_URL',
            '/dev/ttyUSB0',
        )
        self.loop = loop or asyncio.get_event_loop()
        self.serial = serial_for_url(
            self.serial_port_url,
            baudrate=19200,
            parity=PARITY_NONE,
            stopbits=STOPBITS_ONE,
            bytesize=EIGHTBITS,
            timeout=1,
        )
        self.serial.flushInput()
        self.serial.flushOutput()
        self.serial_lock = asyncio.Lock()
        self.read_buffer = BytesIO()


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
            while self.read_buffer.getbuffer().nbytes < cnt:
                data = await self.loop.run_in_executor(None, self.serial.read, cnt)

                self.read_buffer.seek(0, SEEK_END)
                self.read_buffer.write(data)

            self.read_buffer.seek(0, SEEK_SET)
            return self.read_buffer.read(cnt)

    async def write(self, data, flush=True):
        """
        Write data on the controller.

        :param data: The data to write.
        """
        async with self.serial_lock:
            self.serial.write(data)

            if flush:
                self.serial.flush()

    async def get_im_info(self):
        await self.write(b'\x02\x60')
        result = await self.read(9)
        # TODO: Make this better. I assume responses can be out of order.
        assert result[0] == 0x02
        assert result[1] == 0x60
        identifier = '%02x.%02x.%02x' % tuple(result[2:5])
        return identifier
