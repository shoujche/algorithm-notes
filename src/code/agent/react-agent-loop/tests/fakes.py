from __future__ import annotations

from collections import deque
from types import SimpleNamespace
from typing import Any


def text_item(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="message",
        content=[SimpleNamespace(type="output_text", text=text)],
    )


def function_call(call_id: str, name: str, arguments: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="function_call",
        call_id=call_id,
        name=name,
        arguments=arguments,
    )


def response(response_id: str, *items: Any) -> SimpleNamespace:
    return SimpleNamespace(id=response_id, output=list(items))


class FakeResponses:
    def __init__(self, scripted: list[Any]) -> None:
        self.scripted = deque(scripted)
        self.requests: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        next_result = self.scripted.popleft()
        if isinstance(next_result, BaseException):
            raise next_result
        return next_result


class FakeOpenAIClient:
    def __init__(self, scripted: list[Any]) -> None:
        self.responses = FakeResponses(scripted)


class FakeMCPClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.results: dict[str, Any] = {
            "list_files": {"entries": ["a.py"]},
            "read_file": {"content": "print('ok')"},
            "write_file": {"written": True},
            "run_command": {"exit_code": 0},
        }

    async def list_function_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "list_files",
                "description": "List files.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "write_file",
                "description": "Write a file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return __import__("json").dumps(
            self.results.get(name, {"error": f"unknown tool: {name}"}),
            separators=(",", ":"),
            sort_keys=True,
        )
