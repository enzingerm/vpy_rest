import asyncio
from datetime import datetime

from vcontrol_new import ConnectionCache
from vcontrol_new.parameter import AggregatedParameter

from .auth import BaseAuthenticationProvider
from .base_api import BaseApiPart, api_route


class HighlevelApi(BaseApiPart):
    def __init__(
        self,
        conn: ConnectionCache,
        auth_provider: BaseAuthenticationProvider,
        hotwater_program_param: AggregatedParameter,
    ):
        super().__init__("highlevel_api", "/special", conn, auth_provider)
        self.hotwater_heatup_active = False
        self.current_program = None
        self.hotwater_program_param = hotwater_program_param
        self.day_param = None

    @api_route("/hotwater_fast_heatup", {"GET", "POST"})
    async def hotwater_heatup(self, request):
        """Starts a single hotwater heat-up "command" to the configured nominal temperature.

        This works by temporarily setting the hotwater shifting program from 00:00 to 24:00
        and after a few seconds turning it back to the original value.
        """
        assert isinstance(self.hotwater_program_param, AggregatedParameter)
        if request.method == "POST" and not self.hotwater_heatup_active:
            now = datetime.now()
            self.hotwater_heatup_active = True
            self.day_param = self.hotwater_program_param.get_child_param(now.weekday())
            temporary_program = [((0, 0), (24, 00))]
            self.current_program = (
                await self.conn.read_param(self.day_param, force=True)
            ).value
            await self.conn.set_param(self.day_param, temporary_program)
            asyncio.get_event_loop().create_task(self.rollback())
        return {"heatup_status": self.hotwater_heatup_active}

    async def rollback(self):
        await asyncio.sleep(90)
        await self.conn.set_param(self.day_param, self.current_program)
        asyncio.get_event_loop().call_later(15 * 60, self.disable)

    def disable(self):
        print("Disabling hotwater heatup")
        self.hotwater_heatup_active = False
        self.current_program = None
        self.day_param = None
