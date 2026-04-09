"""
Integration tests for billing — plan limits, Stripe webhook handling.
Uses fixture payloads — no live Stripe calls.
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fixtures"))

import pytest
import pytest_asyncio
from conftest import *  # noqa: F401, F403


# ── Stripe webhook fixture payloads ───────────────────────────────────────────

CHECKOUT_COMPLETED_PAYLOAD = {
    "type": "checkout.session.completed",
    "data": {
        "object": {
            "id": "cs_test_123",
            "subscription": None,
            "customer": "cus_test_456",
            "metadata": {},  # org_id injected per test
            "mode": "subscription",
        }
    },
}

SUBSCRIPTION_UPDATED_PAYLOAD = {
    "type": "customer.subscription.updated",
    "data": {
        "object": {
            "id": "sub_test_789",
            "status": "active",
            "current_period_end": 9999999999,
            "items": {
                "data": [{"price": {"id": "price_team_stub"}}]
            },
        }
    },
}

INVOICE_PAID_PAYLOAD = {
    "type": "invoice.paid",
    "data": {
        "object": {
            "id": "inv_test_abc",
            "subscription": "sub_test_789",
            "amount_paid": 7900,
            "invoice_pdf": "https://example.com/invoice.pdf",
            "status": "paid",
        }
    },
}


@pytest.mark.asyncio
class TestPlanLimits:

    async def test_free_plan_message_limit_enforced(self, db_session, test_user):
        from services.billing_service import billing_service, PLAN_LIMITS
        from db.models.user import PlanEnum
        from core.exceptions import PlanLimitError

        # Set org to free plan
        org = test_user["org"]
        org.plan = PlanEnum.free

        # Insert usage logs to hit the daily limit
        from db.models.billing import UsageLog
        from datetime import datetime, timezone

        limit = PLAN_LIMITS[PlanEnum.free]["messages_per_day"]
        for _ in range(limit):
            db_session.add(UsageLog(
                org_id=org.id,
                user_id=test_user["user"].id,
                resource_type="chat",
                model_id="gpt-4o",
                tokens_in=10,
                tokens_out=10,
                cost_usd=0.001,
            ))
        await db_session.flush()

        with pytest.raises(PlanLimitError):
            await billing_service.check_message_limit(db_session, org)

    async def test_pro_plan_no_message_limit(self, db_session, test_user):
        from services.billing_service import billing_service
        from db.models.user import PlanEnum

        org = test_user["org"]
        org.plan = PlanEnum.pro

        # Should not raise even with many messages
        from db.models.billing import UsageLog
        for _ in range(1000):
            db_session.add(UsageLog(
                org_id=org.id,
                user_id=test_user["user"].id,
                resource_type="chat",
                model_id="gpt-4o",
                tokens_in=10,
                tokens_out=10,
                cost_usd=0.001,
            ))
        await db_session.flush()

        # Should not raise
        await billing_service.check_message_limit(db_session, org)

    async def test_free_plan_restricts_models(self):
        from services.billing_service import billing_service
        from db.models.user import PlanEnum
        from unittest.mock import MagicMock

        org = MagicMock()
        org.plan = PlanEnum.free

        assert billing_service.check_model_access(org, "gpt-4o-mini") is True
        assert billing_service.check_model_access(org, "gpt-4o") is False
        assert billing_service.check_model_access(org, "claude-3-5-sonnet-20241022") is False

    async def test_pro_plan_allows_all_models(self):
        from services.billing_service import billing_service
        from db.models.user import PlanEnum
        from unittest.mock import MagicMock

        org = MagicMock()
        org.plan = PlanEnum.pro

        assert billing_service.check_model_access(org, "gpt-4o") is True
        assert billing_service.check_model_access(org, "claude-3-5-sonnet-20241022") is True
        assert billing_service.check_model_access(org, "some-future-model") is True


@pytest.mark.asyncio
class TestStripeWebhookHandling:

    async def test_checkout_completed_creates_subscription(self, db_session, test_user):
        from services.billing_service import billing_service
        from db.models.billing import Subscription

        payload = dict(CHECKOUT_COMPLETED_PAYLOAD)
        payload["data"]["object"]["metadata"] = {"org_id": test_user["org"].id}
        payload["data"]["object"]["customer"] = "cus_integration_test"

        await billing_service._on_checkout_completed(db_session, payload["data"]["object"])

        sub = await billing_service.get_subscription(db_session, test_user["org"].id)
        assert sub is not None
        assert sub.stripe_customer_id == "cus_integration_test"

    async def test_invoice_paid_creates_invoice_record(self, db_session, test_user):
        from services.billing_service import billing_service
        from db.models.billing import Subscription, Invoice
        from sqlalchemy import select

        # Ensure subscription exists
        sub = Subscription(
            org_id=test_user["org"].id,
            stripe_subscription_id="sub_test_789",
            stripe_customer_id="cus_test_456",
            status="active",
        )
        db_session.add(sub)
        await db_session.flush()

        await billing_service._on_invoice_paid(db_session, INVOICE_PAID_PAYLOAD["data"]["object"])

        result = await db_session.execute(
            select(Invoice).where(Invoice.stripe_invoice_id == "inv_test_abc")
        )
        invoice = result.scalar_one_or_none()
        assert invoice is not None
        assert invoice.amount_usd == 79.0
        assert invoice.status == "paid"

    async def test_invoice_paid_idempotent(self, db_session, test_user):
        """Processing the same invoice twice should not create duplicates."""
        from services.billing_service import billing_service
        from db.models.billing import Subscription, Invoice
        from sqlalchemy import select, func

        sub = Subscription(
            org_id=test_user["org"].id,
            stripe_subscription_id="sub_test_idem",
            status="active",
        )
        db_session.add(sub)

        inv_payload = dict(INVOICE_PAID_PAYLOAD["data"]["object"])
        inv_payload["id"] = "inv_idempotent_test"
        inv_payload["subscription"] = "sub_test_idem"

        await db_session.flush()

        await billing_service._on_invoice_paid(db_session, inv_payload)
        await billing_service._on_invoice_paid(db_session, inv_payload)  # second call

        result = await db_session.execute(
            select(func.count(Invoice.id)).where(Invoice.stripe_invoice_id == "inv_idempotent_test")
        )
        count = result.scalar()
        assert count == 1  # only one record created


@pytest.mark.asyncio
class TestUsageSummary:

    async def test_usage_summary_empty(self, db_session, test_user):
        from services.billing_service import billing_service

        summary = await billing_service.get_usage_summary(db_session, test_user["org"].id)
        assert summary["total_requests"] == 0
        assert summary["total_cost_usd"] == 0.0

    async def test_usage_summary_aggregates_correctly(self, db_session, test_user):
        from services.billing_service import billing_service
        from db.models.billing import UsageLog

        db_session.add(UsageLog(
            org_id=test_user["org"].id,
            user_id=test_user["user"].id,
            resource_type="chat",
            model_id="gpt-4o",
            tokens_in=100,
            tokens_out=200,
            cost_usd=0.005,
        ))
        db_session.add(UsageLog(
            org_id=test_user["org"].id,
            user_id=test_user["user"].id,
            resource_type="chat",
            model_id="gpt-4o",
            tokens_in=50,
            tokens_out=100,
            cost_usd=0.002,
        ))
        await db_session.flush()

        summary = await billing_service.get_usage_summary(db_session, test_user["org"].id)
        assert summary["total_requests"] == 2
        assert summary["total_tokens_in"] == 150
        assert summary["total_tokens_out"] == 300
        assert abs(summary["total_cost_usd"] - 0.007) < 0.0001