from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.exceptions import AuthError, InvalidTokenError, to_http_exception
from core.security import decode_token
from db.session import get_db


# ── Database ──────────────────────────────────────────────────────────────────

DBSession = Annotated[AsyncSession, Depends(get_db)]


# ── Auth ──────────────────────────────────────────────────────────────────────

async def get_current_user_payload(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """Validates Bearer token and returns the decoded JWT payload."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "AUTH_ERROR", "message": "Missing or invalid Authorization header"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise InvalidTokenError()
        return payload
    except JWTError:
        raise to_http_exception(InvalidTokenError())


CurrentUser = Annotated[dict, Depends(get_current_user_payload)]


def require_role(*roles: str):
    """Factory for role-checking dependencies."""
    async def _check(payload: CurrentUser) -> dict:
        if payload.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "FORBIDDEN", "message": "Insufficient role"},
            )
        return payload
    return Depends(_check)


def get_workspace_id(payload: CurrentUser) -> str:
    """Extracts workspace_id from JWT claims."""
    workspace_id = payload.get("workspace_id")
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "MISSING_WORKSPACE", "message": "No workspace in token"},
        )
    return workspace_id


WorkspaceID = Annotated[str, Depends(get_workspace_id)]


def get_user_id(payload: CurrentUser) -> str:
    return payload["sub"]


UserID = Annotated[str, Depends(get_user_id)]