from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-process sliding-window rate limit for expensive public endpoints.

    Suitable for a single uvicorn worker on Silk; pair with proxy limits when scaling.
    """

    def __init__(
        self,
        app,
        *,
        max_requests: int = 60,
        window_seconds: float = 60.0,
        path_prefixes: tuple[str, ...] = ("/api/query", "/api/format"),
    ) -> None:
        super().__init__(app)
        self.max_requests = max(1, max_requests)
        self.window_seconds = max(1.0, window_seconds)
        self.path_prefixes = path_prefixes
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip() or "unknown"
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def _limited(self, request: Request) -> bool:
        path = request.url.path
        return any(path == p or path.startswith(p + "/") for p in self.path_prefixes)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS" or not self._limited(request):
            return await call_next(request)

        key = f"{self._client_key(request)}:{request.url.path}"
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            cutoff = now - self.window_seconds
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_requests:
                retry = max(1, int(self.window_seconds - (now - q[0])))
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": {
                            "message": "Too many requests. Please slow down and try again.",
                            "code": "rate_limited",
                        }
                    },
                    headers={"Retry-After": str(retry)},
                )
            q.append(now)

        return await call_next(request)
