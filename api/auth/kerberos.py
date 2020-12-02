import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Set

import kerberos

from . import AuthenticationBackend


class KerberosAuthenticationBackend(AuthenticationBackend):
    def __init__(self, realm_lowercase: str, allowed_users: Set[str] = frozenset()):
        self.realm = realm_lowercase
        self.allowed_users = allowed_users
    
    async def check_password(self, user: str, password: str) -> bool:
        if len(self.allowed_users) > 0 and user not in self.allowed_users:
            return False
        
        with ThreadPoolExecutor(1) as thread:
            try:
                return await asyncio.get_event_loop().run_in_executor(thread, kerberos.checkPassword, user, password, f"krbtgt/{self.realm}", self.realm.upper())
            except:
                return False
