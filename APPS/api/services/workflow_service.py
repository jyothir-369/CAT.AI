from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from db.repos.workflow_repo import WorkflowRepo
from core.exceptions import NotFoundError
from core.security import create_signed_approval_token


class WorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WorkflowRepo(db)

    async def list(self, org_id: str) -> list:
        return await self.repo.list_by_org(UUID(org_id))

    async def create(self, org_id: str, user_id: str, name: str, trigger: dict, description: str | None = None):
        wf = await self.repo.create(
            org_id=UUID(org_id),
            name=name,
            trigger=trigger,
            created_by=UUID(user_id),
            description=description,
        )
        # Create initial version with empty definition
        await self.repo.create_version(wf.id, version=1, definition={"steps": [], "edges": []})
        return wf

    async def get(self, org_id: str, workflow_id: str):
        wf = await self.repo.get(UUID(workflow_id), UUID(org_id))
        if not wf:
            raise NotFoundError("Workflow", workflow_id)
        return wf

    async def trigger_run(self, org_id: str, workflow_id: str, trigger_type: str = "manual", context: dict | None = None):
        wf = await self.get(org_id, workflow_id)
        version = await self.repo.latest_version(wf.id)
        v_num = version.version if version else 1
        run = await self.repo.create_run(
            workflow_id=wf.id,
            version=v_num,
            trigger_type=trigger_type,
            context=context or {},
        )
        # In production: enqueue Celery task execute_workflow(run_id)
        # celery_app.send_task("tasks.workflow_exec.execute_workflow", args=[str(run.id)])
        return run

    async def get_run(self, run_id: str):
        run = await self.repo.get_run(UUID(run_id))
        if not run:
            raise NotFoundError("WorkflowRun", run_id)
        return run

    async def approve_step(self, run_id: str, step_id: str, approved: bool, reason: str | None = None) -> dict:
        """Handle human approval/rejection of an awaiting_approval step."""
        run = await self.get_run(run_id)
        step = await self.repo.get_step_run(UUID(run_id), step_id)
        if not step:
            raise NotFoundError("WorkflowStepRun", step_id)

        step.status = "completed" if approved else "failed"
        if reason and not approved:
            step.output = {"rejection_reason": reason}

        await self.db.flush()

        if approved:
            # In production: re-enqueue workflow to resume from next step
            pass
        else:
            await self.repo.update_run_status(run, "failed", error=f"Step '{step_id}' rejected: {reason}")

        return {"approved": approved, "run_id": run_id, "step_id": step_id}

    def generate_approval_url(self, run_id: str, step_id: str, base_url: str) -> str:
        token = create_signed_approval_token(run_id, step_id)
        return f"{base_url}/api/v1/workflows/runs/{run_id}/approve?token={token}"