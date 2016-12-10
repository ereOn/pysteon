"""
Units conversion utilities.
"""

RAMP_RATES = [
    (0.1, 0x1F),
    (0.2, 0x1E),
    (0.3, 0x1D),
    (0.5, 0x1C),
    (2.0, 0x1B),
    (4.5, 0x1A),
    (6.5, 0x19),
    (8.5, 0x18),
    (19.0, 0x17),
    (21.5, 0x16),
    (23.5, 0x15),
    (26.0, 0x14),
    (28.0, 0x13),
    (30.0, 0x12),
    (32.0, 0x11),
    (34.0, 0x10),
    (38.5, 0x0f),
    (43.0, 0x0e),
    (47.0, 0x0d),
    (60.0, 0x0c),
    (90.0, 0x0b),
    (120.0, 0x0a),
    (150.0, 0x09),
    (180.0, 0x08),
    (210.0, 0x07),
    (240.0, 0x06),
    (270.0, 0x05),
    (300.0, 0x04),
    (360.0, 0x03),
    (420.0, 0x02),
    (480.0, 0x01),
]


def project_onto(value, array, invert=False):
    """
    Project a value onto an array.

    :param value: The input value.
    :param array: An array of (x, y), sorted.
    :param invert: A flag that if set, inverts the array.
    :returns: The projected value.
    """
    if invert:
        array = sorted((y, x) for (x, y) in array)

    for index, (x, _) in enumerate(array[1:], start=1):
        if x > value:
            return array[index - 1][1]

    return array[-1][1]


def ramp_rate_from_seconds(value):
    """
    Convert a number of seconds to a ramp rate.
    """
    return project_onto(value, RAMP_RATES)


def ramp_rate_to_seconds(value):
    """
    Convert a ramp rate to a number of seconds.
    """
    return project_onto(value, RAMP_RATES, invert=True)


def led_brightness_from_percent(value):
    """
    Convert a percent from 0 to 100 to a brightness level.
    """
    value = min(100, max(0, value))
    return round((value / 100.0) * 0x7f)


def led_brightness_to_percent(value):
    """
    Convert a percent from 0 to 100 to a brightness level.
    """
    value = min(0x7f, max(0, value))
    return round((value / 0x7f) * 100)


def on_level_from_percent(value):
    """
    Convert a percent from 0 to 100 to a brightness level.
    """
    value = min(100, max(0, value))
    return round((value / 100.0) * 0xff)


def on_level_to_percent(value):
    """
    Convert a percent from 0 to 100 to a brightness level.
    """
    value = min(0xff, max(0, value))
    return round((value / 0xff) * 100)
