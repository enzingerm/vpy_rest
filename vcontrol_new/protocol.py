import asyncio
from .optolink import OptolinkConnection
from .command import Command, KWReadCommand, KWWriteCommand


class Protocol:
    """Represents a protocol used for the communication to a heating control device."""

    def get_name(self) -> str:
        """Get the name of the protocol"""
        raise NotImplementedError

    def create_read_command(self, address: bytes, size: int) -> Command:
        """Create a command which reads bytes from an address."""
        raise NotImplementedError

    def create_write_command(self, address: bytes, data: bytes) -> Command:
        """Create a command which writes bytes to an address."""
        raise NotImplementedError

    async def run(self, connection: OptolinkConnection, command_queue: asyncio.Queue):
        """Start serving commands as they arrive in a queue using a provided connection."""
        raise NotImplementedError


class KWProtocol(Protocol):
    def get_name(self) -> str:
        return "KW"

    def create_read_command(self, address: bytes, size: int) -> Command:
        return KWReadCommand(address, size)

    def create_write_command(self, address: bytes, data: bytes) -> Command:
        return KWWriteCommand(address, data)

    async def run(self, connection: OptolinkConnection, command_queue: asyncio.Queue):
        connection.flush()
        while True:
            # poll start bytes (0x05) and discard them
            byte = await connection.read()
            if byte[0] != 0x05:
                # we are not in synchronization phase and received a byte other than
                # the synchronization byte -> just wait for the next byte
                continue
            # when there is at least one command waiting in the queue, start the communication
            if not command_queue.empty():
                connection.write(b"\x01")
                # TODO: start measuring utilization here
                try:
                    while True:
                        cmd, fut = await asyncio.wait_for(
                            command_queue.get(), timeout=0.5
                        )
                        connection.write(cmd.get_command_bytes())
                        val = await connection.read(cmd.get_expected_bytes_count())
                        if all(it == 0x05 for it in val):
                            fut.set_exception(Exception("Command failed"))
                            # we must synchronize again
                            break
                        else:
                            if fut.done():
                                print(fut.result())
                                raise Exception("Future was already done")
                            fut.set_result(cmd.handle_result(val))
                except asyncio.TimeoutError:
                    continue
                finally:
                    pass
                    # TODO: stop measuring utilization here
            # no more commands to handle, wait for next synchronization
