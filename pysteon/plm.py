"""
PowerLine Modem interface.
"""

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

from .log import logger
from .messaging import parse_messages


class PowerLineModem(object):
    """
    Represents a PowerLine Modem that responds and controls Insteon devices.
    """
    def __init__(self, serial_port_url):
        assert serial_port_url

        self.serial_port_url = serial_port_url
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

    def close(self):
        self.__must_stop.set()
        self.__thread.join()
        self.__thread = None
        self._serial.close()
        self._serial = None

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

                    if messages:
                        # TODO: Advertise somehow.
                        for message in messages:
                            print(message)
