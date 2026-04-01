import hashlib
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import AuthError, ConflictError, NotFoundError
from core.security import (
    create_access_token, create_refresh_token,
    hash_password, verify_password, hash_api_key, generate_api_key,
)
from db.repos.user_repo import UserRepo
from db.models.user import UserSession
import uuid
from datetime import timedelta


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepo(db)

    async def register(self, email: str, name: str, password: str) -> dict:
        existing = await self.repo.get_by_email(email)
        if existing:
            raise ConflictError(f"Email '{email}' is already registered")

        hashed = hash_password(password)
        user = await self.repo.create(email=email, name=name, hashed_password=hashed)

        # Create a personal workspace for the new user
        slug = email.split("@")[0].lower().replace(".", "-")[:50] + f"-{str(user.id)[:8]}"
        await self.repo.create_org(name=f"{name}'s Workspace", slug=slug, owner_id=user.id)

        tokens = self._issue_tokens(user)
        return {"user": user, **tokens}

    async def login(self, email: str, password: str) -> dict:
        user = await self.repo.get_by_email(email)
        if not user or not user.hashed_password:
            raise AuthError("Invalid email or password")
        if not verify_password(password, user.hashed_password):
            raise AuthError("Invalid email or password")
        if not user.is_active:
            raise AuthError("Account is deactivated")

        await self.repo.update(user, last_login=datetime.now(timezone.utc))
        tokens = self._issue_tokens(user)
        return {"user": user, **tokens}

    async def refresh(self, refresh_token: str) -> dict:
        from jose import JWTError
        from core.security import decode_token
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise AuthError("Invalid token type")
        except JWTError:
            raise AuthError("Invalid or expired refresh token")

        user = await self.repo.get_by_id(uuid.UUID(payload["sub"]))
        if not user or not user.is_active:
            raise AuthError("User not found or inactive")

        return self._issue_tokens(user)

    async def get_user_workspaces(self, user_id: str) -> list:
        return await self.repo.get_user_orgs(uuid.UUID(user_id))

    def _issue_tokens(self, user) -> dict:
        orgs = []  # In a full implementation, fetch the user's primary org
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": None,  # Set after workspace selection
        }
        return {
            "access_token": create_access_token(payload),
            "refresh_token": create_refresh_token(payload),
            "token_type": "bearer",
        }

    async def create_api_key(self, org_id: str, user_id: str, name: str) -> dict:
        raw, hashed = generate_api_key()
        from db.models.user import APIKey
        key = APIKey(
            org_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id),
            name=name,
            key_hash=hashed,
        )
        self.db.add(key)
        await self.db.flush()
        return {"id": str(key.id), "key": raw, "name": name}  # raw shown once only