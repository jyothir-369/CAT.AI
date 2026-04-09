"""
Notification Service — in-app notifications, email dispatch, approval URL signing.
"""
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update as sa_update

from core.config import settings
from core.security import create_signed_url_token
from db.models.audit import Notification


class NotificationService:

    # ── In-app ────────────────────────────────────────────────────────────────

    async def create(
        self,
        db: AsyncSession,
        user_id: str,
        type: str,
        title: str,
        body: Optional[str] = None,
        action_url: Optional[str] = None,
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            action_url=action_url,
        )
        db.add(notif)
        await db.flush()
        return notif

    async def list_for_user(
        self,
        db: AsyncSession,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        q = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            q = q.where(Notification.read_at.is_(None))
        q = q.order_by(Notification.created_at.desc()).limit(limit)
        result = await db.execute(q)
        return list(result.scalars().all())

    async def mark_read(self, db: AsyncSession, notification_id: str, user_id: str) -> bool:
        result = await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        notif = result.scalar_one_or_none()
        if not notif:
            return False
        notif.read_at = datetime.now(timezone.utc)
        return True

    async def mark_all_read(self, db: AsyncSession, user_id: str) -> None:
        await db.execute(
            sa_update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(timezone.utc))
        )

    # ── Email ─────────────────────────────────────────────────────────────────

    def send_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        if not settings.smtp_user or not settings.smtp_password:
            print(f"[Notification] Email skipped (SMTP not configured) → {to}: {subject}")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.from_email
            msg["To"] = to
            if text_body:
                msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as srv:
                srv.ehlo()
                srv.starttls()
                srv.login(settings.smtp_user, settings.smtp_password)
                srv.sendmail(settings.from_email, to, msg.as_string())
            return True
        except Exception as exc:
            print(f"[Notification] Email failed → {to}: {exc}")
            return False

    # ── Approval URLs ─────────────────────────────────────────────────────────

    def generate_approval_urls(
        self, run_id: str, step_id: str, expires_hours: int = 24
    ) -> dict:
        approve_token = create_signed_url_token(
            {"run_id": run_id, "step_id": step_id, "action": "approve"},
            expires_hours=expires_hours,
        )
        reject_token = create_signed_url_token(
            {"run_id": run_id, "step_id": step_id, "action": "reject"},
            expires_hours=expires_hours,
        )
        base = settings.frontend_url.rstrip("/")
        return {
            "approve_url": f"{base}/approve?token={approve_token}",
            "reject_url": f"{base}/approve?token={reject_token}",
        }

    async def notify_approval_required(
        self,
        db: AsyncSession,
        approver_user_id: str,
        approver_email: str,
        workflow_name: str,
        run_id: str,
        step_id: str,
    ) -> None:
        urls = self.generate_approval_urls(run_id, step_id)

        await self.create(
            db=db,
            user_id=approver_user_id,
            type="approval_required",
            title=f"Approval required: {workflow_name}",
            body=f"Workflow '{workflow_name}' is waiting for your approval.",
            action_url=urls["approve_url"],
        )

        html = f"""
        <h2>Approval Required</h2>
        <p>Workflow <strong>{workflow_name}</strong> requires your approval to continue.</p>
        <p style="margin-top:24px">
          <a href="{urls['approve_url']}"
             style="background:#16a34a;color:white;padding:12px 24px;
                    text-decoration:none;border-radius:6px;font-weight:600;">
            Approve
          </a>
          &nbsp;&nbsp;
          <a href="{urls['reject_url']}"
             style="background:#dc2626;color:white;padding:12px 24px;
                    text-decoration:none;border-radius:6px;font-weight:600;">
            Reject
          </a>
        </p>
        <p><small>This link expires in 24 hours.</small></p>
        """
        self.send_email(
            to=approver_email,
            subject=f"[CAT AI] Approval required: {workflow_name}",
            html_body=html,
            text_body=(
                f"Approve:  {urls['approve_url']}\n"
                f"Reject:   {urls['reject_url']}\n"
                f"Expires:  24 hours"
            ),
        )

    async def notify_workflow_complete(
        self,
        db: AsyncSession,
        user_id: str,
        user_email: str,
        workflow_name: str,
        run_id: str,
        success: bool,
    ) -> None:
        status_label = "completed" if success else "failed"
        await self.create(
            db=db,
            user_id=user_id,
            type=f"workflow_{status_label}",
            title=f"Workflow {status_label}: {workflow_name}",
            body=f"Workflow '{workflow_name}' has {status_label}.",
            action_url=f"{settings.frontend_url}/workflows/runs/{run_id}",
        )
        html = f"<p>Your workflow <strong>{workflow_name}</strong> has <strong>{status_label}</strong>.</p>"
        self.send_email(
            to=user_email,
            subject=f"[CAT AI] Workflow {status_label}: {workflow_name}",
            html_body=html,
            text_body=f"Workflow '{workflow_name}' {status_label}.",
        )


notification_service = NotificationService()