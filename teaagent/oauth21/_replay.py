from __future__ import annotations

import threading

from teaagent.oauth21._types import InvalidDPoPError


class DPoPReplayCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seen: dict[str, float] = {}

    def remember_once(self, jti: object, *, iat: float, now: float, ttl: float) -> None:
        if not isinstance(jti, str) or not jti:
            raise InvalidDPoPError('DPoP proof missing jti')
        with self._lock:
            expired = [
                key for key, created in self._seen.items() if now - created > ttl
            ]
            for key in expired:
                del self._seen[key]
            if jti in self._seen:
                raise InvalidDPoPError('DPoP proof jti was already used')
            self._seen[jti] = iat
