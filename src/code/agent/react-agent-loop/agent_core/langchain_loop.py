from __future__ import annotations

import base64
import copy
import errno
import fcntl
import json
import os
import tempfile
import uuid
from collections import defaultdict
from collections.abc import Callable, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    ToolRetryMiddleware,
)
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, ToolCall, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt

from .checkpoints import contains_secret
from .contracts import ApprovalRequest, Risk, RunOutcome, ToolProposal, to_json_value
from .mcp_adapter import decode_mcp_tool_result, validate_function_tools
from .openai_loop import ResumeDecision
from .policy import ToolPolicy, digests_match


class CheckpointDurabilityError(OSError):
    """The replacement landed on disk but could not be confirmed durable.

    Raised only after ``os.replace`` has already committed the new file, so a
    caller must treat the new content as the current on-disk state and must not
    assume the previous file survived.
    """


class ClaimOutcome(Enum):
    """What a caller is allowed to conclude from a claim attempt.

    A side-effect call moves from missing to ``claimed`` and only then to a
    terminal status. ``claimed`` alone never proves the effect ran, so the only
    outcome that may be described to the model as already executed is
    ``FINISHED``.
    """

    GRANTED = "granted"
    UNCONFIRMED = "unconfirmed"
    FINISHED = "finished"


@dataclass(frozen=True)
class SideEffectClaim:
    outcome: ClaimOutcome
    status: str


class SideEffectLedger:
    """Persist side-effect claims so replay cannot dispatch a call twice."""

    _TERMINAL_STATUSES = frozenset({"executed", "failed"})
    _STATUSES = frozenset({"claimed"}) | _TERMINAL_STATUSES

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def claim(self, run_id: str, tool_call_id: str) -> SideEffectClaim:
        """Reserve a side-effect call, reporting whether it may be dispatched.

        ``GRANTED`` is returned only for a fresh claim whose record is
        confirmed durable. Every other path leaves a ``claimed`` record whose
        execution nobody can vouch for: the durability flush after the rename
        may have failed here, an earlier process may have died between the
        claim and the dispatch, or a replay may be re-entering a call whose
        outcome was never recorded.
        """
        with _exclusive_file_lock(self.lock_path):
            data = self._load()
            calls = data.setdefault(run_id, {})
            existing = calls.get(tool_call_id)
            if existing in self._TERMINAL_STATUSES:
                return SideEffectClaim(ClaimOutcome.FINISHED, existing)
            if existing == "claimed":
                return SideEffectClaim(ClaimOutcome.UNCONFIRMED, existing)
            calls[tool_call_id] = "claimed"
            try:
                _atomic_json_replace(self.path, data)
            except CheckpointDurabilityError:
                return SideEffectClaim(ClaimOutcome.UNCONFIRMED, "claimed")
            return SideEffectClaim(ClaimOutcome.GRANTED, "claimed")

    def finish(self, run_id: str, tool_call_id: str, status: str) -> bool:
        """Record a terminal status, returning whether it is confirmed durable.

        A ``False`` return means the record is already on disk but its flush
        could not be confirmed. The side effect has happened either way, so the
        record is kept rather than rolled back.
        """
        if status not in self._TERMINAL_STATUSES:
            raise ValueError("side-effect result must be executed or failed")
        with _exclusive_file_lock(self.lock_path):
            data = self._load()
            calls = data.get(run_id, {})
            if calls.get(tool_call_id) != "claimed":
                raise ValueError("side-effect call has no active claim")
            calls[tool_call_id] = status
            try:
                _atomic_json_replace(self.path, data)
            except CheckpointDurabilityError:
                return False
            return True

    def status(self, run_id: str, tool_call_id: str) -> str | None:
        with _exclusive_file_lock(self.lock_path):
            return self._load().get(run_id, {}).get(tool_call_id)

    def _load(self) -> dict[str, dict[str, str]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict):
            raise ValueError("invalid side-effect ledger")
        for run_id, calls in data.items():
            if not isinstance(run_id, str) or not isinstance(calls, dict):
                raise ValueError("invalid side-effect ledger")
            if not all(
                isinstance(call_id, str) and status in self._STATUSES
                for call_id, status in calls.items()
            ):
                raise ValueError("invalid side-effect ledger")
        return data


class JsonMemorySaver(InMemorySaver):
    """LangGraph checkpointer persisted as atomic, permission-restricted JSON."""

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")
        with _exclusive_file_lock(self.lock_path):
            self._load()

    def put(self, config, checkpoint, metadata, new_versions):
        if contains_secret(
            {
                "checkpoint": checkpoint,
                "metadata": metadata,
                "new_versions": new_versions,
            }
        ):
            raise ValueError("checkpoint state contains a secret-bearing field")
        with _exclusive_file_lock(self.lock_path):
            self._load()
            candidate = self._copy_store()
            result = candidate.put(
                config,
                checkpoint,
                metadata,
                new_versions,
            )
            self._validate_candidate(candidate)
            self._commit(candidate)
            return result

    def put_writes(self, config, writes, task_id, task_path="") -> None:
        if contains_secret({"writes": writes}):
            raise ValueError("checkpoint writes contain a secret-bearing field")
        with _exclusive_file_lock(self.lock_path):
            self._load()
            candidate = self._copy_store()
            candidate.put_writes(config, writes, task_id, task_path)
            self._validate_candidate(candidate)
            self._commit(candidate)

    def delete_thread(self, thread_id: str) -> None:
        with _exclusive_file_lock(self.lock_path):
            self._load()
            super().delete_thread(thread_id)
            self._sync_unlocked()

    def _load(self) -> None:
        self.storage.clear()
        self.writes.clear()
        self.blobs.clear()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        if set(data) != {"storage", "writes", "blobs"}:
            raise ValueError("invalid LangGraph checkpoint file")
        for thread_id, namespace, checkpoint_id, checkpoint, metadata, parent in data[
            "storage"
        ]:
            self.storage[thread_id][namespace][checkpoint_id] = (
                _decode_typed(checkpoint),
                _decode_typed(metadata),
                parent,
            )
        for row in data["writes"]:
            (
                thread_id,
                namespace,
                checkpoint_id,
                task_key,
                index,
                task_id,
                channel,
                value,
                task_path,
            ) = row
            self.writes[(thread_id, namespace, checkpoint_id)][
                (task_key, index)
            ] = (task_id, channel, _decode_typed(value), task_path)
        for thread_id, namespace, channel, version, value in data["blobs"]:
            self.blobs[(thread_id, namespace, channel, version)] = _decode_typed(
                value
            )

    def _sync_unlocked(self, source: InMemorySaver | None = None) -> None:
        source = source or self
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        payload = {
            "storage": [
                [
                    thread_id,
                    namespace,
                    checkpoint_id,
                    _encode_typed(checkpoint),
                    _encode_typed(metadata),
                    parent,
                ]
                for thread_id, namespaces in source.storage.items()
                for namespace, checkpoints in namespaces.items()
                for checkpoint_id, (checkpoint, metadata, parent) in checkpoints.items()
            ],
            "writes": [
                [
                    thread_id,
                    namespace,
                    checkpoint_id,
                    task_key,
                    index,
                    task_id,
                    channel,
                    _encode_typed(value),
                    task_path,
                ]
                for (
                    thread_id,
                    namespace,
                    checkpoint_id,
                ), writes in source.writes.items()
                for (
                    task_key,
                    index,
                ), (
                    task_id,
                    channel,
                    value,
                    task_path,
                ) in writes.items()
            ],
            "blobs": [
                [thread_id, namespace, channel, version, _encode_typed(value)]
                for (
                    thread_id,
                    namespace,
                    channel,
                    version,
                ), value in source.blobs.items()
            ],
        }
        _atomic_json_replace(self.path, payload)

    def _commit(self, candidate: InMemorySaver) -> None:
        """Persist ``candidate`` first, then adopt it into the live store.

        Anything that fails before the rename leaves both the file and the live
        store on the previous state. Once the rename has happened the file is
        the new truth, so an unconfirmed durability flush still reloads and
        adopts it rather than leaving this process disagreeing with its own
        checkpoint file.
        """
        try:
            self._sync_unlocked(candidate)
        except CheckpointDurabilityError:
            self._load()
            raise
        self._adopt(candidate)

    def _copy_store(self) -> InMemorySaver:
        candidate = InMemorySaver(serde=self.serde)
        candidate.storage = copy.deepcopy(self.storage)
        candidate.writes = copy.deepcopy(self.writes)
        candidate.blobs = copy.deepcopy(self.blobs)
        return candidate

    def _adopt(self, candidate: InMemorySaver) -> None:
        self.storage = candidate.storage
        self.writes = candidate.writes
        self.blobs = candidate.blobs

    def _validate_candidate(self, candidate: InMemorySaver) -> None:
        decoded = {
            "storage": [
                {
                    "thread_id": thread_id,
                    "namespace": namespace,
                    "checkpoint_id": checkpoint_id,
                    "checkpoint": candidate.serde.loads_typed(checkpoint),
                    "metadata": candidate.serde.loads_typed(metadata),
                    "parent": parent,
                }
                for thread_id, namespaces in candidate.storage.items()
                for namespace, checkpoints in namespaces.items()
                for checkpoint_id, (
                    checkpoint,
                    metadata,
                    parent,
                ) in checkpoints.items()
            ],
            "writes": [
                {
                    "thread_id": thread_id,
                    "namespace": namespace,
                    "checkpoint_id": checkpoint_id,
                    "task_key": task_key,
                    "index": index,
                    "task_id": task_id,
                    "channel": channel,
                    "value": candidate.serde.loads_typed(value),
                    "task_path": task_path,
                }
                for (
                    thread_id,
                    namespace,
                    checkpoint_id,
                ), writes in candidate.writes.items()
                for (
                    task_key,
                    index,
                ), (
                    task_id,
                    channel,
                    value,
                    task_path,
                ) in writes.items()
            ],
            "blobs": [
                {
                    "thread_id": thread_id,
                    "namespace": namespace,
                    "channel": channel,
                    "version": version,
                    "value": (
                        None
                        if value[0] == "empty"
                        else candidate.serde.loads_typed(value)
                    ),
                }
                for (
                    thread_id,
                    namespace,
                    channel,
                    version,
                ), value in candidate.blobs.items()
            ],
        }
        if contains_secret(decoded):
            raise ValueError("checkpoint store contains a secret-bearing field")


class SequentialHumanInTheLoopMiddleware(HumanInTheLoopMiddleware):
    """Review sensitive calls one-by-one before the tool node can run."""

    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        messages = state["messages"]
        last_ai_message = next(
            (
                message
                for message in reversed(messages)
                if isinstance(message, AIMessage)
            ),
            None,
        )
        if last_ai_message is None or not last_ai_message.tool_calls:
            return None

        revised_calls: list[ToolCall] = []
        rejection_messages: list[ToolMessage] = []
        for tool_call in last_ai_message.tool_calls:
            config = self.interrupt_on.get(tool_call["name"])
            if config is None:
                revised_calls.append(tool_call)
                continue
            response = interrupt(
                {
                    "action_requests": [
                        {
                            "name": tool_call["name"],
                            "args": tool_call["args"],
                            "description": (
                                f"{self.description_prefix}\n\n"
                                f"Tool: {tool_call['name']}\n"
                                f"Args: {tool_call['args']}"
                            ),
                        }
                    ],
                    "review_configs": [
                        {
                            "action_name": tool_call["name"],
                            "allowed_decisions": config["allowed_decisions"],
                        }
                    ],
                }
            )
            decisions = response.get("decisions", [])
            if len(decisions) != 1:
                raise ValueError("exactly one decision is required per tool call")
            decision = decisions[0]
            decision_type = decision.get("type")
            if decision_type not in config["allowed_decisions"]:
                raise ValueError(
                    f"decision {decision_type!r} is not allowed for "
                    f"{tool_call['name']!r}"
                )
            if decision_type == "approve":
                revised_calls.append(tool_call)
            elif decision_type == "edit":
                edited = decision.get("edited_action", {})
                revised_calls.append(
                    ToolCall(
                        type="tool_call",
                        id=tool_call["id"],
                        name=edited.get("name"),
                        args=edited.get("args"),
                    )
                )
            elif decision_type == "reject":
                reason = decision.get("message")
                revised_calls.append(tool_call)
                rejection_messages.append(
                    ToolMessage(
                        content=(
                            f"User rejected the tool call for "
                            f"`{tool_call['name']}` with reason: {reason}"
                            if reason
                            else (
                                f"User rejected the tool call for "
                                f"`{tool_call['name']}`. The tool was not executed."
                            )
                        ),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"],
                        status="error",
                    )
                )

        last_ai_message.tool_calls = revised_calls
        return {"messages": [last_ai_message, *rejection_messages]}


class LangChainReActAgent:
    def __init__(
        self,
        *,
        model: Any,
        mcp: Any,
        checkpoint_path: str | Path,
        policy: ToolPolicy | None = None,
        max_model_calls: int = 8,
        max_tool_calls: int = 12,
        max_tool_retries: int = 0,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if min(max_model_calls, max_tool_calls) < 1 or max_tool_retries < 0:
            raise ValueError("call limits must be positive and retries non-negative")
        self._model = model
        self._mcp = mcp
        self._checkpoint_path = Path(checkpoint_path)
        self._policy = policy or ToolPolicy()
        self._max_model_calls = max_model_calls
        self._max_tool_calls = max_tool_calls
        self._max_tool_retries = max_tool_retries
        self._run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)
        self._side_effects = SideEffectLedger(
            self._checkpoint_path.with_name(
                f"{self._checkpoint_path.name}.side-effects.json"
            )
        )

    async def start(self, user_input: str) -> RunOutcome:
        run_id = self._run_id_factory()
        graph = await self._build_graph()
        result = await graph.ainvoke(
            {"messages": [{"role": "user", "content": user_input}]},
            _config(run_id),
        )
        return _to_outcome(result, run_id, self._policy)

    async def resume(
        self,
        run_id: str,
        decision: ResumeDecision,
    ) -> RunOutcome:
        with self._claim(run_id):
            graph = await self._build_graph()
            snapshot = await graph.aget_state(_config(run_id))
            pending = _pending_from_snapshot(snapshot, self._policy)
            if pending is None:
                raise ValueError("run has no pending approval")
            if decision.action not in {"approve", "reject"}:
                raise ValueError("decision action must be approve or reject")
            if not digests_match(decision.digest, pending.digest):
                raise ValueError("approval digest does not match pending proposal")
            if decision.action == "reject" and decision.arguments is not None:
                raise ValueError("a rejection cannot edit arguments")

            if decision.action == "reject":
                mapped: dict[str, Any] = {
                    "type": "reject",
                    "message": decision.reason,
                }
            elif decision.arguments is None:
                mapped = {"type": "approve"}
            else:
                arguments = to_json_value(decision.arguments)
                await self._validate_edit(pending.proposal.tool_name, arguments)
                edited = ToolProposal(
                    pending.proposal.call_id,
                    pending.proposal.tool_name,
                    arguments,
                )
                if self._policy.classify(edited) is not Risk.APPROVAL:
                    raise ValueError("edited proposal is not approvable")
                mapped = {
                    "type": "edit",
                    "edited_action": {
                        "name": edited.tool_name,
                        "args": arguments,
                    },
                }

            result = await graph.ainvoke(
                Command(resume={"decisions": [mapped]}),
                _config(run_id),
            )
            return _to_outcome(result, run_id, self._policy)

    async def pending_approval(self, run_id: str) -> ApprovalRequest | None:
        graph = await self._build_graph()
        snapshot = await graph.aget_state(_config(run_id))
        return _pending_from_snapshot(snapshot, self._policy)

    async def _build_graph(self):
        definitions = validate_function_tools(
            await self._mcp.list_function_tools()
        )
        tools: list[StructuredTool] = []
        interrupt_on: dict[str, dict[str, Any]] = {}
        retryable_tools: list[str] = []
        for definition in definitions:
            name = _required_string(definition, "name")
            schema = definition.get("parameters")
            if not isinstance(schema, Mapping):
                raise ValueError(f"tool {name!r} has no object schema")
            risk = self._policy.classify(ToolProposal("policy-check", name, {}))
            if risk is Risk.DENY:
                continue

            async def invoke_tool(
                runtime: ToolRuntime,
                _tool_name: str = name,
                _risk: Risk = risk,
                **arguments: Any,
            ) -> ToolMessage:
                if _risk is Risk.READ_ONLY:
                    result = await self._mcp.call(_tool_name, arguments)
                    try:
                        decoded = decode_mcp_tool_result(result)
                    except (TypeError, ValueError) as error:
                        return _tool_message(
                            runtime,
                            _tool_name,
                            _observation(
                                error="malformed_mcp_result",
                                detail=str(error),
                            ),
                            error=True,
                        )
                    return _tool_message(
                        runtime,
                        _tool_name,
                        _json_value(decoded.envelope),
                        error=decoded.is_error,
                    )
                if runtime.tool_call_id is None:
                    raise ValueError("side-effect tool call has no call ID")
                run_id = _required_string(
                    runtime.config["configurable"],
                    "thread_id",
                )
                tool_call_id = runtime.tool_call_id
                claim = self._side_effects.claim(run_id, tool_call_id)
                if claim.outcome is ClaimOutcome.FINISHED:
                    return _tool_message(
                        runtime,
                        _tool_name,
                        _observation(
                            error="duplicate_side_effect_call",
                            status=claim.status,
                            detail="this call already finished and is not repeated",
                        ),
                        error=True,
                    )
                if claim.outcome is ClaimOutcome.UNCONFIRMED:
                    return _tool_message(
                        runtime,
                        _tool_name,
                        _observation(
                            error="side_effect_status_uncertain",
                            status=claim.status,
                            detail=(
                                "the call is claimed but never finished, so "
                                "whether the side effect ran is unconfirmed"
                            ),
                            action_required=(
                                "check the target system by hand and reconcile "
                                "the ledger; this call is never dispatched again "
                                "automatically"
                            ),
                        ),
                        error=True,
                    )
                try:
                    result = await self._mcp.call(_tool_name, arguments)
                    decoded = decode_mcp_tool_result(result)
                except Exception as error:
                    durable = self._side_effects.finish(
                        run_id,
                        tool_call_id,
                        "failed",
                    )
                    return _tool_message(
                        runtime,
                        _tool_name,
                        _observation(
                            error=(
                                "side_effect_outcome_uncertain"
                                if durable
                                else "side_effect_status_uncertain"
                            ),
                            status="failed",
                            detail=str(error),
                            action_required=(
                                "check the target system and ledger by hand; "
                                "this call is not retried automatically"
                            ),
                        ),
                        error=True,
                    )
                if decoded.is_error:
                    if not self._side_effects.finish(
                        run_id,
                        tool_call_id,
                        "failed",
                    ):
                        return _tool_message(
                            runtime,
                            _tool_name,
                            _observation(
                                error="side_effect_status_uncertain",
                                status="failed",
                                detail=(
                                    "the tool reported failure but its ledger "
                                    "record is not confirmed durable"
                                ),
                                action_required=(
                                    "check the target system and ledger by hand; "
                                    "this call is not retried automatically"
                                ),
                            ),
                            error=True,
                        )
                    return _tool_message(
                        runtime,
                        _tool_name,
                        _observation(
                            error="side_effect_tool_error",
                            status="failed",
                            content=decoded.envelope,
                            action_required=(
                                "check the target system by hand; this call is "
                                "not retried automatically"
                            ),
                        ),
                        error=True,
                    )
                if not self._side_effects.finish(run_id, tool_call_id, "executed"):
                    return _tool_message(
                        runtime,
                        _tool_name,
                        _observation(
                            error="side_effect_status_uncertain",
                            status="executed",
                            detail=(
                                "the side effect ran but its finished ledger "
                                "record is not confirmed durable"
                            ),
                            action_required=(
                                "check the ledger by hand; this call is not "
                                "retried automatically"
                            ),
                        ),
                        error=True,
                    )
                return _tool_message(
                    runtime,
                    _tool_name,
                    _json_value(decoded.envelope),
                )

            tools.append(
                StructuredTool.from_function(
                    coroutine=invoke_tool,
                    name=name,
                    description=str(definition.get("description", "")),
                    args_schema=dict(schema),
                )
            )
            if risk is Risk.APPROVAL:
                interrupt_on[name] = {
                    "allowed_decisions": ["approve", "edit", "reject"],
                    "args_schema": dict(schema),
                }
            else:
                retryable_tools.append(name)

        middleware = [
            ModelCallLimitMiddleware(
                thread_limit=self._max_model_calls,
                exit_behavior="end",
            ),
            ToolCallLimitMiddleware(
                thread_limit=self._max_tool_calls,
                exit_behavior="end",
            ),
            ToolRetryMiddleware(
                max_retries=self._max_tool_retries,
                tools=retryable_tools,
                on_failure=lambda error: str(error),
                initial_delay=0,
                jitter=False,
            ),
            SequentialHumanInTheLoopMiddleware(interrupt_on=interrupt_on),
        ]
        return create_agent(
            self._model,
            tools,
            middleware=middleware,
            checkpointer=JsonMemorySaver(self._checkpoint_path),
        )

    async def _validate_edit(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> None:
        definitions = await self._mcp.list_function_tools()
        matches = [
            item
            for item in definitions
            if item.get("name") == tool_name
            and isinstance(item.get("parameters"), Mapping)
        ]
        if len(matches) != 1:
            raise ValueError(f"no unique schema for tool {tool_name!r}")
        try:
            schema = matches[0]["parameters"]
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(arguments)
        except (SchemaError, ValidationError) as error:
            raise ValueError(
                f"arguments do not match schema for {tool_name!r}: {error.message}"
            ) from error

    @contextmanager
    def _claim(self, run_id: str) -> Iterator[None]:
        if not run_id or not all(character.isalnum() or character in "-_" for character in run_id):
            raise ValueError("run_id may contain only letters, digits, '-' and '_'")
        lock_path = self._checkpoint_path.with_name(
            f"{self._checkpoint_path.name}.{run_id}.lock"
        )
        lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        except BlockingIOError as error:
            raise RuntimeError(f"run {run_id!r} is already claimed") from error
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)


def _config(run_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": run_id}}


def _observation(**fields: Any) -> str:
    return json.dumps(fields, sort_keys=True, separators=(",", ":"))


def _json_value(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _tool_message(
    runtime: ToolRuntime,
    name: str,
    content: str,
    *,
    error: bool = False,
) -> ToolMessage:
    if runtime.tool_call_id is None:
        raise ValueError("tool call has no call ID")
    return ToolMessage(
        content=content,
        name=name,
        tool_call_id=runtime.tool_call_id,
        status="error" if error else "success",
    )


def _to_outcome(
    result: Mapping[str, Any],
    run_id: str,
    policy: ToolPolicy,
) -> RunOutcome:
    pending = _pending_from_result(result, policy)
    if pending is not None:
        return RunOutcome(pending_approval=pending, run_id=run_id)
    messages = result.get("messages", [])
    final_text = ""
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            final_text = _message_text(message.content)
            break
    return RunOutcome(final_text=final_text, run_id=run_id)


def _pending_from_snapshot(snapshot: Any, policy: ToolPolicy) -> ApprovalRequest | None:
    interrupts = getattr(snapshot, "interrupts", ())
    values = getattr(snapshot, "values", {})
    if not interrupts:
        return None
    return _approval_from_interrupt(interrupts[0], values.get("messages", []), policy)


def _pending_from_result(
    result: Mapping[str, Any],
    policy: ToolPolicy,
) -> ApprovalRequest | None:
    interrupts = result.get("__interrupt__", ())
    if not interrupts:
        return None
    return _approval_from_interrupt(interrupts[0], result.get("messages", []), policy)


def _approval_from_interrupt(
    interrupt: Any,
    messages: list[Any],
    policy: ToolPolicy,
) -> ApprovalRequest:
    value = getattr(interrupt, "value", interrupt)
    requests = value.get("action_requests", []) if isinstance(value, Mapping) else []
    if len(requests) != 1:
        raise ValueError("exactly one pending approval is supported")
    request = requests[0]
    tool_name = _required_string(request, "name")
    arguments = request.get("args")
    if not isinstance(arguments, Mapping):
        raise ValueError("pending tool arguments must be an object")
    call_id = ""
    for message in reversed(messages):
        if not isinstance(message, AIMessage):
            continue
        for call in message.tool_calls:
            if call["name"] == tool_name and call["args"] == arguments:
                call_id = call["id"]
                break
        if call_id:
            break
    if not call_id:
        raise ValueError("pending approval has no matching tool call")
    proposal = ToolProposal(call_id, tool_name, arguments)
    return policy.approval_for(proposal)


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, Mapping) and block.get("type") == "text"
        )
    return str(content)


def _required_string(item: Mapping[str, Any], name: str) -> str:
    value = item.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _encode_typed(value: tuple[str, bytes]) -> list[str]:
    return [value[0], base64.b64encode(value[1]).decode("ascii")]


def _decode_typed(value: Any) -> tuple[str, bytes]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(item, str) for item in value)
    ):
        raise ValueError("invalid typed checkpoint value")
    return value[0], base64.b64decode(value[1], validate=True)


@contextmanager
def _exclusive_file_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.chmod(path, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _atomic_json_replace(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.fchmod(temporary.fileno(), 0o600)
            json.dump(
                payload,
                temporary,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            temporary.flush()
            os.fsync(temporary.fileno())
        # The rename is the commit point. The temporary file already carries
        # the final 0600 mode, so no fallible step is left between it and the
        # caller adopting the new state in memory.
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    _fsync_directory(path.parent)


def _fsync_directory(directory: Path) -> None:
    """Flush a completed rename so it survives a crash."""
    descriptor: int | None = None
    try:
        descriptor = os.open(directory, os.O_RDONLY)
        os.fsync(descriptor)
    except OSError as error:
        raise CheckpointDurabilityError(
            errno.EIO, "checkpoint rename durability uncertain"
        ) from error
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
