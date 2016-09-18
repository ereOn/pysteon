"""
Unit tests for objects.
"""

import pytest

from pysteon.objects import Identity


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
