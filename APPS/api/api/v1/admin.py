"""
Admin routes — platform-wide metrics · user management · audit logs
All routes require superadmin or org-admin role.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user, get_db, require_superadmin
from db.models.user import User, Organization, Membership, PlanEnum
from db.models.conversation import Conversation
from db.models.billing import UsageLog
from db.models.audit import AuditLog

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class UserAdminOut(BaseModel):
    id: str
    email: str
    name: str
    is_active: bool
    is_superadmin: bool
    created_at: datetime
    last_login: Optional[datetime]


class OrgAdminOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    member_count: int
    created_at: datetime


class PlatformMetrics(BaseModel):
    total_users: int
    active_users_30d: int
    total_orgs: int
    total_conversations: int
    total_requests_30d: int
    total_tokens_30d: int
    total_cost_usd_30d: float


class AuditLogOut(BaseModel):
    id: str
    org_id: Optional[str]
    user_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    ip_address: Optional[str]
    created_at: datetime


class UserStatusUpdate(BaseModel):
    is_active: bool


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/metrics", response_model=PlatformMetrics)
async def get_platform_metrics(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Platform-wide aggregate metrics for the ops dashboard."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

    active_users_30d = (
        await db.execute(
            select(func.count(User.id)).where(User.last_login >= thirty_days_ago)
        )
    ).scalar() or 0

    total_orgs = (await db.execute(select(func.count(Organization.id)))).scalar() or 0

    total_conversations = (
        await db.execute(select(func.count(Conversation.id)))
    ).scalar() or 0

    usage_result = await db.execute(
        select(
            func.count(UsageLog.id).label("requests"),
            func.coalesce(func.sum(UsageLog.tokens_in + UsageLog.tokens_out), 0).label("tokens"),
            func.coalesce(func.sum(UsageLog.cost_usd), 0.0).label("cost"),
        ).where(UsageLog.created_at >= thirty_days_ago)
    )
    usage_row = usage_result.one()

    return PlatformMetrics(
        total_users=total_users,
        active_users_30d=active_users_30d,
        total_orgs=total_orgs,
        total_conversations=total_conversations,
        total_requests_30d=usage_row.requests or 0,
        total_tokens_30d=usage_row.tokens or 0,
        total_cost_usd_30d=round(float(usage_row.cost or 0), 4),
    )


@router.get("/users", response_model=list[UserAdminOut])
async def list_all_users(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(default=None),
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    q = select(User)
    if search:
        q = q.where(
            User.email.ilike(f"%{search}%") | User.name.ilike(f"%{search}%")
        )
    q = q.order_by(User.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    users = result.scalars().all()
    return [_user_admin_out(u) for u in users]


@router.get("/users/{user_id}", response_model=UserAdminOut)
async def get_user(
    user_id: str,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_admin_out(user)


@router.patch("/users/{user_id}/status", response_model=UserAdminOut)
async def update_user_status(
    user_id: str,
    body: UserStatusUpdate,
    current_admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own active status")

    user.is_active = body.is_active

    # Write audit log
    db.add(AuditLog(
        org_id=None,
        user_id=current_admin.id,
        action="admin.user.status_change",
        resource_type="user",
        resource_id=user_id,
        metadata_={"is_active": body.is_active},
    ))

    return _user_admin_out(user)


@router.get("/orgs", response_model=list[OrgAdminOut])
async def list_all_orgs(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    plan: Optional[str] = Query(default=None),
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    q = select(Organization)
    if plan:
        try:
            q = q.where(Organization.plan == PlanEnum(plan))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid plan: {plan}")
    q = q.order_by(Organization.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    orgs = result.scalars().all()

    # Get member counts in one query
    counts_result = await db.execute(
        select(Membership.org_id, func.count(Membership.id).label("count"))
        .where(Membership.org_id.in_([o.id for o in orgs]))
        .group_by(Membership.org_id)
    )
    member_counts = {row.org_id: row.count for row in counts_result.all()}

    return [
        OrgAdminOut(
            id=o.id,
            name=o.name,
            slug=o.slug,
            plan=o.plan.value if hasattr(o.plan, "value") else str(o.plan),
            member_count=member_counts.get(o.id, 0),
            created_at=o.created_at,
        )
        for o in orgs
    ]


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def get_audit_logs(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    action: Optional[str] = Query(default=None),
    org_id: Optional[str] = Query(default=None),
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog)
    if action:
        q = q.where(AuditLog.action.ilike(f"%{action}%"))
    if org_id:
        q = q.where(AuditLog.org_id == org_id)
    q = q.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    logs = result.scalars().all()
    return [
        AuditLogOut(
            id=log.id,
            org_id=log.org_id,
            user_id=log.user_id,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log in logs
    ]


# ── Health check (public) ─────────────────────────────────────────────────────

@router.get("/health", include_in_schema=True, tags=["health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Liveness probe — checks DB connectivity."""
    try:
        await db.execute(select(func.now()))
        db_ok = True
    except Exception:
        db_ok = False

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "db": "ok" if db_ok else "error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_admin_out(u: User) -> UserAdminOut:
    return UserAdminOut(
        id=u.id,
        email=u.email,
        name=u.name,
        is_active=u.is_active,
        is_superadmin=u.is_superadmin,
        created_at=u.created_at,
        last_login=u.last_login,
    )