import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings

# In-process sliding window (replace with Redis in production)
# Structure: { key: [timestamp, timestamp, ...] }
_windows: dict[str, list[float]] = {}

PLAN_LIMITS = {
    "free":       settings.RATE_LIMIT_FREE,
    "pro":        settings.RATE_LIMIT_PRO,
    "team":       settings.RATE_LIMIT_TEAM,
    "enterprise": 2000,
}

RATE_LIMITED_PATHS_PREFIX = "/api/v1/"
WINDOW_SECONDS = 60


def _get_limit(plan: str) -> int:
    return PLAN_LIMITS.get(plan, settings.RATE_LIMIT_FREE)


def _sliding_window_check(key: str, limit: int) -> tuple[bool, int]:
    """Returns (allowed, current_count)."""
    now = time.time()
    window_start = now - WINDOW_SECONDS
    timestamps = _windows.get(key, [])
    # Evict old entries
    timestamps = [t for t in timestamps if t > window_start]
    if len(timestamps) >= limit:
        _windows[key] = timestamps
        return False, len(timestamps)
    timestamps.append(now)
    _windows[key] = timestamps
    return True, len(timestamps)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not request.url.path.startswith(RATE_LIMITED_PATHS_PREFIX):
            return await call_next(request)

        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            return await call_next(request)

        workspace_id = getattr(request.state, "workspace_id", "unknown")
        plan = getattr(request.state, "plan", "free")  # enriched by billing check
        limit = _get_limit(plan)

        # Rate limit per user within workspace
        key = f"rl:{workspace_id}:{user_id}"
        allowed, count = _sliding_window_check(key, limit)

        if not allowed:
            return JSONResponse(
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(WINDOW_SECONDS),
                },
                content={
                    "error": "RATE_LIMITED",
                    "message": f"Rate limit exceeded. Max {limit} requests per minute.",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        return response