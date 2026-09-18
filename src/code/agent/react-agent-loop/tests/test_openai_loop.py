from __future__ import annotations

import asyncio
import json
import multiprocessing
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agent_core.checkpoints import JsonCheckpointStore
from agent_core.contracts import ToolProposal
from agent_core.mcp_adapter import MCPToolClient
from agent_core.openai_loop import (
    BudgetExceeded,
    OpenAIReActAgent,
    ResponsesRetryError,
    ResumeDecision,
)
from agent_core.policy import approval_digest
from tests.fakes import (
    FakeMCPClient,
    FakeOpenAIClient,
    function_call,
    response,
    text_item,
)


class ProcessBlockingMCP(FakeMCPClient):
    def __init__(
        self,
        side_effect_path: str,
        entered: Any,
        release: Any,
    ) -> None:
        super().__init__()
        self.side_effect_path = side_effect_path
        self.entered = entered
        self.release = release

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        with Path(self.side_effect_path).open("a", encoding="utf-8") as marker:
            marker.write(f"{name}\n")
            marker.flush()
        self.entered.set()
        self.release.wait(5)
        return '{"written":true}'


def resume_in_process(
    runs_path: str,
    side_effect_path: str,
    digest: str,
    entered: Any,
    release: Any,
    results: Any,
) -> None:
    agent = OpenAIReActAgent(
        client=FakeOpenAIClient([response("resp-2", text_item("done"))]),
        mcp=ProcessBlockingMCP(side_effect_path, entered, release),
        checkpoints=JsonCheckpointStore(runs_path),
        model="test-model",
    )
    try:
        outcome = asyncio.run(
            agent.resume(
                "run-1",
                ResumeDecision(action="approve", digest=digest),
            )
        )
        results.put(("ok", outcome.final_text))
    except Exception as error:
        results.put((type(error).__name__, str(error)))


class FakeSession:
    def __init__(self, schema: dict | None = None, *, is_error: bool = False) -> None:
        self.schema = schema or {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        }
        self.is_error = is_error

    async def list_tools(self):
        tool = SimpleNamespace(
            name="read_file",
            description="Read a file.",
            inputSchema=self.schema,
        )
        return SimpleNamespace(tools=[tool])

    async def call_tool(self, name, arguments):
        return SimpleNamespace(
            isError=self.is_error,
            structuredContent={"name": name, "arguments": arguments},
            content=[],
        )


@pytest.mark.asyncio
async def test_adapter_emits_strict_responses_tools_and_json_results() -> None:
    adapter = MCPToolClient(FakeSession())

    assert await adapter.list_function_tools() == [
        {
            "type": "function",
            "name": "read_file",
            "description": "Read a file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
            "strict": True,
        }
    ]
    assert json.loads(await adapter.call("read_file", {"path": "a.py"})) == {
        "is_error": False,
        "content": {
            "arguments": {"path": "a.py"},
            "name": "read_file",
        },
    }


@pytest.mark.asyncio
async def test_adapter_rejects_schema_that_cannot_be_strictly_preserved() -> None:
    adapter = MCPToolClient(
        FakeSession(
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": [],
                "additionalProperties": False,
            }
        )
    )

    with pytest.raises(ValueError, match="required"):
        await adapter.list_function_tools()


@pytest.mark.asyncio
async def test_adapter_preserves_error_flag_with_structured_content() -> None:
    adapter = MCPToolClient(FakeSession(is_error=True))

    result = json.loads(await adapter.call("read_file", {"path": "missing"}))

    assert result["is_error"] is True
    assert result["content"]["arguments"] == {"path": "missing"}


@pytest.mark.asyncio
@pytest.mark.parametrize("root_type", ["string", "array"])
async def test_adapter_rejects_non_object_function_parameter_roots(
    root_type: str,
) -> None:
    schema = {"type": root_type}
    if root_type == "array":
        schema["items"] = {"type": "string"}
    adapter = MCPToolClient(FakeSession(schema))

    with pytest.raises(ValueError, match="root.*object"):
        await adapter.list_function_tools()


def make_agent(tmp_path, scripted, **limits):
    client = FakeOpenAIClient(scripted)
    mcp = FakeMCPClient()
    agent = OpenAIReActAgent(
        client=client,
        mcp=mcp,
        checkpoints=JsonCheckpointStore(tmp_path / ".runs"),
        model="test-model",
        run_id_factory=lambda: "run-1",
        **limits,
    )
    return agent, client, mcp


@pytest.mark.asyncio
async def test_direct_answer_collects_text_from_all_output_items(tmp_path) -> None:
    agent, client, _ = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                SimpleNamespace(type="reasoning"),
                text_item("first"),
                text_item(" second"),
            )
        ],
    )

    outcome = await agent.start("hello")

    assert outcome.final_text == "first second"
    assert client.responses.requests[0]["input"] == "hello"


@pytest.mark.asyncio
async def test_read_only_calls_submit_exact_call_ids_and_response_chain(tmp_path) -> None:
    agent, client, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call("call-1", "list_files", '{"path":"."}'),
                function_call("call-2", "read_file", '{"path":"a.py"}'),
            ),
            response("resp-2", text_item("done")),
        ],
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "done"
    assert mcp.calls == [
        ("list_files", {"path": "."}),
        ("read_file", {"path": "a.py"}),
    ]
    follow_up = client.responses.requests[1]
    assert follow_up["previous_response_id"] == "resp-1"
    assert [item["call_id"] for item in follow_up["input"]] == ["call-1", "call-2"]
    assert {item["type"] for item in follow_up["input"]} == {
        "function_call_output"
    }


@pytest.mark.asyncio
async def test_sensitive_batch_pauses_before_any_tool_side_effect(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call("call-read", "read_file", '{"path":"a.py"}'),
                function_call(
                    "call-write",
                    "write_file",
                    '{"path":"b.py","content":"x"}',
                ),
            )
        ],
    )

    outcome = await agent.start("change")

    assert outcome.pending_approval is not None
    assert outcome.pending_approval.proposal.call_id == "call-write"
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_approve_executes_pending_once_then_continues_batch(tmp_path) -> None:
    agent, client, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call("call-read", "read_file", '{"path":"a.py"}'),
                function_call(
                    "call-write",
                    "write_file",
                    '{"path":"b.py","content":"x"}',
                ),
            ),
            response("resp-2", text_item("saved")),
        ],
    )
    pending = await agent.start("change")

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=pending.pending_approval.digest,
        ),
    )

    assert outcome.final_text == "saved"
    assert mcp.calls == [
        ("read_file", {"path": "a.py"}),
        ("write_file", {"path": "b.py", "content": "x"}),
    ]
    assert [item["call_id"] for item in client.responses.requests[1]["input"]] == [
        "call-read",
        "call-write",
    ]

    with pytest.raises(ValueError, match="pending"):
        await agent.resume(
            "run-1",
            ResumeDecision(
                action="approve",
                digest=pending.pending_approval.digest,
            ),
        )
    assert len(mcp.calls) == 2


@pytest.mark.asyncio
async def test_reject_becomes_tool_observation_without_execution(tmp_path) -> None:
    agent, client, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call(
                    "call-write",
                    "write_file",
                    '{"path":"b.py","content":"x"}',
                ),
            ),
            response("resp-2", text_item("not changed")),
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
    observation = json.loads(client.responses.requests[1]["input"][0]["output"])
    assert observation == {"error": "rejected", "reason": "not now"}


@pytest.mark.asyncio
async def test_edited_write_binds_and_executes_edited_arguments(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call(
                    "call-write",
                    "write_file",
                    '{"path":"b.py","content":"old"}',
                ),
            ),
            response("resp-2", text_item("saved")),
        ],
    )
    pending = await agent.start("change")

    await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=pending.pending_approval.digest,
            arguments={"path": "b.py", "content": "edited"},
        ),
    )

    assert mcp.calls == [("write_file", {"path": "b.py", "content": "edited"})]


@pytest.mark.asyncio
async def test_edited_arguments_must_match_the_function_schema(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call(
                    "call-write",
                    "write_file",
                    '{"path":"b.py","content":"old"}',
                ),
            )
        ],
    )
    pending = await agent.start("change")

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
async def test_edited_approval_rebinds_digest_before_any_dispatch(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call(
                    "call-first",
                    "write_file",
                    '{"path":"a.py","content":"old"}',
                ),
                function_call(
                    "call-second",
                    "write_file",
                    '{"path":"b.py","content":"b"}',
                ),
            )
        ],
    )
    first = await agent.start("change both")

    second = await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=first.pending_approval.digest,
            arguments={"path": "a.py", "content": "edited"},
        ),
    )

    expected = approval_digest(
        ToolProposal(
            "call-first",
            "write_file",
            {"path": "a.py", "content": "edited"},
        )
    )
    state = agent._checkpoints.load("run-1")
    assert state.approved_call_digests["call-first"] == expected
    assert second.pending_approval.proposal.call_id == "call-second"
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_multiple_sensitive_calls_pause_and_execute_sequentially(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call(
                    "call-first",
                    "write_file",
                    '{"path":"a.py","content":"a"}',
                ),
                function_call(
                    "call-second",
                    "write_file",
                    '{"path":"b.py","content":"b"}',
                ),
            )
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

    assert mcp.calls == []
    assert second.pending_approval.proposal.call_id == "call-second"
    state = agent._checkpoints.load("run-1")
    assert set(state.response_state) == {"response_id", "calls"}
    assert "outputs" not in state.response_state


@pytest.mark.asyncio
async def test_dispatch_revalidates_approved_digest_after_checkpoint_tampering(
    tmp_path,
) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call(
                    "call-first",
                    "write_file",
                    '{"path":"a.py","content":"a"}',
                ),
                function_call(
                    "call-second",
                    "write_file",
                    '{"path":"b.py","content":"b"}',
                ),
            )
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
    checkpoint_path = tmp_path / ".runs" / "run-1.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["response_state"]["calls"][0]["arguments"] = (
        '{"path":"a.py","content":"tampered"}'
    )
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")

    with pytest.raises(ValueError, match="digest binding"):
        await agent.resume(
            "run-1",
            ResumeDecision(
                action="approve",
                digest=second.pending_approval.digest,
            ),
        )

    assert mcp.calls == []


@pytest.mark.asyncio
async def test_stale_digest_is_rejected_without_side_effect(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call(
                    "call-write",
                    "write_file",
                    '{"path":"b.py","content":"x"}',
                ),
            )
        ],
    )
    await agent.start("change")

    with pytest.raises(ValueError, match="digest"):
        await agent.resume(
            "run-1",
            ResumeDecision(action="approve", digest="stale"),
        )
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_concurrent_resumes_dispatch_side_effect_at_most_once(tmp_path) -> None:
    runs_path = tmp_path / ".runs"
    agent, _, _ = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call(
                    "call-write",
                    "write_file",
                    '{"path":"b.py","content":"x"}',
                ),
            )
        ],
    )
    pending = await agent.start("change")
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    release = context.Event()
    results = context.Queue()
    side_effect_path = tmp_path / "dispatches.txt"
    arguments = (
        str(runs_path),
        str(side_effect_path),
        pending.pending_approval.digest,
        entered,
        release,
        results,
    )
    first = context.Process(target=resume_in_process, args=arguments)
    second = context.Process(target=resume_in_process, args=arguments)

    first.start()
    assert entered.wait(5)
    second.start()
    second.join(1)
    release.set()
    first.join(5)
    second.join(5)

    assert first.exitcode == 0
    assert second.exitcode == 0
    assert side_effect_path.read_text(encoding="utf-8").splitlines() == [
        "write_file"
    ]
    outcomes = sorted([results.get(timeout=1), results.get(timeout=1)])
    assert outcomes == [
        ("RunClaimedError", "run 'run-1' is already claimed"),
        ("ok", "done"),
    ]


@pytest.mark.asyncio
async def test_unknown_and_malformed_calls_return_errors_to_model(tmp_path) -> None:
    agent, client, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call("call-unknown", "delete_all", "{}"),
                function_call("call-bad", "read_file", "{"),
            ),
            response("resp-2", text_item("recovered")),
        ],
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "recovered"
    assert mcp.calls == []
    outputs = {
        item["call_id"]: json.loads(item["output"])
        for item in client.responses.requests[1]["input"]
    }
    assert outputs["call-unknown"]["error"] == "tool_denied"
    assert outputs["call-bad"]["error"] == "malformed_arguments"


@pytest.mark.asyncio
async def test_duplicate_call_id_executes_only_once(tmp_path) -> None:
    agent, client, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call("same", "read_file", '{"path":"a.py"}'),
                function_call("same", "read_file", '{"path":"other.py"}'),
            ),
            response("resp-2", text_item("done")),
        ],
    )

    await agent.start("inspect")

    assert mcp.calls == [("read_file", {"path": "a.py"})]
    assert [item["call_id"] for item in client.responses.requests[1]["input"]] == [
        "same"
    ]


@pytest.mark.asyncio
async def test_max_turns_stops_before_another_model_call(tmp_path) -> None:
    agent, client, _ = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call("call-1", "read_file", '{"path":"a.py"}'),
            )
        ],
        max_turns=1,
    )

    with pytest.raises(BudgetExceeded, match="turn"):
        await agent.start("inspect")
    assert len(client.responses.requests) == 1


@pytest.mark.asyncio
async def test_max_tool_calls_stops_before_tool_execution(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call("call-1", "read_file", '{"path":"a.py"}'),
                function_call("call-2", "read_file", '{"path":"b.py"}'),
            )
        ],
        max_tool_calls=1,
    )

    with pytest.raises(BudgetExceeded, match="tool"):
        await agent.start("inspect")
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_responses_api_retries_then_exhausts(tmp_path) -> None:
    agent, client, _ = make_agent(
        tmp_path,
        [RuntimeError("temporary"), RuntimeError("still failing")],
        max_retries=1,
    )

    with pytest.raises(ResponsesRetryError, match="2 attempts"):
        await agent.start("hello")
    assert len(client.responses.requests) == 2


def test_pure_openai_cli_help_needs_no_api_key() -> None:
    project = Path(__file__).parents[1]

    completed = subprocess.run(
        [sys.executable, str(project / "pure_openai.py"), "--help"],
        cwd=project,
        env={},
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "OpenAI Responses API" in completed.stdout
