"""Lightweight middlewares: request-id assignment and per-IP rate limiting."""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("rolling.http")


class RequestIdMiddleware(BaseHTTPMiddleware):
    HEADER = "X-Request-Id"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get(self.HEADER) or uuid.uuid4().hex
        request.state.request_id = rid
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000.0
            logger.exception(
                "request_failed rid=%s method=%s path=%s elapsed_ms=%.1f",
                rid,
                request.method,
                request.url.path,
                elapsed,
            )
            raise
        elapsed = (time.perf_counter() - start) * 1000.0
        response.headers[self.HEADER] = rid
        logger.info(
            "request rid=%s method=%s path=%s status=%s elapsed_ms=%.1f",
            rid,
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response


# In-memory sliding-window rate limiter. Single-process only; for multi-worker
# deploys, swap with Redis-backed alternative.
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        rules: dict[str, tuple[int, float]],
    ) -> None:
        """rules: { path_prefix: (max_requests, window_seconds) }."""
        super().__init__(app)
        self.rules = rules
        self.buckets: dict[str, deque[float]] = defaultdict(deque)

    def _match_rule(self, path: str) -> tuple[int, float] | None:
        for prefix, rule in self.rules.items():
            if path.startswith(prefix):
                return rule
        return None

    def _client_key(self, request: Request, prefix: str) -> str:
        fwd = request.headers.get("x-forwarded-for")
        ip = (
            fwd.split(",")[0].strip()
            if fwd
            else (request.client.host if request.client else "unknown")
        )
        return f"{ip}:{prefix}"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rule = self._match_rule(request.url.path)
        if rule is None:
            return await call_next(request)
        max_req, window = rule
        prefix = request.url.path
        key = self._client_key(request, prefix)
        now = time.monotonic()
        bucket = self.buckets[key]
        cutoff = now - window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= max_req:
            retry_after = max(0.0, window - (now - bucket[0]))
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please try again shortly.",
                        "details": {"retry_after_seconds": round(retry_after, 1)},
                    }
                },
                headers={"Retry-After": str(int(retry_after) + 1)},
            )
        bucket.append(now)
        return await call_next(request)
