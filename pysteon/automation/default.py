"""
Automation default script.
"""

from ..log import logger
from ..objects import (
    DeviceCategory,
    SecurityHealthSafetySubcatory,
)


def register(automate):
    @automate.fire_on_state_changed(from_states=[], to_states=[])
    def on_state_changed(old_state, new_state):
        logger.info(
            "Automation state changed from %s to %s.",
            important(old_state),
            important(new_state),
        )

    @automate.fire_on_event(
        device_categories=[DeviceCategory.security_health_safety],
        device_subcategories=[SecurityHealthSafetySubcatory.motion_sensor],
        commands=[0x11, 0x12],
    )
    def on_motion_sensor_activated(device, command, group):
        logger.info(
            "Motion sensor %s activated (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_event(
        device_categories=[DeviceCategory.security_health_safety],
        device_subcategories=[SecurityHealthSafetySubcatory.motion_sensor],
        commands=[0x13, 0x14],
    )
    def on_motion_sensor_deactivated(device, command, group):
        logger.info(
            "Motion sensor %s deactivated (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_event(
        device_categories=[DeviceCategory.security_health_safety],
        device_subcategories=[SecurityHealthSafetySubcatory.open_close_sensor],
        commands=[0x11, 0x12],
    )
    def on_open_close_sensor_opened(device, command, group):
        logger.info(
            "Open/Close sensor %s is open (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_event(
        device_categories=[DeviceCategory.security_health_safety],
        device_subcategories=[SecurityHealthSafetySubcatory.open_close_sensor],
        commands=[0x13, 0x14],
    )
    def on_open_close_sensor_closed(device, command, group):
        logger.info(
            "Open/Close sensor %s is closed (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_event(
        device_categories=[
            DeviceCategory.dimmable_lighting_control,
            DeviceCategory.switched_lighting_control,
        ],
        commands=[0x11, 0x12],
    )
    def on_light_turned_on(device, command, group):
        logger.info(
            "Light %s turned on (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_event(
        device_categories=[
            DeviceCategory.dimmable_lighting_control,
            DeviceCategory.switched_lighting_control,
        ],
        commands=[0x13, 0x14],
    )
    def on_light_turned_off(device, command, group):
        logger.info(
            "Light %s turned off (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_event(
        device_categories=[
            DeviceCategory.generalized_controllers,
        ],
        commands=[0x11, 0x12],
    )
    def on_remote_pressed_on(device, command, group):
        logger.info(
            "Remote %s pressed on (group %s).",
            device.name,
            group,
        )

    @automate.fire_on_event(
        device_categories=[
            DeviceCategory.generalized_controllers,
        ],
        commands=[0x13, 0x14],
    )
    def on_remote_pressed_off(device, command, group):
        logger.info(
            "Remote %s pressed off (group %s).",
            device.name,
            group,
        )


def unregister(automate):
    pass
