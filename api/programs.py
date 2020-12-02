from sanic import Blueprint
from util import Weekday
from vcontrol_new import ConnectionCache
from vcontrol_new.parameter import AggregatedParameter
from vcontrol_new.unit import CycleTimeUnit

from .auth import BaseAuthenticationProvider
from .base_api import BaseApiPart, api_route
from .serializer import Serializer


class ProgramApi(BaseApiPart):
    def __init__(
        self,
        program_param: AggregatedParameter,
        conn: ConnectionCache,
        auth_provider: BaseAuthenticationProvider,
    ):
        super().__init__(
            f"program_api_{program_param.id}",
            f"/{program_param.id}",
            conn,
            auth_provider,
        )
        self.program_param = program_param

    async def get(self, request, force: bool = False):
        reading = await self.conn.read_param(self.program_param, force=force)
        return {
            "id": self.program_param.id,
            "name": self.program_param.name,
            "lastReload": reading.time.isoformat(),
            "cycleTimes": [await self.get_day(request, day.id) for day in Weekday],
        }

    @api_route("/")
    async def get_normal(self, request):
        return await self.get(request, force=False)

    @api_route("/reload")
    async def get_reload(self, request):
        return await self.get(request, force=True)

    @api_route("/day/<day_id:int>", methods={"GET", "POST"})
    async def day(self, request, day_id):
        if request.method == "POST":
            return await self.set_day(request, day_id)
        else:
            return await self.get_day(request, day_id, force=False)

    @api_route("/day/<day_id:int>/reload")
    async def reload_day(self, request, day_id):
        return await self.get_day(request, day_id, force=True)

    async def get_day(self, request, day_id, force: bool = False):
        day = Weekday(day_id)
        reading = await self.conn.read_param(
            f"{self.program_param.id}.{day_id}", force=force
        )
        return {
            "dayID": day.value,
            "dayName": day.name,
            "lastReload": reading.time.isoformat(),
            "cycleTimes": Serializer.serialize(reading.value, CycleTimeUnit()),
        }

    async def set_day(self, request, day_id):
        times = Serializer.deserialize(request.json, CycleTimeUnit())
        await self.conn.set_param(f"{self.program_param.id}.{day_id}", times)
        return {"success": True}


class ProgramsApi(BaseApiPart):
    def __init__(
        self, conn: ConnectionCache, auth_provider: BaseAuthenticationProvider
    ):
        super().__init__("programs_api", "/", conn, auth_provider)
        self.programs = [
            param
            for param in conn.param_storage.get_supported_parameters()
            if isinstance(param, AggregatedParameter)
            and isinstance(param.member_unit, CycleTimeUnit)
        ]

        self.program_apis = [
            ProgramApi(program_param, conn, auth_provider)
            for program_param in self.programs
        ]
        self.blueprint_group = Blueprint.group(
            *[api.blueprint for api in self.program_apis],
            self.blueprint,
            url_prefix="/programs",
        )

    @api_route("")
    async def get_programs(self, request):
        return [{"id": program.id, "name": program.name} for program in self.programs]

    def get_blueprint(self):
        return self.blueprint_group
