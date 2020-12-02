class AuthenticationBackend:
    async def check_password(self, user: str, password: str) -> bool:
        raise NotImplementedError

class DummyAuthenticationBackend(AuthenticationBackend):
    async def check_password(self, user: str, password: str) -> bool:
        return True

class ListAuthenticationBackend(AuthenticationBackend):
    def __init__(self, users_list):
        self.users_list = users_list
    
    async def check_password(self, user: str, password: str) -> bool:
        return any(it["username"] == user and it["password"] == password for it in self.users_list)

class AuthenticationException(Exception):
    pass

class BaseAuthenticationProvider:
    def __init__(self, backend: AuthenticationBackend):
        self.backend = backend
    
    async def login(self, user: str, password: str) -> dict:
        raise NotImplementedError

    def check_auth(self, request):
        raise NotImplementedError

class NoAuthenticationProvider(BaseAuthenticationProvider):
    async def login(self, user: str, password: str) -> dict:
        return { "success": "logged in successfully" }
    
    def check_auth(self, request):
        pass
