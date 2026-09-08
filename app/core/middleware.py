"""Cross-cutting HTTP middleware, wired up in app/main.py.

Kept separate from tenancy/auth: this module only touches request/response
plumbing (timing, request IDs, logging) — it never resolves identity or
tenant context. That stays in app/core/auth.py and app/core/tenancy.py.
"""
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

logger = logging.getLogger("flowgard.request")


def add_middleware(app: FastAPI) -> None:
    """Registers all app-wide middleware. Called once from app/main.py."""

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled request failure [%s]", request_id)
            response = Response(status_code=500, content="Internal server error")

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = request_id
        logger.info(
            "%s %s -> %s (%.1fms) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
