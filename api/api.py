from typing import List

from sanic import Blueprint
from sanic.response import json
from util import get_param_from_request
from vcontrol_new import ConnectionCache

from .auth import BaseAuthenticationProvider, AuthenticationException
from .base_api import BaseApiPart


class Api:
    def __init__(
        self,
        conn: ConnectionCache,
        auth_provider: BaseAuthenticationProvider,
        api_parts: List[BaseApiPart],
    ):
        self.conn = conn
        self.blueprint = None
        self.auth_provider = None
        self.auth_blueprint = None
        self.auth_provider = auth_provider
        self._init_auth()
        self._api_parts = api_parts

    def get_conn(self):
        return self.conn

    def get_blueprint(self):
        if not self.blueprint:
            self.blueprint = Blueprint.group(
                self.auth_blueprint, *[it.get_blueprint() for it in self._api_parts]
            )
        return self.blueprint

    def _init_auth(self):
        self.auth_blueprint = Blueprint("auth_api", url_prefix="/auth")

        async def login(request):
            try:
                username = get_param_from_request(request, "user")
                password = get_param_from_request(request, "password")
                if not username or not password:
                    return json(
                        {"error": "'user' and 'password' must be provided!"}, status=401
                    )
                return json(await self.auth_provider.login(username, password))
            except AuthenticationException as e:
                return json({"error": e.args[0]}, status=401)
            except Exception:
                return json({"error": "Authentication failed!"}, status=401)

        self.auth_blueprint.add_route(login, "/login", methods=["POST"])
