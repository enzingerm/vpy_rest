import asyncio
from datetime import datetime

from sanic import Blueprint
from util import get_param_from_request, Weekday, ExtendedLock, LockedException
from vcontrol_new import ConnectionCache
from vcontrol_new.parameter import AggregatedParameter, ParameterReading
from vcontrol_new.unit import CycleTimeUnit

from .auth import BaseAuthenticationProvider
from .base_api import BaseApiPart, api_route
from .serializer import Serializer


class PartyModeManager:
    class PartyModeState:
        pass
    class Enabled(PartyModeState):
        def __init__(self, until):
            self.until = until
    class Disabled(PartyModeState):
        pass

    def __init__(
        self,
        program_param: AggregatedParameter,
        conn: ConnectionCache
    ):
        self.program_param = program_param
        self.conn = conn
        self.cancel_task = None
        self.cached_reading = None
        self.until = None
        self.working_lock = ExtendedLock()
    
    async def get_status(self) -> PartyModeState:
        async with self.working_lock:
            if self.until is None:
                return self.Disabled()
            else:
                return self.Enabled(self.until)

    async def enable(self, until):
        # expect 'until' to be a valid datetime somewhen later this day
        def _disable():
            self.cancel_task = None
            asyncio.get_event_loop().create_task(self._disable())
        async with self.working_lock.nowait():
            if self.until is not None:
                raise Exception("Party mode is already enabled!")
            day_param = self.program_param.get_child_param(datetime.now().weekday())
            cached_reading = await self.conn.read_param(day_param)
            temporary_program = [((0, 0), (24, 00))]
            await self.conn.set_param(day_param, temporary_program)
            seconds = (until - datetime.now()).total_seconds()
            print(f"Scheduling disabling party mode of {self.program_param.name} at {until} which is in {seconds} seconds!")
            self.cancel_task = asyncio.get_event_loop().call_later(seconds, _disable)
            self.until = until
            self.cached_reading = cached_reading
        
    async def _disable(self):
        async with self.working_lock.nowait():
            if self.until is None:
                raise Exception("Party mode is already disabled!")
            try:
                await self.conn.set_param(self.cached_reading.parameter, self.cached_reading.value)
            finally:
                self.cached_reading = None
                self.until = None

    async def disable(self):
        # disable the cancel task and run _disable() manually
        if self.cancel_task is not None:
            self.cancel_task.cancel()
            self.cancel_task = None
        await self._disable()

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
        self.party_mode_manager = PartyModeManager(program_param, conn)

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
    
    @api_route("/party_mode")
    async def get_party_mode(self, request):
        status = await self.party_mode_manager.get_status()
        if isinstance(status, PartyModeManager.Disabled):
            return {"active": False}
        elif isinstance(status, PartyModeManager.Enabled):
            return {"active": True, "activeUntil": status.until.isoformat()}
        # we shouldn't end up here
        raise Exception("Invalid party mode status!")

    @api_route("/party_mode/enable", methods={"POST"})
    async def enable_party_mode(self, request):
        until = get_param_from_request(request, "until")
        if until is None:
            raise Exception("Parameter 'until' was not given!")
        now = datetime.now()
        until = datetime.fromisoformat(until)
        if now.date() != until.date() or now.time() >= until.time():
            raise Exception("Party mode can only be activated for the current day!")
        await self.party_mode_manager.enable(until)
        return {"success": True}

    @api_route("/party_mode/disable", methods={"POST"})
    async def disable_party_mode(self, request):
        await self.party_mode_manager.disable()
        return {"success": True}

    async def get_day(self, request, day_id, force: bool = False):
        day = Weekday(day_id)
        day_param_id = f"{self.program_param.id}.{day_id}"
        cached_reading = self.party_mode_manager.cached_reading
        reading = None
        if cached_reading is not None and cached_reading.parameter.id == day_param_id:
            reading = cached_reading
        else:
            reading = await self.conn.read_param(day_param_id, force=force)
        return {
            "dayID": day.value,
            "dayName": day.name,
            "lastReload": reading.time.isoformat(),
            "cycleTimes": Serializer.serialize(reading.value, CycleTimeUnit()),
        }

    async def set_day(self, request, day_id):
        day_param = self.program_param.get_child_param(day_id)
        times = Serializer.deserialize(request.json, CycleTimeUnit())
        cached_reading = self.party_mode_manager.cached_reading
        if cached_reading is not None and cached_reading.parameter.id == day_param.id:
            self.party_mode_manager.cached_reading = ParameterReading(
                day_param,
                times,
                datetime.now()
            )
        else:
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
