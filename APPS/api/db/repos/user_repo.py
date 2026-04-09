"""
User repository — data access for users, organizations, memberships.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User, Organization, Membership, RoleEnum


class UserRepo:

    async def get_by_id(self, db: AsyncSession, user_id: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        email: str,
        name: str,
        hashed_password: Optional[str] = None,
    ) -> User:
        user = User(email=email, name=name, hashed_password=hashed_password)
        db.add(user)
        await db.flush()
        return user

    async def get_memberships(self, db: AsyncSession, user_id: str) -> list[Membership]:
        result = await db.execute(
            select(Membership).where(Membership.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_membership(
        self, db: AsyncSession, user_id: str, org_id: str
    ) -> Optional[Membership]:
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()


class OrgRepo:

    async def get_by_id(self, db: AsyncSession, org_id: str) -> Optional[Organization]:
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, db: AsyncSession, slug: str) -> Optional[Organization]:
        result = await db.execute(select(Organization).where(Organization.slug == slug))
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        name: str,
        slug: str,
        owner_id: str,
    ) -> Organization:
        org = Organization(name=name, slug=slug, owner_id=owner_id)
        db.add(org)
        await db.flush()
        return org

    async def add_member(
        self,
        db: AsyncSession,
        user_id: str,
        org_id: str,
        role: RoleEnum = RoleEnum.member,
    ) -> Membership:
        membership = Membership(user_id=user_id, org_id=org_id, role=role)
        db.add(membership)
        await db.flush()
        return membership

    async def list_members(self, db: AsyncSession, org_id: str) -> list[Membership]:
        result = await db.execute(
            select(Membership).where(Membership.org_id == org_id)
        )
        return list(result.scalars().all())


user_repo = UserRepo()
org_repo = OrgRepo()