class Command:
    def get_command_bytes(self) -> bytes:
        """Return the actual bytes to be sent to the heating control"""
        raise NotImplementedError

    def handle_result(self, data: bytes):
        """Handles the bytes received from the heating control"""
        raise NotImplementedError

    def get_expected_bytes_count(self):
        """Return the number of bytes which the heating control is expected to answer"""
        raise NotImplementedError


class Answer:
    pass


class Success(Answer):
    pass


class Failure(Answer):
    pass


class Data(Answer):
    def __init__(self, value: bytes):
        self.value = value


class KWReadCommand(Command):
    """Command for reading bytes from a given (2-byte) address from a device over the KW protocol."""

    def __init__(self, address: bytes, size: int):
        assert len(address) == 2
        assert size > 0
        self.size = size
        self.address = address

    def get_command_bytes(self):
        cmd = b"\xF7" + self.address + self.size.to_bytes(1, byteorder="little")
        return cmd

    def handle_result(self, data: bytes):
        return Data(data)

    def get_expected_bytes_count(self):
        return self.size


class KWWriteCommand(Command):
    """Command for writing bytes to a given (2-byte) address to a device over the KW protocol."""

    def __init__(self, address: bytes, value: bytes):
        assert len(address) == 2
        assert len(value) > 0
        self.address = address
        self.value = value

    def get_command_bytes(self):
        cmd = (
            b"\xF4"
            + self.address
            + len(self.value).to_bytes(1, byteorder="little")
            + self.value
        )
        return cmd

    def handle_result(self, data: bytes):
        assert len(data) == 1
        if data[0] != 0:
            return Failure()
        return Success()

    def get_expected_bytes_count(self):
        return 1
