import asyncio
from datetime import datetime
from collections import defaultdict


class HeatingDummy:
    """
    Emulates a serial connection to a heating control device speaking KW.
    Can be used for testing purposes instead of an OptolinkConnection.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        # here the dummy devices writes its data
        self.send_queue = asyncio.Queue()
        # here the data sent to the dummy device gets stored
        self.read_queue = asyncio.Queue()
        self.storage = defaultdict(int)
        self.loop.create_task(self.run())

    async def run(self):
        while True:
            last_sync_byte = datetime.now()
            self._send(b"\x05")
            # wait up to 600ms for an incoming command
            try:
                (b,) = await self._recv(1, 0.5)
                if b == 0x01:
                    while True:
                        await self._handle_command()
            except asyncio.TimeoutError:
                pass
            except ValueError:
                pass
            await asyncio.sleep(2 - (datetime.now() - last_sync_byte).total_seconds())

    async def _handle_command(self):
        (b,) = await self._recv(1, 0.1)
        if b == 0xF7:
            await self._handle_read_command()
        elif b == 0xF4:
            await self._handle_write_command()
        else:
            raise ValueError

    async def _handle_read_command(self):
        addr1, addr2, size = await self._recv(3)
        addr = int.from_bytes(bytes([addr1, addr2]), byteorder="big")
        self._send(bytes(self.storage[addr + i] for i in range(size)))

    async def _handle_write_command(self):
        addr1, addr2, size = await self._recv(3)
        addr = int.from_bytes(bytes([addr1, addr2]), byteorder="big")
        for index, value in zip(range(size), await self._recv(size)):
            self.storage[addr + index] = value
        self._send(b"\x00")

    def _send(self, b: bytes):
        for byte in b:
            self.send_queue.put_nowait(byte)

    async def _recv(self, size, timeout=0) -> bytearray:
        if timeout == 0:
            return bytearray(self.read_queue.get_nowait() for _ in range(size))
        start = datetime.now()
        ret = bytearray()
        for _ in range(size):
            timeout_left = timeout - (datetime.now() - start).total_seconds()
            ret.append(
                await asyncio.wait_for(self.read_queue.get(), timeout=timeout_left)
            )
        return ret

    def write(self, b: bytes):
        for byte in b:
            self.read_queue.put_nowait(byte)

    async def read(self, count=1, timeout=10):
        start = datetime.now()
        ret = bytearray()
        try:
            for _ in range(count):
                timeout_left = timeout - (datetime.now() - start).total_seconds()
                ret.append(
                    await asyncio.wait_for(self.send_queue.get(), timeout=timeout_left)
                )
        except asyncio.TimeoutError:
            pass
        return ret

    def flush(self):
        try:
            while True:
                self.send_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
