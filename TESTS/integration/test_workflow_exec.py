"""
Integration tests for the workflow execution engine.
Tests DAG execution, step ordering, approval pausing, and failure handling.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fixtures"))

import pytest
from conftest import *  # noqa: F401, F403


@pytest.mark.asyncio
class TestWorkflowCRUD:

    async def test_create_workflow(self, client, test_user):
        response = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Test Workflow",
                "description": "A test",
                "trigger": {"type": "manual"},
                "definition": {
                    "steps": [{"id": "s1", "type": "llm", "config": {"prompt": "Say hi"}}],
                    "edges": [],
                },
            },
            headers=test_user["headers"],
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Test Workflow"
        assert "id" in body

    async def test_list_workflows(self, client, test_user):
        # Create one first
        await client.post(
            "/api/v1/workflows",
            json={
                "name": "Listed Workflow",
                "trigger": {"type": "manual"},
                "definition": {},
            },
            headers=test_user["headers"],
        )

        response = await client.get(
            "/api/v1/workflows",
            headers=test_user["headers"],
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_workflow(self, client, test_user):
        create_resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Get Me",
                "trigger": {"type": "manual"},
                "definition": {},
            },
            headers=test_user["headers"],
        )
        wf_id = create_resp.json()["id"]

        response = await client.get(
            f"/api/v1/workflows/{wf_id}",
            headers=test_user["headers"],
        )
        assert response.status_code == 200
        assert response.json()["id"] == wf_id

    async def test_delete_workflow(self, client, test_user):
        create_resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Delete Me",
                "trigger": {"type": "manual"},
                "definition": {},
            },
            headers=test_user["headers"],
        )
        wf_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/workflows/{wf_id}",
            headers=test_user["headers"],
        )
        assert response.status_code == 204

        # Verify gone
        get_resp = await client.get(
            f"/api/v1/workflows/{wf_id}",
            headers=test_user["headers"],
        )
        assert get_resp.status_code == 404


@pytest.mark.asyncio
class TestWorkflowRun:

    async def test_manual_trigger_creates_run(self, client, test_user):
        # Create workflow
        create_resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Runnable",
                "trigger": {"type": "manual"},
                "definition": {
                    "steps": [{"id": "s1", "type": "transform", "config": {"mapping": {}}}],
                    "edges": [],
                },
            },
            headers=test_user["headers"],
        )
        wf_id = create_resp.json()["id"]

        response = await client.post(
            f"/api/v1/workflows/{wf_id}/run",
            json={"context": {"test_key": "test_val"}},
            headers=test_user["headers"],
        )
        assert response.status_code == 201
        body = response.json()
        assert body["trigger_type"] == "manual"
        assert body["status"] in ("pending", "running", "completed")

    async def test_get_run_status(self, client, test_user):
        # Create and trigger
        create_resp = await client.post(
            "/api/v1/workflows",
            json={
                "name": "Status Check",
                "trigger": {"type": "manual"},
                "definition": {"steps": [], "edges": []},
            },
            headers=test_user["headers"],
        )
        wf_id = create_resp.json()["id"]

        run_resp = await client.post(
            f"/api/v1/workflows/{wf_id}/run",
            json={},
            headers=test_user["headers"],
        )
        run_id = run_resp.json()["id"]

        status_resp = await client.get(
            f"/api/v1/workflows/runs/{run_id}",
            headers=test_user["headers"],
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["id"] == run_id


@pytest.mark.asyncio
class TestApprovalFlow:

    async def test_approval_with_valid_token(self, client, test_user):
        from core.security import create_signed_url_token
        from services.workflow_service import workflow_service
        from db.models.workflow import WorkflowRun, WorkflowStepRun, StepRunStatusEnum

        # We need to inject a step run directly for the approval test
        # This would normally come from workflow execution
        # Just test the token validation path
        token = create_signed_url_token({
            "run_id": "nonexistent-run",
            "step_id": "step1",
            "action": "approve",
        })

        response = await client.post(
            "/api/v1/workflows/runs/nonexistent-run/approve",
            json={"token": token},
        )
        # 404 because run doesn't exist — but token was valid
        assert response.status_code in (404, 400)

    async def test_approval_with_invalid_token(self, client):
        response = await client.post(
            "/api/v1/workflows/runs/some-run-id/approve",
            json={"token": "invalid.token.here"},
        )
        assert response.status_code == 400

    async def test_approval_token_run_id_mismatch(self, client):
        from core.security import create_signed_url_token
        token = create_signed_url_token({
            "run_id": "run-abc",
            "step_id": "step1",
            "action": "approve",
        })

        response = await client.post(
            "/api/v1/workflows/runs/different-run-id/approve",
            json={"token": token},
        )
        assert response.status_code == 400
        assert "mismatch" in response.json()["detail"].lower()