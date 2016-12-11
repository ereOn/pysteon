"""
Automation primitives.
"""

import importlib

from functools import wraps

from chromalog.mark.helpers.simple import (
    important,
)

from ..log import logger


class Automate(object):
    def __init__(self, plm, database):
        self.state = 'initial'
        self.modules = []
        self.on_state_changed_callbacks = []
        self.on_event_callbacks = []
        self.plm = plm
        self.database = database

    def load_module(self, module):
        self.modules.append(importlib.import_module(module))


    def __enter__(self):
        for module in self.modules:
            module.register(automate=self)

    def __exit__(self, *args):
        for module in self.modules:
            module.unregister(automate=self)

    @staticmethod
    def in_list(value, choices):
        return not choices or value in choices

    def transition(self, new_state):
        if new_state != self.state:
            old_state, self.state = self.state, new_state

            for attrs, callback in self.on_state_changed_callbacks:
                from_states = attrs['from_states']
                to_states = attrs['to_states']

                if self.in_list(old_state, attrs['from_states']):
                    if self.in_list(new_state, attrs['to_states']):
                        callback(old_state=old_state, new_state=new_state)

    def handle_message(self, msg):
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
                callback(
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
