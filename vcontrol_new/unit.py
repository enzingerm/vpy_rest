from datetime import datetime
from typing import Any

from .encoding import OperatingStatus


class Unit:
    def get_id(self):
        raise NotImplementedError

    def get_display_string(self, value: Any):
        raise NotImplementedError

    def validate(self, value: Any):
        """
        Validates a value
        """
        raise NotImplementedError


class ArrayUnit(Unit):
    def __init__(self, unit: Unit):
        self.child_unit = unit

    def get_id(self):
        return f"[{self.child_unit.get_id()}]"

    def get_display_string(self, value: Any):
        assert isinstance(value, list), "List of values expected"
        return (
            "[" + ", ".join(self.child_unit.get_display_string(v) for v in value) + "]"
        )

    def validate(self, value: Any):
        assert isinstance(value, list), "List of values expected"
        [self.child_unit.validate(v) for v in value]


class SystemTimeUnit(Unit):
    def get_display_string(self, value):
        return value.strftime("%d.%m.%Y %H:%M:%S")

    def validate(self, value: Any):
        assert isinstance(value, datetime), "datetime expected!"


class CycleTimeUnit(Unit):
    def get_id(self):
        return "timer"

    def get_display_string(self, value: Any):
        def show(t):
            return f"{t[0]:02d}:{t[1]:02d}"

        return " ".join(f"{show(on)}-{show(off)}" for on, off in value)

    def validate(self, value: Any):
        assert all(
            it[1] % 10 == 0 for cycle in value for it in cycle
        ), "Minute must be a multiple of 10"
        assert all(
            0 <= it[1] < 60 and (0, 0) <= it <= (24, 0)
            for cycle in value
            for it in cycle
        ), "Cycle times must be between 00:00 and 24:00"
        assert all(
            start < end for start, end in value
        ), "Cycle end time must be after cycle start time"
        assert all(
            t1_end <= t2_start for (_, t1_end), (t2_start, _) in zip(value, value[1:])
        ), "Cycle times must not overlap"


class OperatingStatusUnit(Unit):
    def get_id(self):
        return "operating_status"

    def get_display_string(self, value):
        return {
            OperatingStatus.ON: "An",
            OperatingStatus.OFF: "Aus",
            OperatingStatus.FAULT: "Fehler",
        }[value]

    def validate(self, value):
        assert isinstance(value, int), "OperatingStatus expected"


class NumberUnit(Unit):
    def __init__(
        self,
        lower_bound: float = None,
        upper_bound: float = None,
        integer: bool = False,
        suffix: str = "",
    ):
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.integer = integer
        self.suffix = suffix

    def get_id(self):
        return "number"

    def get_display_string(self, value):
        return f"{value}{self.suffix}"

    def validate(self, value):
        assert isinstance(value, int) or isinstance(value, float), "Number expected"
        if self.integer:
            assert int(value) == value, "Expected integral number"
        if self.lower_bound is not None:
            assert (
                self.lower_bound <= value
            ), f"value {value} may not be smaller than {self.lower_bound}"
        if self.upper_bound is not None:
            assert (
                value <= self.upper_bound
            ), f"value {value} may not be bigger than {self.upper_bound}"


class HourUnit(NumberUnit):
    def __init__(self):
        super().__init__(lower_bound=0, integer=False)

    def get_display_string(self, value):
        # format 323:03h
        return f"{value:.0f}:{int((value % 1) * 60):02d}h"
