from enum import Enum


class Weekday(Enum):
    MONDAY = ("Montag", 0)
    TUESDAY = ("Dienstag", 1)
    WEDNESDAY = ("Mittwoch", 2)
    THURSDAY = ("Donnerstag", 3)
    FRIDAY = ("Freitag", 4)
    SATURDAY = ("Samstag", 5)
    SUNDAY = ("Sonntag", 6)

    def __new__(cls, name, id):
        obj = object.__new__(cls)
        obj._value_ = id
        return obj

    def __init__(self, name, id):
        self._name_ = name

    @property
    def name(self):
        return self._name_

    @property
    def id(self):
        return self._value_
