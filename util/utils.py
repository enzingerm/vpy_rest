from sanic.request import Request


def get_param_from_request(request: Request, param: str):
    try:
        if param in request.args:
            return request.args[param][0]
        if request.method == "POST":
            if "application/json" in request.headers["Content-Type"]:
                if isinstance(request.json, dict):
                    return request.json[param]
            else:
                return request.form[param][0]
        return None
    except KeyError:
        return None
