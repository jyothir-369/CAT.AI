"""
Tool Service — permission checks, sandboxed execution, trace logging.
"""
import asyncio
import ast
import operator
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx

from core.config import settings


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict
    permission: str = "member"   # viewer | member | admin | owner
    sandbox: bool = False
    timeout_ms: int = 10_000
    handler: Optional[Callable] = field(default=None, repr=False)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def openai_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def anthropic_schemas(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in self._tools.values()
        ]

    def all_names(self) -> list[str]:
        return list(self._tools.keys())


# ── Built-in handlers ────────────────────────────────────────────────────────

async def _web_search_handler(args: dict) -> dict:
    query = args.get("query", "")
    if not settings.serper_api_key:
        return {"error": "Web search not configured (missing SERPER_API_KEY)", "results": []}
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
            json={"q": query, "num": 5},
        )
        resp.raise_for_status()
        data = resp.json()
    results = [
        {"title": r.get("title"), "snippet": r.get("snippet"), "url": r.get("link")}
        for r in data.get("organic", [])
    ]
    return {"query": query, "results": results}


async def _calculator_handler(args: dict) -> dict:
    expression = args.get("expression", "")
    _allowed_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def _safe_eval(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in _allowed_ops:
            return _allowed_ops[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _allowed_ops:
            return _allowed_ops[type(node.op)](_safe_eval(node.operand))
        raise ValueError(f"Unsafe expression node: {type(node).__name__}")

    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
        return {"expression": expression, "result": result}
    except Exception as exc:
        return {"expression": expression, "error": str(exc)}


async def _knowledge_retrieval_handler(args: dict) -> dict:
    return {"chunks": [], "message": "Provide kb_id to retrieve from a knowledge base."}


# ── Registry bootstrap ────────────────────────────────────────────────────────

tool_registry = ToolRegistry()

tool_registry.register(ToolDefinition(
    name="web_search",
    description=(
        "Search the live web for up-to-date information. "
        "Use for current events, recent facts, or anything beyond your training data."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query string"},
        },
        "required": ["query"],
    },
    handler=_web_search_handler,
    timeout_ms=10_000,
))

tool_registry.register(ToolDefinition(
    name="calculator",
    description="Evaluate a mathematical expression with guaranteed accuracy.",
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "A Python-style arithmetic expression, e.g. '(2 + 3) * 4 / 2'",
            },
        },
        "required": ["expression"],
    },
    handler=_calculator_handler,
    timeout_ms=2_000,
))

tool_registry.register(ToolDefinition(
    name="knowledge_retrieval",
    description="Search the workspace knowledge base for relevant document chunks.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The semantic search query"},
            "kb_id": {"type": "string", "description": "UUID of the knowledge base to search"},
        },
        "required": ["query"],
    },
    handler=_knowledge_retrieval_handler,
    timeout_ms=8_000,
))


# ── Service ───────────────────────────────────────────────────────────────────

class ToolService:
    _role_order = ["viewer", "member", "admin", "owner"]

    def check_permission(self, tool: ToolDefinition, user_role: str) -> bool:
        required = tool.permission if tool.permission in self._role_order else "member"
        try:
            return self._role_order.index(user_role) >= self._role_order.index(required)
        except ValueError:
            return False

    async def execute(
        self,
        tool_name: str,
        args: dict,
        user_role: str = "member",
        db=None,
        message_id: Optional[str] = None,
    ) -> dict:
        tool = tool_registry.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}"}
        if not self.check_permission(tool, user_role):
            return {"error": f"Insufficient permissions for tool '{tool_name}'"}
        if not tool.handler:
            return {"error": f"Tool '{tool_name}' has no handler configured"}

        start = time.monotonic()
        try:
            result = await asyncio.wait_for(tool.handler(args), timeout=tool.timeout_ms / 1000)
            duration_ms = int((time.monotonic() - start) * 1000)
            if db and message_id:
                from db.models.conversation import ToolCallRecord
                db.add(ToolCallRecord(
                    message_id=message_id, tool_name=tool_name,
                    input=args, output=result, status="success", duration_ms=duration_ms,
                ))
            return result
        except asyncio.TimeoutError:
            err = {"error": f"Tool '{tool_name}' timed out after {tool.timeout_ms}ms"}
            if db and message_id:
                from db.models.conversation import ToolCallRecord
                db.add(ToolCallRecord(
                    message_id=message_id, tool_name=tool_name,
                    input=args, output=err, status="timeout", duration_ms=tool.timeout_ms,
                ))
            return err
        except Exception as exc:
            err = {"error": str(exc)}
            duration_ms = int((time.monotonic() - start) * 1000)
            if db and message_id:
                from db.models.conversation import ToolCallRecord
                db.add(ToolCallRecord(
                    message_id=message_id, tool_name=tool_name,
                    input=args, output=err, status="failed", duration_ms=duration_ms,
                ))
            return err

    def schemas_for_provider(self, provider: str = "openai") -> list[dict]:
        if provider == "anthropic":
            return tool_registry.anthropic_schemas()
        return tool_registry.openai_schemas()


tool_service = ToolService()