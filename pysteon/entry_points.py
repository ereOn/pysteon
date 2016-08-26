"""
Entry points.
"""

import asyncio
import click

from .controller import Controller


@click.command()
def pysteon():
    controller = Controller()
    loop = asyncio.get_event_loop()
    print("READY")
    controller.serial.flushInput()
    controller.serial.flushOutput()
    controller.serial.write(b'\x02\x60')
    #controller.serial.write(b'\x02\x62\x3e\x38\x47\x0f\x11\xff')
    controller.serial.flush()
    for x in range(32):
        print(controller.serial.read())
    print("DONE")
    controller.close()
