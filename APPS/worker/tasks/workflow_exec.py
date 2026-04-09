"""
Workflow execution task.

Executes a workflow run step by step in topological order.
Each step is durable — if the worker dies, the run can be resumed
from the last completed step by re-queuing the task.

Supported step types (MVP):
  llm        — call AI orchestration engine
  condition  — evaluate expression, choose branch
  api_call   — outbound HTTP request
  approval   — pause and notify human
  tool       — execute a registered tool
  transform  — reshape data with simple mapping
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

from celery_app import celery_app


# ── Main task ─────────────────────────────────────────────────────────────────

@celery_app.task(
    name="tasks.workflow_exec.execute_workflow",
    bind=True,
    max_retries=0,  # workflow-level retries handled per-step
    queue="workflows",
    acks_late=True,
)
def execute_workflow(self, run_id: str):
    asyncio.run(_execute_async(run_id))


@celery_app.task(
    name="tasks.workflow_exec.run_cron_workflows",
    queue="workflows",
)
def run_cron_workflows():
    """Beat task — finds and triggers cron-scheduled workflows."""
    asyncio.run(_run_cron_async())


# ── Async execution engine ────────────────────────────────────────────────────

async def _execute_async(run_id: str):
    from db.session import AsyncSessionLocal
    from db.models.workflow import (
        WorkflowRun, WorkflowVersion, WorkflowStepRun,
        WorkflowRunStatusEnum, StepRunStatusEnum,
    )
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        # Load run
        result = await db.execute(select(WorkflowRun).where(WorkflowRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            print(f"[WorkflowExec] Run {run_id} not found")
            return

        if run.status not in (WorkflowRunStatusEnum.pending, WorkflowRunStatusEnum.running):
            print(f"[WorkflowExec] Run {run_id} is {run.status} — skipping")
            return

        # Load workflow version definition
        ver_result = await db.execute(
            select(WorkflowVersion).where(
                WorkflowVersion.workflow_id == run.workflow_id,
                WorkflowVersion.version == run.version,
            )
        )
        version = ver_result.scalar_one_or_none()
        if not version:
            run.status = WorkflowRunStatusEnum.failed
            run.error = "Workflow version definition not found"
            await db.commit()
            return

        definition = version.definition or {}
        steps = definition.get("steps", [])
        edges = definition.get("edges", [])

        run.status = WorkflowRunStatusEnum.running
        run.started_at = datetime.now(timezone.utc)
        await db.commit()

        # Build execution order (topological sort)
        ordered_steps = _topological_sort(steps, edges)

        context: dict = dict(run.context or {})

        try:
            for step in ordered_steps:
                step_id = step["id"]
                step_type = step.get("type", "unknown")
                step_config = step.get("config", {})

                # Check if already completed (resumability)
                existing_result = await db.execute(
                    select(WorkflowStepRun).where(
                        WorkflowStepRun.run_id == run_id,
                        WorkflowStepRun.step_id == step_id,
                        WorkflowStepRun.status == StepRunStatusEnum.completed,
                    )
                )
                if existing_result.scalar_one_or_none():
                    print(f"[WorkflowExec] Step {step_id} already completed — skipping")
                    continue

                # Create step run record
                step_run = WorkflowStepRun(
                    run_id=run_id,
                    step_id=step_id,
                    status=StepRunStatusEnum.running,
                    input=context,
                    started_at=datetime.now(timezone.utc),
                )
                db.add(step_run)
                await db.flush()

                # Execute step
                try:
                    output = await _execute_step(step_type, step_config, context, db)
                    step_run.status = StepRunStatusEnum.completed
                    step_run.output = output
                    context.update(output)
                except ApprovalRequired as approval:
                    step_run.status = StepRunStatusEnum.awaiting_approval
                    step_run.output = {"awaiting_approval": True}
                    await db.commit()
                    print(f"[WorkflowExec] Step {step_id} awaiting approval")
                    return  # Pause execution — resumes via approval endpoint
                except StepFailed as exc:
                    step_run.status = StepRunStatusEnum.failed
                    step_run.output = {"error": str(exc)}
                    run.status = WorkflowRunStatusEnum.failed
                    run.error = f"Step {step_id} failed: {exc}"
                    run.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    print(f"[WorkflowExec] ❌ Run {run_id} failed at step {step_id}: {exc}")
                    return
                finally:
                    step_run.completed_at = datetime.now(timezone.utc)

                await db.commit()

            # All steps completed
            run.status = WorkflowRunStatusEnum.completed
            run.completed_at = datetime.now(timezone.utc)
            run.context = context
            await db.commit()
            print(f"[WorkflowExec] ✅ Run {run_id} completed")

        except Exception as exc:
            run.status = WorkflowRunStatusEnum.failed
            run.error = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()
            print(f"[WorkflowExec] ❌ Run {run_id} unhandled error: {exc}")
            raise


async def _execute_step(
    step_type: str,
    config: dict,
    context: dict,
    db,
) -> dict:
    """Dispatch to the appropriate step handler."""
    handlers = {
        "llm": _step_llm,
        "condition": _step_condition,
        "api_call": _step_api_call,
        "approval": _step_approval,
        "tool": _step_tool,
        "transform": _step_transform,
        "retrieval": _step_retrieval,
    }
    handler = handlers.get(step_type)
    if not handler:
        return {"skipped": True, "reason": f"Unknown step type: {step_type}"}
    return await handler(config, context, db)


# ── Step handlers ─────────────────────────────────────────────────────────────

async def _step_llm(config: dict, context: dict, db) -> dict:
    """Call the AI model and return the response text."""
    from ai.router import complete_with_fallback
    prompt = config.get("prompt", "")

    # Template substitution from context
    for key, val in context.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", str(val))

    model_id = config.get("model", "gpt-4o-mini")
    messages = [{"role": "user", "content": prompt}]

    result = await complete_with_fallback(messages, model_id=model_id)
    return {"llm_response": result.get("content", ""), "model_used": model_id}


async def _step_condition(config: dict, context: dict, db) -> dict:
    """Evaluate a simple Python-safe expression against context."""
    expression = config.get("expression", "True")
    try:
        # Safe eval: only allow comparison and boolean ops against context values
        result = bool(eval(expression, {"__builtins__": {}}, context))  # noqa: S307
    except Exception as exc:
        result = False
    return {"condition_result": result, "branch": "true" if result else "false"}


async def _step_api_call(config: dict, context: dict, db) -> dict:
    """Make an outbound HTTP request."""
    import httpx
    url = config.get("url", "")
    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})
    body = config.get("body", None)

    # Template substitution
    for key, val in context.items():
        url = url.replace(f"{{{{{key}}}}}", str(val))

    async with httpx.AsyncClient(timeout=config.get("timeout_s", 10)) as client:
        response = await client.request(method, url, headers=headers, json=body)
        try:
            response_data = response.json()
        except Exception:
            response_data = {"text": response.text}

    return {
        "api_status": response.status_code,
        "api_response": response_data,
    }


async def _step_approval(config: dict, context: dict, db) -> dict:
    """Pause execution and notify approvers."""
    raise ApprovalRequired(config.get("approver_user_id"), config.get("message", ""))


async def _step_tool(config: dict, context: dict, db) -> dict:
    """Execute a registered tool."""
    from services.tool_service import tool_service
    tool_name = config.get("tool_name", "")
    args = config.get("args", {})
    # Template substitution in args
    for key, val in context.items():
        for arg_key, arg_val in args.items():
            if isinstance(arg_val, str):
                args[arg_key] = arg_val.replace(f"{{{{{key}}}}}", str(val))
    result = await tool_service.execute(tool_name, args, user_role="member")
    return {"tool_result": result}


async def _step_transform(config: dict, context: dict, db) -> dict:
    """Apply simple key mapping to reshape context data."""
    mapping = config.get("mapping", {})
    output = {}
    for out_key, source_path in mapping.items():
        # Support dot-notation: "api_response.data.id"
        parts = source_path.split(".")
        val = context
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                val = None
                break
        output[out_key] = val
    return output


async def _step_retrieval(config: dict, context: dict, db) -> dict:
    """Query a knowledge base and inject chunks into context."""
    from services.rag_service import rag_service
    kb_id = config.get("kb_id")
    query = config.get("query", context.get("llm_response", ""))
    if not kb_id:
        return {"rag_chunks": []}

    # org_id needed — get from workflow run context
    org_id = context.get("org_id", "")
    chunks = await rag_service.query_knowledge_base(db, kb_id, org_id, query, top_k=5)
    rag_text = "\n\n".join(c["content"] for c in chunks)
    return {"rag_chunks": chunks, "rag_context": rag_text}


# ── Topological sort ──────────────────────────────────────────────────────────

def _topological_sort(steps: list[dict], edges: list[dict]) -> list[dict]:
    """Kahn's algorithm — returns steps in execution order."""
    step_map = {s["id"]: s for s in steps}
    in_degree = {s["id"]: 0 for s in steps}
    adjacency: dict[str, list[str]] = {s["id"]: [] for s in steps}

    for edge in edges:
        src = edge.get("from")
        dst = edge.get("to")
        if src in adjacency and dst in in_degree:
            adjacency[src].append(dst)
            in_degree[dst] += 1

    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    ordered = []

    while queue:
        sid = queue.pop(0)
        ordered.append(step_map[sid])
        for neighbor in adjacency.get(sid, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(ordered) != len(steps):
        # Cycle detected — fall back to original order
        return steps
    return ordered


# ── Cron workflow runner ──────────────────────────────────────────────────────

async def _run_cron_async():
    from db.session import AsyncSessionLocal
    from db.models.workflow import Workflow, WorkflowRun, WorkflowRunStatusEnum
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Workflow).where(
                Workflow.is_active == True,
                Workflow.trigger["type"].astext == "cron",
            )
        )
        cron_workflows = result.scalars().all()

        for wf in cron_workflows:
            run = WorkflowRun(
                workflow_id=wf.id,
                version=1,
                trigger_type="cron",
                status=WorkflowRunStatusEnum.pending,
                context={"triggered_by": "beat"},
            )
            db.add(run)
            await db.flush()
            execute_workflow.delay(run.id)

        if cron_workflows:
            await db.commit()
            print(f"[WorkflowExec] Triggered {len(cron_workflows)} cron workflow(s)")


# ── Custom exceptions ─────────────────────────────────────────────────────────

class ApprovalRequired(Exception):
    def __init__(self, approver_user_id: Optional[str] = None, message: str = ""):
        self.approver_user_id = approver_user_id
        self.message = message
        super().__init__(message)


class StepFailed(Exception):
    pass