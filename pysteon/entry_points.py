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
from .log import logger


def _setup_logging(debug):
    chromalog.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='[%(levelname)s] %(message)s',
    )

    if debug:
        logging.getLogger('asyncio').setLevel(logging.INFO)


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
        print(loop.run_until_complete(plm.get_info()))
    except Exception as ex:
        if debug:
            logger.exception("Unexpected error.")
        else:
            logger.error("Unexpected error: %s.", ex)
