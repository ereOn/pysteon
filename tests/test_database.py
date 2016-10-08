"""
Database tests.
"""

import yaml

from io import StringIO

from pysteon.database import Database
from pysteon.objects import (
    Identity,
    GenericDeviceCategory,
    GenericSubcategory,
)


def test_load_from_stream_empty():
    stream = StringIO('{}')
    Database.load_from_stream(stream)


def test_save_to_stream_empty():
    database = Database()
    stream = StringIO()
    database.save_to_stream(stream)
    stream.seek(0)
    assert yaml.load(stream.read()) == {
        'devices': {},
    }


def test_save_to_stream_with_devices():
    database = Database()
    identity = Identity(b'\x01\x02\x03')
    database.set_device(
        identity=identity,
        categories=(GenericDeviceCategory(0x42), GenericSubcategory(0x80)),
        firmware_version=0x99,
    )
    stream = StringIO()
    database.save_to_stream(stream)
    stream.seek(0)
    assert yaml.load(stream.read()) == {
        'devices': {
            '01.02.03': {
                'categories': [66, 128],
                'firmware_version': 0x99,
            },
        },
    }


def test_get_device_non_existing():
    database = Database()
    assert database.get_device(Identity(b'\x01\x02\x03')) is None


def test_set_device_new():
    database = Database()
    identity = Identity(b'\x01\x02\x03')
    database.set_device(
        identity=identity,
        categories=(GenericDeviceCategory(0x42), GenericSubcategory(0x80)),
        firmware_version=0x99,
    )

    assert database.get_device(identity) == dict(
        categories=(GenericDeviceCategory(0x42), GenericSubcategory(0x80)),
        firmware_version=0x99,
    )
