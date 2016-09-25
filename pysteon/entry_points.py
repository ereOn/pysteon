"""
Entry points.
"""

import asyncio
import chromalog
import click
import logging
import os
import signal

from chromalog.mark.helpers.simple import (
    important,
    error,
)

from .database import Database
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
@click.option(
    '-r',
    '--root',
    default=os.environ.get(
        'PYSTEON_ROOT',
        os.path.expanduser('~/.pysteon'),
    ),
    type=click.Path(file_okay=False, writable=True),
)
@click.pass_context
def pysteon(ctx, debug, serial_port_url, root):
    _setup_logging(debug=debug)
    ctx.obj = {'debug': debug}

    logger.debug("Using configuration root at: %s.", important(root))

    # Make sure the root directory exists.
    os.makedirs(root, exist_ok=True)

    database_path = os.path.join(root, 'database.yml')

    try:
        with open(database_path) as database_file:
            logger.debug("Loading database at %s.", important(database_path))
            database = Database.load_from_stream(database_file)
    except OSError:
        logger.debug(
            "No database found at %s. A default one will be used.",
            important(database_path),
        )
        database = Database()

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
        logger.debug("Saving database at %s.", important(database_path))

        try:
            with open(database_path, 'w') as database_file:
                database.save_to_stream(database_file)
        except OSError as ex:
            logger.warning(
                "Could not save updated database to %s ! Error was: %s",
                important(database_path),
                error(str(ex)),
            )

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

    except Exception as ex:
        if debug:
            logger.exception("Unexpected error.")
        else:
            logger.error("Unexpected error: %s.", ex)


@pysteon.command()
@click.pass_context
def monitor(ctx):
    debug = ctx.obj['debug']
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']

    try:
        logger.info(
            "Monitoring %s...",
            important(plm),
        )

        loop.add_signal_handler(signal.SIGINT, plm.interrupt)

        try:
            loop.run_until_complete(plm.monitor())
        finally:
            loop.remove_signal_handler(signal.SIGINT)
            logger.info(
                "No longer monitoring %s.",
                important(plm),
            )

    except Exception as ex:
        if debug:
            logger.exception("Unexpected error.")
        else:
            logger.error("Unexpected error: %s.", ex)
