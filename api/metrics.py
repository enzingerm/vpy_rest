from vcontrol_new import ConnectionCache

from sanic import response
from .auth import BaseAuthenticationProvider
from .base_api import BaseApiPart, api_route
from collections import namedtuple
from typing import List

MetricMapping = namedtuple("MetricMapping", ["param", "prometheus_name", "type"])


class MetricsApi(BaseApiPart):
    def __init__(
        self,
        conn: ConnectionCache,
        auth_provider: BaseAuthenticationProvider,
        mappings: List[MetricMapping],
    ):
        super().__init__("metrics_api", "/metrics", conn, auth_provider)
        self.mappings = mappings

    @api_route("/", raw_mode=True, require_auth=False)
    async def metrics(self, request):
        ret = ""
        for m in self.mappings:
            try:
                reading = await self.conn.read_param(m.param, force=True)
                ret += f"""# HELP {m.prometheus_name} {m.param.name}
# TYPE {m.prometheus_name} {m.type}
{m.prometheus_name} {reading.value}
"""
            except Exception as e:
                ret += f"## Error reading value of {m.param.name}: {e}\n"
        return response.text(ret)