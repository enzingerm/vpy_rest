from datetime import datetime
from enum import IntEnum
from typing import Any, List, Tuple


class Encoding:
    """Representation of the data format of a value on a heating control device

    Defines how values are converted back and forth between their python representation
    and the actual bytes stored in the heating control device.
    """

    def serialize(self, data: Any) -> bytes:
        """
        Serializes the data into bytes understood by the heating control
        """
        raise NotImplementedError

    def deserialize(self, data: bytes) -> Any:
        """
        Deserializes the value from the bytes received by the heating control
        """
        raise NotImplementedError

    def validate(self, data: Any):
        """
        Validates the data before sending it to the heating control.
        Throws if the data is invalid
        """
        pass

    def get_size(self) -> int:
        """
        Return the number of bytes of a value using this Encoding
        """
        raise NotImplementedError


class FloatEncoding(Encoding):
    def __init__(self, size: int, divisor: int):
        self.size = size
        self.divisor = divisor

    def deserialize(self, data: bytes) -> float:
        return int.from_bytes(data, byteorder="little", signed=True) / self.divisor

    def serialize(self, data: Any) -> bytes:
        self.validate(data)
        return int(data * self.divisor).to_bytes(length=self.size, byteorder="little")

    def validate(self, data: Any):
        if not isinstance(data, (float, int)):
            raise AssertionError("Wrong argument type, number expected!")

    def get_size(self):
        return self.size


class UIntEncoding(Encoding):
    def __init__(self, size: int):
        self.size = size

    def deserialize(self, data: bytes) -> int:
        return int.from_bytes(data, byteorder="little", signed=False)

    def serialize(self, data: Any) -> bytes:
        self.validate(data)
        return int(data).to_bytes(length=self.size, byteorder="little")

    def validate(self, data: Any):
        if not isinstance(data, (int, float)) or not int(data) == data:
            raise AssertionError("Wrong argument type, integral number expected!")
        if data < 0:
            raise AssertionError("Positive number expected!")

    def get_size(self):
        return self.size


class IntEncoding(Encoding):
    def __init__(self, size: int):
        self.size = size

    def deserialize(self, data: bytes) -> int:
        return int.from_bytes(data, byteorder="little", signed=True)

    def serialize(self, data: Any) -> bytes:
        self.validate(data)
        return int(data).to_bytes(length=self.size, byteorder="little", signed=True)

    def validate(self, data: Any):
        if not isinstance(data, (int, float)) or not int(data) == data:
            raise AssertionError("Wrong argument type, integral number expected!")

    def get_size(self):
        return self.size


class SystemTimeEncoding(Encoding):
    def deserialize(self, data: bytes) -> datetime:
        # convert every byte to its decimal value
        converted = [b - (b // 16 * 6) for b in data]
        return datetime(
            year=converted[0] * 100 + converted[1],
            month=converted[2],
            day=converted[3],
            hour=converted[5],
            minute=converted[6],
            second=converted[7],
        )

    def serialize(self, data: datetime):
        val = [
            data.year // 100,
            data.year % 100,
            data.month,
            data.day,
            (data.weekday() + 1) % 7,
            data.hour,
            data.minute,
            data.second,
        ]
        return bytes(b // 10 * 6 + b for b in val)

    def get_size(self):
        return 8


class TimerEncoding(Encoding):
    def deserialize(self, data: bytes) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        first_undefined = (data + b"\xFF\xFF").index(b"\xFF")
        if any(it != 0xFF for it in data[first_undefined:]) or first_undefined % 2 != 0:
            # only complete cycles (2 bytes) may be undefined and they must be at the end
            raise ValueError("Invalid value received for a cycle timer")
        # first 5 bits are the hour, last 3 bits are minute / 10
        decoded = [(it >> 3, (it & 7) * 10) for it in data[:first_undefined]]
        if not all(
            0 <= minute < 60 and (0, 0) <= (hour, minute) <= (24, 0)
            for hour, minute in decoded
        ):
            raise ValueError("Invalid hour or minute given for a cycle timer")
        times = [(hour, minute) for hour, minute in decoded]
        return [(times[i], times[i + 1]) for i in range(0, len(times), 2)]

    def serialize(self, data: Any) -> bytes:
        self.validate(data)
        encoded = bytes(t[0] << 3 | t[1] // 10 for interval in data for t in interval)
        return (encoded + b"\xFF" * 8)[:8]

    def validate(self, data: Any):
        assert isinstance(data, list), "List expected"
        assert 0 <= len(data) <= 4, "Only 0 to 4 switching times supported"
        for interval in data:
            assert (
                isinstance(interval, tuple)
                and len(interval) == 2
                and all(
                    isinstance(it, tuple)
                    and len(it) == 2
                    and isinstance(it[0], int)
                    and isinstance(it[1], int)
                    for it in interval
                )
            ), "Tuples of the format ((<start_hr>, <start_min>), (<end_hr>, (<end_min>)) expected!"

    def get_size(self):
        # 4 cycles with start and end time, each using 1 byte
        return 8


class ArrayEncoding(Encoding):
    def __init__(self, member_encoding: Encoding, count: int):
        self.member_encoding = member_encoding
        self.count = count

    def deserialize(self, data: bytes) -> List[Any]:
        member_size = self.member_encoding.get_size()
        return [
            self.member_encoding.deserialize(data[offset : offset + member_size])
            for offset in [i * member_size for i in range(self.count)]
        ]

    def serialize(self, data: List[Any]) -> bytes:
        assert len(data) == self.count
        return b"".join(self.member_encoding.serialize(d) for d in data)

    def get_size(self):
        return self.count * self.member_encoding.get_size()


class OperatingStatus(IntEnum):
    OFF = 0
    ON = 1
    FAULT = 2


class OperatingStatusEncoding(Encoding):
    def deserialize(self, data: bytes) -> OperatingStatus:
        if data[0] == 0:
            return OperatingStatus.OFF
        elif data[0] == 1:
            return OperatingStatus.ON
        else:
            return OperatingStatus.FAULT

    def serialize(self, data: Any) -> bytes:
        self.validate(data)
        return b"\x00" if data is OperatingStatus.OFF else b"\x01"

    def validate(self, data: Any):
        assert isinstance(data, OperatingStatus), "OperatingStatus expected"

    def get_size(self):
        return 1
