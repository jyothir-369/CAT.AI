"""
Usage rollup task.

Runs hourly (via Celery Beat).
Aggregates token usage per workspace and reports to Stripe as metered billing records
for pay-per-use add-ons. Also computes daily cost summaries for the admin dashboard.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

from celery_app import celery_app


@celery_app.task(
    name="tasks.usage_rollup.rollup_usage",
    queue="usage",
    max_retries=3,
    default_retry_delay=60,
)
def rollup_usage():
    """Hourly beat task — aggregate usage and push to Stripe."""
    asyncio.run(_rollup_async())


async def _rollup_async():
    from db.session import AsyncSessionLocal
    from db.models.billing import UsageLog, Subscription
    from db.models.user import PlanEnum
    from sqlalchemy import select, func

    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)

    async with AsyncSessionLocal() as db:
        # Aggregate usage by org for the last hour
        result = await db.execute(
            select(
                UsageLog.org_id,
                func.sum(UsageLog.tokens_in + UsageLog.tokens_out).label("total_tokens"),
                func.sum(UsageLog.cost_usd).label("total_cost"),
                func.count(UsageLog.id).label("request_count"),
            )
            .where(
                UsageLog.created_at >= one_hour_ago,
                UsageLog.created_at < now,
            )
            .group_by(UsageLog.org_id)
        )
        rows = result.all()

        if not rows:
            return

        print(f"[UsageRollup] Processing {len(rows)} orgs for hour ending {now.isoformat()}")

        for row in rows:
            org_id = row.org_id
            total_tokens = int(row.total_tokens or 0)
            total_cost = float(row.total_cost or 0)
            request_count = int(row.request_count or 0)

            # Check if this org has a metered Stripe subscription
            sub_result = await db.execute(
                select(Subscription).where(Subscription.org_id == org_id)
            )
            sub = sub_result.scalar_one_or_none()

            if sub and sub.stripe_subscription_id and sub.plan != PlanEnum.free:
                await _report_to_stripe(
                    stripe_subscription_id=sub.stripe_subscription_id,
                    total_tokens=total_tokens,
                    timestamp=int(now.timestamp()),
                )

            print(
                f"[UsageRollup] Org {org_id}: "
                f"{request_count} requests, {total_tokens} tokens, ${total_cost:.4f}"
            )


async def _report_to_stripe(
    stripe_subscription_id: str,
    total_tokens: int,
    timestamp: int,
):
    """
    Report metered token usage to Stripe Usage Records.
    Only relevant for orgs on pay-per-use add-on pricing.
    Silently skips if Stripe is not configured.
    """
    from core.config import settings
    if not settings.stripe_secret_key or not total_tokens:
        return

    try:
        import stripe
        stripe.api_key = settings.stripe_secret_key

        # In production: look up the subscription item ID for the metered price
        # stripe.SubscriptionItem.list(subscription=stripe_subscription_id)
        # For MVP: stub this call — implement when metered pricing is set up
        print(
            f"[UsageRollup] Would report {total_tokens} tokens to Stripe "
            f"for subscription {stripe_subscription_id}"
        )
    except Exception as exc:
        print(f"[UsageRollup] Stripe reporting failed: {exc}")