from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional, Protocol

from teaagent.oauth21._types import OAuth21Client, _AuthorizationCode


class OAuthStore(Protocol):
    def register_client(self, client: OAuth21Client) -> None: ...

    def get_client(self, client_id: str) -> Optional[OAuth21Client]: ...

    def save_code(self, code: _AuthorizationCode) -> None: ...

    def consume_code(self, code: str) -> Optional[_AuthorizationCode]: ...

    def save_nonce(self, nonce: str, created_at: float) -> None: ...

    def get_nonce(self, nonce: str) -> Optional[float]: ...

    def delete_nonce(self, nonce: str) -> None: ...

    def prune(self, *, now: float, code_ttl_cutoff: float, nonce_ttl: float) -> None: ...


class InMemoryOAuthStore:
    def __init__(self) -> None:
        self.clients: dict[str, OAuth21Client] = {}
        self.codes: dict[str, _AuthorizationCode] = {}
        self.nonces: dict[str, float] = {}

    def register_client(self, client: OAuth21Client) -> None:
        self.clients[client.client_id] = client

    def get_client(self, client_id: str) -> Optional[OAuth21Client]:
        return self.clients.get(client_id)

    def save_code(self, code: _AuthorizationCode) -> None:
        self.codes[code.code] = code

    def consume_code(self, code: str) -> Optional[_AuthorizationCode]:
        return self.codes.pop(code, None)

    def save_nonce(self, nonce: str, created_at: float) -> None:
        self.nonces[nonce] = created_at

    def get_nonce(self, nonce: str) -> Optional[float]:
        return self.nonces.get(nonce)

    def delete_nonce(self, nonce: str) -> None:
        self.nonces.pop(nonce, None)

    def prune(self, *, now: float, code_ttl_cutoff: float, nonce_ttl: float) -> None:
        expired_codes = [c for c, ac in self.codes.items() if ac.expires_at < now]
        for code in expired_codes:
            del self.codes[code]
        expired_nonces = [
            nonce for nonce, created in self.nonces.items() if now - created > nonce_ttl
        ]
        for nonce in expired_nonces:
            del self.nonces[nonce]


@dataclass(frozen=True)
class OAuthKeyRing:
    active_kid: str
    keys: Mapping[str, bytes]

    @classmethod
    def single(cls, key: bytes, *, kid: str = 'default') -> 'OAuthKeyRing':
        return cls(active_kid=kid, keys={kid: key})

    @property
    def active_key(self) -> bytes:
        return self.keys[self.active_kid]

    def key_for(self, kid: Optional[str]) -> bytes:
        if kid and kid in self.keys:
            return self.keys[kid]
        return self.active_key
