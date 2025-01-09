import asyncio
from datetime import datetime
from typing import Any

from .command import Command, Data, Success
from .heating_control import BaseHeatingControl
from .optolink import OptolinkConnection
from .parameter import Parameter, ParameterReading, ParameterValue


class ViessmannConnection:
    """Combines a heating control device object and an Optolink connection.

    Instances of this class can then be used to actually read parameters from,
    or write parameters to the heating control device. A command queue is created
    and shared with the underlying protocol and commands can be sent to the device
    through coroutines like `set_param()` or `get_param()`.
    """

    def __init__(self, device: BaseHeatingControl, connection: OptolinkConnection):
        self.device = device
        self.connection = connection
        self.commands = asyncio.Queue()
        self.protocol = self.device.get_protocol()

    @property
    def param_storage(self):
        return self.device.get_param_storage()

    def get_param(self, param_id: str):
        return self.device.get_param_storage().get_parameter(param_id)

    async def set_param(self, param: Parameter, value: Any):
        """Set a parameter of the heating control device to a given value"""
        param, (address, offset), encoding = self.device.get_param_storage().get_storage(param)
        if param.is_read_only():
            raise Exception("Readonly parameter cannot be set!")
        if offset != 0:
            raise Exception("Parameter with aligned address cannot be set (for now)!")
        encoding.validate(value)
        param.unit.validate(value)
        cmd = self.protocol.create_write_command(address, encoding.serialize(value))
        now = datetime.now()
        result = await self._execute_command(cmd)
        if not isinstance(result, Success):
            raise Exception("Failure setting parameter!")
        print(
            f"Setting {param.id} took {(datetime.now() - now).total_seconds() * 1000:.0f}ms"
        )
        return True

    async def set_value(self, value: ParameterValue):
        """Shorthand for `set_param(param, value)`"""
        return await self.set_param(value.parameter, value.value)

    async def read_param(self, param: Parameter) -> ParameterReading:
        """Read a parameter value from the heating control device"""
        param, (address, offset), encoding = self.device.get_param_storage().get_storage(param)
        cmd = self.protocol.create_read_command(address, offset + encoding.get_size())
        now = datetime.now()
        result = await self._execute_command(cmd)
        if not isinstance(result, Data):
            raise Exception("Could not read parameter")
        print(
            f"Reading {param.id} took {(datetime.now() - now).total_seconds() * 1000:.0f}ms"
        )
        val = encoding.deserialize(result.value[offset:])
        param.unit.validate(val)
        return ParameterReading.create_now(param, val)

    async def read_address(self, address: bytes, size: int) -> bytes:
        """Low-Level method directly reading bytes at a specific address from the heating control device."""
        cmd = self.protocol.create_read_command(address, size)
        result = await self._execute_command(cmd)
        if not isinstance(result, Data):
            raise Exception("Could not read data at given address!")
        return result.value

    async def _execute_command(self, cmd: Command) -> bytes:
        # put (cmd, future) tuple in command queue and await the future
        fut = asyncio.Future()
        self.commands.put_nowait((cmd, fut))
        return await fut

    def start_communication(self):
        """Start the communication with the heating control device.

        After this method has been called, commands can be sent to the device to read or
        write data.
        """
        self.connection.loop.create_task(
            self.protocol.run(self.connection, self.commands)
        )
