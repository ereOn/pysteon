"""
Entry points.
"""

import asyncio
import click

from .controller import Controller


@click.command()
def pysteon():
    loop = asyncio.get_event_loop()
    controller = Controller(loop=loop)
    print(loop.run_until_complete(controller.get_im_info()))
    controller.close()
