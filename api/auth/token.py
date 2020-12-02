from datetime import datetime, timedelta
from secrets import token_hex
from typing import Union


class AuthenticationToken:
    def __init__(self, valid_until: datetime):
        self.valid_until = valid_until
        self.data = token_hex(16)
    
    def __eq__(self, other):
        return other == self.data \
            or self.__class__ == other.__class__ and self.data == other.data

    def __hash__(self):
        return hash(self.data) 

class TokenState:
    pass

class TokenInvalid(TokenState):
    def get_reason(self):
        return "Token invalid!"

class TokenExpired(TokenInvalid):
    def get_reason(self):
        return "Token expired!"

class TokenValid(TokenState):
    def __init__(self, valid_until: datetime, user: str):
        self.valid_until = valid_until
        self.user = user

class TokenStore:
    def __init__(self, cleanup_tokencount: int = 1000, cleanup_expired_longer_than: timedelta = timedelta(days=90)):
        self.tokens = {}
        self.cleanup_tokencount = cleanup_tokencount
        self.cleanup_expired_longer_than = cleanup_expired_longer_than
    
    def insert(self, user: str, token: AuthenticationToken):
        self.tokens[token.data] = token, user
        if len(self.tokens) > self.cleanup_tokencount:
            self._cleanup()
    
    def is_valid(self, token: Union[str, AuthenticationToken]) -> TokenState:
        token_data = token if isinstance(token, str) else token.data
        if token_data not in self.tokens:
            return TokenInvalid()
        token, user = self.tokens[token_data]
        if token.valid_until < datetime.now():
            del self.tokens[token_data]
            return TokenExpired()
        return TokenValid(token.valid_until, user)
    
    def _cleanup(self):
        keys_to_delete = [ 
            key 
            for key, (token, user)
            in self.tokens.items()
            if token.valid_until + self.cleanup_expired_longer_than < datetime.now()
        ]
        for key in keys_to_delete:
            del self.tokens[key]
