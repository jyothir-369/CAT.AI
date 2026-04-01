from fastapi import Request, Response
from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from core.security import decode_token

# Routes that don't require auth
PUBLIC_PATHS = {
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/webhooks/stripe",  # verified by signature, not JWT
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/api/v1/webhooks/"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "AUTH_ERROR", "message": "Missing Authorization header"},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                raise JWTError("Wrong token type")
            # Inject decoded claims into request state for downstream use
            request.state.user_id = payload.get("sub")
            request.state.workspace_id = payload.get("workspace_id")
            request.state.role = payload.get("role", "member")
        except JWTError:
            return JSONResponse(
                status_code=401,
                content={"error": "INVALID_TOKEN", "message": "Token is invalid or expired"},
            )

        return await call_next(request)