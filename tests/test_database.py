"""
Database tests.
"""

from pysteon.database import (
    Database,
    DatabaseDevice,
)
from pysteon.objects import (
    Identity,
    GenericDeviceCategory,
    GenericSubcategory,
)


def test_load_from_file():
    Database.load_from_file(':memory:')


def test_get_device_non_existing():
    database = Database.load_from_file(':memory:')
    assert database.get_device(Identity(b'\x01\x02\x03')) is None


def test_set_device():
    database = Database.load_from_file(':memory:')
    identity = Identity(b'\x01\x02\x03')
    database_device = DatabaseDevice(
        identity=identity,
        alias='foo',
        description='',
        category=GenericDeviceCategory(0x42),
        subcategory=GenericSubcategory(0x80),
        firmware_version=0x99,
    )
    database.set_device(*database_device)

    assert database.get_device(identity) == database_device


def test_set_existing_device():
    database = Database.load_from_file(':memory:')
    identity = Identity(b'\x01\x02\x03')
    database_device = DatabaseDevice(
        identity=identity,
        alias='foo',
        description='',
        category=GenericDeviceCategory(0x42),
        subcategory=GenericSubcategory(0x80),
        firmware_version=0x99,
    )
    database.set_device(*database_device)

    database_device2 = DatabaseDevice(
        identity=identity,
        alias='foo',
        description='My description',
        category=GenericDeviceCategory(0x42),
        subcategory=GenericSubcategory(0x80),
        firmware_version=0x99,
    )
    database.set_device(*database_device2)
    assert database.get_device(identity) == database_device2
