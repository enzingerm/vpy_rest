from datetime import datetime
from typing import Any

from vcontrol_new.encoding import OperatingStatus
from vcontrol_new.unit import (
    ArrayUnit,
    CycleTimeUnit,
    NumberUnit,
    OperatingStatusUnit,
    SystemTimeUnit,
    Unit,
)


class Serializer:
    """Provides conversion functions between python objects and JSON serializable objects."""

    @staticmethod
    def describe_unit(unit: Unit):
        if isinstance(unit, NumberUnit):
            return {
                "type": "number",
                "integral": unit.integer,
                "min": unit.lower_bound,
                "max": unit.upper_bound,
                "suffix": unit.suffix,
            }
        elif isinstance(unit, OperatingStatusUnit):
            return {
                "type": "enum",
                "possible_values": [
                    {"value": OperatingStatus.OFF, "text": "Aus"},
                    {"value": OperatingStatus.ON, "text": "An"},
                ],
            }
        elif isinstance(unit, CycleTimeUnit):
            return {"type": "day_timer"}
        elif isinstance(unit, ArrayUnit) and isinstance(unit.child_unit, CycleTimeUnit):
            return {"type": "timer"}
        elif isinstance(unit, SystemTimeUnit):
            return {"type": "system_time"}
        else:
            raise NotImplementedError

    @staticmethod
    def serialize(value: Any, unit: Unit):
        if isinstance(unit, ArrayUnit):
            return [Serializer.serialize(val, unit.child_unit) for val in value]
        elif isinstance(unit, NumberUnit):
            # numbers can be serialized primitively
            return value
        elif isinstance(unit, OperatingStatusUnit):
            return {
                OperatingStatus.OFF: "Aus",
                OperatingStatus.ON: "An",
                OperatingStatus.FAULT: "Fehler",
            }[value]
        elif isinstance(unit, CycleTimeUnit):
            return [
                {
                    "on": f"{start[0]:02d}:{start[1]:02d}",
                    "off": f"{end[0]:02d}:{end[1]:02d}",
                }
                for start, end in value
            ]
        elif isinstance(unit, SystemTimeUnit):
            return value.isoformat()
        else:
            return str(value)

    @staticmethod
    def deserialize(value: Any, unit: Unit):
        try:
            if isinstance(unit, CycleTimeUnit):
                converted = [
                    {k: v.split(":") for k, v in it.items() if k in ["on", "off"]}
                    for it in value
                ]
                return [
                    (
                        (int(it["on"][0]), int(it["on"][1])),
                        (int(it["off"][0]), int(it["off"][1])),
                    )
                    for it in converted
                ]
            elif isinstance(unit, NumberUnit):
                return float(value)
            elif isinstance(unit, OperatingStatusUnit):
                return {
                    0: OperatingStatus.OFF,
                    1: OperatingStatus.ON,
                    "Aus": OperatingStatus.OFF,
                    "An": OperatingStatus.ON,
                }[value]
            elif isinstance(unit, SystemTimeUnit):
                return datetime.fromisoformat(value)
            else:
                raise NotImplementedError
        except Exception as e:
            raise DeserializationException(e)


class DeserializationException(Exception):
    pass
