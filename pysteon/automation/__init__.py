"""
Automation primitives.
"""

import importlib

from functools import wraps

from chromalog.mark.helpers.simple import (
    important,
)

from ..objects import (
    DeviceCategory,
    SecurityHealthSafetySubcatory,
)
from ..log import logger


class Automate(object):
    def __init__(self, plm, database, loop):
        self.state = 'initial'
        self.modules = []
        self.on_state_changed_callbacks = []
        self.on_event_callbacks = []
        self.plm = plm
        self.database = database
        self.loop = loop
        self._registration_data = []

    def load_module(self, module):
        self.modules.append(importlib.import_module(module))


    async def __aenter__(self):
        for module in self.modules:
            data = await module.register(automate=self)
            self._registration_data.append(data)

    async def __aexit__(self, *args):
        for module, data in zip(self.modules, self._registration_data):
            await module.unregister(automate=self, data=data)

    @staticmethod
    def in_list(value, choices):
        return not choices or value in choices

    async def transition(self, new_state):
        if new_state != self.state:
            old_state, self.state = self.state, new_state

            for attrs, callback in self.on_state_changed_callbacks:
                from_states = attrs['from_states']
                to_states = attrs['to_states']

                if self.in_list(old_state, attrs['from_states']):
                    if self.in_list(new_state, attrs['to_states']):
                        await callback(old_state=old_state, new_state=new_state)

    async def handle_message(self, msg):
        device = self.database.get_device(msg.sender)

        if not device:
            return

        for attrs, callback in self.on_event_callbacks:
            if all([
                self.in_list(device.category, attrs['device_categories']),
                self.in_list(
                    device.subcategory,
                    attrs['device_subcategories'],
                ),
                self.in_list(msg.command_bytes[0], attrs['commands']),
                self.in_list(msg.command_bytes[1], attrs['groups']),
            ]):
                await callback(
                    device=device,
                    command=msg.command_bytes[0],
                    group=msg.command_bytes[1],
                )

    def fire_on_state_changed(self, from_states=None, to_states=None):
        def decorator(func):
            self.on_state_changed_callbacks.append((
                {
                    'from_states': from_states,
                    'to_states': to_states,
                },
                func,
            ))

            return func

        return decorator

    def fire_on_event(
        self,
        device_categories=None,
        device_subcategories=None,
        commands=None,
        groups=None,
    ):
        def decorator(func):
            self.on_event_callbacks.append((
                {
                    'device_categories': device_categories,
                    'device_subcategories': device_subcategories,
                    'commands': commands,
                    'groups': groups,
                },
                func,
            ))

            return func

        return decorator

    def fire_on_motion_sensor_activated(self):
        return self.fire_on_event(
            device_categories=[DeviceCategory.security_health_safety],
            device_subcategories=[SecurityHealthSafetySubcatory.motion_sensor],
            commands=[0x11, 0x12],
        )

    def fire_on_motion_sensor_deactivated(self):
        return self.fire_on_event(
            device_categories=[DeviceCategory.security_health_safety],
            device_subcategories=[SecurityHealthSafetySubcatory.motion_sensor],
            commands=[0x13, 0x14],
        )

    def fire_on_open_close_sensor_opened(self):
        return self.fire_on_event(
            device_categories=[DeviceCategory.security_health_safety],
            device_subcategories=[
                SecurityHealthSafetySubcatory.open_close_sensor,
            ],
            commands=[0x11, 0x12],
        )

    def fire_on_open_close_sensor_closed(self):
        return self.fire_on_event(
            device_categories=[DeviceCategory.security_health_safety],
            device_subcategories=[
                SecurityHealthSafetySubcatory.open_close_sensor,
            ],
            commands=[0x13, 0x14],
        )

    def fire_on_light_turned_on(self):
        return self.fire_on_event(
            device_categories=[
                DeviceCategory.dimmable_lighting_control,
                DeviceCategory.switched_lighting_control,
            ],
            commands=[0x11, 0x12],
        )

    def fire_on_light_turned_off(self):
        return self.fire_on_event(
            device_categories=[
                DeviceCategory.dimmable_lighting_control,
                DeviceCategory.switched_lighting_control,
            ],
            commands=[0x13, 0x14],
        )

    def fire_on_remote_pressed_on(self, groups=None):
        return self.fire_on_event(
            device_categories=[
                DeviceCategory.generalized_controllers,
            ],
            commands=[0x11, 0x12],
        )

    def fire_on_remote_pressed_off(self, groups=None):
        return self.fire_on_event(
            device_categories=[
                DeviceCategory.generalized_controllers,
            ],
            commands=[0x13, 0x14],
        )
