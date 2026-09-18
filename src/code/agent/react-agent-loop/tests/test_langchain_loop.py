from __future__ import annotations

import subprocess
import sys
from collections import deque
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from agent_core.contracts import to_json_value
from agent_core.langchain_loop import LangChainReActAgent
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
        return "react-agent-loop-fake"

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


class FakeLangChainMCP(FakeMCPClient):
    async def list_function_tools(self) -> list[dict[str, Any]]:
        tools = await super().list_function_tools()
        for tool in tools:
            if tool["name"] == "write_file":
                tool["annotations"] = {"readOnlyHint": True}
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
                "annotations": {"readOnlyHint": True},
            }
        )
        return tools


class FailingMCP(FakeLangChainMCP):
    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        raise RuntimeError("sandbox unavailable")


def tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> AIMessage:
    return AIMessage(
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


def make_agent(tmp_path, scripted, *, mcp=None, **limits):
    model = FakeChatModel(scripted)
    mcp = mcp or FakeLangChainMCP()
    agent = LangChainReActAgent(
        model=model,
        mcp=mcp,
        checkpoint_path=tmp_path / "langchain.sqlite",
        run_id_factory=lambda: "run-1",
        **limits,
    )
    return agent, model, mcp


@pytest.mark.asyncio
async def test_read_tool_executes_automatically_and_returns_shared_outcome(
    tmp_path,
) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            tool_call("call-read", "read_file", {"path": "a.py"}),
            AIMessage(content="done"),
        ],
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "done"
    assert outcome.run_id == "run-1"
    assert mcp.calls == [("read_file", {"path": "a.py"})]
    observation = model.seen_messages[1][-1]
    assert isinstance(observation, ToolMessage)
    assert observation.tool_call_id == "call-read"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "arguments", "preview"),
    [
        ("write_file", {"path": "b.py", "content": "new"}, "new"),
        ("run_command", {"argv": ["pytest", "-q"], "cwd": "."}, ["pytest", "-q"]),
    ],
)
async def test_local_policy_interrupts_sensitive_tools_despite_read_only_annotation(
    tmp_path,
    name: str,
    arguments: dict[str, Any],
    preview: str | list[str],
) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [tool_call("call-sensitive", name, arguments)],
    )

    outcome = await agent.start("change")

    assert outcome.pending_approval is not None
    assert outcome.pending_approval.proposal.tool_name == name
    assert to_json_value(outcome.pending_approval.proposal.arguments) == arguments
    assert outcome.pending_approval.preview == preview
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_new_agent_instance_resumes_same_persistent_thread_and_approves(
    tmp_path,
) -> None:
    database = tmp_path / "langchain.sqlite"
    mcp = FakeLangChainMCP()
    first_model = FakeChatModel(
        [tool_call("call-write", "write_file", {"path": "b.py", "content": "new"})]
    )
    first_agent = LangChainReActAgent(
        model=first_model,
        mcp=mcp,
        checkpoint_path=database,
        run_id_factory=lambda: "run-1",
    )
    pending = await first_agent.start("change")
    second_agent = LangChainReActAgent(
        model=FakeChatModel([AIMessage(content="saved")]),
        mcp=mcp,
        checkpoint_path=database,
    )

    outcome = await second_agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=pending.pending_approval.digest,
        ),
    )

    assert outcome.final_text == "saved"
    assert outcome.run_id == "run-1"
    assert mcp.calls == [("write_file", {"path": "b.py", "content": "new"})]


@pytest.mark.asyncio
async def test_reject_is_returned_to_model_without_tool_execution(tmp_path) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            tool_call("call-write", "write_file", {"path": "b.py", "content": "new"}),
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
    rejection = model.seen_messages[1][-1]
    assert isinstance(rejection, ToolMessage)
    assert rejection.status == "error"
    assert "not now" in str(rejection.content)


@pytest.mark.asyncio
async def test_edit_executes_only_revalidated_arguments(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            tool_call("call-write", "write_file", {"path": "b.py", "content": "old"}),
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
    assert mcp.calls == [("write_file", {"path": "b.py", "content": "edited"})]


@pytest.mark.asyncio
async def test_stale_digest_is_rejected_before_dispatch(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [tool_call("call-write", "write_file", {"path": "b.py", "content": "new"})],
    )
    await agent.start("change")

    with pytest.raises(ValueError, match="digest"):
        await agent.resume(
            "run-1",
            ResumeDecision(action="approve", digest="stale"),
        )

    assert mcp.calls == []


@pytest.mark.asyncio
async def test_multiple_sensitive_calls_are_approved_sequentially_before_dispatch(
    tmp_path,
) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-first",
                        "name": "write_file",
                        "args": {"path": "a.py", "content": "a"},
                        "type": "tool_call",
                    },
                    {
                        "id": "call-second",
                        "name": "write_file",
                        "args": {"path": "b.py", "content": "b"},
                        "type": "tool_call",
                    },
                ],
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
async def test_tool_failure_becomes_controlled_observation(tmp_path) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            tool_call("call-read", "read_file", {"path": "a.py"}),
            AIMessage(content="could not inspect"),
        ],
        mcp=FailingMCP(),
        max_tool_retries=0,
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "could not inspect"
    assert len(mcp.calls) == 1
    failure = model.seen_messages[1][-1]
    assert isinstance(failure, ToolMessage)
    assert failure.status == "error"
    assert "sandbox unavailable" in str(failure.content)


@pytest.mark.asyncio
async def test_model_call_limit_returns_controlled_outcome(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [tool_call("call-read", "read_file", {"path": "a.py"})],
        max_model_calls=1,
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text is not None
    assert "Model call limit" in outcome.final_text
    assert mcp.calls == [("read_file", {"path": "a.py"})]


@pytest.mark.asyncio
async def test_tool_call_limit_stops_before_excess_tool_execution(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "read_file",
                        "args": {"path": "a.py"},
                        "type": "tool_call",
                    },
                    {
                        "id": "call-2",
                        "name": "read_file",
                        "args": {"path": "b.py"},
                        "type": "tool_call",
                    },
                ],
            )
        ],
        max_tool_calls=1,
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text is not None
    assert "Tool call limit" in outcome.final_text
    assert mcp.calls == []


def test_langchain_cli_help_needs_no_api_key() -> None:
    project = Path(__file__).parents[1]

    completed = subprocess.run(
        [sys.executable, str(project / "langchain_agent.py"), "--help"],
        cwd=project,
        env={},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "LangChain" in completed.stdout
