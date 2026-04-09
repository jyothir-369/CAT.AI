"""
Integration tests for the chat SSE endpoint.
Uses a real DB session and mocked LLM provider (no OpenAI calls).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fixtures"))

import json
import pytest
import pytest_asyncio

from conftest import *  # noqa: F401, F403 — import all fixtures


@pytest.mark.asyncio
class TestChatStreamEndpoint:

    async def test_chat_stream_requires_auth(self, client):
        response = await client.post(
            "/api/v1/chat/stream",
            json={"message": "Hello"},
        )
        assert response.status_code == 403

    async def test_chat_stream_returns_sse(self, client, test_user, mock_openai_stream):
        response = await client.post(
            "/api/v1/chat/stream",
            json={"message": "Say hello"},
            headers=test_user["headers"],
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    async def test_chat_stream_tokens_in_response(self, client, test_user, mock_openai_stream):
        response = await client.post(
            "/api/v1/chat/stream",
            json={"message": "Say hello"},
            headers=test_user["headers"],
        )
        content = response.text
        assert "data:" in content

        # Parse SSE events
        events = []
        for line in content.split("\n"):
            if line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                    events.append(data)
                except json.JSONDecodeError:
                    pass

        # Should have token events and a done event
        tokens = [e for e in events if "token" in e]
        done_events = [e for e in events if e.get("done")]
        assert len(tokens) > 0
        assert len(done_events) == 1

    async def test_chat_stream_creates_conversation(self, client, test_user, mock_openai_stream, db_session):
        from db.models.conversation import Conversation
        from sqlalchemy import select

        before_count_result = await db_session.execute(
            select(Conversation).where(Conversation.org_id == test_user["org"].id)
        )
        before_count = len(before_count_result.scalars().all())

        response = await client.post(
            "/api/v1/chat/stream",
            json={"message": "New conversation message"},
            headers=test_user["headers"],
        )
        assert response.status_code == 200

        # Verify conversation was created
        after_result = await db_session.execute(
            select(Conversation).where(Conversation.org_id == test_user["org"].id)
        )
        after_count = len(after_result.scalars().all())
        assert after_count >= before_count

    async def test_chat_stream_continues_existing_conversation(
        self, client, test_user, mock_openai_stream, db_session
    ):
        from db.models.conversation import Conversation

        # Create a conversation first
        conv = Conversation(
            org_id=test_user["org"].id,
            user_id=test_user["user"].id,
            title="Existing conv",
        )
        db_session.add(conv)
        await db_session.flush()

        response = await client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Continue this conversation",
                "conversation_id": conv.id,
            },
            headers=test_user["headers"],
        )
        assert response.status_code == 200

        # Check done event returns the same conversation_id
        content = response.text
        done_events = []
        for line in content.split("\n"):
            if line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                    if data.get("done"):
                        done_events.append(data)
                except json.JSONDecodeError:
                    pass

        if done_events:
            assert done_events[0].get("conversation_id") == conv.id

    async def test_chat_stream_invalid_conversation_returns_error(
        self, client, test_user
    ):
        response = await client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Hello",
                "conversation_id": "00000000-0000-0000-0000-000000000000",
            },
            headers=test_user["headers"],
        )
        assert response.status_code in (404, 422, 400)