"""Optional shared-secret access control for /api (env LINGENIOUS_ACCESS_TOKEN). The token is never logged or echoed."""
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Callable, Optional

from fastapi import Request

COOKIE = "lingenious_session"
OPEN_PATHS = {"/api/health", "/api/auth/login", "/api/auth/logout"}
MAX_FREE_FAILS = 5        # failed logins per client before backoff starts
MAX_BACKOFF_S = 300.0
_MAX_TRACKED = 2000


class Auth:
    def __init__(self, token: Optional[str], clock: Callable[[], float] = time.monotonic):
        self.token = token or None
        self._clock = clock
        # the cookie carries a derived value, not the token itself
        self._session = hmac.new((self.token or "").encode(), b"lingenious-session-v1", hashlib.sha256).hexdigest()
        self._fails: dict[str, tuple[int, float]] = {}  # ip -> (failures, blocked_until)

    @property
    def required(self) -> bool:
        return self.token is not None

    @staticmethod
    def _eq(a: str, b: str) -> bool:
        return hmac.compare_digest(hashlib.sha256(a.encode()).digest(), hashlib.sha256(b.encode()).digest())

    def check_token(self, candidate: str) -> bool:
        return self.token is not None and self._eq(candidate, self.token)

    def authenticated(self, request: Request) -> bool:
        if not self.required:
            return True
        h = request.headers.get("authorization", "")
        if h[:7].lower() == "bearer " and self.check_token(h[7:].strip()):
            return True
        c = request.cookies.get(COOKIE)
        return bool(c) and self._eq(c, self._session)  # type: ignore[arg-type]

    # ---- failed-login throttling (in memory, per client address)
    @staticmethod
    def client(request: Request) -> str:
        return request.client.host if request.client else "?"

    def retry_after(self, ip: str) -> int:
        _, until = self._fails.get(ip, (0, 0.0))
        left = until - self._clock()
        return int(left) + 1 if left > 0 else 0

    def record_failure(self, ip: str) -> None:
        if len(self._fails) >= _MAX_TRACKED:
            now = self._clock()
            self._fails = {k: v for k, v in self._fails.items() if v[1] > now}
        n = self._fails.get(ip, (0, 0.0))[0] + 1
        delay = min(MAX_BACKOFF_S, 2.0 ** (n - MAX_FREE_FAILS)) if n >= MAX_FREE_FAILS else 0.0
        self._fails[ip] = (n, self._clock() + delay)

    def record_success(self, ip: str) -> None:
        self._fails.pop(ip, None)

    def session_value(self) -> str:
        return self._session
