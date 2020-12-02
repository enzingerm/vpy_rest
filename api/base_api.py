import functools

from sanic import Blueprint
from sanic.response import json, text
from vcontrol_new import ConnectionCache

from .auth import AuthenticationException, BaseAuthenticationProvider


class BaseApiPart:
    def __init__(
        self,
        id: str,
        url_prefix: str,
        conn: ConnectionCache,
        auth_provider: BaseAuthenticationProvider,
    ):
        self.conn = conn
        self.auth_provider = auth_provider
        self.blueprint = Blueprint(id, url_prefix=url_prefix)
        for fn, name, uri, methods, args, kwargs in self.__class__._routes:
            # sanic internally sets attributes like __blueprintname__ and expects
            # __name__ to be set, thus bound methods are not possible here
            bound = functools.partial(fn, self)
            setattr(bound, "__name__", name)
            self.blueprint.add_route(bound, uri, methods, *args, **kwargs)

    def get_blueprint(self):
        return self.blueprint


class api_route:
    """Creates a route within an BaseApiPart.

    Per default, it will handle authentication checks and return a JSON response.

    Parameters
    ---------
    uri: `str`
        The URI for the route, check Sanic docs on how to specify parameters in URIs.
    methods: `set`
        Request HTTP methods, defaults to {'GET'}
    require_auth: `bool`
        Whether this route is only accessible after successful authentication.
    raw_mode: `bool`
        Whether the handler function is responsible for creating the Sanic response object
        (no JSON response will be created per default from the returned object)

    """

    class inner:
        def __init__(self, fn, uri, methods, require_auth, raw_mode, args, kwargs):
            self.fn = fn
            self.uri = uri
            self.methods = methods
            self.require_auth = require_auth
            self.raw_mode = raw_mode
            self.args = args
            self.kwargs = kwargs

        def __set_name__(self, owner, name):
            assert issubclass(owner, BaseApiPart)
            if not hasattr(owner, "_routes"):
                setattr(owner, "_routes", [])
            routes = getattr(owner, "_routes")
            method = self.create_handler()
            routes.append(
                (method, name, self.uri, self.methods, self.args, self.kwargs)
            )

        def create_handler(self):
            async def handler(inner_self, request, *args, **kwargs):
                if self.require_auth:
                    try:
                        inner_self.auth_provider.check_auth(request)
                    except AuthenticationException as e:
                        if self.raw_mode:
                            return text("Error: " + str(e.args[0]), status=401)
                        else:
                            return json({"error": e.args[0]}, status=401)
                    except Exception:
                        if self.raw_mode:
                            return text(
                                "Error: Failed checking authentication!", status=401
                            )
                        else:
                            return json(
                                {"Error": "Failed checking authentication!"}, state=401
                            )
                try:
                    result = await self.fn(inner_self, request, *args, **kwargs)
                    return json(result) if not self.raw_mode else result
                except Exception as e:
                    return (
                        json({"error": str(e)})
                        if not self.raw_mode
                        else text("Error: " + str(e))
                    )

            return handler

    def __init__(
        self,
        uri,
        methods=frozenset({"GET"}),
        require_auth=True,
        raw_mode=False,
        *args,
        **kwargs
    ):
        self.uri = uri
        self.methods = methods
        self.require_auth = require_auth
        self.args = args
        self.kwargs = kwargs
        self.raw_mode = raw_mode

    def __call__(self, fn) -> inner:
        return api_route.inner(
            fn,
            self.uri,
            self.methods,
            self.require_auth,
            self.raw_mode,
            self.args,
            self.kwargs,
        )
