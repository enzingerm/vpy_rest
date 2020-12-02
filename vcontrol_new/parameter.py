from datetime import datetime
from typing import Any

from .unit import ArrayUnit, Unit


class Parameter:
    """Represents a single data location in the heating control device."""

    def __init__(self, name: str, id: str, unit: Unit, readonly: bool = True):
        self.name = name
        self.id = id
        self.unit = unit
        self.readonly = readonly

    def validate(self, value: Any):
        """
        Validates whether a value is valid for this parameter.
        This includes checking whether the value is valid for the unit associated with
        the parameter, as well as possibly checking specific bounds for the parameter.
        """
        self.unit.validate(value)

    def is_read_only(self):
        return self.readonly


class AggregatedParameter(Parameter):
    def __init__(
        self,
        name: str,
        id: str,
        child_unit: Unit,
        child_count: int,
        readonly: bool = True,
    ):
        super().__init__(name, id, ArrayUnit(child_unit), readonly=readonly)
        self.child_count = child_count

    def get_child_param(self, index: int):
        assert 0 <= index < self.child_count
        return Parameter(
            f"{self.name}[{index}]",
            f"{self.id}.{index}",
            self.member_unit,
            readonly=self.readonly,
        )

    @property
    def member_unit(self):
        return self.unit.child_unit


class ParameterValue:
    """
    Represents a concrete value for a parameter.
    """

    def __init__(self, parameter: Parameter, value: Any):
        self.parameter = parameter
        self.value = value

    @classmethod
    def create(cls, parameter: Parameter, value: Any):
        """
        Creates a parameter value after checking if the given value is valid.
        """
        parameter.validate(value)
        return cls(parameter, value)

    def get_display_string(self):
        return self.parameter.unit.get_display_string(self.value)


class ParameterReading(ParameterValue):
    """
    Represents the value of a parameter at a specific time.
    """

    def __init__(self, parameter: Parameter, value: Any, time: datetime):
        super().__init__(parameter, value)
        self.time = time

    @classmethod
    def create_now(cls, parameter: Parameter, value: Any):
        parameter.validate(value)
        return cls(parameter, value, datetime.now())
