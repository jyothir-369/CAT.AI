"""
Workflow repository — data access for workflows, versions, runs, step runs.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.workflow import (
    Workflow,
    WorkflowVersion,
    WorkflowRun,
    WorkflowStepRun,
    WorkflowRunStatusEnum,
    StepRunStatusEnum,
)


class WorkflowRepo:

    async def get_by_id(
        self, db: AsyncSession, workflow_id: str, org_id: str
    ) -> Optional[Workflow]:
        result = await db.execute(
            select(Workflow).where(
                Workflow.id == workflow_id,
                Workflow.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, db: AsyncSession, org_id: str) -> list[Workflow]:
        result = await db.execute(
            select(Workflow)
            .where(Workflow.org_id == org_id)
            .order_by(Workflow.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        org_id: str,
        user_id: str,
        name: str,
        trigger: dict,
        definition: dict,
        description: Optional[str] = None,
    ) -> Workflow:
        wf = Workflow(
            org_id=org_id,
            created_by=user_id,
            name=name,
            description=description,
            trigger=trigger,
        )
        db.add(wf)
        await db.flush()

        version = WorkflowVersion(
            workflow_id=wf.id,
            version=1,
            definition=definition,
        )
        db.add(version)
        await db.flush()
        return wf

    async def get_latest_version(
        self, db: AsyncSession, workflow_id: str
    ) -> Optional[WorkflowVersion]:
        result = await db.execute(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(WorkflowVersion.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_run(
        self,
        db: AsyncSession,
        workflow_id: str,
        version: int,
        trigger_type: str,
        context: Optional[dict] = None,
    ) -> WorkflowRun:
        run = WorkflowRun(
            workflow_id=workflow_id,
            version=version,
            trigger_type=trigger_type,
            status=WorkflowRunStatusEnum.pending,
            context=context or {},
        )
        db.add(run)
        await db.flush()
        return run

    async def get_run(self, db: AsyncSession, run_id: str) -> Optional[WorkflowRun]:
        result = await db.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_runs(
        self,
        db: AsyncSession,
        workflow_id: str,
        limit: int = 50,
    ) -> list[WorkflowRun]:
        result = await db.execute(
            select(WorkflowRun)
            .where(WorkflowRun.workflow_id == workflow_id)
            .order_by(WorkflowRun.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_step_run(
        self, db: AsyncSession, run_id: str, step_id: str
    ) -> Optional[WorkflowStepRun]:
        result = await db.execute(
            select(WorkflowStepRun).where(
                WorkflowStepRun.run_id == run_id,
                WorkflowStepRun.step_id == step_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_pending_approval(
        self, db: AsyncSession, run_id: str, step_id: str
    ) -> Optional[WorkflowStepRun]:
        result = await db.execute(
            select(WorkflowStepRun).where(
                WorkflowStepRun.run_id == run_id,
                WorkflowStepRun.step_id == step_id,
                WorkflowStepRun.status == StepRunStatusEnum.awaiting_approval,
            )
        )
        return result.scalar_one_or_none()

    async def update_run_status(
        self,
        db: AsyncSession,
        run_id: str,
        status: WorkflowRunStatusEnum,
        error: Optional[str] = None,
    ) -> Optional[WorkflowRun]:
        run = await self.get_run(db, run_id)
        if not run:
            return None
        run.status = status
        if error:
            run.error = error
        if status in (WorkflowRunStatusEnum.completed, WorkflowRunStatusEnum.failed):
            run.completed_at = datetime.now(timezone.utc)
        return run


workflow_repo = WorkflowRepo()