"""
Unit tests for objects.
"""

import pytest

from pysteon.objects import (
    AllLinkMode,
    DeviceCategory,
    DimmableLightingControlSubcategory,
    GenericDeviceCategory,
    GenericSubcategory,
    Identity,
    parse_device_categories,
)


def test_identity_invalid_id():
    with pytest.raises(AssertionError):
        Identity(b'')

    with pytest.raises(AssertionError):
        Identity(b'\x01\x02\x03\x04')


def test_identity_equality():
    a = Identity(b'\x01\x02\x03')
    b = Identity(b'\x01\x02\x03')
    c = Identity(b'\x01\x02\x04')

    assert a == a
    assert a == b
    assert a != c
    assert not a != a
    assert not a != b
    assert not a == c


def test_identity_as_bytes():
    ident = Identity(b'\x01\x02\x03')

    assert bytes(ident) == b'\x01\x02\x03'


def test_identity_repr():
    ident = Identity(b'\x01\x02\x03')

    assert repr(ident) == repr(b'\x01\x02\x03')


def test_identity_str():
    ident = Identity(b'\x01\x02\x03')

    assert str(ident) == '01.02.03'


def test_parse_device_categories():
    devcat, subcat = parse_device_categories(b'\x01\x01')

    assert devcat == DeviceCategory.dimmable_lighting_control
    assert subcat == \
        DimmableLightingControlSubcategory.switchlinc_v2_dimmer_600w


def test_parse_device_categories_unknown_category():
    devcat, subcat = parse_device_categories(b'\xfe\x01')

    assert devcat == GenericDeviceCategory(0xfe)
    assert subcat == GenericSubcategory(0x01)


def test_parse_device_categories_unknown_sub_category():
    devcat, subcat = parse_device_categories(b'\x01\xfe')

    assert devcat == DeviceCategory.dimmable_lighting_control
    assert subcat == GenericSubcategory(0xfe)


def test_device_categories():
    devcat = DeviceCategory(0x01)

    assert devcat == DeviceCategory.dimmable_lighting_control
    assert devcat.title == "Dimmable Lighting Control"
    assert devcat.subcategory_class is DimmableLightingControlSubcategory

    subcat = devcat.subcategory_class(0x01)

    assert subcat == \
        DimmableLightingControlSubcategory.switchlinc_v2_dimmer_600w
    assert subcat.title == "SwitchLinc V2 Dimmer 600W [2476D]"


def test_all_link_mode_from_string():
    assert AllLinkMode.from_string("responder") == AllLinkMode.responder


def test_all_link_mode_from_string_non_existing():
    with pytest.raises(ValueError):
        AllLinkMode.from_string("foo")


def test_all_link_mode_to_string():
    assert str(AllLinkMode.auto) == "auto"
    assert str(AllLinkMode.controller) == "controller"
    assert str(AllLinkMode.delete) == "delete"
    assert str(AllLinkMode.responder) == "responder"
    assert str(AllLinkMode.unknown) == "unknown"
