"""
Entry points.
"""

import asyncio
import chromalog
import click
import logging
import os

from chromalog.mark.helpers.simple import important

from .controller import Controller
from .log import logger
from .messages import (
    AllLinkCode,
    Flags,
)


def setup_logging(debug):
    chromalog.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='[%(levelname)s] %(message)s',
    )

    if debug:
        logging.getLogger('asyncio').setLevel(logging.INFO)


@click.command()
@click.option(
    '-d',
    '--debug',
    is_flag=True,
    default=None,
    help="Enabled debug output.",
)
@click.option(
    '-s',
    '--serial-port-url',
    default=os.environ.get('PYSTEON_SERIAL_PORT_URL', '/dev/ttyUSB0'),
)
def pysteon(debug, serial_port_url):
    setup_logging(debug=debug)
    loop = asyncio.get_event_loop()

    logger.info(
        "Pysteon starting on serial port: %s. Please wait...",
        important(serial_port_url),
    )
    controller = Controller(
        serial_port_url=serial_port_url,
        loop=loop,
    )
    im_info = loop.run_until_complete(controller.get_im_info())

    logger.info(
        "Pysteon started. Connected to: %s",
        important(im_info),
    )
    records = loop.run_until_complete(controller.get_all_link_records())

    for record in records:
        print(record)

    for x in range(5):
        print(
            loop.run_until_complete(
                controller.send_message(
                    to=records[-1].identity,
                    hops=(3, 3),
                    flags=set(),
                    command_data=b'\x11\xff',
                ),
            ),
        )

        import time
        time.sleep(1)

        print(
            loop.run_until_complete(
                controller.send_message(
                    to=records[-1].identity,
                    hops=(3, 3),
                    flags=set(),
                    command_data=b'\x13\xff',
                ),
            ),
        )

        import time
        time.sleep(1)


    for _ in range(25):
        print(loop.run_until_complete(controller.recv_response()))

    logger.info(
        "Pysteon closing...",
    )
    controller.close()
    logger.info(
        "Pysteon closed.",
    )
