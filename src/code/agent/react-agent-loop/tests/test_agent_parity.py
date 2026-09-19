from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from agent_core.checkpoints import JsonCheckpointStore
from agent_core.langchain_loop import LangChainReActAgent
from agent_core.langgraph_loop import LangGraphReActAgent
from agent_core.openai_loop import OpenAIReActAgent, ResumeDecision


EXPECTED_EVENTS = [
    "user",
    "skill_list",
    "skill_read",
    "file_read",
    "write_proposed",
    "paused",
    "approved",
    "write_result",
    "final",
]


class EventMCP:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def list_function_tools(self) -> list[dict[str, Any]]:
        return [
            _tool("list_skills", {"path": {"type": "string"}}),
            _tool(
                "read_skill",
                {
                    "name": {"type": "string"},
                    "path": {"type": "string"},
                },
            ),
            _tool("read_file", {"path": {"type": "string"}}),
            _tool(
                "write_file",
                {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
            ),
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        event = {
            "list_skills": "skill_list",
            "read_skill": "skill_read",
            "read_file": "file_read",
            "write_file": "write_result",
        }[name]
        self.events.append(event)
        return json.dumps(
            {
                "list_skills": {"skills": ["workspace-helper"]},
                "read_skill": {"content": "Use workspace tools safely."},
                "read_file": {"content": "old"},
                "write_file": {"written": True},
            }[name],
            separators=(",", ":"),
            sort_keys=True,
        )


def _tool(name: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": name.replace("_", " "),
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
        "strict": True,
    }


def _actions() -> list[tuple[str, str, dict[str, Any]] | str]:
    return [
        ("call-skills", "list_skills", {"path": "."}),
        (
            "call-skill",
            "read_skill",
            {"name": "workspace-helper", "path": "workspace-helper/SKILL.md"},
        ),
        ("call-read", "read_file", {"path": "answer.py"}),
        (
            "call-write",
            "write_file",
            {"path": "answer.py", "content": "new"},
        ),
        "saved",
    ]


class EventResponses:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.actions = deque(_actions())
        self.number = 0

    async def create(self, **_: Any) -> Any:
        self.number += 1
        action = self.actions.popleft()
        if isinstance(action, str):
            self.events.append("final")
            output = [
                SimpleNamespace(
                    type="message",
                    content=[
                        SimpleNamespace(type="output_text", text=action)
                    ],
                )
            ]
        else:
            call_id, name, arguments = action
            if name == "write_file":
                self.events.append("write_proposed")
            output = [
                SimpleNamespace(
                    type="function_call",
                    call_id=call_id,
                    name=name,
                    arguments=json.dumps(arguments),
                )
            ]
        return SimpleNamespace(id=f"response-{self.number}", output=output)


class EventOpenAIClient:
    def __init__(self, events: list[str]) -> None:
        self.responses = EventResponses(events)


class EventChatModel(BaseChatModel):
    _events: list[str] = PrivateAttr()
    _actions: deque[tuple[str, str, dict[str, Any]] | str] = PrivateAttr()

    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self._events = events
        self._actions = deque(_actions())

    @property
    def _llm_type(self) -> str:
        return "parity-event-model"

    def bind_tools(self, tools: Any, **kwargs: Any) -> EventChatModel:
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        action = self._actions.popleft()
        if isinstance(action, str):
            self._events.append("final")
            message = AIMessage(content=action)
        else:
            call_id, name, arguments = action
            if name == "write_file":
                self._events.append("write_proposed")
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": call_id,
                        "name": name,
                        "args": arguments,
                        "type": "tool_call",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


def _agent(
    implementation: str,
    tmp_path: Path,
    events: list[str],
    mcp: EventMCP,
) -> Any:
    if implementation == "openai":
        return OpenAIReActAgent(
            client=EventOpenAIClient(events),
            mcp=mcp,
            checkpoints=JsonCheckpointStore(tmp_path / "openai-runs"),
            model="fake",
            run_id_factory=lambda: "run-1",
        )
    if implementation == "langchain":
        return LangChainReActAgent(
            model=EventChatModel(events),
            mcp=mcp,
            checkpoint_path=tmp_path / "langchain.json",
            run_id_factory=lambda: "run-1",
        )
    return LangGraphReActAgent(
        model=EventChatModel(events),
        mcp=mcp,
        checkpoint_path=tmp_path / "langgraph.json",
        run_id_factory=lambda: "run-1",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("implementation", ["openai", "langchain", "langgraph"])
async def test_all_implementations_emit_the_complete_same_action_sequence(
    implementation: str,
    tmp_path: Path,
) -> None:
    events = ["user"]
    mcp = EventMCP(events)
    agent = _agent(implementation, tmp_path, events, mcp)

    paused = await agent.start("update answer.py")
    assert paused.pending_approval is not None
    events.append("paused")
    events.append("approved")
    final = await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=paused.pending_approval.digest,
        ),
    )

    assert final.final_text == "saved"
    assert events == EXPECTED_EVENTS
