from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Paths that don't belong to a workspace
UNSCOPED_PATHS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/me",
}


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Ensures every authenticated request carries a workspace_id.
    The workspace_id is injected by AuthMiddleware from the JWT.
    This middleware guards against requests that somehow bypass that.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in UNSCOPED_PATHS:
            return await call_next(request)

        # Only enforce on authenticated routes
        if hasattr(request.state, "user_id"):
            workspace_id = getattr(request.state, "workspace_id", None)
            if not workspace_id:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "MISSING_WORKSPACE",
                        "message": "Request is not scoped to a workspace. Include a workspace_id in your JWT.",
                    },
                )

        return await call_next(request)