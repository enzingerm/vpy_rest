import asyncio

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

class LockedException(Exception):
    pass

class ExtendedLock:
    def __init__(self):
        self.lock = asyncio.Lock()
    
    def nowait(self):
        if self.lock.locked():
            raise LockedException()
        return self
    
    def locked(self):
        return self.lock.locked()
    
    async def acquire(self):
        return await self.lock.acquire()
    
    def release(self):
        return self.lock.release()
    
    async def __aenter__(self):
        return await self.lock.__aenter__()
    
    async def __aexit__(self, exc_type, exc, tb):
        return await self.lock.__aexit__(exc_type, exc, tb)
