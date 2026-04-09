"""
Usage routes — summary stats · per-model breakdown · daily usage
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user, get_current_org, get_db
from db.models.user import User, Organization
from db.models.billing import UsageLog

router = APIRouter(prefix="/usage", tags=["usage"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class UsageSummaryOut(BaseModel):
    org_id: str
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    total_requests: int
    total_tokens_in: int
    total_tokens_out: int
    total_tokens: int
    total_cost_usd: float


class ModelBreakdownItem(BaseModel):
    model_id: str
    requests: int
    tokens_in: int
    tokens_out: int
    cost_usd: float


class DailyUsageItem(BaseModel):
    date: str
    requests: int
    tokens_in: int
    tokens_out: int
    cost_usd: float


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=UsageSummaryOut)
async def get_usage_summary(
    days: int = Query(default=30, ge=1, le=365, description="Number of past days to include"),
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)

    result = await db.execute(
        select(
            func.count(UsageLog.id).label("requests"),
            func.coalesce(func.sum(UsageLog.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(UsageLog.tokens_out), 0).label("tokens_out"),
            func.coalesce(func.sum(UsageLog.cost_usd), 0.0).label("cost_usd"),
        ).where(
            UsageLog.org_id == current_org.id,
            UsageLog.created_at >= period_start,
        )
    )
    row = result.one()

    return UsageSummaryOut(
        org_id=current_org.id,
        period_start=period_start,
        period_end=now,
        total_requests=row.requests or 0,
        total_tokens_in=row.tokens_in or 0,
        total_tokens_out=row.tokens_out or 0,
        total_tokens=(row.tokens_in or 0) + (row.tokens_out or 0),
        total_cost_usd=round(float(row.cost_usd or 0), 6),
    )


@router.get("/models", response_model=list[ModelBreakdownItem])
async def get_model_breakdown(
    days: int = Query(default=30, ge=1, le=365),
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Per-model token and cost breakdown."""
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)

    result = await db.execute(
        select(
            UsageLog.model_id,
            func.count(UsageLog.id).label("requests"),
            func.coalesce(func.sum(UsageLog.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(UsageLog.tokens_out), 0).label("tokens_out"),
            func.coalesce(func.sum(UsageLog.cost_usd), 0.0).label("cost_usd"),
        )
        .where(
            UsageLog.org_id == current_org.id,
            UsageLog.created_at >= period_start,
        )
        .group_by(UsageLog.model_id)
        .order_by(func.sum(UsageLog.cost_usd).desc())
    )
    rows = result.all()

    return [
        ModelBreakdownItem(
            model_id=row.model_id or "unknown",
            requests=row.requests or 0,
            tokens_in=row.tokens_in or 0,
            tokens_out=row.tokens_out or 0,
            cost_usd=round(float(row.cost_usd or 0), 6),
        )
        for row in rows
    ]


@router.get("/daily", response_model=list[DailyUsageItem])
async def get_daily_usage(
    days: int = Query(default=30, ge=1, le=90),
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Daily usage rollup for charts."""
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)

    result = await db.execute(
        select(
            func.date(UsageLog.created_at).label("day"),
            func.count(UsageLog.id).label("requests"),
            func.coalesce(func.sum(UsageLog.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(UsageLog.tokens_out), 0).label("tokens_out"),
            func.coalesce(func.sum(UsageLog.cost_usd), 0.0).label("cost_usd"),
        )
        .where(
            UsageLog.org_id == current_org.id,
            UsageLog.created_at >= period_start,
        )
        .group_by(func.date(UsageLog.created_at))
        .order_by(func.date(UsageLog.created_at).asc())
    )
    rows = result.all()

    return [
        DailyUsageItem(
            date=str(row.day),
            requests=row.requests or 0,
            tokens_in=row.tokens_in or 0,
            tokens_out=row.tokens_out or 0,
            cost_usd=round(float(row.cost_usd or 0), 6),
        )
        for row in rows
    ]