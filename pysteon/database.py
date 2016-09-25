"""
Database utilities.
"""

import yaml


class Database(object):
    @classmethod
    def load_from_stream(cls, fs):
        data = yaml.load(fs)
        return cls(data)

    def __init__(self, data=None):
        self._data = data or {}

    def save_to_stream(self, fs):
        yaml.dump(self._data, fs)
