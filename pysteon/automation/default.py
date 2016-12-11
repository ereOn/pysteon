"""
Automation default script.
"""

import asyncio

from ..log import logger
from ..objects import (
    DeviceCategory,
    SecurityHealthSafetySubcatory,
)


async def register(automate):
    @automate.fire_on_state_changed(from_states=[], to_states=[])
    async def on_state_changed(old_state, new_state):
        logger.info(
            "Automation state changed from %s to %s.",
            important(old_state),
            important(new_state),
        )

    @automate.fire_on_motion_sensor_activated()
    async def on_motion_sensor_activated(device, command, group):
        logger.info(
            "Motion sensor %s activated (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_motion_sensor_deactivated()
    async def on_motion_sensor_deactivated(device, command, group):
        logger.info(
            "Motion sensor %s deactivated (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_open_close_sensor_opened()
    async def on_open_close_sensor_opened(device, command, group):
        logger.info(
            "Open/Close sensor %s is open (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_open_close_sensor_closed()
    async def on_open_close_sensor_closed(device, command, group):
        logger.info(
            "Open/Close sensor %s is closed (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_light_turned_on()
    async def on_light_turned_on(device, command, group):
        logger.info(
            "Light %s turned on (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_light_turned_off()
    async def on_light_turned_off(device, command, group):
        logger.info(
            "Light %s turned off (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_remote_pressed_on()
    async def on_remote_pressed_on(device, command, group):
        logger.info(
            "Remote %s pressed on (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_remote_pressed_off()
    async def on_remote_pressed_off(device, command, group):
        logger.info(
            "Remote %s pressed off (group %s).",
            device.name,
            group,
        )


async def unregister(automate, data):
    pass
