"""
Entry points.
"""

import asyncio
import chromalog
import click
import logging
import os
import signal

from binascii import hexlify
from chromalog.mark.helpers.simple import (
    error,
    important,
    success,
)
from itertools import chain

from .automation import Automate
from .database import Database
from .plm import PowerLineModem
from .objects import (
    AllLinkMode,
    DeviceInfo,
    Identity,
)
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


class IdentityType(click.ParamType):
    name = "Identity"
    def convert(self, value, param, ctx):
        try:
            return Identity.from_string(value)
        except ValueError:
            raise click.BadParameter(
                message=value,
                ctx=ctx,
                param=param,
            )


class DeviceType(click.ParamType):
    name = "Device"

    def __init__(self, required=True):
        super().__init__()
        self.required = required

    def convert(self, value, param, ctx):
        database = ctx.obj['database']

        try:
            identity = Identity.from_string(value)
        except ValueError:
            device = database.get_device_by_alias(value)
        else:
            device = database.get_device(identity)

        if not device and self.required:
            raise click.BadParameter(
                message="No such device: %s" % value,
                ctx=ctx,
                param=param,
            )

        return device


class DeviceInfoType(click.ParamType):
    name = "DeviceInfo"

    def convert(self, value, param, ctx):
        try:
            return DeviceInfo.from_string(value)
        except ValueError:
            raise click.BadParameter(
                message="%s. Can be: %s" % (
                    value,
                    ', '.join(map(str, DeviceInfo)),
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
    help="Enable debug output.",
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
def pysteon(ctx, debug, root):
    _setup_logging(debug=debug)
    ctx.obj = {'debug': debug}

    logger.debug("Using configuration root at: %s.", important(root))

    # Make sure the root directory exists.
    os.makedirs(root, exist_ok=True)

    database_path = os.path.join(root, 'database.sqlite')

    try:
        logger.debug("Loading database at %s.", important(database_path))
        database = Database.load_from_file(database_path)
    except OSError:
        logger.debug(
            "No database found at %s. A default one will be used.",
            important(database_path),
        )
        database = Database()

    ctx.obj['database'] = database

    @ctx.call_on_close
    def close():
        logger.debug("Closing database at %s.", important(database_path))

        try:
            database.close()
        except OSError as ex:
            logger.warning(
                "Could not close database to %s ! Error was: %s",
                important(database_path),
                error(str(ex)),
            )


@pysteon.group(
    help="Manage and monitor the Insteon devices network.",
)
@click.option(
    '-s',
    '--serial-port-url',
    default=os.environ.get('PYSTEON_SERIAL_PORT_URL', '/dev/ttyUSB0'),
    help="The serial port URL through which the PLM is exposed.",
)
@click.pass_context
def plm(ctx, serial_port_url):
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
    def close():
        logger.debug("Closing %s. Please wait...", important(str(plm)))
        plm.close()
        logger.debug("Closed %s.", important(str(plm)))

    logger.debug(
        "Connected with: %s.",
        important(str(plm)),
    )


@plm.command(help="Show information about the PLM.")
@click.option(
    '-f',
    '--fetch',
    is_flag=True,
    default=None,
    help="Fetch missing information about devices.",
)
@click.pass_context
def info(ctx, fetch):
    debug = ctx.obj['debug']
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']
    database = ctx.obj['database']

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

        devices = database.get_devices()

        if fetch:
            missing_device_identities = {
                record.identity for record in chain(controllers, responders)
                if devices.get(record.identity) is None
            }

            if missing_device_identities:
                logger.info(
                    "Fetching missing device information for %d device(s)...",
                    len(missing_device_identities),
                )

                for index, identity in enumerate(
                    missing_device_identities,
                    start=1,
                ):
                    logger.info(
                        "[%d/%d] %s...",
                        index,
                        len(missing_device_identities),
                        identity,
                    )

                    try:
                        device_info = loop.run_until_complete(
                            asyncio.wait_for(
                                plm.id_request(identity),
                                2,
                            ),
                        )
                    except asyncio.TimeoutError:
                        logger.info(
                            "[%d/%d] %s: %s",
                            index,
                            len(missing_device_identities),
                            identity,
                            error("timed out"),
                        )
                    else:
                        devices[identity] = database.set_device(
                            identity=device_info['identity'],
                            alias=None,
                            description=None,
                            category=device_info['category'],
                            subcategory=device_info['subcategory'],
                            firmware_version=device_info['firmware_version'],
                        )
                        logger.info(
                            "[%d/%d] %s: %s",
                            index,
                            len(missing_device_identities),
                            identity,
                            success("success"),
                        )

                logger.info("Done fetching missing device information.")

        if controllers:
            logger.info("Controllers:")

            for controller in controllers:
                device = devices.get(controller.identity)

                if device:
                    logger.info("%s - %s", controller, success(device))
                else:
                    logger.info("%s", controller)

        if responders:
            logger.info("Responders:")

            for responder in responders:
                device = devices.get(responder.identity)

                if device:
                    logger.info("%s - %s", responder, success(device))
                else:
                    logger.info("%s", responder)

    except Exception as ex:
        if debug:
            logger.exception("Unexpected error.")
        else:
            logger.error("Unexpected error: %s.", ex)


@plm.command(help="Monitor the PLM for Insteon events.")
@click.option(
    '-m',
    '--automate-module',
    default=None,
    help="A python module path to load for automation.",
)
@click.pass_context
def monitor(ctx, automate_module):
    debug = ctx.obj['debug']
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']
    database = ctx.obj['database']

    try:
        logger.info(
            "Monitoring %s...",
            important(plm),
        )

        loop.add_signal_handler(signal.SIGINT, plm.interrupt)
        automate = Automate(plm=plm, database=database)

        automate.load_module('pysteon.automation.default')

        if automate_module:
            automate.load_module(automate_module)

        with automate:
            try:
                loop.run_until_complete(
                    plm.monitor(on_event_callback=automate.handle_message),
                )
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


@plm.command(
    help="Associate the PLM with a new Insteon device.",
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
    database = ctx.obj['database']

    try:
        logger.info(
            "Starting all-linking process on %s for group %s in mode '%s'...",
            important(plm),
            important(hex(group)),
            important(mode),
        )

        async def all_link(plm, alias, description):
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

                if all_link_info['mode'] is None:
                    logger.warning(
                        "All linking failed with %s-%s (%s) in mode %s.",
                        important(all_link_info['identity']),
                        hex(all_link_info['group']),
                        all_link_info['subcategory'],
                        important(mode),
                    )
                else:
                    logger.info(
                        "All linking succeeded with %s-%s (%s) in mode %s.",
                        important(all_link_info['identity']),
                        hex(all_link_info['group']),
                        all_link_info['subcategory'],
                        important(mode),
                    )

                identity = all_link_info['identity']
                device = database.get_device(identity)

                # Make sure to keep the existing information.
                if device:
                    logger.info(
                        "Device %s is known already. Updating the entry.",
                        device,
                    )

                    if alias is None:
                        alias = device.alias

                    if description is None:
                        description = device.description

                database.set_device(
                    identity=identity,
                    alias=alias,
                    description=description,
                    category=all_link_info['category'],
                    subcategory=all_link_info['subcategory'],
                    firmware_version=all_link_info['firmware_version'],
                )

        loop.add_signal_handler(signal.SIGINT, plm.interrupt)

        try:
            loop.run_until_complete(all_link(plm, alias, description))
        finally:
            loop.remove_signal_handler(signal.SIGINT)

    except Exception as ex:
        if debug:
            logger.exception("Unexpected error.")
        else:
            logger.error("Unexpected error: %s.", ex)

    finally:
        logger.info("All-linking process completed.")


@plm.command(
    'light-on',
    help="Turn a light on.",
)
@click.option(
    '-l',
    '--level',
    default=100.0,
    type=float,
    help="The light level to set, as a floating-point number.",
)
@click.option(
    '-i',
    '--instant',
    is_flag=True,
    default=False,
    help="Change the light level instantly.",
)
@click.argument(
    'device',
    type=DeviceType(),
)
@click.pass_context
def light_on(ctx, device, level, instant):
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']

    level = loop.run_until_complete(plm.light_on(device.identity, level, instant))
    logger.info("%s light level set to: %s%%", device, level)


@plm.command(
    'light-off',
    help="Turn a light off.",
)
@click.option(
    '-i',
    '--instant',
    is_flag=True,
    default=False,
    help="Change the light level instantly.",
)
@click.argument(
    'device',
    type=DeviceType(),
)
@click.pass_context
def light_off(ctx, device, instant):
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']

    level = loop.run_until_complete(plm.light_off(device.identity, instant))
    logger.info("%s light level set to: %s%%", device, level)


@plm.command(
    'remote-enter-linking',
    help="Cause a device enter in linking mode.",
)
@click.option(
    '-g',
    '--group',
    default=0x01,
    type=int,
    help="The group to enter remote-linking into.",
)
@click.argument(
    'device',
    type=DeviceType(),
)
@click.pass_context
def remote_enter_linking(ctx, device, group):
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']

    loop.run_until_complete(
        plm.remote_enter_linking(device.identity, group=group),
    )


@plm.command(
    'remote-enter-unlinking',
    help="Cause a device enter in unlinking mode.",
)
@click.option(
    '-g',
    '--group',
    default=0x01,
    type=int,
    help="The group to enter remote-unlinking into.",
)
@click.argument(
    'device',
    type=DeviceType(),
)
@click.pass_context
def remote_enter_unlinking(ctx, device, group):
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']

    loop.run_until_complete(
        plm.remote_enter_unlinking(device.identity, group=group),
    )


@plm.command(
    'remote-set',
    help="Cause a device set button tap.",
)
@click.argument(
    'device',
    type=DeviceType(),
)
@click.pass_context
def remote_set(ctx, device):
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']

    loop.run_until_complete(
        plm.remote_set(device.identity),
    )


@plm.command(
    'beep',
    help="Cause a device to beep.",
)
@click.argument(
    'device',
    type=DeviceType(),
)
@click.pass_context
def remote_set(ctx, device):
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']

    loop.run_until_complete(plm.beep(device.identity))


@plm.command(
    'get-device-info',
    help="Get a device parameters.\n\nValid parameters are: %s" % ', '.join(
        str(device_info) for device_info in DeviceInfo
    ),
)
@click.argument(
    'device',
    type=DeviceType(),
)
@click.pass_context
def get_device_info(ctx, device):
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']

    info = loop.run_until_complete(plm.get_device_info(device.identity))
    logger.info("Device information for: %s", important(device))
    logger.info("Ramp rate: %s second(s)", info['ramp_rate'])
    logger.info("On level: %s", info['on_level'])
    logger.info("LED level: %d / 100", info['led_level'])
    logger.info("X10 house code: %s", info['x10_house_code'])
    logger.info("X10 unit code: %s", info['x10_unit_code'])


@plm.command(
    'set-device-info',
    help="Set a device parameter.\n\nValid parameters are: %s" % ', '.join(
        str(device_info) for device_info in DeviceInfo
    ),
)
@click.argument(
    'device',
    type=DeviceType(),
)
@click.argument(
    'device_info',
    type=DeviceInfoType(),
)
@click.argument(
    'value',
    type=float,
)
@click.pass_context
def set_device_info(ctx, device, device_info, value):
    loop = ctx.obj['loop']
    plm = ctx.obj['plm']

    value = loop.run_until_complete(
        plm.set_device_info(device.identity, device_info, value),
    )
    logger.info("%s set to: %s", device_info, value)


@pysteon.command(
    'db',
    help="Manipulate the device database entry",
)
@click.argument(
    'device',
    type=DeviceType(),
)
@click.option(
    '-a',
    '--alias',
    default=None,
    help="The alias to set.",
)
@click.option(
    '-d',
    '--description',
    default=None,
    help="The description to set.",
)
@click.pass_context
def update(ctx, device, alias, description):
    database = ctx.obj['database']

    if alias:
        device = device._replace(alias=alias)

    if description:
        device = device._replace(description=description)

    database.set_device(*device)
