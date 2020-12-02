from vcontrol_new import ConnectionCache

from .auth import BaseAuthenticationProvider
from .base_api import BaseApiPart, api_route


class RawApi(BaseApiPart):
    def __init__(
        self, conn: ConnectionCache, auth_provider: BaseAuthenticationProvider
    ):
        super().__init__("raw_api", "/raw", conn, auth_provider)

    @api_route("/<address>/<size:int>")
    async def read_address(self, request, address, size):
        assert 0 < size < 32
        address = bytes.fromhex(address)
        return {
            "address": address.hex(),
            "size": size,
            "value": "0x" + (await self.conn.conn.read_address(address, size)).hex(),
        }
