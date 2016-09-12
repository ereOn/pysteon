"""
Objects classes.
"""

from binascii import hexlify


class Identity(object):
    def __init__(self, value):
        assert len(value) == 3
        self.value = value

    def __str__(self):
        return '%02x.%02x.%02x' % tuple(self.value)

    def __repr__(self):
        return 'Identity(%r)' % self.value


class IMInfo(object):
    def __init__(
        self,
        identity,
        device_category,
        device_subcategory,
        firmware_version,
    ):
        self.identity = identity
        self.device_category = device_category
        self.device_subcategory = device_subcategory
        self.firmware_version = firmware_version

    def __str__(self):
        return "Insteon Modem at %s (%02x.%02x - v%d)" % (
            self.identity,
            self.device_category,
            self.device_subcategory,
            self.firmware_version,
        )


class AllLinkRecord(object):
    def __init__(self, flags, group, identity, data):
        self.flags = flags
        self.group = group
        self.identity = identity
        self.data = data

    @property
    def controller(self):
        return self.flags & 0x40

    @property
    def responder(self):
        return not self.controller

    def __str__(self):
        return "%s - %s - %02x (%s)" % (
            self.identity,
            'controller' if self.controller else 'responder',
            self.group,
            hexlify(self.data).decode(),
        )
