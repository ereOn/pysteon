"""
Database utilities.
"""

import sqlite3

from collections import namedtuple
from itertools import chain

from pysteon.objects import (
    Identity,
    parse_device_categories,
)


class DatabaseDevice(namedtuple('_DatabaseDevice', (
    'identity',
    'alias',
    'description',
    'category',
    'subcategory',
    'firmware_version',
))):
    @classmethod
    def from_row(cls, row):
        category, subcategory = parse_device_categories(bytes(row[3:5]))

        return cls(
            identity=Identity.from_string(row[0]),
            alias=row[1],
            description=row[2],
            category=category,
            subcategory=subcategory,
            firmware_version=row[5],
        )

    def to_row(self):
        return (
            str(self.identity),
            self.alias,
            self.description,
            self.category.value,
            self.subcategory.value,
            self.firmware_version,
        )

    def __str__(self):
        return '%s (%s)' % (
            self.alias if self.alias else self.identity,
            self.description if self.description else self.subcategory,
        )


class Database(object):
    DATABASE_FIELDS = (
        ('identity', 'TEXT'),
        ('alias', 'TEXT'),
        ('description', 'TEXT'),
        ('category', 'INTEGER'),
        ('subcategory', 'INTEGER'),
        ('firmware_version', 'INTEGER'),
    )
    DATABASE_UNIQUE_FIELDS = ('identity',)

    @classmethod
    def load_from_file(cls, path):
        db = sqlite3.connect(path)
        db.execute(
            'CREATE TABLE IF NOT EXISTS devices (%s)' % ', '.join(
                chain(
                    (' '.join(f) for f in cls.DATABASE_FIELDS),
                    (
                        'UNIQUE(%s)' % ', '.join(cls.DATABASE_UNIQUE_FIELDS),
                    ),
                ),
            )
        )
        return cls(db)

    def __init__(self, db=None):
        self._db = db

    def close(self):
        self._db.close()
        self._db = None

    def get_device(self, identity):
        return next(map(DatabaseDevice.from_row, self._db.execute(
            'SELECT * FROM devices WHERE (identity = ?)',
            [
                str(identity),
            ],
        )), None)

    def get_devices(self):
        return {
            device.identity: device
            for device in map(DatabaseDevice.from_row, self._db.execute(
                'SELECT * FROM devices',
            ))
        }

    def get_device_by_alias(self, alias):
        return next(map(DatabaseDevice.from_row, self._db.execute(
            'SELECT * FROM devices WHERE (alias = ?)',
            [
                alias,
            ],
        )), None)

    def set_device(self, *args, **kwargs):
        device = DatabaseDevice(*args, **kwargs)
        self._db.execute(
            'INSERT OR REPLACE INTO devices VALUES (%s)' % ', '.join(
                '?' * len(self.DATABASE_FIELDS),
            ),
            device.to_row(),
        )
        self._db.commit()

        return device
