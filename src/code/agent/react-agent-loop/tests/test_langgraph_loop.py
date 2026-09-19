from __future__ import annotations

import json
import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.types import Command
from pydantic import PrivateAttr

from agent_core.contracts import to_json_value
from agent_core.langgraph_loop import LangGraphReActAgent
from agent_core.openai_loop import ResumeDecision
from tests.fakes import FakeMCPClient


class FakeChatModel(BaseChatModel):
    _scripted: deque[AIMessage] = PrivateAttr()
    _seen_messages: list[list[Any]] = PrivateAttr(default_factory=list)

    def __init__(self, scripted: list[AIMessage]) -> None:
        super().__init__()
        self._scripted = deque(scripted)

    @property
    def _llm_type(self) -> str:
        return "explicit-langgraph-fake"

    @property
    def seen_messages(self) -> list[list[Any]]:
        return self._seen_messages

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeChatModel:
        return self

    def _generate(
        self,
        messages: list[Any],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._seen_messages.append(list(messages))
        return ChatResult(
            generations=[ChatGeneration(message=self._scripted.popleft())]
        )


class GraphMCP(FakeMCPClient):
    async def list_function_tools(self) -> list[dict[str, Any]]:
        tools = await super().list_function_tools()
        tools.append(
            {
                "type": "function",
                "name": "run_command",
                "description": "Run an allow-listed command.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "argv": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "cwd": {"type": "string"},
                    },
                    "required": ["argv", "cwd"],
                    "additionalProperties": False,
                },
                "strict": True,
            }
        )
        return tools


class FailingMCP(GraphMCP):
    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        raise RuntimeError("sandbox unavailable")


def tool_call(
    call_id: str,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": call_id,
        "name": name,
        "args": arguments,
        "type": "tool_call",
    }


def ai_with_calls(*calls: dict[str, Any]) -> AIMessage:
    return AIMessage(content="", tool_calls=list(calls))


def make_agent(tmp_path, scripted, *, mcp=None, **limits):
    model = FakeChatModel(scripted)
    mcp = mcp or GraphMCP()
    agent = LangGraphReActAgent(
        model=model,
        mcp=mcp,
        checkpoint_path=tmp_path / "langgraph.json",
        run_id_factory=lambda: "run-1",
        **limits,
    )
    return agent, model, mcp


@pytest.mark.asyncio
async def test_graph_has_all_explicit_named_nodes(tmp_path) -> None:
    agent, _, _ = make_agent(tmp_path, [AIMessage(content="done")])

    graph = await agent.build_graph()

    assert {
        "call_model",
        "route_response",
        "request_approval",
        "execute_tools",
        "record_observation",
        "finish",
    } <= set(graph.nodes)


@pytest.mark.asyncio
async def test_final_answer_routes_to_finish_without_tool_execution(tmp_path) -> None:
    agent, _, mcp = make_agent(tmp_path, [AIMessage(content="done")])

    outcome = await agent.start("inspect")

    assert outcome.final_text == "done"
    assert outcome.run_id == "run-1"
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_empty_final_answer_still_finishes_without_an_extra_model_call(
    tmp_path,
) -> None:
    agent, model, mcp = make_agent(tmp_path, [AIMessage(content="")])

    outcome = await agent.start("inspect")

    assert outcome.final_text == ""
    assert len(model.seen_messages) == 1
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_read_only_call_routes_through_execution_and_observation(tmp_path) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            ai_with_calls(tool_call("call-read", "read_file", {"path": "a.py"})),
            AIMessage(content="inspected"),
        ],
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "inspected"
    assert mcp.calls == [("read_file", {"path": "a.py"})]
    observation = model.seen_messages[1][-1]
    assert isinstance(observation, ToolMessage)
    assert observation.tool_call_id == "call-read"


@pytest.mark.asyncio
async def test_sensitive_call_interrupts_before_any_side_effect(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            ai_with_calls(
                tool_call(
                    "call-write",
                    "write_file",
                    {"path": "b.py", "content": "new"},
                )
            )
        ],
    )

    outcome = await agent.start("change")

    assert outcome.pending_approval is not None
    assert outcome.pending_approval.proposal.call_id == "call-write"
    assert outcome.pending_approval.preview == "new"
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_stable_thread_resumes_with_command_not_plain_input(
    tmp_path,
    monkeypatch,
) -> None:
    agent, _, _ = make_agent(
        tmp_path,
        [
            ai_with_calls(
                tool_call(
                    "call-write",
                    "write_file",
                    {"path": "b.py", "content": "new"},
                )
            ),
            AIMessage(content="saved"),
        ],
    )
    graph = await agent.build_graph()
    calls: list[tuple[Any, dict[str, Any]]] = []
    real_ainvoke = graph.ainvoke

    async def recording_ainvoke(value, config):
        calls.append((value, config))
        return await real_ainvoke(value, config)

    monkeypatch.setattr(graph, "ainvoke", recording_ainvoke)
    monkeypatch.setattr(agent, "build_graph", lambda: _async_value(graph))

    pending = await agent.start("change")
    await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=pending.pending_approval.digest,
        ),
    )

    assert calls[0][0] == {"messages": [{"role": "user", "content": "change"}]}
    assert isinstance(calls[1][0], Command)
    assert calls[0][1]["configurable"]["thread_id"] == "run-1"
    assert calls[1][1]["configurable"]["thread_id"] == "run-1"


async def _async_value(value):
    return value


@pytest.mark.asyncio
async def test_rejection_becomes_observation_without_execution(tmp_path) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            ai_with_calls(
                tool_call(
                    "call-write",
                    "write_file",
                    {"path": "b.py", "content": "new"},
                )
            ),
            AIMessage(content="not changed"),
        ],
    )
    pending = await agent.start("change")

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(
            action="reject",
            digest=pending.pending_approval.digest,
            reason="not now",
        ),
    )

    assert outcome.final_text == "not changed"
    assert mcp.calls == []
    observation = model.seen_messages[1][-1]
    assert isinstance(observation, ToolMessage)
    assert observation.status == "error"
    assert "not now" in str(observation.content)


@pytest.mark.asyncio
async def test_edited_arguments_are_revalidated_and_executed(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            ai_with_calls(
                tool_call(
                    "call-write",
                    "write_file",
                    {"path": "b.py", "content": "old"},
                )
            ),
            AIMessage(content="saved"),
        ],
    )
    pending = await agent.start("change")

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=pending.pending_approval.digest,
            arguments={"path": "b.py", "content": "edited"},
        ),
    )

    assert outcome.final_text == "saved"
    assert mcp.calls == [
        ("write_file", {"path": "b.py", "content": "edited"})
    ]


@pytest.mark.asyncio
async def test_stale_digest_and_invalid_edit_are_rejected_before_dispatch(
    tmp_path,
) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            ai_with_calls(
                tool_call(
                    "call-write",
                    "write_file",
                    {"path": "b.py", "content": "old"},
                )
            )
        ],
    )
    pending = await agent.start("change")

    with pytest.raises(ValueError, match="digest"):
        await agent.resume(
            "run-1",
            ResumeDecision(action="approve", digest="stale"),
        )
    with pytest.raises(ValueError, match="schema"):
        await agent.resume(
            "run-1",
            ResumeDecision(
                action="approve",
                digest=pending.pending_approval.digest,
                arguments={"path": "b.py"},
            ),
        )

    assert mcp.calls == []


@pytest.mark.asyncio
async def test_all_sensitive_calls_are_approved_before_dispatch(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            ai_with_calls(
                tool_call(
                    "call-first",
                    "write_file",
                    {"path": "a.py", "content": "a"},
                ),
                tool_call(
                    "call-second",
                    "write_file",
                    {"path": "b.py", "content": "b"},
                ),
            ),
            AIMessage(content="saved"),
        ],
    )

    first = await agent.start("change both")
    second = await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=first.pending_approval.digest,
        ),
    )

    assert second.pending_approval is not None
    assert second.pending_approval.proposal.call_id == "call-second"
    assert mcp.calls == []

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=second.pending_approval.digest,
        ),
    )

    assert outcome.final_text == "saved"
    assert mcp.calls == [
        ("write_file", {"path": "a.py", "content": "a"}),
        ("write_file", {"path": "b.py", "content": "b"}),
    ]


@pytest.mark.asyncio
async def test_replayed_approved_checkpoint_executes_side_effect_exactly_once(
    tmp_path,
) -> None:
    checkpoint_path = tmp_path / "langgraph.json"
    mcp = GraphMCP()
    first = LangGraphReActAgent(
        model=FakeChatModel(
            [
                ai_with_calls(
                    tool_call(
                        "call-write",
                        "write_file",
                        {"path": "b.py", "content": "new"},
                    )
                ),
                AIMessage(content="saved"),
            ]
        ),
        mcp=mcp,
        checkpoint_path=checkpoint_path,
        run_id_factory=lambda: "run-1",
    )
    pending = await first.start("change")
    interrupted_checkpoint = checkpoint_path.read_bytes()
    decision = ResumeDecision(
        action="approve",
        digest=pending.pending_approval.digest,
    )

    assert (await first.resume("run-1", decision)).final_text == "saved"

    checkpoint_path.write_bytes(interrupted_checkpoint)
    replay_model = FakeChatModel([AIMessage(content="replay handled")])
    replay = LangGraphReActAgent(
        model=replay_model,
        mcp=mcp,
        checkpoint_path=checkpoint_path,
    )
    outcome = await replay.resume("run-1", decision)

    assert outcome.final_text == "replay handled"
    assert mcp.calls == [
        ("write_file", {"path": "b.py", "content": "new"})
    ]
    duplicate = json.loads(str(replay_model.seen_messages[-1][-1].content))
    assert duplicate["error"] == "duplicate_side_effect_call"
    assert duplicate["status"] == "executed"


@pytest.mark.asyncio
async def test_unfinished_claim_is_reported_uncertain_and_never_dispatched(
    tmp_path,
) -> None:
    checkpoint_path = tmp_path / "langgraph.json"
    mcp = GraphMCP()
    first = LangGraphReActAgent(
        model=FakeChatModel(
            [
                ai_with_calls(
                    tool_call(
                        "call-write",
                        "write_file",
                        {"path": "b.py", "content": "new"},
                    )
                )
            ]
        ),
        mcp=mcp,
        checkpoint_path=checkpoint_path,
        run_id_factory=lambda: "run-1",
    )
    pending = await first.start("change")
    ledger = first.side_effect_ledger
    assert ledger.claim("run-1", "call-write").outcome.value == "granted"
    resumed_model = FakeChatModel([AIMessage(content="manual check required")])
    resumed = LangGraphReActAgent(
        model=resumed_model,
        mcp=mcp,
        checkpoint_path=checkpoint_path,
    )

    outcome = await resumed.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=pending.pending_approval.digest,
        ),
    )

    assert outcome.final_text == "manual check required"
    assert mcp.calls == []
    uncertain = json.loads(str(resumed_model.seen_messages[-1][-1].content))
    assert uncertain["error"] == "side_effect_status_uncertain"
    assert uncertain["status"] == "claimed"
    assert "by hand" in uncertain["action_required"]


@pytest.mark.asyncio
async def test_tool_error_is_a_controlled_observation(tmp_path) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            ai_with_calls(tool_call("call-read", "read_file", {"path": "a.py"})),
            AIMessage(content="could not inspect"),
        ],
        mcp=FailingMCP(),
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "could not inspect"
    assert mcp.calls == [("read_file", {"path": "a.py"})]
    failure = model.seen_messages[-1][-1]
    assert isinstance(failure, ToolMessage)
    assert failure.status == "error"
    assert "sandbox unavailable" in str(failure.content)


@pytest.mark.asyncio
async def test_sensitive_tool_error_is_uncertain_and_never_retried(tmp_path) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            ai_with_calls(
                tool_call(
                    "call-write",
                    "write_file",
                    {"path": "b.py", "content": "new"},
                )
            ),
            AIMessage(content="manual check required"),
        ],
        mcp=FailingMCP(),
    )
    pending = await agent.start("change")

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=pending.pending_approval.digest,
        ),
    )

    assert outcome.final_text == "manual check required"
    assert mcp.calls == [
        ("write_file", {"path": "b.py", "content": "new"})
    ]
    uncertain = json.loads(str(model.seen_messages[-1][-1].content))
    assert uncertain["error"] == "side_effect_outcome_uncertain"
    assert "not retried" in uncertain["action_required"]


@pytest.mark.asyncio
async def test_budgets_stop_before_excess_model_or_tool_calls(tmp_path) -> None:
    model_limited, _, model_mcp = make_agent(
        tmp_path / "model",
        [
            ai_with_calls(tool_call("call-read", "read_file", {"path": "a.py"})),
        ],
        max_model_calls=1,
    )
    tool_limited, _, tool_mcp = make_agent(
        tmp_path / "tool",
        [
            ai_with_calls(
                tool_call("call-a", "read_file", {"path": "a.py"}),
                tool_call("call-b", "read_file", {"path": "b.py"}),
            )
        ],
        max_tool_calls=1,
    )

    model_outcome = await model_limited.start("inspect")
    tool_outcome = await tool_limited.start("inspect")

    assert "model call budget exceeded" in model_outcome.final_text
    assert model_mcp.calls == [("read_file", {"path": "a.py"})]
    assert "tool call budget exceeded" in tool_outcome.final_text
    assert tool_mcp.calls == []


@pytest.mark.asyncio
async def test_strict_mcp_schema_and_checkpoint_secret_guard_are_reused(
    tmp_path,
) -> None:
    invalid = GraphMCP()
    definitions = await invalid.list_function_tools()
    definitions[0]["strict"] = False
    invalid.list_function_tools = lambda: _async_value(definitions)
    invalid_agent = LangGraphReActAgent(
        model=FakeChatModel([AIMessage(content="unused")]),
        mcp=invalid,
        checkpoint_path=tmp_path / "invalid.json",
    )

    with pytest.raises(ValueError, match="strict"):
        await invalid_agent.start("inspect")

    secret_agent, _, _ = make_agent(
        tmp_path,
        [
            AIMessage(
                content=[
                    {
                        "type": "text",
                        "text": "password=not-for-disk",
                    }
                ]
            )
        ],
    )
    with pytest.raises(ValueError, match="secret"):
        await secret_agent.start("inspect")


def test_langgraph_cli_help_needs_no_api_key() -> None:
    project = Path(__file__).parents[1]

    completed = subprocess.run(
        [sys.executable, str(project / "langgraph_agent.py"), "--help"],
        cwd=project,
        env={},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "LangGraph" in completed.stdout
