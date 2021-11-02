from vcontrol_new import ConnectionCache

from .auth import BaseAuthenticationProvider
from .base_api import BaseApiPart, api_route
from .serializer import Serializer, DeserializationException


class ParameterApi(BaseApiPart):
    def __init__(
        self, conn: ConnectionCache, auth_provider: BaseAuthenticationProvider
    ):
        super().__init__("parameters_api", "/parameters", conn, auth_provider)

    @api_route("/")
    async def get_parameters(self, request):
        parameters = self.conn.param_storage.get_supported_parameters()
        return [
            {
                "id": param.id,
                "title": param.name,
                "readonly": param.readonly,
                "unit": Serializer.describe_unit(param.unit),
            }
            for param in parameters
        ]

    @api_route("/<param_id>", {"POST"})
    async def set_parameter(self, request, param_id):
        try:
            param = self.conn.param_storage.get_parameter(param_id)
            value = self.get_param_value(request)
            if value is None:
                return {"error": "Parameter value must be given as 'value' key in a JSON object!"}
            await self.conn.set_param(
                param, Serializer.deserialize(value, param.unit)
            )
            return {"success": "Parameter set successfully"}
        except (IndexError, KeyError):
            return {"error", "Parameter not found!"}
        except DeserializationException:
            return {"error": "Could not set parameter, wrong format given!"}
        except:
            return {"error": "Error occured while setting parameter!"}

    @api_route("/<param_id>/reload")
    async def reload_param(self, request, param_id):
        return await self.get_parameter(request, param_id, force_load=True)

    @api_route("/<param_id>", {"GET"})
    async def get_param_normal(self, request, param_id):
        return await self.get_parameter(request, param_id)

    async def get_parameter(self, request, parameter_id, force_load: bool = False):
        reading = await self.conn.read_param(parameter_id, force=force_load)
        return {
            "id": reading.parameter.id,
            "name": reading.parameter.name,
            "lastReload": reading.time.isoformat(),
            "value": Serializer.serialize(reading.value, reading.parameter.unit),
            "display_string": reading.parameter.unit.get_display_string(reading.value),
            "readonly": reading.parameter.readonly,
            "unit": Serializer.describe_unit(reading.parameter.unit),
        }

    def get_param_value(self, request):
        try:
            if isinstance(request.json, dict):
                return request.json.get("value")
        except:
            pass
        return None
