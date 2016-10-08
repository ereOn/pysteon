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


class AllLinkModeType(click.ParamType):
    name = "All-link mode"
    def convert(self, value, param, ctx):
        try:
            return AllLinkMode.from_string(value)
        except ValueError:
            raise click.BadParameter(
                message="%s. Can be: %s" % (
                    value,
                    ', '.join(map(str, AllLinkMode)),
                ),
                ctx=ctx,
                param=param,
            )


@click.group(
    help="pysteon is a command-line interface (CLI) for managing and "
    "monitoring your Insteon network through a PLM device.",
)
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
    help="The serial port URL through which the PLM is exposed.",
)
@click.option(
    '-r',
    '--root',
    default=os.environ.get(
        'PYSTEON_ROOT',
        os.path.expanduser('~/.pysteon'),
    ),
    type=click.Path(file_okay=False, writable=True),
    help="The root path for all the configuration and database files.",
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

    ctx.obj['database'] = database
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


@pysteon.command(help="Show information about the PLM.")
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


@pysteon.command(help="Monitor the PLM for Insteon events.")
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


@pysteon.command(
    help="Associate the PLM with a new Insteon device (all-link).",
)
@click.option(
    '-g',
    '--group',
    default=0xff,
    type=click.IntRange(min=0x00, max=0xff),
    help="The group number to use during all-linking.",
)
@click.option(
    '-m',
    '--mode',
    default="auto",
    type=AllLinkModeType(),
    help="The All-link mode that the PLM uses.",
)
@click.option(
    '-t',
    '--timeout',
    default=30,
    help="The time to wait for a device to link, in seconds.",
)
@click.option(
    '-a',
    '--alias',
    default=None,
    help="An alias to associate to the device in case of an association.",
)
@click.option(
    '-d',
    '--description',
    default=None,
    help="A description to associate to the device.",
)
@click.pass_context
def link(ctx, group, mode, timeout, alias, description):
    debug = ctx.obj['debug']
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']

    try:
        logger.info(
            "Starting all-linking process on %s for group %s in mode '%s'...",
            important(plm),
            important(hex(group)),
            important(mode),
        )

        async def all_link(plm):
            async with plm.all_linking_session(group=group, mode=mode):
                logger.info(
                    "Waiting for a device to be all-linked for a maximum of %s"
                    " second(s)...",
                    timeout,
                )
                future = plm.wait_all_linking_completed()
                loop.add_signal_handler(signal.SIGINT, future.cancel)

                try:
                    all_link_info = await future
                except asyncio.CancelledError:
                    logger.warning(
                        "All linking was cancelled before completion.",
                    )
                    return
                finally:
                    loop.remove_signal_handler(signal.SIGINT)

                kwargs = {}

                if alias is not None:
                    kwargs['alias'] = alias

                if description is not None:
                    kwargs['description'] = description

                database.set_device(
                    identity=all_link_info['identity'],
                    categories=(
                        all_link_info['category'],
                        all_link_info['subcategory'],
                    ),
                )

        loop.add_signal_handler(signal.SIGINT, plm.interrupt)

        try:
            loop.run_until_complete(all_link(plm))
        finally:
            loop.remove_signal_handler(signal.SIGINT)

    except Exception as ex:
        if debug:
            logger.exception("Unexpected error.")
        else:
            logger.error("Unexpected error: %s.", ex)

    finally:
        logger.info("All-linking process completed.")
