"""
Objects classes.
"""


class Identity(object):
    def __init__(self, value):
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
