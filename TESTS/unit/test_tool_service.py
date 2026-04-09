"""
Unit tests for the tool service — registry, calculator, permission checks.
No DB, no HTTP calls (calculator is sandboxed pure Python).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))

import pytest
import asyncio


class TestCalculator:

    def setup_method(self):
        from services.tool_service import _calculator_handler
        self.handler = _calculator_handler

    def _run(self, args):
        return asyncio.run(self.handler(args))

    def test_addition(self):
        result = self._run({"expression": "2 + 3"})
        assert result["result"] == 5.0

    def test_multiplication(self):
        result = self._run({"expression": "4 * 7"})
        assert result["result"] == 28.0

    def test_division(self):
        result = self._run({"expression": "10 / 4"})
        assert result["result"] == 2.5

    def test_power(self):
        result = self._run({"expression": "2 ** 8"})
        assert result["result"] == 256.0

    def test_complex_expression(self):
        result = self._run({"expression": "(2 + 3) * 4 - 1"})
        assert result["result"] == 19.0

    def test_negative_number(self):
        result = self._run({"expression": "-5 * 2"})
        assert result["result"] == -10.0

    def test_unsafe_expression_returns_error(self):
        result = self._run({"expression": "__import__('os').system('ls')"})
        assert "error" in result

    def test_invalid_syntax_returns_error(self):
        result = self._run({"expression": "2 +"})
        assert "error" in result

    def test_string_operations_blocked(self):
        result = self._run({"expression": "'hello' + 'world'"})
        assert "error" in result

    def test_empty_expression(self):
        result = self._run({"expression": ""})
        assert "error" in result


class TestToolRegistry:

    def setup_method(self):
        from services.tool_service import tool_registry
        self.registry = tool_registry

    def test_builtin_tools_registered(self):
        names = self.registry.all_names()
        assert "web_search" in names
        assert "calculator" in names
        assert "knowledge_retrieval" in names

    def test_openai_schema_format(self):
        schemas = self.registry.openai_schemas()
        for schema in schemas:
            assert schema["type"] == "function"
            assert "name" in schema["function"]
            assert "description" in schema["function"]
            assert "parameters" in schema["function"]

    def test_anthropic_schema_format(self):
        schemas = self.registry.anthropic_schemas()
        for schema in schemas:
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema

    def test_get_existing_tool(self):
        tool = self.registry.get("calculator")
        assert tool is not None
        assert tool.name == "calculator"

    def test_get_nonexistent_tool_returns_none(self):
        assert self.registry.get("nonexistent_tool_xyz") is None


class TestToolPermissions:

    def setup_method(self):
        from services.tool_service import ToolService, tool_registry
        self.service = ToolService()
        self.registry = tool_registry

    def test_member_can_use_member_tool(self):
        tool = self.registry.get("calculator")
        assert self.service.check_permission(tool, "member") is True

    def test_viewer_cannot_use_member_tool(self):
        tool = self.registry.get("calculator")
        assert self.service.check_permission(tool, "viewer") is False

    def test_admin_can_use_member_tool(self):
        tool = self.registry.get("calculator")
        assert self.service.check_permission(tool, "admin") is True

    def test_owner_can_use_any_tool(self):
        tool = self.registry.get("web_search")
        assert self.service.check_permission(tool, "owner") is True

    def test_unknown_role_cannot_use_tool(self):
        tool = self.registry.get("calculator")
        assert self.service.check_permission(tool, "superuser") is False


class TestToolExecution:

    def _run(self, coro):
        return asyncio.run(coro)

    def test_unknown_tool_returns_error(self):
        from services.tool_service import tool_service
        result = self._run(tool_service.execute("nonexistent", {}, user_role="member"))
        assert "error" in result

    def test_insufficient_permission_returns_error(self):
        from services.tool_service import tool_service
        result = self._run(tool_service.execute("calculator", {"expression": "1+1"}, user_role="viewer"))
        assert "error" in result
        assert "permission" in result["error"].lower()

    def test_calculator_executes_successfully(self):
        from services.tool_service import tool_service
        result = self._run(tool_service.execute("calculator", {"expression": "3 * 3"}, user_role="member"))
        assert result.get("result") == 9.0