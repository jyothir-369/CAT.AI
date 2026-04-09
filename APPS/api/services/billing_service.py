"""
Billing Service — Stripe integration, plan enforcement, usage metering.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.config import settings
from core.exceptions import AppError, NotFoundError, PlanLimitError
from db.models.user import Organization, PlanEnum
from db.models.billing import Subscription, Invoice, UsageLog

# Stripe is optional — guard import so app boots without the key configured
try:
    import stripe
    stripe.api_key = settings.stripe_secret_key
    _STRIPE_AVAILABLE = bool(settings.stripe_secret_key)
except ImportError:
    stripe = None  # type: ignore
    _STRIPE_AVAILABLE = False


PLAN_LIMITS: dict[PlanEnum, dict] = {
    PlanEnum.free: {
        "messages_per_day": 50,
        "storage_bytes": 10 * 1024 * 1024,
        "workspaces": 1,
        "models": ["gpt-4o-mini", "gpt-3.5-turbo", "llama-3.1-70b-versatile"],
    },
    PlanEnum.pro: {
        "messages_per_day": -1,
        "storage_bytes": 5 * 1024 * 1024 * 1024,
        "workspaces": 1,
        "models": None,  # all models
    },
    PlanEnum.team: {
        "messages_per_day": -1,
        "storage_bytes": 50 * 1024 * 1024 * 1024,
        "workspaces": 5,
        "models": None,
    },
    PlanEnum.enterprise: {
        "messages_per_day": -1,
        "storage_bytes": -1,
        "workspaces": -1,
        "models": None,
    },
}


class BillingService:

    def get_plan_limits(self, plan: PlanEnum) -> dict:
        return PLAN_LIMITS.get(plan, PLAN_LIMITS[PlanEnum.free])

    async def check_message_limit(self, db: AsyncSession, org: Organization) -> None:
        limits = self.get_plan_limits(org.plan)
        daily_limit = limits["messages_per_day"]
        if daily_limit == -1:
            return

        today = datetime.now(timezone.utc).date()
        result = await db.execute(
            select(func.count(UsageLog.id)).where(
                UsageLog.org_id == org.id,
                UsageLog.resource_type == "chat",
                func.date(UsageLog.created_at) == today,
            )
        )
        count = result.scalar() or 0
        if count >= daily_limit:
            raise PlanLimitError(
                f"Daily message limit ({daily_limit}) reached. Upgrade your plan to continue."
            )

    def check_model_access(self, org: Organization, model_id: str) -> bool:
        limits = self.get_plan_limits(org.plan)
        allowed = limits.get("models")
        if allowed is None:
            return True
        return model_id in allowed

    async def get_subscription(self, db: AsyncSession, org_id: str) -> Optional[Subscription]:
        result = await db.execute(
            select(Subscription).where(Subscription.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_subscription(self, db: AsyncSession, org_id: str) -> Subscription:
        sub = await self.get_subscription(db, org_id)
        if not sub:
            sub = Subscription(org_id=org_id, plan=PlanEnum.free, status="active")
            db.add(sub)
            await db.flush()
        return sub

    # ── Stripe ────────────────────────────────────────────────────────────────

    async def create_checkout_session(
        self,
        db: AsyncSession,
        org: Organization,
        price_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        if not _STRIPE_AVAILABLE:
            raise AppError("Stripe is not configured on this server", 503)

        sub = await self.get_subscription(db, org.id)
        customer_id = sub.stripe_customer_id if sub else None

        kwargs: dict = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {"org_id": org.id},
        }
        if customer_id:
            kwargs["customer"] = customer_id

        session = stripe.checkout.Session.create(**kwargs)
        return session.url

    async def create_portal_session(
        self, db: AsyncSession, org_id: str, return_url: str
    ) -> str:
        if not _STRIPE_AVAILABLE:
            raise AppError("Stripe is not configured on this server", 503)

        sub = await self.get_subscription(db, org_id)
        if not sub or not sub.stripe_customer_id:
            raise NotFoundError("Billing customer")

        portal = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=return_url,
        )
        return portal.url

    async def handle_stripe_webhook(
        self, db: AsyncSession, payload: bytes, sig_header: str
    ) -> dict:
        if not _STRIPE_AVAILABLE:
            raise AppError("Stripe is not configured", 503)

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        except stripe.error.SignatureVerificationError:
            raise AppError("Invalid Stripe webhook signature", 400)

        event_type = event["type"]
        data = event["data"]["object"]

        handlers = {
            "checkout.session.completed": self._on_checkout_completed,
            "customer.subscription.updated": self._on_subscription_updated,
            "customer.subscription.created": self._on_subscription_updated,
            "customer.subscription.deleted": self._on_subscription_deleted,
            "invoice.paid": self._on_invoice_paid,
        }

        handler = handlers.get(event_type)
        if handler:
            await handler(db, data)

        return {"received": True, "event": event_type}

    async def _on_checkout_completed(self, db: AsyncSession, session: dict):
        org_id = (session.get("metadata") or {}).get("org_id")
        if not org_id:
            return

        stripe_sub_id = session.get("subscription")
        customer_id = session.get("customer")
        plan = PlanEnum.pro

        if stripe_sub_id:
            stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
            plan = self._plan_from_stripe_sub(stripe_sub)

        sub = await self.get_subscription(db, org_id)
        if sub:
            sub.stripe_subscription_id = stripe_sub_id
            sub.stripe_customer_id = customer_id
            sub.plan = plan
            sub.status = "active"
        else:
            db.add(Subscription(
                org_id=org_id,
                stripe_subscription_id=stripe_sub_id,
                stripe_customer_id=customer_id,
                plan=plan,
                status="active",
            ))

        org_result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = org_result.scalar_one_or_none()
        if org:
            org.plan = plan

    async def _on_subscription_updated(self, db: AsyncSession, subscription: dict):
        stripe_sub_id = subscription.get("id")
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
        )
        sub = result.scalar_one_or_none()
        if not sub:
            return

        plan = self._plan_from_stripe_sub(subscription)
        sub.plan = plan
        sub.status = subscription.get("status", "active")

        ts = subscription.get("current_period_end")
        if ts:
            sub.current_period_end = datetime.fromtimestamp(ts, tz=timezone.utc)

        org_result = await db.execute(select(Organization).where(Organization.id == sub.org_id))
        org = org_result.scalar_one_or_none()
        if org:
            org.plan = plan

    async def _on_subscription_deleted(self, db: AsyncSession, subscription: dict):
        stripe_sub_id = subscription.get("id")
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
        )
        sub = result.scalar_one_or_none()
        if not sub:
            return
        sub.plan = PlanEnum.free
        sub.status = "cancelled"
        org_result = await db.execute(select(Organization).where(Organization.id == sub.org_id))
        org = org_result.scalar_one_or_none()
        if org:
            org.plan = PlanEnum.free

    async def _on_invoice_paid(self, db: AsyncSession, invoice: dict):
        stripe_sub_id = invoice.get("subscription")
        if not stripe_sub_id:
            return
        sub_result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
        )
        sub = sub_result.scalar_one_or_none()
        if not sub:
            return
        existing = await db.execute(
            select(Invoice).where(Invoice.stripe_invoice_id == invoice.get("id"))
        )
        if existing.scalar_one_or_none():
            return  # idempotent
        db.add(Invoice(
            org_id=sub.org_id,
            stripe_invoice_id=invoice.get("id"),
            amount_usd=(invoice.get("amount_paid") or 0) / 100,
            status="paid",
            pdf_url=invoice.get("invoice_pdf"),
            paid_at=datetime.now(timezone.utc),
        ))

    def _plan_from_stripe_sub(self, subscription: dict) -> PlanEnum:
        items = (subscription.get("items") or {}).get("data", [])
        if not items:
            return PlanEnum.pro
        price_id = (items[0].get("price") or {}).get("id", "")
        if price_id == settings.stripe_team_price_id:
            return PlanEnum.team
        if price_id == settings.stripe_pro_price_id:
            return PlanEnum.pro
        return PlanEnum.pro

    # ── Usage ─────────────────────────────────────────────────────────────────

    async def get_usage_summary(self, db: AsyncSession, org_id: str) -> dict:
        result = await db.execute(
            select(
                func.sum(UsageLog.tokens_in).label("tokens_in"),
                func.sum(UsageLog.tokens_out).label("tokens_out"),
                func.sum(UsageLog.cost_usd).label("cost_usd"),
                func.count(UsageLog.id).label("requests"),
            ).where(UsageLog.org_id == org_id)
        )
        row = result.one()
        return {
            "total_tokens_in": row.tokens_in or 0,
            "total_tokens_out": row.tokens_out or 0,
            "total_cost_usd": round(row.cost_usd or 0.0, 6),
            "total_requests": row.requests or 0,
        }


billing_service = BillingService()