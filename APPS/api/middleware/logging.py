import time
import uuid
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("catai.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Attaches a correlation_id to every request and logs
    method, path, status, and latency in structured JSON format.
    In production: replace logger calls with structlog for JSON output.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id

        start = time.monotonic()
        response = await call_next(request)
        latency_ms = round((time.monotonic() - start) * 1000, 2)

        # Skip logging for health checks to reduce noise
        if request.url.path not in ("/health", "/"):
            logger.info(
                "request",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "user_id": getattr(request.state, "user_id", None),
                    "workspace_id": getattr(request.state, "workspace_id", None),
                },
            )

        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time"] = f"{latency_ms}ms"
        return response