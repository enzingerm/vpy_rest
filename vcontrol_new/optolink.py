import asyncio
from asyncio import AbstractEventLoop
from datetime import datetime

import serial


class OptolinkConnection:
    """Represents an asynchronous connection to a Viessmann Optolink device.

    This class has very basic functionality and only provides methods to read data from the device
    as well as send data to the device.
    """

    def __init__(self, event_loop: AbstractEventLoop, device="/dev/ttyUSB0"):
        """Create and open a new connection to an Optolink device."""
        self.device = device
        self.loop = event_loop
        # timeout=0 for non-blocking reads
        self.port = serial.Serial(
            self.device,
            4800,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_TWO,
            timeout=0,
        )
        self.read_queue = asyncio.Queue()
        event_loop.add_reader(self.port.fileno(), self._read_serial)

    def _read_serial(self):
        # read as many bytes as are available at once
        for b in self.port.read(1000):
            self.read_queue.put_nowait(b)

    def flush(self):
        """Flush the read buffer of all data received from the device by now."""
        try:
            while True:
                self.read_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass

    async def read(self, count=1, timeout=10):
        """Read a specific number of bytes from the device with a timeout."""
        start = datetime.now()
        ret = bytearray()
        try:
            for _ in range(count):
                timeout_left = timeout - (datetime.now() - start).total_seconds()
                ret.append(
                    await asyncio.wait_for(self.read_queue.get(), timeout=timeout_left)
                )
        except asyncio.TimeoutError:
            pass
        return ret

    def write(self, b: bytes):
        """Send some bytes to the device.

        This method is blocking but this is not a problem as we won't ever send
        more than 15-20 bytes per command at once so the event loop is not occupied
        for too long. Bytes per second: 4800 / (1 + 1 + 2 + 8) = 400. So a theoretical
        command 20 bytes long would take 5 ms to be transmitted which is OK.
        """
        return self.port.write(b)
