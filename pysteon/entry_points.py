"""
Entry points.
"""

import asyncio
import chromalog
import click
import logging
import os

from chromalog.mark.helpers.simple import important

from .plm import PowerLineModem
from .objects import AllLinkMode
from .log import logger


def _setup_logging(debug):
    if debug:
        chromalog.basicConfig(
            level=logging.DEBUG,
            format='[%(levelname)s] %(message)s',
        )
        logging.getLogger('asyncio').setLevel(logging.INFO)
    else:
        chromalog.basicConfig(
            level=logging.INFO,
            format='%(message)s',
        )


@click.group()
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
@click.pass_context
def pysteon(ctx, debug, serial_port_url):
    _setup_logging(debug=debug)
    ctx.obj = {'debug': debug}

    logger.debug(
        "Connecting with PowerLine Modem on serial port: %s. Please wait...",
        important(serial_port_url),
    )

    loop = ctx.obj['loop'] = asyncio.get_event_loop()
    plm = ctx.obj['plm'] = PowerLineModem(
        serial_port_url=serial_port_url,
        loop=loop,
    )

    @ctx.call_on_close
    def close_plm():
        logger.debug("Closing %s. Please wait...", important(str(plm)))
        plm.close()
        logger.debug("Closed %s.", important(str(plm)))

    logger.debug(
        "Connected with: %s.",
        important(str(plm)),
    )


@pysteon.command()
@click.pass_context
def info(ctx):
    debug = ctx.obj['debug']
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']

    try:
        logger.info(
            "Device information for PowerLine Modem on serial port: %s",
            important(plm.serial_port_url),
        )
        logger.info(
            "Device category: %s (%s)",
            important(plm.device_category.title),
            plm.device_category.examples,
        )
        logger.info(
            "Device subcategory: %s",
            important(plm.device_subcategory.title),
        )
        logger.info("Identity: %s", important(plm.identity))
        logger.info("Firmware version: %s", important(plm.firmware_version))

        controllers, responders = loop.run_until_complete(
            plm.get_all_link_records(),
        )

        if controllers:
            logger.info("Controllers:")

            for controller in controllers:
                logger.info("%s", controller)

        if responders:
            logger.info("Responders:")

            for responder in responders:
                logger.info("%s", responder)

        async def foo():
            #async with plm.all_linking_session(
            #    group=0x01,
            #    mode=AllLinkMode.delete,
            #):
            await asyncio.sleep(10)

        loop.run_until_complete(foo())

    except Exception as ex:
        if debug:
            logger.exception("Unexpected error.")
        else:
            logger.error("Unexpected error: %s.", ex)
