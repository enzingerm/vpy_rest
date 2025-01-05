import asyncio
import uvloop

from sanic import Sanic

from api import Api, HighlevelApi, MetricsApi, ParameterApi, ProgramsApi, RawApi
from config import get_config
from vcontrol_new import ConnectionCache

app = Sanic(__name__)


def create_api(conn: ConnectionCache, api_cfg):
    auth_provider = api_cfg.auth.provider
    api_parts = [
        ProgramsApi(conn, auth_provider),
        ParameterApi(conn, auth_provider),
        RawApi(conn, auth_provider),
        HighlevelApi(conn, auth_provider, api_cfg.highlevel.hotwater_program_param),
    ]
    if api_cfg.prometheus_metrics.enabled:
        api_parts.append(
            MetricsApi(conn, auth_provider, api_cfg.prometheus_metrics.mappings)
        )
    return Api(conn, auth_provider, api_parts)


async def main():
    loop = asyncio.get_event_loop()
    cfg = get_config(loop)
    cfg.device.conn.start_communication()
    api = create_api(cfg.device, cfg.api)
    app.blueprint(api.get_blueprint())
    server = await app.create_server(
        host=cfg.server.ip, port=cfg.server.port, return_asyncio_server=True
    )
    await server.startup()
    await server.serve_forever()


if __name__ == "__main__":
    asyncio.set_event_loop(uvloop.new_event_loop())
    asyncio.run(main())
