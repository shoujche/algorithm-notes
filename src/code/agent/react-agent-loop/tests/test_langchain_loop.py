from __future__ import annotations

import errno
import json
import os
import stat
import subprocess
import sys
from collections import namedtuple
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import attrs
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.types import Command, Send
from pydantic import PrivateAttr

from agent_core import langchain_loop
from agent_core.checkpoints import contains_secret
from agent_core.contracts import to_json_value
from agent_core.langchain_loop import (
    CheckpointDurabilityError,
    ClaimOutcome,
    JsonMemorySaver,
    LangChainReActAgent,
    SideEffectLedger,
)
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


class ErrorEnvelopeMCP(FakeLangChainMCP):
    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return json.dumps(
            {
                "is_error": True,
                "content": {"message": "tool reported failure"},
            },
            separators=(",", ":"),
            sort_keys=True,
        )


class MalformedEnvelopeMCP(FakeLangChainMCP):
    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return json.dumps(
            {"is_error": "yes", "content": {"message": "invalid flag"}},
            separators=(",", ":"),
            sort_keys=True,
        )


class DefinitionMCP(FakeLangChainMCP):
    def __init__(self, definitions: list[dict[str, Any]]) -> None:
        super().__init__()
        self.definitions = definitions

    async def list_function_tools(self) -> list[dict[str, Any]]:
        return self.definitions


class ClaimCheckingMCP(FakeLangChainMCP):
    def __init__(self, ledger_path: Path) -> None:
        super().__init__()
        self.ledger_path = ledger_path
        self.statuses_at_dispatch: list[str | None] = []

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.statuses_at_dispatch.append(
            SideEffectLedger(self.ledger_path).status("run-1", "call-write")
        )
        return await super().call(name, arguments)


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


@pytest.mark.parametrize(
    "nested_state",
    [
        {
            "messages": [
                {
                    "role": "user",
                    "content": {"profile": {"password": "not-for-disk"}},
                }
            ]
        },
        {
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "name": "write_file",
                            "args": {"nested": {"api_key": "not-for-disk"}},
                        }
                    ],
                }
            ]
        },
        {
            "messages": [
                {
                    "role": "tool",
                    "content": {"result": {"credential": "not-for-disk"}},
                }
            ]
        },
    ],
)
def test_json_memory_saver_rejects_nested_secrets_before_checkpoint_write(
    tmp_path,
    nested_state: dict[str, Any],
) -> None:
    path = tmp_path / "langchain.json"
    saver = JsonMemorySaver(path)
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = nested_state

    with pytest.raises(ValueError, match="secret"):
        saver.put(
            {"configurable": {"thread_id": "run-secret", "checkpoint_ns": ""}},
            checkpoint,
            {},
            {},
        )

    assert not path.exists()


def test_json_memory_saver_rejects_nested_secret_in_pending_writes(
    tmp_path,
) -> None:
    path = tmp_path / "langchain.json"
    saver = JsonMemorySaver(path)

    with pytest.raises(ValueError, match="secret"):
        saver.put_writes(
            {
                "configurable": {
                    "thread_id": "run-secret",
                    "checkpoint_ns": "",
                    "checkpoint_id": "cp",
                }
            },
            [("messages", {"tool_output": {"authorization": "not-for-disk"}})],
            "task-1",
        )

    assert not path.exists()


@pytest.mark.parametrize(
    "config",
    [
        {
            "configurable": {
                "thread_id": "run-config-secret",
                "checkpoint_ns": "",
            },
            "metadata": {"password": "not-for-disk"},
        },
        {
            "configurable": {
                "thread_id": "run-config-secret",
                "checkpoint_ns": "",
                "api_key": "not-for-disk",
            }
        },
    ],
)
def test_json_memory_saver_rejects_persisted_config_metadata_without_mutation(
    tmp_path,
    config: dict[str, Any],
) -> None:
    path = tmp_path / "langchain.json"
    saver = JsonMemorySaver(path)
    original = empty_checkpoint()
    saver.put(
        {"configurable": {"thread_id": "run-good", "checkpoint_ns": ""}},
        original,
        {},
        {},
    )
    before = path.read_bytes()
    candidate = empty_checkpoint()

    with pytest.raises(ValueError, match="secret"):
        saver.put(config, candidate, {}, {})

    assert path.read_bytes() == before
    assert saver.get_tuple(config) is None
    assert (
        saver.get_tuple(
            {"configurable": {"thread_id": "run-good", "checkpoint_ns": ""}}
        )
        is not None
    )


def _checkpoint_ids(saver: JsonMemorySaver) -> list[str]:
    return sorted(
        item.config["configurable"]["checkpoint_id"]
        for item in saver.list(None)
    )


def test_put_serialization_failure_preserves_memory_and_disk(tmp_path) -> None:
    path = tmp_path / "langchain.json"
    saver = JsonMemorySaver(path)
    original = empty_checkpoint()
    saver.put(
        {"configurable": {"thread_id": "run-good", "checkpoint_ns": ""}},
        original,
        {},
        {},
    )
    before_disk = path.read_bytes()
    before_ids = _checkpoint_ids(saver)
    rejected = empty_checkpoint()

    with pytest.raises(ValueError, match="Out of range float"):
        saver.put(
            {
                "configurable": {
                    "thread_id": "run-bad",
                    "checkpoint_ns": "",
                    "checkpoint_id": float("nan"),
                }
            },
            rejected,
            {},
            {},
        )

    assert path.read_bytes() == before_disk
    assert _checkpoint_ids(saver) == before_ids
    assert (
        saver.get_tuple(
            {"configurable": {"thread_id": "run-bad", "checkpoint_ns": ""}}
        )
        is None
    )
    assert list(tmp_path.glob("langchain.json.*.tmp")) == []


def test_put_writes_serialization_failure_preserves_memory_and_disk(
    tmp_path,
) -> None:
    path = tmp_path / "langchain.json"
    saver = JsonMemorySaver(path)
    checkpoint = empty_checkpoint()
    config = saver.put(
        {"configurable": {"thread_id": "run-good", "checkpoint_ns": ""}},
        checkpoint,
        {},
        {},
    )
    before_disk = path.read_bytes()
    before = saver.get_tuple(config)
    assert before is not None
    assert before.pending_writes == []

    with pytest.raises(ValueError, match="Out of range float"):
        saver.put_writes(
            config,
            [("messages", {"content": "safe"})],
            "task-bad",
            task_path=float("nan"),
        )

    assert path.read_bytes() == before_disk
    after = saver.get_tuple(config)
    assert after is not None
    assert after.pending_writes == []
    assert _checkpoint_ids(saver) == [checkpoint["id"]]
    assert list(tmp_path.glob("langchain.json.*.tmp")) == []


def _fail_chmod_on(monkeypatch, target: Path) -> None:
    real_chmod = os.chmod

    def guarded(path, mode, **kwargs) -> None:
        if not isinstance(path, int) and Path(path) == target:
            raise PermissionError(errno.EPERM, "injected chmod failure")
        real_chmod(path, mode, **kwargs)

    monkeypatch.setattr(os, "chmod", guarded)


def _fail_fsync_on(monkeypatch, *, directories: bool) -> None:
    real_fsync = os.fsync

    def guarded(descriptor: int) -> None:
        if stat.S_ISDIR(os.fstat(descriptor).st_mode) is directories:
            raise OSError(errno.EIO, "injected fsync failure")
        real_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", guarded)


def _fail_durability_flush_for(monkeypatch, target: Path, *, skip: int = 0) -> None:
    """Report writes to ``target`` as committed but not confirmed durable.

    Directory fsync failures cannot be aimed at a single file, because the
    ledger and the checkpoint share one directory. This reproduces the same
    post-rename state for one file: the new content is on disk and the caller
    is told the flush could not be confirmed.
    """
    real_replace = langchain_loop._atomic_json_replace
    remaining = skip

    def guarded(path: Path, payload: Any) -> None:
        nonlocal remaining
        real_replace(path, payload)
        if Path(path) != target:
            return
        if remaining > 0:
            remaining -= 1
            return
        raise CheckpointDurabilityError(errno.EIO, "injected durability failure")

    monkeypatch.setattr(langchain_loop, "_atomic_json_replace", guarded)


def test_persisted_checkpoint_needs_no_permission_change_after_rename(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "langchain.json"
    saver = JsonMemorySaver(path)
    checkpoint = empty_checkpoint()
    _fail_chmod_on(monkeypatch, path)

    config = saver.put(
        {"configurable": {"thread_id": "run-chmod", "checkpoint_ns": ""}},
        checkpoint,
        {},
        {},
    )
    saver.put_writes(config, [("messages", {"content": "written"})], "task-1")

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    live = saver.get_tuple(config)
    assert live is not None
    assert [write[1] for write in live.pending_writes] == ["messages"]
    reloaded = JsonMemorySaver(path).get_tuple(config)
    assert reloaded is not None
    assert [write[1] for write in reloaded.pending_writes] == ["messages"]
    assert list(tmp_path.glob("langchain.json.*.tmp")) == []


def test_put_directory_fsync_failure_adopts_the_persisted_checkpoint(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "langchain.json"
    saver = JsonMemorySaver(path)
    checkpoint = empty_checkpoint()
    _fail_fsync_on(monkeypatch, directories=True)

    with pytest.raises(CheckpointDurabilityError, match="durability uncertain"):
        saver.put(
            {"configurable": {"thread_id": "run-durability", "checkpoint_ns": ""}},
            checkpoint,
            {},
            {},
        )

    assert _checkpoint_ids(saver) == [checkpoint["id"]]
    assert _checkpoint_ids(JsonMemorySaver(path)) == [checkpoint["id"]]
    assert list(tmp_path.glob("langchain.json.*.tmp")) == []


def test_put_writes_directory_fsync_failure_adopts_the_persisted_writes(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "langchain.json"
    saver = JsonMemorySaver(path)
    config = saver.put(
        {"configurable": {"thread_id": "run-durability", "checkpoint_ns": ""}},
        empty_checkpoint(),
        {},
        {},
    )
    _fail_fsync_on(monkeypatch, directories=True)

    with pytest.raises(CheckpointDurabilityError, match="durability uncertain"):
        saver.put_writes(config, [("messages", {"content": "written"})], "task-1")

    live = saver.get_tuple(config)
    assert live is not None
    assert [write[1] for write in live.pending_writes] == ["messages"]
    reloaded = JsonMemorySaver(path).get_tuple(config)
    assert reloaded is not None
    assert [write[1] for write in reloaded.pending_writes] == ["messages"]
    assert list(tmp_path.glob("langchain.json.*.tmp")) == []


def test_failure_before_rename_keeps_memory_and_disk_on_the_old_checkpoint(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "langchain.json"
    saver = JsonMemorySaver(path)
    kept = empty_checkpoint()
    saver.put(
        {"configurable": {"thread_id": "run-good", "checkpoint_ns": ""}},
        kept,
        {},
        {},
    )
    before_disk = path.read_bytes()
    _fail_fsync_on(monkeypatch, directories=False)

    with pytest.raises(OSError) as failure:
        saver.put(
            {"configurable": {"thread_id": "run-lost", "checkpoint_ns": ""}},
            empty_checkpoint(),
            {},
            {},
        )

    assert not isinstance(failure.value, CheckpointDurabilityError)
    assert path.read_bytes() == before_disk
    assert _checkpoint_ids(saver) == [kept["id"]]
    assert list(tmp_path.glob("langchain.json.*.tmp")) == []


@dataclass(slots=True)
class SlottedEnvelope:
    payload: Any


@attrs.define(slots=True)
class AttrsEnvelope:
    payload: Any


SecretTuple = namedtuple("SecretTuple", ["api_key"])


@pytest.mark.parametrize(
    "wrapped",
    [
        SlottedEnvelope({"password": "not-for-disk"}),
        AttrsEnvelope({"api_key": "not-for-disk"}),
        SecretTuple("not-for-disk"),
        Command(update={"nested": {"password": "not-for-disk"}}),
        Send("tools", {"nested": {"api_key": "not-for-disk"}}),
    ],
)
def test_json_memory_saver_rejects_serializable_wrappers_in_pending_writes(
    tmp_path,
    wrapped: Any,
) -> None:
    path = tmp_path / "langchain.json"
    saver = JsonMemorySaver(path)

    with pytest.raises(ValueError, match="secret"):
        saver.put_writes(
            {
                "configurable": {
                    "thread_id": "run-wrapper",
                    "checkpoint_ns": "",
                    "checkpoint_id": "cp",
                }
            },
            [("pending", wrapped)],
            "task-1",
        )

    assert not path.exists()


def test_secret_detector_rejects_cycles_and_unknown_objects_without_properties() -> None:
    cyclic: list[Any] = []
    cyclic.append(cyclic)

    class Unknown:
        @property
        def password(self) -> str:
            raise AssertionError("properties must not be evaluated")

    assert contains_secret(cyclic) is True
    assert contains_secret(Unknown()) is True


@pytest.mark.parametrize(
    "metric",
    [
        {"input_tokens": 12},
        {"output_tokens": 8},
        {"total_tokens": 20},
        {"token_count": 20},
        {"token_budget": 100},
        {"max_tokens": 200},
    ],
)
def test_json_memory_saver_allows_non_negative_token_metrics(
    tmp_path,
    metric: dict[str, int],
) -> None:
    path = tmp_path / "langchain.json"
    saver = JsonMemorySaver(path)
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {"usage": {"nested": metric}}

    saver.put(
        {"configurable": {"thread_id": "run-metrics", "checkpoint_ns": ""}},
        checkpoint,
        {},
        {},
    )
    saver.put_writes(
        {
            "configurable": {
                "thread_id": "run-metrics",
                "checkpoint_ns": "",
                "checkpoint_id": checkpoint["id"],
            }
        },
        [("usage", {"nested": metric})],
        "task-1",
    )

    assert path.exists()
    assert contains_secret({"usage": metric}) is False


def test_side_effect_claim_is_persistent_across_processes(tmp_path) -> None:
    ledger_path = tmp_path / "side-effects.json"
    barrier = tmp_path / "go"
    script = """
import sys
import time
from pathlib import Path
from agent_core.langchain_loop import SideEffectLedger

ledger, ready, barrier = map(Path, sys.argv[1:])
ready.write_text("ready", encoding="utf-8")
while not barrier.exists():
    time.sleep(0.01)
print(SideEffectLedger(ledger).claim("run-1", "call-write").outcome.value, flush=True)
"""
    processes: list[tuple[subprocess.Popen[str], Path]] = []
    for index in range(2):
        ready = tmp_path / f"claim-{index}.ready"
        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                script,
                str(ledger_path),
                str(ready),
                str(barrier),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        processes.append((process, ready))
    for _, ready in processes:
        for _ in range(500):
            if ready.exists():
                break
            __import__("time").sleep(0.01)
        assert ready.exists()
    barrier.write_text("go", encoding="utf-8")
    results = []
    for process, _ in processes:
        stdout, _ = process.communicate(timeout=10)
        assert process.returncode == 0
        results.append(stdout.strip())

    assert sorted(results) == ["granted", "unconfirmed"]
    assert SideEffectLedger(ledger_path).status("run-1", "call-write") == "claimed"


def test_claim_after_a_durability_failure_stays_unconfirmed(
    tmp_path,
    monkeypatch,
) -> None:
    ledger = SideEffectLedger(tmp_path / "side-effects.json")
    _fail_fsync_on(monkeypatch, directories=True)

    claim = ledger.claim("run-1", "call-write")

    assert claim.outcome is ClaimOutcome.UNCONFIRMED
    assert claim.status == "claimed"
    assert ledger.status("run-1", "call-write") == "claimed"


def test_only_a_finished_call_is_reported_as_a_duplicate(tmp_path) -> None:
    ledger = SideEffectLedger(tmp_path / "side-effects.json")

    first = ledger.claim("run-1", "call-write")
    before_finish = ledger.claim("run-1", "call-write")
    durable = ledger.finish("run-1", "call-write", "executed")
    after_finish = ledger.claim("run-1", "call-write")

    assert first.outcome is ClaimOutcome.GRANTED
    assert before_finish.outcome is ClaimOutcome.UNCONFIRMED
    assert before_finish.status == "claimed"
    assert durable is True
    assert after_finish.outcome is ClaimOutcome.FINISHED
    assert after_finish.status == "executed"


def test_finish_reports_an_unconfirmed_but_preserved_terminal_record(
    tmp_path,
    monkeypatch,
) -> None:
    ledger = SideEffectLedger(tmp_path / "side-effects.json")
    assert ledger.claim("run-1", "call-write").outcome is ClaimOutcome.GRANTED
    _fail_fsync_on(monkeypatch, directories=True)

    durable = ledger.finish("run-1", "call-write", "executed")

    assert durable is False
    assert ledger.status("run-1", "call-write") == "executed"
    assert ledger.claim("run-1", "call-write").outcome is ClaimOutcome.FINISHED


@pytest.mark.asyncio
async def test_runtime_call_id_is_claimed_before_dispatch_and_blocks_replay(
    tmp_path,
) -> None:
    checkpoint_path = tmp_path / "langchain.json"
    ledger_path = tmp_path / "langchain.json.side-effects.json"
    mcp = ClaimCheckingMCP(ledger_path)
    first_agent = LangChainReActAgent(
        model=FakeChatModel(
            [
                tool_call(
                    "call-write",
                    "write_file",
                    {"path": "b.py", "content": "new"},
                ),
                AIMessage(content="saved"),
            ]
        ),
        mcp=mcp,
        checkpoint_path=checkpoint_path,
        run_id_factory=lambda: "run-1",
    )
    pending = await first_agent.start("change")
    pending_checkpoint = checkpoint_path.read_bytes()
    decision = ResumeDecision(
        action="approve",
        digest=pending.pending_approval.digest,
    )

    first = await first_agent.resume("run-1", decision)

    assert first.final_text == "saved"
    assert mcp.statuses_at_dispatch == ["claimed"]
    assert mcp.calls == [
        ("write_file", {"path": "b.py", "content": "new"})
    ]
    assert SideEffectLedger(ledger_path).status(
        "run-1",
        "call-write",
    ) == "executed"

    checkpoint_path.write_bytes(pending_checkpoint)
    replay_model = FakeChatModel([AIMessage(content="replay handled")])
    replay_agent = LangChainReActAgent(
        model=replay_model,
        mcp=mcp,
        checkpoint_path=checkpoint_path,
    )
    replay = await replay_agent.resume("run-1", decision)

    assert replay.final_text == "replay handled"
    assert mcp.statuses_at_dispatch == ["claimed"]
    assert mcp.calls == [
        ("write_file", {"path": "b.py", "content": "new"})
    ]
    observation = json.loads(str(replay_model.seen_messages[-1][-1].content))
    assert observation["error"] == "duplicate_side_effect_call"
    assert observation["status"] == "executed"


@pytest.mark.asyncio
async def test_claim_durability_failure_never_dispatches_or_claims_a_duplicate(
    tmp_path,
    monkeypatch,
) -> None:
    checkpoint_path = tmp_path / "langchain.json"
    ledger_path = tmp_path / "langchain.json.side-effects.json"
    mcp = FakeLangChainMCP()
    model = FakeChatModel(
        [
            tool_call("call-write", "write_file", {"path": "b.py", "content": "new"}),
            AIMessage(content="reported uncertain"),
        ]
    )
    agent = LangChainReActAgent(
        model=model,
        mcp=mcp,
        checkpoint_path=checkpoint_path,
        run_id_factory=lambda: "run-1",
    )
    pending = await agent.start("change")
    pending_checkpoint = checkpoint_path.read_bytes()
    decision = ResumeDecision(
        action="approve",
        digest=pending.pending_approval.digest,
    )
    _fail_durability_flush_for(monkeypatch, ledger_path)

    outcome = await agent.resume("run-1", decision)

    assert outcome.final_text == "reported uncertain"
    assert mcp.calls == []
    first = json.loads(str(model.seen_messages[-1][-1].content))
    assert first["error"] == "side_effect_status_uncertain"
    assert first["status"] == "claimed"
    assert "unconfirmed" in first["detail"]
    assert "by hand" in first["action_required"]
    assert SideEffectLedger(ledger_path).status("run-1", "call-write") == "claimed"

    monkeypatch.undo()
    checkpoint_path.write_bytes(pending_checkpoint)
    replay_model = FakeChatModel([AIMessage(content="replay handled")])
    replay_agent = LangChainReActAgent(
        model=replay_model,
        mcp=mcp,
        checkpoint_path=checkpoint_path,
    )

    replay = await replay_agent.resume("run-1", decision)

    assert replay.final_text == "replay handled"
    assert mcp.calls == []
    assert json.loads(str(replay_model.seen_messages[-1][-1].content)) == first
    assert SideEffectLedger(ledger_path).status("run-1", "call-write") == "claimed"


@pytest.mark.asyncio
async def test_finish_durability_failure_reports_uncertainty_without_retry(
    tmp_path,
    monkeypatch,
) -> None:
    checkpoint_path = tmp_path / "langchain.json"
    ledger_path = tmp_path / "langchain.json.side-effects.json"
    mcp = FakeLangChainMCP()
    model = FakeChatModel(
        [
            tool_call("call-write", "write_file", {"path": "b.py", "content": "new"}),
            AIMessage(content="reported uncertain"),
        ]
    )
    agent = LangChainReActAgent(
        model=model,
        mcp=mcp,
        checkpoint_path=checkpoint_path,
        run_id_factory=lambda: "run-1",
    )
    pending = await agent.start("change")
    _fail_durability_flush_for(monkeypatch, ledger_path, skip=1)

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(action="approve", digest=pending.pending_approval.digest),
    )

    assert outcome.final_text == "reported uncertain"
    assert mcp.calls == [("write_file", {"path": "b.py", "content": "new"})]
    observation = json.loads(str(model.seen_messages[-1][-1].content))
    assert observation["error"] == "side_effect_status_uncertain"
    assert observation["status"] == "executed"
    assert "not retried" in observation["action_required"]
    assert SideEffectLedger(ledger_path).status("run-1", "call-write") == "executed"


def test_subprocess_reads_persisted_checkpoint(tmp_path) -> None:
    path = tmp_path / "langchain.json"
    saver = JsonMemorySaver(path)
    checkpoint = empty_checkpoint()
    saver.put(
        {"configurable": {"thread_id": "run-subprocess", "checkpoint_ns": ""}},
        checkpoint,
        {},
        {},
    )
    script = (
        "from agent_core.langchain_loop import JsonMemorySaver;"
        "import sys;"
        "config={'configurable':"
        "{'thread_id':'run-subprocess','checkpoint_ns':''}};"
        "print(JsonMemorySaver(sys.argv[1]).get_tuple(config) is not None)"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "True"


def test_different_processes_merge_different_threads_without_lost_update(
    tmp_path,
) -> None:
    path = tmp_path / "langchain.json"
    go = tmp_path / "go"
    script = """
import sys
import time
from pathlib import Path
from agent_core.langchain_loop import JsonMemorySaver
from langgraph.checkpoint.base import empty_checkpoint

path, run_id, ready, go = map(Path, sys.argv[1:])
saver = JsonMemorySaver(path)
ready.write_text("ready", encoding="utf-8")
while not go.exists():
    time.sleep(0.01)
checkpoint = empty_checkpoint()
checkpoint["channel_values"] = {"run_id": run_id.name}
saver.put(
    {"configurable": {"thread_id": run_id.name, "checkpoint_ns": ""}},
    checkpoint,
    {},
    {},
)
"""
    processes = []
    for run_id in ("run-a", "run-b"):
        ready = tmp_path / f"{run_id}.ready"
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    script,
                    str(path),
                    run_id,
                    str(ready),
                    str(go),
                ]
            )
        )
    for run_id in ("run-a", "run-b"):
        ready = tmp_path / f"{run_id}.ready"
        for _ in range(500):
            if ready.exists():
                break
            __import__("time").sleep(0.01)
        assert ready.exists()
    go.write_text("go", encoding="utf-8")
    for process in processes:
        assert process.wait(timeout=10) == 0

    reloaded = JsonMemorySaver(path)
    for run_id in ("run-a", "run-b"):
        saved = reloaded.get_tuple(
            {"configurable": {"thread_id": run_id, "checkpoint_ns": ""}}
        )
        assert saved is not None


def test_same_run_claim_remains_exclusive_across_processes(tmp_path) -> None:
    checkpoint = tmp_path / "langchain.json"
    release = tmp_path / "release"
    holder_script = """
import sys
import time
from pathlib import Path
from agent_core.langchain_loop import LangChainReActAgent

agent = LangChainReActAgent(model=None, mcp=None, checkpoint_path=sys.argv[1])
with agent._claim("run-1"):
    print("claimed", flush=True)
    while not Path(sys.argv[2]).exists():
        time.sleep(0.01)
"""
    holder = subprocess.Popen(
        [sys.executable, "-c", holder_script, str(checkpoint), str(release)],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout is not None
    assert holder.stdout.readline().strip() == "claimed"
    contender_script = (
        "from agent_core.langchain_loop import LangChainReActAgent;"
        "import sys;"
        "agent=LangChainReActAgent(model=None,mcp=None,checkpoint_path=sys.argv[1]);"
        "\nwith agent._claim('run-1'):\n print('unexpected')"
    )
    contender = subprocess.run(
        [sys.executable, "-c", contender_script, str(checkpoint)],
        capture_output=True,
        text=True,
    )
    release.write_text("release", encoding="utf-8")
    assert holder.wait(timeout=10) == 0

    assert contender.returncode != 0
    assert "already claimed" in contender.stderr


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("definitions", "message"),
    [
        (
            [
                {
                    "type": "function",
                    "name": "read_file",
                    "description": "Read.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                        "additionalProperties": False,
                    },
                    "strict": False,
                }
            ],
            "strict",
        ),
        (
            [
                {
                    "type": "function",
                    "name": "read_file",
                    "description": "Read.",
                    "parameters": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "strict": True,
                }
            ],
            "root.*object",
        ),
        (
            [
                {
                    "type": "function",
                    "name": "read_file",
                    "description": "Read.",
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
                    "name": "read_file",
                    "description": "Duplicate.",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                },
            ],
            "unique",
        ),
    ],
)
async def test_structured_tools_require_task5_strict_definitions(
    tmp_path,
    definitions: list[dict[str, Any]],
    message: str,
) -> None:
    agent = LangChainReActAgent(
        model=FakeChatModel([AIMessage(content="unused")]),
        mcp=DefinitionMCP(definitions),
        checkpoint_path=tmp_path / "langchain.json",
    )

    with pytest.raises(ValueError, match=message):
        await agent.start("inspect")


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
async def test_read_error_envelope_is_an_error_observation_without_retry(
    tmp_path,
) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            tool_call("call-read", "read_file", {"path": "missing.py"}),
            AIMessage(content="could not inspect"),
        ],
        mcp=ErrorEnvelopeMCP(),
        max_tool_retries=2,
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "could not inspect"
    assert mcp.calls == [("read_file", {"path": "missing.py"})]
    failure = model.seen_messages[1][-1]
    assert isinstance(failure, ToolMessage)
    assert failure.status == "error"
    assert json.loads(str(failure.content)) == {
        "content": {"message": "tool reported failure"},
        "is_error": True,
    }


@pytest.mark.asyncio
async def test_sensitive_error_envelope_finishes_failed_without_retry(
    tmp_path,
) -> None:
    checkpoint_path = tmp_path / "langchain.sqlite"
    agent, model, mcp = make_agent(
        tmp_path,
        [
            tool_call(
                "call-write",
                "write_file",
                {"path": "b.py", "content": "new"},
            ),
            AIMessage(content="manual check required"),
        ],
        mcp=ErrorEnvelopeMCP(),
        max_tool_retries=2,
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
    assert SideEffectLedger(
        checkpoint_path.with_name(f"{checkpoint_path.name}.side-effects.json")
    ).status("run-1", "call-write") == "failed"
    failure_message = model.seen_messages[1][-1]
    assert isinstance(failure_message, ToolMessage)
    assert failure_message.status == "error"
    failure = json.loads(str(failure_message.content))
    assert failure["error"] == "side_effect_tool_error"
    assert failure["status"] == "failed"
    assert failure["content"] == {
        "content": {"message": "tool reported failure"},
        "is_error": True,
    }
    assert "not retried" in failure["action_required"]


@pytest.mark.asyncio
async def test_sensitive_error_finish_durability_failure_stays_uncertain(
    tmp_path,
    monkeypatch,
) -> None:
    checkpoint_path = tmp_path / "langchain.sqlite"
    ledger_path = checkpoint_path.with_name(
        f"{checkpoint_path.name}.side-effects.json"
    )
    agent, model, mcp = make_agent(
        tmp_path,
        [
            tool_call(
                "call-write",
                "write_file",
                {"path": "b.py", "content": "new"},
            ),
            AIMessage(content="manual reconciliation required"),
        ],
        mcp=ErrorEnvelopeMCP(),
        max_tool_retries=2,
    )
    pending = await agent.start("change")
    _fail_durability_flush_for(monkeypatch, ledger_path, skip=1)

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=pending.pending_approval.digest,
        ),
    )

    assert outcome.final_text == "manual reconciliation required"
    assert mcp.calls == [
        ("write_file", {"path": "b.py", "content": "new"})
    ]
    assert SideEffectLedger(ledger_path).status("run-1", "call-write") == "failed"
    uncertain_message = model.seen_messages[1][-1]
    assert isinstance(uncertain_message, ToolMessage)
    assert uncertain_message.status == "error"
    uncertain = json.loads(str(uncertain_message.content))
    assert uncertain["error"] == "side_effect_status_uncertain"
    assert uncertain["status"] == "failed"
    assert "not retried" in uncertain["action_required"]


@pytest.mark.asyncio
async def test_malformed_read_envelope_fails_closed_without_retry(tmp_path) -> None:
    agent, model, mcp = make_agent(
        tmp_path,
        [
            tool_call("call-read", "read_file", {"path": "a.py"}),
            AIMessage(content="protocol failure"),
        ],
        mcp=MalformedEnvelopeMCP(),
        max_tool_retries=2,
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "protocol failure"
    assert mcp.calls == [("read_file", {"path": "a.py"})]
    failure = model.seen_messages[1][-1]
    assert isinstance(failure, ToolMessage)
    assert failure.status == "error"
    parsed = json.loads(str(failure.content))
    assert parsed["error"] == "malformed_mcp_result"
    assert "invalid result envelope" in parsed["detail"]


@pytest.mark.asyncio
async def test_read_tool_failure_uses_bounded_automatic_retries(tmp_path) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            tool_call("call-read", "read_file", {"path": "a.py"}),
            AIMessage(content="could not inspect"),
        ],
        mcp=FailingMCP(),
        max_tool_retries=1,
    )

    outcome = await agent.start("inspect")

    assert outcome.final_text == "could not inspect"
    assert mcp.calls == [
        ("read_file", {"path": "a.py"}),
        ("read_file", {"path": "a.py"}),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("write_file", {"path": "b.py", "content": "new"}),
        ("run_command", {"argv": ["pytest", "-q"], "cwd": "."}),
    ],
)
async def test_sensitive_tool_failure_is_never_automatically_retried(
    tmp_path,
    name: str,
    arguments: dict[str, Any],
) -> None:
    agent, _, mcp = make_agent(
        tmp_path,
        [
            tool_call("call-sensitive", name, arguments),
            AIMessage(content="side effect outcome uncertain"),
        ],
        mcp=FailingMCP(),
        max_tool_retries=2,
    )
    pending = await agent.start("change")

    outcome = await agent.resume(
        "run-1",
        ResumeDecision(
            action="approve",
            digest=pending.pending_approval.digest,
        ),
    )

    assert outcome.final_text == "side effect outcome uncertain"
    assert mcp.calls == [(name, arguments)]


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
