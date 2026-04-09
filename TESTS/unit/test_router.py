"""
Unit tests for the AI model router.
Verifies correct provider selection and fallback logic.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))

import pytest
from ai.router import get_provider, select_model


class TestGetProvider:

    def test_gpt_routes_to_openai(self):
        provider = get_provider("gpt-4o")
        assert provider.name == "openai"

    def test_gpt4o_mini_routes_to_openai(self):
        provider = get_provider("gpt-4o-mini")
        assert provider.name == "openai"

    def test_claude_routes_to_anthropic(self):
        provider = get_provider("claude-3-5-sonnet-20241022")
        assert provider.name == "anthropic"

    def test_claude_haiku_routes_to_anthropic(self):
        provider = get_provider("claude-3-haiku-20240307")
        assert provider.name == "anthropic"

    def test_llama_routes_to_openai_as_fallback(self):
        # Groq models route through the OpenAI-compatible adapter in MVP
        provider = get_provider("llama-3.1-70b-versatile")
        assert provider.name == "openai"

    def test_unknown_model_defaults_to_openai(self):
        provider = get_provider("some-unknown-model-xyz")
        assert provider.name == "openai"

    def test_case_insensitive_routing(self):
        provider = get_provider("CLAUDE-3-5-SONNET-20241022")
        assert provider.name == "anthropic"


class TestSelectModel:

    def test_user_requested_model_wins(self):
        model = select_model(
            user_requested="claude-3-5-sonnet-20241022",
            org_default="gpt-4o",
        )
        assert model == "claude-3-5-sonnet-20241022"

    def test_org_default_used_when_no_user_preference(self):
        model = select_model(
            user_requested=None,
            org_default="gpt-4o-mini",
        )
        assert model == "gpt-4o-mini"

    def test_hardcoded_fallback_when_no_defaults(self):
        model = select_model(
            user_requested=None,
            org_default=None,
        )
        assert model == "gpt-4o"

    def test_long_context_routes_to_gemini(self):
        model = select_model(
            user_requested=None,
            org_default="gpt-4o",
            long_context_needed=True,
        )
        assert model == "gemini-1.5-pro"

    def test_user_model_overrides_long_context(self):
        # Explicit user selection always wins
        model = select_model(
            user_requested="gpt-4o",
            org_default="gpt-4o-mini",
            long_context_needed=True,
        )
        assert model == "gpt-4o"