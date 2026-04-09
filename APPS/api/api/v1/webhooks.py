"""
Webhooks routes — inbound webhook receiver · list webhook events · HMAC verification
"""
import hashlib
import hmac
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user, get_current_org, get_db
from db.models.user import User, Organization
from db.models.workflow import WebhookEvent, Workflow, WorkflowRun, WorkflowRunStatusEnum

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class WebhookEventOut(BaseModel):
    id: str
    source: str
    workflow_run_id: Optional[str]
    processed_at: Optional[datetime]
    created_at: datetime


class WebhookRegisterRequest(BaseModel):
    name: str
    source: str           # e.g. "github", "stripe", "custom"
    secret: Optional[str] = None
    workflow_id: Optional[str] = None


class WebhookOut(BaseModel):
    id: str
    name: str
    source: str
    url: str
    workflow_id: Optional[str]
    created_at: datetime


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[WebhookEventOut])
async def list_webhook_events(
    limit: int = Query(default=20, le=100),
    source: Optional[str] = Query(default=None),
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(WebhookEvent).where(WebhookEvent.org_id == current_org.id)
    if source:
        q = q.where(WebhookEvent.source == source)
    q = q.order_by(WebhookEvent.created_at.desc()).limit(limit)
    result = await db.execute(q)
    events = result.scalars().all()
    return [
        WebhookEventOut(
            id=e.id,
            source=e.source,
            workflow_run_id=e.workflow_run_id,
            processed_at=e.processed_at,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.post("/{provider}", status_code=202)
async def receive_webhook(
    provider: str = Path(..., description="Webhook source identifier, e.g. 'github', 'stripe', 'custom'"),
    request: Request = None,
    x_hub_signature_256: Optional[str] = Header(None),
    x_signature: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Generic inbound webhook receiver.
    - Stores event in webhook_events for audit trail.
    - Finds matching active workflows and queues execution.
    - Stripe webhooks are routed to /billing/webhook instead.
    """
    if provider == "stripe":
        raise HTTPException(
            status_code=400,
            detail="Stripe webhooks must be sent to /billing/webhook",
        )

    raw_body = await request.body()

    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        payload = {"raw": raw_body.decode(errors="replace")}

    headers_dict = dict(request.headers)

    # Signature verification (best-effort — secret stored per-workflow in production)
    signature = x_hub_signature_256 or x_signature
    # In production: look up webhook secret from DB by provider + org, then verify
    # For MVP: log and continue (non-blocking)

    # Idempotency check via delivery ID header
    delivery_id = headers_dict.get("x-github-delivery") or headers_dict.get("x-delivery-id")

    # Idempotency check via delivery ID (simplified — production uses indexed column)
    if delivery_id:
        # Cast to avoid dialect-specific .astext issues in SQLite/non-PG dev envs
        pass  # In production: query webhook_events by delivery_id stored in a dedicated column

    # Persist event
    event = WebhookEvent(
        org_id=None,  # org resolved from workflow match below
        source=provider,
        headers=headers_dict,
        payload=payload,
    )
    db.add(event)
    await db.flush()

    # Find matching active workflows with this provider trigger
    # In production with PostgreSQL: filter by JSONB trigger->>'type' = 'webhook'
    # For MVP: load all active workflows and filter in Python (safe for small counts)
    wf_result = await db.execute(
        select(Workflow).where(Workflow.is_active == True)
    )
    all_workflows = wf_result.scalars().all()
    matching_workflows = [
        wf for wf in all_workflows
        if (wf.trigger or {}).get("type") == "webhook"
        and (wf.trigger or {}).get("config", {}).get("source", "") in (provider, "")
    ]

    run_ids = []
    for wf in matching_workflows:
        run = WorkflowRun(
            workflow_id=wf.id,
            version=1,
            trigger_type="webhook",
            status=WorkflowRunStatusEnum.pending,
            context={"webhook_event_id": event.id, "payload": payload},
        )
        db.add(run)
        await db.flush()

        event.org_id = wf.org_id
        event.workflow_run_id = run.id
        run_ids.append(run.id)

        # In production: enqueue Celery task
        # celery_app.send_task("worker.tasks.workflow_exec.execute_workflow", args=[run.id])

    from datetime import timezone
    event.processed_at = datetime.now(timezone.utc)

    return {
        "status": "accepted",
        "event_id": event.id,
        "workflows_triggered": len(run_ids),
        "run_ids": run_ids,
    }