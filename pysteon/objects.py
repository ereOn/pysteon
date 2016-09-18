"""
Objects.
"""


class Identity(object):
    """
    Represents an identity.
    """

    def __init__(self, id_):
        assert len(id_) == 3
        self.id_ = bytes(id_)

    def __eq__(self, value):
        if not isinstance(value, Identity):
            return NotImplemented

        return self.id_ == value.id_

    def __bytes__(self):
        return self.id_

    def __repr__(self):
        return repr(bytes(self))

    def __str__(self):
        return '%02x.%02x.%02x' % tuple(self.id_)
