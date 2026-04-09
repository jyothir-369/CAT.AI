"""
Billing routes — Stripe checkout · customer portal · webhook handler · plan info
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.deps import get_current_user, get_current_org, get_db
from core.exceptions import AppError
from db.models.user import User, Organization, PlanEnum
from db.models.billing import Subscription, Invoice
from services.billing_service import billing_service, PLAN_LIMITS

router = APIRouter(prefix="/billing", tags=["billing"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan: str   # "pro" | "team"
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class PortalRequest(BaseModel):
    return_url: Optional[str] = None


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class SubscriptionOut(BaseModel):
    plan: str
    status: str
    current_period_end: Optional[datetime]
    stripe_customer_id: Optional[str]


class PlanLimitsOut(BaseModel):
    plan: str
    messages_per_day: int
    storage_bytes: int
    workspaces: int
    models: Optional[list[str]]


class InvoiceOut(BaseModel):
    id: str
    amount_usd: float
    status: str
    pdf_url: Optional[str]
    paid_at: Optional[datetime]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/subscription", response_model=SubscriptionOut)
async def get_subscription(
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await billing_service.get_or_create_subscription(db, current_org.id)
    return SubscriptionOut(
        plan=sub.plan.value if hasattr(sub.plan, "value") else str(sub.plan),
        status=sub.status,
        current_period_end=sub.current_period_end,
        stripe_customer_id=sub.stripe_customer_id,
    )


@router.get("/plans", response_model=list[PlanLimitsOut])
async def list_plans():
    """Return all plan limits — no auth required (public pricing page data)."""
    return [
        PlanLimitsOut(
            plan=plan.value,
            messages_per_day=limits["messages_per_day"],
            storage_bytes=limits["storage_bytes"],
            workspaces=limits["workspaces"],
            models=limits.get("models"),
        )
        for plan, limits in PLAN_LIMITS.items()
    ]


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    plan_map = {
        "pro": settings.stripe_pro_price_id,
        "team": settings.stripe_team_price_id,
    }
    price_id = plan_map.get(body.plan.lower())
    if not price_id:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown plan '{body.plan}'. Valid options: {list(plan_map.keys())}",
        )

    success_url = body.success_url or f"{settings.frontend_url}/settings/billing?success=1"
    cancel_url = body.cancel_url or f"{settings.frontend_url}/settings/billing?cancelled=1"

    try:
        checkout_url = await billing_service.create_checkout_session(
            db, current_org, price_id, success_url, cancel_url
        )
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    body: PortalRequest,
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return_url = body.return_url or f"{settings.frontend_url}/settings/billing"
    try:
        portal_url = await billing_service.create_portal_session(db, current_org.id, return_url)
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return PortalResponse(portal_url=portal_url)


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Stripe webhook receiver.
    Stripe signs every request — we verify via stripe-signature header.
    This endpoint is intentionally excluded from the OpenAPI docs.
    """
    raw_body = await request.body()

    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        result = await billing_service.handle_stripe_webhook(
            db, payload=raw_body, sig_header=stripe_signature
        )
    except AppError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return result


@router.get("/invoices", response_model=list[InvoiceOut])
async def list_invoices(
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    result = await db.execute(
        select(Invoice)
        .where(Invoice.org_id == current_org.id)
        .order_by(Invoice.paid_at.desc().nulls_last())
        .limit(24)
    )
    invoices = result.scalars().all()
    return [
        InvoiceOut(
            id=inv.id,
            amount_usd=inv.amount_usd or 0.0,
            status=inv.status,
            pdf_url=inv.pdf_url,
            paid_at=inv.paid_at,
        )
        for inv in invoices
    ]