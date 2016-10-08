"""
Database utilities.
"""

import yaml

from voluptuous import (
    Optional,
    Required,
    Schema,
)

from pysteon.objects import (
    Identity,
    parse_device_categories,
)


def _read_categories(value):
    values = Schema((int, int))(value)
    return parse_device_categories(bytes(values))


def _write_categories(value):
    return [cat.value for cat in value]


class Database(object):
    READ_SCHEMA = Schema({
        Required('devices', default=dict): {
            Identity.from_string: Schema({
                Required('categories'): _read_categories,
                Required('firmware_version'): int,
                Required('alias', default=''): str,
                Required('description', default=''): str,
            })
        },
    })
    WRITE_SCHEMA = Schema({
        Required('devices'): {
            Identity.__str__: Schema({
                Required('categories'): _write_categories,
                Required('firmware_version'): int,
                Optional('alias'): str,
                Optional('description'): str,
            })
        },
    })

    @classmethod
    def load_from_stream(cls, fs):
        data = yaml.load(fs)
        return cls(data)

    def __init__(self, data=None):
        self._data = self.READ_SCHEMA(data or {})

    def save_to_stream(self, fs):
        yaml.dump(self.WRITE_SCHEMA(self._data), fs)

    def get_device(self, identity):
        return self._data['devices'].get(identity)

    def set_device(
        self,
        identity,
        **kwargs
    ):
        info = self._data['devices'].get(identity, {})
        info.update(kwargs)
        self._data['devices'][identity] = info
