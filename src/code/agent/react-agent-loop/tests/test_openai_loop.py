from __future__ import annotations

import asyncio
import errno
import json
import multiprocessing
import subprocess
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agent_core import side_effects
from agent_core.checkpoints import JsonCheckpointStore
from agent_core.contracts import ToolProposal
from agent_core.mcp_adapter import MCPToolClient
from agent_core.openai_loop import (
    BudgetExceeded,
    OpenAIReActAgent,
    ResponsesRetryError,
    ResumeDecision,
    is_transient_model_error,
)
from agent_core.policy import approval_digest
from agent_core.side_effects import CheckpointDurabilityError, ClaimOutcome
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


class SimulatedCrash(BaseException):
    """Stands in for a process death between the claim and the terminal record.

    A ``BaseException`` is deliberate: the loop only converts ordinary
    exceptions into a recorded ``failed`` status, so this leaves the ledger
    exactly as an abrupt process death would.
    """


class CrashingMCP(FakeMCPClient):
    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        raise SimulatedCrash("killed mid-dispatch")


class ErroringMCP(FakeMCPClient):
    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return json.dumps(
            {"is_error": True, "content": {"detail": "disk is full"}},
            separators=(",", ":"),
            sort_keys=True,
        )


def write_response() -> SimpleNamespace:
    return response(
        "resp-1",
        function_call("call-write", "write_file", '{"path":"b.py","content":"x"}'),
    )


def make_agent_with(tmp_path, scripted, mcp, **limits):
    agent = OpenAIReActAgent(
        client=FakeOpenAIClient(scripted),
        mcp=mcp,
        checkpoints=JsonCheckpointStore(tmp_path / ".runs"),
        model="test-model",
        run_id_factory=lambda: "run-1",
        **limits,
    )
    return agent, agent._client, mcp


def fail_ledger_durability_after(monkeypatch, *, skip: int) -> None:
    """Report ledger writes as committed but not confirmed durable."""
    real_replace = side_effects.atomic_json_replace
    remaining = skip

    def guarded(path: Path, payload: Any) -> None:
        nonlocal remaining
        real_replace(path, payload)
        if remaining > 0:
            remaining -= 1
            return
        raise CheckpointDurabilityError(errno.EIO, "injected durability failure")

    monkeypatch.setattr(side_effects, "atomic_json_replace", guarded)


@pytest.mark.asyncio
async def test_executed_side_effect_records_a_terminal_ledger_status(
    tmp_path,
) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [write_response(), response("resp-2", text_item("saved"))],
    )
    pending = await agent.start("change")

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(action="approve", digest=pending.pending_approval.digest),
    )

    assert outcome.final_text == "saved"
    assert mcp.calls == [("write_file", {"path": "b.py", "content": "x"})]
    assert agent.side_effect_ledger.status("run-1", "call-write") == "executed"


@pytest.mark.asyncio
async def test_read_only_calls_leave_no_side_effect_ledger_record(tmp_path) -> None:
    agent, _, _ = make_agent(
        tmp_path,
        [
            response(
                "resp-1",
                function_call("call-read", "read_file", '{"path":"a.py"}'),
            ),
            response("resp-2", text_item("done")),
        ],
    )

    await agent.start("inspect")

    assert agent.side_effect_ledger.status("run-1", "call-read") is None


@pytest.mark.asyncio
async def test_claimed_call_is_reported_uncertain_and_never_dispatched(
    tmp_path,
) -> None:
    agent, client, mcp = make_agent(
        tmp_path,
        [write_response(), response("resp-2", text_item("acknowledged"))],
    )
    pending = await agent.start("change")
    # A process that died between the claim and the dispatch leaves exactly
    # this record behind.
    assert (
        agent.side_effect_ledger.claim("run-1", "call-write").outcome
        is ClaimOutcome.GRANTED
    )

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(action="approve", digest=pending.pending_approval.digest),
    )

    assert mcp.calls == []
    assert outcome.final_text == "acknowledged"
    observation = json.loads(client.responses.requests[1]["input"][0]["output"])
    assert observation["error"] == "side_effect_status_uncertain"
    assert observation["status"] == "claimed"
    assert "by hand" in observation["action_required"]
    assert agent.side_effect_ledger.status("run-1", "call-write") == "claimed"


@pytest.mark.asyncio
async def test_crash_between_claim_and_dispatch_keeps_the_run_resumable(
    tmp_path,
) -> None:
    crashing, _, first_mcp = make_agent_with(
        tmp_path,
        [write_response()],
        CrashingMCP(),
    )
    pending = await crashing.start("change")
    decision = ResumeDecision(
        action="approve",
        digest=pending.pending_approval.digest,
    )

    with pytest.raises(SimulatedCrash):
        await crashing.resume("run-1", decision)

    assert len(first_mcp.calls) == 1
    assert crashing.side_effect_ledger.status("run-1", "call-write") == "claimed"

    # The claim is the only record the dispatch wrote, so the checkpoint still
    # holds the pending approval and the stored calls. Without them a resume
    # could only report "run has no pending approval" and the operator would
    # never learn what happened to the write.
    stranded = JsonCheckpointStore(tmp_path / ".runs").load("run-1")
    assert stranded.pending_approval.digest == decision.digest
    assert [call["call_id"] for call in stranded.response_state["calls"]] == [
        "call-write"
    ]

    recovered, client, second_mcp = make_agent_with(
        tmp_path,
        [response("resp-2", text_item("reported"))],
        FakeMCPClient(),
    )
    outcome = await recovered.resume("run-1", decision)

    assert second_mcp.calls == []
    assert outcome.final_text == "reported"
    observation = json.loads(client.responses.requests[0]["input"][0]["output"])
    assert observation["error"] == "side_effect_status_uncertain"
    assert observation["status"] == "claimed"


@pytest.mark.asyncio
async def test_mcp_tool_error_records_failed_and_is_not_retried(tmp_path) -> None:
    agent, client, mcp = make_agent_with(
        tmp_path,
        [write_response(), response("resp-2", text_item("reported"))],
        ErroringMCP(),
    )
    pending = await agent.start("change")
    decision = ResumeDecision(
        action="approve",
        digest=pending.pending_approval.digest,
    )

    outcome = await agent.resume("run-1", decision)

    assert outcome.final_text == "reported"
    assert len(mcp.calls) == 1
    assert agent.side_effect_ledger.status("run-1", "call-write") == "failed"
    observation = json.loads(client.responses.requests[1]["input"][0]["output"])
    assert observation["error"] == "side_effect_tool_error"
    assert observation["status"] == "failed"
    assert observation["content"] == {
        "is_error": True,
        "content": {"detail": "disk is full"},
    }


@pytest.mark.asyncio
async def test_finished_call_is_reported_as_a_duplicate_on_replay(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [write_response(), SimulatedCrash("killed after the tool finished")],
    )
    pending = await agent.start("change")
    decision = ResumeDecision(
        action="approve",
        digest=pending.pending_approval.digest,
    )

    # The tool finished, then the process died before the next checkpoint
    # write, so the pending approval is still the one on disk.
    with pytest.raises(SimulatedCrash):
        await agent.resume("run-1", decision)

    assert mcp.calls == [("write_file", {"path": "b.py", "content": "x"})]
    assert agent.side_effect_ledger.status("run-1", "call-write") == "executed"

    replayed, client, second_mcp = make_agent_with(
        tmp_path,
        [response("resp-2", text_item("already done"))],
        FakeMCPClient(),
    )
    outcome = await replayed.resume("run-1", decision)

    assert second_mcp.calls == []
    assert outcome.final_text == "already done"
    observation = json.loads(client.responses.requests[0]["input"][0]["output"])
    assert observation["error"] == "duplicate_side_effect_call"
    assert observation["status"] == "executed"


@pytest.mark.asyncio
async def test_unconfirmed_terminal_record_is_reported_as_uncertain(
    tmp_path,
    monkeypatch,
) -> None:
    agent, client, mcp = make_agent(
        tmp_path,
        [write_response(), response("resp-2", text_item("reported"))],
    )
    pending = await agent.start("change")
    fail_ledger_durability_after(monkeypatch, skip=1)

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(action="approve", digest=pending.pending_approval.digest),
    )

    assert outcome.final_text == "reported"
    assert len(mcp.calls) == 1
    observation = json.loads(client.responses.requests[1]["input"][0]["output"])
    assert observation["error"] == "side_effect_status_uncertain"
    assert observation["status"] == "executed"
    assert "by hand" in observation["action_required"]


@pytest.mark.asyncio
async def test_unconfirmed_claim_is_never_dispatched(tmp_path, monkeypatch) -> None:
    agent, client, mcp = make_agent(
        tmp_path,
        [write_response(), response("resp-2", text_item("reported"))],
    )
    pending = await agent.start("change")
    fail_ledger_durability_after(monkeypatch, skip=0)

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(action="approve", digest=pending.pending_approval.digest),
    )

    assert mcp.calls == []
    assert outcome.final_text == "reported"
    observation = json.loads(client.responses.requests[1]["input"][0]["output"])
    assert observation["error"] == "side_effect_status_uncertain"
    assert observation["status"] == "claimed"


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


class APIStatusError(Exception):
    """Shaped like the SDK's HTTP error, which always carries a status code."""

    def __init__(self, status_code: int, message: str = "api failure") -> None:
        super().__init__(message)
        self.status_code = status_code


class APIResponseStatusError(Exception):
    """Carries its status on the response object instead of the exception."""

    def __init__(self, status_code: int) -> None:
        super().__init__("api failure")
        self.response = SimpleNamespace(status_code=status_code)


class APIConnectionError(Exception):
    """Named after the SDK transport error, which carries no status code."""


TRANSIENT_ERRORS = [
    TimeoutError("read timed out"),
    ConnectionResetError("peer reset the connection"),
    APIConnectionError("connection refused"),
    APIStatusError(408),
    APIStatusError(429),
    APIStatusError(500),
    APIStatusError(503),
    APIResponseStatusError(502),
]

NON_TRANSIENT_ERRORS = [
    APIStatusError(400),
    APIStatusError(401),
    APIStatusError(403),
    APIStatusError(404),
    APIStatusError(422),
    APIResponseStatusError(400),
    ValueError("arguments do not match schema"),
    RuntimeError("unclassified failure"),
]


def recording_sleep() -> tuple[list[float], Any]:
    delays: list[float] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)

    return delays, sleep


@pytest.mark.parametrize("error", TRANSIENT_ERRORS, ids=repr)
def test_transient_model_errors_are_classified_as_retryable(error: Exception) -> None:
    assert is_transient_model_error(error) is True


@pytest.mark.parametrize("error", NON_TRANSIENT_ERRORS, ids=repr)
def test_other_model_errors_are_classified_as_final(error: Exception) -> None:
    assert is_transient_model_error(error) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("error", TRANSIENT_ERRORS, ids=repr)
async def test_transient_model_errors_are_retried(tmp_path, error: Exception) -> None:
    delays, sleep = recording_sleep()
    agent, client, _ = make_agent(
        tmp_path,
        [error, response("resp-1", text_item("recovered"))],
        max_retries=1,
        retry_initial_delay=0.25,
        sleep=sleep,
    )

    outcome = await agent.start("hello")

    assert outcome.final_text == "recovered"
    assert len(client.responses.requests) == 2
    assert delays == [0.25]


@pytest.mark.asyncio
@pytest.mark.parametrize("error", NON_TRANSIENT_ERRORS, ids=repr)
async def test_non_transient_model_errors_fail_without_a_retry(
    tmp_path,
    error: Exception,
) -> None:
    delays, sleep = recording_sleep()
    agent, client, _ = make_agent(
        tmp_path,
        [error, response("resp-1", text_item("never reached"))],
        max_retries=3,
        sleep=sleep,
    )

    with pytest.raises(ResponsesRetryError, match="not retryable"):
        await agent.start("hello")

    assert len(client.responses.requests) == 1
    assert delays == []


@pytest.mark.asyncio
async def test_transient_model_failures_retry_then_exhaust(tmp_path) -> None:
    delays, sleep = recording_sleep()
    agent, client, _ = make_agent(
        tmp_path,
        [APIStatusError(503), APIStatusError(503)],
        max_retries=1,
        retry_initial_delay=0.25,
        sleep=sleep,
    )

    with pytest.raises(ResponsesRetryError, match="2 attempts") as failure:
        await agent.start("hello")

    assert len(client.responses.requests) == 2
    assert delays == [0.25]
    assert failure.value.attempts == 2
    assert failure.value.retryable is True
    assert failure.value.status_code == 503


@pytest.mark.asyncio
async def test_retry_backoff_grows_exponentially_up_to_a_ceiling(tmp_path) -> None:
    delays, sleep = recording_sleep()
    agent, _, _ = make_agent(
        tmp_path,
        [APIStatusError(500)] * 5,
        max_retries=4,
        retry_initial_delay=0.5,
        max_retry_delay=1.5,
        sleep=sleep,
    )

    with pytest.raises(ResponsesRetryError):
        await agent.start("hello")

    assert delays == [0.5, 1.0, 1.5, 1.5]


@pytest.mark.asyncio
async def test_retry_failure_reveals_no_request_or_credential(tmp_path) -> None:
    marker = "AUTH-MARKER-MUST-NOT-LEAK"
    delays, sleep = recording_sleep()
    agent, _, _ = make_agent(
        tmp_path,
        [
            APIStatusError(
                500,
                f"upstream rejected header Authorization: {marker}",
            )
        ],
        max_retries=0,
        sleep=sleep,
    )

    with pytest.raises(ResponsesRetryError) as failure:
        await agent.start(f"please send {marker}")

    error = failure.value
    rendered = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    assert marker not in str(error)
    assert marker not in repr(error)
    assert marker not in rendered
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.error_type == "APIStatusError"


@pytest.mark.asyncio
async def test_model_retry_never_redispatches_a_finished_side_effect(
    tmp_path,
) -> None:
    delays, sleep = recording_sleep()
    agent, client, mcp = make_agent(
        tmp_path,
        [
            write_response(),
            APIStatusError(503),
            APIStatusError(429),
            response("resp-2", text_item("saved")),
        ],
        max_retries=2,
        retry_initial_delay=0.25,
        sleep=sleep,
    )
    pending = await agent.start("change")

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(action="approve", digest=pending.pending_approval.digest),
    )

    assert outcome.final_text == "saved"
    assert mcp.calls == [("write_file", {"path": "b.py", "content": "x"})]
    assert delays == [0.25, 0.5]
    assert agent.side_effect_ledger.status("run-1", "call-write") == "executed"
    # All three follow-up attempts resubmit the same recorded output.
    outputs = [request["input"] for request in client.responses.requests[1:]]
    assert len(outputs) == 3
    assert outputs[0] == outputs[1] == outputs[2]


@pytest.mark.asyncio
async def test_exhausted_model_retries_leave_the_side_effect_finished(
    tmp_path,
) -> None:
    delays, sleep = recording_sleep()
    agent, _, mcp = make_agent(
        tmp_path,
        [write_response(), APIStatusError(503), APIStatusError(503)],
        max_retries=1,
        sleep=sleep,
    )
    pending = await agent.start("change")
    decision = ResumeDecision(
        action="approve",
        digest=pending.pending_approval.digest,
    )

    with pytest.raises(ResponsesRetryError):
        await agent.resume("run-1", decision)

    assert len(mcp.calls) == 1
    assert agent.side_effect_ledger.status("run-1", "call-write") == "executed"

    replayed, client, second_mcp = make_agent_with(
        tmp_path,
        [response("resp-2", text_item("already done"))],
        FakeMCPClient(),
    )
    outcome = await replayed.resume("run-1", decision)

    assert second_mcp.calls == []
    assert outcome.final_text == "already done"
    observation = json.loads(client.responses.requests[0]["input"][0]["output"])
    assert observation["error"] == "duplicate_side_effect_call"
    assert observation["status"] == "executed"


def test_pure_sdk_loop_imports_no_agent_framework() -> None:
    project = Path(__file__).parents[1]
    program = (
        "import sys\n"
        "import agent_core.openai_loop\n"
        "frameworks = {'langchain', 'langchain_core', 'langgraph'}\n"
        "leaked = sorted(\n"
        "    {name.split('.')[0] for name in sys.modules}\n"
        "    & frameworks\n"
        ")\n"
        "print(','.join(leaked))\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )

    assert completed.stdout.strip() == ""


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
