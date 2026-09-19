from __future__ import annotations

import json
import subprocess
import sys
import time
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
from agent_core.openai_loop import BudgetExceeded, ResponsesRetryError, ResumeDecision
from agent_core.policy import ToolPolicy
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
        next_result = self._scripted.popleft()
        if isinstance(next_result, BaseException):
            raise next_result
        return ChatResult(
            generations=[ChatGeneration(message=next_result)]
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


class ErrorEnvelopeMCP(GraphMCP):
    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return json.dumps(
            {
                "is_error": True,
                "content": {"message": "tool reported failure"},
            }
        )


class LargeOutputMCP(GraphMCP):
    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return json.dumps(
            {
                "is_error": False,
                "content": {"text": "x" * 200},
            }
        )


class LargeErrorOutputMCP(GraphMCP):
    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return json.dumps(
            {
                "is_error": True,
                "content": {"message": "x" * 200},
            }
        )


class ScriptedMonotonic:
    def __init__(self, values: list[float]) -> None:
        self._values = deque(values)

    def __call__(self) -> float:
        return self._values.popleft()


class SlowChatModel(FakeChatModel):
    def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
        time.sleep(0.05)
        return super()._generate(*args, **kwargs)


class RecordingPolicy(ToolPolicy):
    def __init__(self) -> None:
        self.approved_arguments: list[dict[str, Any]] = []

    def approval_for(self, proposal):
        self.approved_arguments.append(to_json_value(proposal.arguments))
        return super().approval_for(proposal)


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

    assert calls[0][0] == {
        "messages": [{"role": "user", "content": "change"}],
        "remaining_timeout_seconds": 120,
    }
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
    policy = RecordingPolicy()
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
        policy=policy,
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
    assert policy.approved_arguments[0] == {
        "path": "b.py",
        "content": "old",
    }
    assert policy.approved_arguments[-2:] == [
        {"path": "b.py", "content": "edited"},
        {"path": "b.py", "content": "edited"},
    ]


@pytest.mark.asyncio
async def test_dispatch_rejects_tampered_approved_arguments_and_digest(
    tmp_path,
) -> None:
    agent, _, mcp = make_agent(tmp_path, [AIMessage(content="unused")])
    await agent.build_graph()

    observation = await agent._execute_call(
        "run-1",
        {
            "call_id": "call-write",
            "tool_name": "write_file",
            "arguments": {"path": "b.py", "content": "tampered"},
            "risk": "approval",
            "approval_status": "approved",
            "approval_digest": "digest-for-old-arguments",
            "rejection_reason": "",
        },
    )

    assert json.loads(observation["content"])["error"] == "approval_binding_invalid"
    assert mcp.calls == []


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
async def test_adapter_error_envelope_becomes_error_tool_message(tmp_path) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            ai_with_calls(tool_call("call-read", "read_file", {"path": "a.py"})),
            AIMessage(content="could not inspect"),
        ],
        mcp=ErrorEnvelopeMCP(),
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "could not inspect"
    assert mcp.calls == [("read_file", {"path": "a.py"})]
    failure = model.seen_messages[-1][-1]
    assert isinstance(failure, ToolMessage)
    assert failure.status == "error"
    assert "tool reported failure" in str(failure.content)


@pytest.mark.asyncio
async def test_sensitive_adapter_error_finishes_failed_and_is_not_retried(
    tmp_path,
) -> None:
    mcp = ErrorEnvelopeMCP()
    agent, model, _ = make_agent(
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
        mcp=mcp,
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
    assert agent.side_effect_ledger.status("run-1", "call-write") == "failed"
    failure = json.loads(str(model.seen_messages[-1][-1].content))
    assert failure["error"] == "side_effect_tool_error"
    assert failure["status"] == "failed"
    assert "not retried" in failure["action_required"]


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
async def test_total_timeout_uses_shared_budget_exception(tmp_path) -> None:
    agent = LangGraphReActAgent(
        model=SlowChatModel([AIMessage(content="too late")]),
        mcp=GraphMCP(),
        checkpoint_path=tmp_path / "timeout.json",
        timeout_seconds=0.001,
        run_id_factory=lambda: "run-timeout",
    )

    with pytest.raises(BudgetExceeded, match="total timeout"):
        await agent.start("inspect")
    graph = await agent.build_graph()
    snapshot = await graph.aget_state(
        {"configurable": {"thread_id": "run-timeout"}}
    )
    assert snapshot.values["remaining_timeout_seconds"] == 0


@pytest.mark.asyncio
async def test_timeout_budget_accumulates_across_resumes_without_human_wait(
    tmp_path,
) -> None:
    clock = ScriptedMonotonic(
        [
            0.0,
            2.0,
            10_000.0,
            10_003.0,
            20_000.0,
            20_006.0,
        ]
    )
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
                tool_call(
                    "call-third",
                    "write_file",
                    {"path": "c.py", "content": "c"},
                ),
            )
        ],
        timeout_seconds=10,
        monotonic=clock,
    )

    first = await agent.start("change three")
    second = await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=first.pending_approval.digest,
        ),
    )
    with pytest.raises(BudgetExceeded, match="total timeout"):
        await agent.resume(
            "run-1",
            ResumeDecision(
                action="approve",
                digest=second.pending_approval.digest,
            ),
        )

    graph = await agent.build_graph()
    snapshot = await graph.aget_state(
        {"configurable": {"thread_id": "run-1"}}
    )
    assert snapshot.values["remaining_timeout_seconds"] == 0
    assert mcp.calls == []
    pending = await agent.pending_approval("run-1")
    assert pending is not None
    with pytest.raises(BudgetExceeded, match="total timeout"):
        await agent.resume(
            "run-1",
            ResumeDecision(
                action="approve",
                digest=pending.digest,
            ),
        )


@pytest.mark.asyncio
async def test_token_budget_accumulates_declared_usage_only(tmp_path) -> None:
    over_budget = AIMessage(
        content="large",
        usage_metadata={
            "input_tokens": 6,
            "output_tokens": 5,
            "total_tokens": 11,
        },
    )
    agent, _, _ = make_agent(
        tmp_path,
        [over_budget],
        max_token_budget=10,
    )

    with pytest.raises(BudgetExceeded, match="token budget"):
        await agent.start("inspect")


@pytest.mark.asyncio
async def test_transient_model_errors_retry_with_bounded_exponential_backoff(
    tmp_path,
) -> None:
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    agent, model, _ = make_agent(
        tmp_path,
        [
            RuntimeError("temporary-1"),
            RuntimeError("temporary-2"),
            AIMessage(content="recovered"),
        ],
        max_model_retries=2,
        retry_initial_delay=0.5,
        sleep=fake_sleep,
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "recovered"
    assert len(model.seen_messages) == 3
    assert delays == [0.5, 1.0]


@pytest.mark.asyncio
async def test_exhausted_model_retries_raise_documented_error(tmp_path) -> None:
    async def no_sleep(delay: float) -> None:
        return None

    agent, model, _ = make_agent(
        tmp_path,
        [RuntimeError("temporary"), RuntimeError("still unavailable")],
        max_model_retries=1,
        sleep=no_sleep,
        timeout_seconds=10,
        monotonic=ScriptedMonotonic([0.0, 2.0]),
    )

    with pytest.raises(ResponsesRetryError, match="2 attempts"):
        await agent.start("inspect")
    assert len(model.seen_messages) == 2
    graph = await agent.build_graph()
    snapshot = await graph.aget_state(
        {"configurable": {"thread_id": "run-1"}}
    )
    assert snapshot.values["remaining_timeout_seconds"] == 8


@pytest.mark.asyncio
async def test_tool_output_is_bounded_and_marked_truncated(tmp_path) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            ai_with_calls(tool_call("call-read", "read_file", {"path": "a.py"})),
            AIMessage(content="reported truncation"),
        ],
        mcp=LargeOutputMCP(),
        max_output_chars=80,
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "reported truncation"
    assert len(str(model.seen_messages[-1][-1].content)) <= 80
    truncated = json.loads(str(model.seen_messages[-1][-1].content))
    assert truncated["error"] == "tool_output_truncated"
    assert truncated["status"] == "success"
    assert truncated["truncated"] is True
    assert mcp.calls == [("read_file", {"path": "a.py"})]


@pytest.mark.asyncio
async def test_sensitive_output_truncation_keeps_executed_ledger_status(
    tmp_path,
) -> None:
    mcp = LargeOutputMCP()
    agent, model, _ = make_agent(
        tmp_path,
        [
            ai_with_calls(
                tool_call(
                    "call-write",
                    "write_file",
                    {"path": "b.py", "content": "new"},
                )
            ),
            AIMessage(content="reported truncation"),
        ],
        mcp=mcp,
        max_output_chars=80,
    )
    pending = await agent.start("change")

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=pending.pending_approval.digest,
        ),
    )

    assert outcome.final_text == "reported truncation"
    assert agent.side_effect_ledger.status("run-1", "call-write") == "executed"
    truncated = json.loads(str(model.seen_messages[-1][-1].content))
    assert truncated["error"] == "tool_output_truncated"
    assert truncated["status"] == "success"
    assert truncated["truncated"] is True
    assert mcp.calls == [
        ("write_file", {"path": "b.py", "content": "new"})
    ]


@pytest.mark.asyncio
async def test_error_output_truncation_preserves_error_status(tmp_path) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            ai_with_calls(tool_call("call-read", "read_file", {"path": "a.py"})),
            AIMessage(content="reported error"),
        ],
        mcp=LargeErrorOutputMCP(),
        max_output_chars=80,
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "reported error"
    rendered = str(model.seen_messages[-1][-1].content)
    assert len(rendered) <= 80
    truncated = json.loads(rendered)
    assert truncated == {
        "error": "tool_output_truncated",
        "status": "error",
        "truncated": True,
    }
    assert model.seen_messages[-1][-1].status == "error"
    assert mcp.calls == [("read_file", {"path": "a.py"})]


@pytest.mark.asyncio
async def test_sensitive_error_truncation_finishes_failed(tmp_path) -> None:
    mcp = LargeErrorOutputMCP()
    agent, model, _ = make_agent(
        tmp_path,
        [
            ai_with_calls(
                tool_call(
                    "call-write",
                    "write_file",
                    {"path": "b.py", "content": "new"},
                )
            ),
            AIMessage(content="reported error"),
        ],
        mcp=mcp,
        max_output_chars=80,
    )
    pending = await agent.start("change")

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=pending.pending_approval.digest,
        ),
    )

    assert outcome.final_text == "reported error"
    assert agent.side_effect_ledger.status("run-1", "call-write") == "failed"
    truncated = json.loads(str(model.seen_messages[-1][-1].content))
    assert truncated["status"] == "error"
    assert mcp.calls == [
        ("write_file", {"path": "b.py", "content": "new"})
    ]


@pytest.mark.asyncio
async def test_tiny_output_budget_terminates_without_oversized_observation(
    tmp_path,
) -> None:
    mcp = LargeOutputMCP()
    agent, _, _ = make_agent(
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
        mcp=mcp,
        max_output_chars=20,
    )
    pending = await agent.start("change")

    with pytest.raises(BudgetExceeded, match="tool output budget"):
        await agent.resume(
            "run-1",
            ResumeDecision(
                action="approve",
                digest=pending.pending_approval.digest,
            ),
        )

    assert agent.side_effect_ledger.status("run-1", "call-write") == "executed"
    assert mcp.calls == [
        ("write_file", {"path": "b.py", "content": "new"})
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_call",
    [
        {
            "type": "invalid_tool_call",
            "id": None,
            "name": "read_file",
            "args": '{"path":"a.py"}',
            "error": "missing call id",
        },
        {
            "type": "invalid_tool_call",
            "id": "call-bad-name",
            "name": None,
            "args": '{"path":"a.py"}',
            "error": "missing tool name",
        },
        {
            "type": "invalid_tool_call",
            "id": "call-bad-args",
            "name": "read_file",
            "args": "not-json",
            "error": "invalid arguments",
        },
    ],
)
async def test_invalid_model_tool_calls_become_structured_observations(
    tmp_path,
    invalid_call: dict[str, Any],
) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            AIMessage(content="", invalid_tool_calls=[invalid_call]),
            AIMessage(content="handled invalid call"),
        ],
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "handled invalid call"
    assert mcp.calls == []
    observation = model.seen_messages[-1][-1]
    assert isinstance(observation, ToolMessage)
    assert observation.status == "error"
    assert json.loads(str(observation.content))["error"] == "malformed_tool_call"


@pytest.mark.asyncio
async def test_schema_invalid_arguments_become_observation_not_exception(
    tmp_path,
) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            ai_with_calls(tool_call("call-read", "read_file", {})),
            AIMessage(content="handled invalid schema"),
        ],
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "handled invalid schema"
    assert mcp.calls == []
    observation = model.seen_messages[-1][-1]
    assert json.loads(str(observation.content))["error"] == "malformed_arguments"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "corrupt_call",
    [
        {"tool_name": "read_file", "arguments": {"path": "a.py"}},
        {"call_id": "call-no-name", "arguments": {"path": "a.py"}},
        {
            "call_id": "call-no-args",
            "tool_name": "read_file",
            "arguments": "not-an-object",
        },
        {
            "call_id": "call-no-schema",
            "tool_name": "unknown_tool",
            "arguments": {},
            "risk": "read_only",
        },
    ],
)
async def test_corrupt_checkpoint_calls_fail_closed_as_observations(
    tmp_path,
    corrupt_call: dict[str, Any],
) -> None:
    agent, _, mcp = make_agent(tmp_path, [AIMessage(content="unused")])
    await agent.build_graph()

    observation = await agent._execute_call("run-1", corrupt_call)

    assert observation["error"] is True
    assert json.loads(observation["content"])["error"] in {
        "malformed_tool_call",
        "malformed_arguments",
    }
    assert mcp.calls == []


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
