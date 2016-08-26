"""
A controller.
"""

import asyncio
import os

from serial import (
    EIGHTBITS,
    PARITY_NONE,
    STOPBITS_ONE,
    serial_for_url,
)
from serial.aio import create_serial_connection


class Controller(object):
    def __init__(self, serial_port_url=None, loop=None):
        self.serial_port_url = serial_port_url or os.environ.get(
            'PYSTEON_SERIAL_PORT_URL',
            '/dev/ttyUSB0',
        )
        self.loop = loop or asyncio.get_event_loop()
        self.serial = serial_for_url(self.serial_port_url)

    def close(self):
        if self.serial:
            self.serial.close()
            self.serial = None
