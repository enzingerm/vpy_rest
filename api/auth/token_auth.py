from datetime import datetime, timedelta

from util import get_param_from_request

from . import (AuthenticationBackend, AuthenticationException,
               BaseAuthenticationProvider)
from .token import AuthenticationToken, TokenInvalid, TokenStore


class TokenAuthenticationProvider(BaseAuthenticationProvider):
    def __init__(self, backend: AuthenticationBackend, token_validity: timedelta = timedelta(days=90)):
        super().__init__(backend)
        self.token_store = TokenStore()
        self.token_validity = token_validity

    async def login(self, user: str, password: str) -> AuthenticationToken:
        try:
            if not await self.backend.check_password(user, password):
                raise AuthenticationException
            token = AuthenticationToken(datetime.now() + self.token_validity)
            self.token_store.insert(user, token)
            return {
                "token": token.data,
                "valid_until": token.valid_until.isoformat()
            }
        except:
            raise AuthenticationException("Login failed!")

    def check_auth(self, request) -> bool:
        token = request.token or get_param_from_request(request, "token")
        if not token:
            raise AuthenticationException("No authentication token given!")
        token_state = self.token_store.is_valid(token)
        if isinstance(token_state, TokenInvalid):
            raise AuthenticationException(token_state.get_reason())
