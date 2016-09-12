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
    AllLinkingCompleteResponse,
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

    async def foo():
        records = await controller.get_all_link_records()

        for record in records:
            print(record)

        logger.info("Turning led off")

        await controller.write(b'\x02\x6e')
        print(await controller.read(3))

        return
        await controller.start_all_linking_session(
            all_link_code=AllLinkCode.controller,
            all_link_group=b'\xfe',
        )

        print(await controller.recv_response(
            expected_class=AllLinkingCompleteResponse,
        ))

        await controller.start_all_linking_session(
            all_link_code=AllLinkCode.responder,
            all_link_group=b'\x01',
        )

        print(await controller.recv_response(
            expected_class=AllLinkingCompleteResponse,
        ))

        records = await controller.get_all_link_records()

        for record in records:
            print(record)

        for x in range(20):
            print(await controller.recv_response())

    loop.run_until_complete(foo())

    logger.info(
        "Pysteon closing...",
    )
    controller.close()
    logger.info(
        "Pysteon closed.",
    )
