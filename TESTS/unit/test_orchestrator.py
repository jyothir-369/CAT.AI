"""
Unit tests for the chat service prompt assembler and token budgeting.
No DB, no HTTP — pure logic tests.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))

import pytest
from services.chat_service import ChatService, MODEL_COSTS


class TestPromptAssembly:

    def setup_method(self):
        self.service = ChatService()

    def test_basic_prompt_includes_user_message(self):
        messages = self.service.assemble_prompt(
            user_message="Hello, world!",
            history=[],
        )
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "Hello, world!"

    def test_system_prompt_is_first_message(self):
        messages = self.service.assemble_prompt(
            user_message="test",
            history=[],
            system_prompt="You are a helpful assistant.",
        )
        assert messages[0]["role"] == "system"
        assert "You are a helpful assistant." in messages[0]["content"]

    def test_memories_injected_into_system_prompt(self):
        messages = self.service.assemble_prompt(
            user_message="test",
            history=[],
            system_prompt="Base prompt.",
            memories=["User prefers Python", "User is building a SaaS"],
        )
        system_content = messages[0]["content"]
        assert "User prefers Python" in system_content
        assert "User is building a SaaS" in system_content

    def test_rag_context_injected_into_system_prompt(self):
        messages = self.service.assemble_prompt(
            user_message="What is X?",
            history=[],
            rag_context="X is a framework for building AI apps.",
        )
        system_content = messages[0]["content"]
        assert "X is a framework" in system_content

    def test_history_preserved_in_order(self):
        history = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First reply"},
            {"role": "user", "content": "Second message"},
            {"role": "assistant", "content": "Second reply"},
        ]
        messages = self.service.assemble_prompt(
            user_message="Third message",
            history=history,
        )
        # History comes before current user message
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles
        assert messages[-1]["content"] == "Third message"

    def test_empty_history_no_error(self):
        messages = self.service.assemble_prompt(
            user_message="Solo message",
            history=[],
        )
        assert len(messages) >= 1
        assert messages[-1]["content"] == "Solo message"

    def test_no_system_prompt_no_system_message(self):
        messages = self.service.assemble_prompt(
            user_message="test",
            history=[],
            system_prompt=None,
            memories=None,
            rag_context=None,
        )
        roles = [m["role"] for m in messages]
        assert "system" not in roles

    def test_all_components_combined(self):
        messages = self.service.assemble_prompt(
            user_message="What do you know about me?",
            history=[
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello!"},
            ],
            system_prompt="You are CAT AI.",
            memories=["User likes Python"],
            rag_context="Relevant doc chunk here.",
        )
        # System first
        assert messages[0]["role"] == "system"
        # User message last
        assert messages[-1]["role"] == "user"
        assert "What do you know" in messages[-1]["content"]


class TestModelCosts:

    def test_gpt4o_cost_defined(self):
        assert "gpt-4o" in MODEL_COSTS
        assert MODEL_COSTS["gpt-4o"]["in"] > 0
        assert MODEL_COSTS["gpt-4o"]["out"] > 0

    def test_all_costs_positive(self):
        for model, costs in MODEL_COSTS.items():
            assert costs["in"] >= 0, f"{model} in-cost is negative"
            assert costs["out"] >= 0, f"{model} out-cost is negative"

    def test_claude_cheaper_than_gpt4o_input(self):
        # Claude Haiku should be cheaper than GPT-4o for input
        haiku_in = MODEL_COSTS.get("claude-3-haiku-20240307", {}).get("in", 999)
        gpt4o_in = MODEL_COSTS["gpt-4o"]["in"]
        assert haiku_in < gpt4o_in


class TestModelSelection:

    def setup_method(self):
        self.service = ChatService()

    def test_explicit_model_wins(self):
        from unittest.mock import MagicMock
        org = MagicMock()
        org.default_model = "gpt-4o"
        assert self.service.select_model("claude-3-5-sonnet-20241022", org) == "claude-3-5-sonnet-20241022"

    def test_falls_back_to_org_default(self):
        from unittest.mock import MagicMock
        org = MagicMock()
        org.default_model = "gpt-4o-mini"
        assert self.service.select_model(None, org) == "gpt-4o-mini"

    def test_falls_back_to_hardcoded_default(self):
        from unittest.mock import MagicMock
        org = MagicMock()
        org.default_model = None
        assert self.service.select_model(None, org) == "gpt-4o"