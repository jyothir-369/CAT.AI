"""
Notification tasks — async email dispatch, in-app notification writes.
These run in the background so they don't block HTTP responses.
"""
import asyncio
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

from celery_app import celery_app


@celery_app.task(
    name="tasks.notifications.send_email_async",
    queue="notifications",
    max_retries=3,
    default_retry_delay=30,
)
def send_email_async(
    to: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
):
    """Fire-and-forget email task."""
    from services.notification_service import notification_service
    success = notification_service.send_email(
        to=to,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )
    if not success:
        raise Exception(f"Email delivery failed to {to}")


@celery_app.task(
    name="tasks.notifications.notify_approval_required",
    queue="notifications",
    max_retries=2,
    default_retry_delay=15,
)
def notify_approval_required(
    approver_user_id: str,
    approver_email: str,
    workflow_name: str,
    run_id: str,
    step_id: str,
):
    asyncio.run(
        _notify_approval_async(
            approver_user_id, approver_email, workflow_name, run_id, step_id
        )
    )


async def _notify_approval_async(
    approver_user_id: str,
    approver_email: str,
    workflow_name: str,
    run_id: str,
    step_id: str,
):
    from db.session import AsyncSessionLocal
    from services.notification_service import notification_service

    async with AsyncSessionLocal() as db:
        await notification_service.notify_approval_required(
            db=db,
            approver_user_id=approver_user_id,
            approver_email=approver_email,
            workflow_name=workflow_name,
            run_id=run_id,
            step_id=step_id,
        )
        await db.commit()


@celery_app.task(
    name="tasks.notifications.notify_workflow_complete",
    queue="notifications",
    max_retries=2,
    default_retry_delay=15,
)
def notify_workflow_complete(
    user_id: str,
    user_email: str,
    workflow_name: str,
    run_id: str,
    success: bool,
):
    asyncio.run(
        _notify_workflow_complete_async(user_id, user_email, workflow_name, run_id, success)
    )


async def _notify_workflow_complete_async(
    user_id: str,
    user_email: str,
    workflow_name: str,
    run_id: str,
    success: bool,
):
    from db.session import AsyncSessionLocal
    from services.notification_service import notification_service

    async with AsyncSessionLocal() as db:
        await notification_service.notify_workflow_complete(
            db=db,
            user_id=user_id,
            user_email=user_email,
            workflow_name=workflow_name,
            run_id=run_id,
            success=success,
        )
        await db.commit()


@celery_app.task(
    name="tasks.notifications.create_in_app",
    queue="notifications",
    max_retries=2,
)
def create_in_app_notification(
    user_id: str,
    type: str,
    title: str,
    body: Optional[str] = None,
    action_url: Optional[str] = None,
):
    asyncio.run(_create_in_app_async(user_id, type, title, body, action_url))


async def _create_in_app_async(
    user_id: str,
    type: str,
    title: str,
    body: Optional[str],
    action_url: Optional[str],
):
    from db.session import AsyncSessionLocal
    from services.notification_service import notification_service

    async with AsyncSessionLocal() as db:
        await notification_service.create(
            db=db,
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            action_url=action_url,
        )
        await db.commit()