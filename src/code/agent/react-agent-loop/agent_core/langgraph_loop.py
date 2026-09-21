from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any
from typing_extensions import Annotated, TypedDict

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt

from .checkpoints import JsonCheckpointStore
from .contracts import ApprovalRequest, Risk, RunOutcome, ToolProposal, to_json_value
from .langchain_loop import (
    ClaimOutcome,
    JsonMemorySaver,
    SideEffectLedger,
    _atomic_json_replace,
    _exclusive_file_lock,
)
from .mcp_adapter import decode_mcp_tool_result, validate_function_tools
from .openai_loop import BudgetExceeded, ResponsesRetryError, ResumeDecision
from .policy import ToolPolicy, digests_match


class GraphState(TypedDict, total=False):
    messages: Annotated[list[Any], add_messages]
    calls: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    model_calls: int
    tool_calls: int
    usage_units: int
    final_text: str
    halt: bool


class ActiveBudgetStore:
    """The single authoritative store of each run's active timeout budget.

    The budget deliberately lives outside the graph checkpoint: a second copy
    in `GraphState` would diverge silently whenever one of the two writes is
    skipped, and nodes must never decide budgets from replayed state.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def initialize(self, run_id: str, remaining: float) -> None:
        with _exclusive_file_lock(self.lock_path):
            data = self._load()
            if run_id in data:
                raise ValueError(f"run {run_id!r} already has a timeout budget")
            data[run_id] = _valid_remaining(remaining)
            _atomic_json_replace(self.path, data)

    def load(self, run_id: str) -> float | None:
        with _exclusive_file_lock(self.lock_path):
            return self._load().get(run_id)

    def save(self, run_id: str, remaining: float) -> None:
        with _exclusive_file_lock(self.lock_path):
            data = self._load()
            if run_id not in data:
                raise ValueError(f"run {run_id!r} has no timeout budget")
            data[run_id] = _valid_remaining(remaining)
            _atomic_json_replace(self.path, data)

    def _load(self) -> dict[str, float]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if not isinstance(raw, Mapping):
            raise ValueError("invalid active budget sidecar")
        return {
            str(run_id): _valid_remaining(remaining)
            for run_id, remaining in raw.items()
        }


class LangGraphReActAgent:
    """A ReAct loop whose orchestration is an explicit, inspectable graph."""

    def __init__(
        self,
        *,
        model: Any,
        mcp: Any,
        checkpoint_path: str | Path,
        policy: ToolPolicy | None = None,
        max_model_calls: int = 8,
        max_tool_calls: int = 12,
        max_token_budget: int = 100_000,
        max_output_chars: int = 32_768,
        timeout_seconds: float = 120,
        max_model_retries: int = 2,
        retry_initial_delay: float = 0.25,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if min(
            max_model_calls,
            max_tool_calls,
            max_token_budget,
            max_output_chars,
        ) < 1:
            raise ValueError("call budgets must be positive")
        if (
            timeout_seconds <= 0
            or max_model_retries < 0
            or retry_initial_delay < 0
        ):
            raise ValueError("timeout and retry budgets are invalid")
        self._model = model
        self._mcp = mcp
        self._checkpoint_path = Path(checkpoint_path)
        self._policy = policy or ToolPolicy()
        self._max_model_calls = max_model_calls
        self._max_tool_calls = max_tool_calls
        self._max_token_budget = max_token_budget
        self._max_output_chars = max_output_chars
        self._timeout_seconds = timeout_seconds
        self._max_model_retries = max_model_retries
        self._retry_initial_delay = retry_initial_delay
        self._sleep = sleep
        self._monotonic = monotonic
        self._run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)
        self._definitions: dict[str, dict[str, Any]] = {}
        self._bound_model: Any = None
        self._claims = JsonCheckpointStore(
            self._checkpoint_path.with_name(
                f"{self._checkpoint_path.name}.run-claims"
            )
        )
        self._side_effects = SideEffectLedger(
            self._checkpoint_path.with_name(
                f"{self._checkpoint_path.name}.side-effects.json"
            )
        )
        self._budgets = ActiveBudgetStore(
            self._checkpoint_path.with_name(
                f"{self._checkpoint_path.name}.active-budgets.json"
            )
        )

    @property
    def side_effect_ledger(self) -> SideEffectLedger:
        return self._side_effects

    def remaining_timeout_seconds(self, run_id: str) -> float | None:
        """Read the authoritative remaining active timeout for a run."""
        return self._budgets.load(run_id)

    async def start(self, user_input: str) -> RunOutcome:
        started = self._monotonic()
        run_id = self._run_id_factory()
        self._budgets.initialize(run_id, self._timeout_seconds)

        async def invoke() -> Mapping[str, Any]:
            graph = await self.build_graph()
            return await graph.ainvoke(
                {"messages": [{"role": "user", "content": user_input}]},
                _config(run_id),
            )

        result = await self._run_active_interval(
            run_id,
            self._timeout_seconds,
            started,
            invoke,
        )
        return _to_outcome(result, run_id, self._policy)

    async def resume(
        self,
        run_id: str,
        decision: ResumeDecision,
    ) -> RunOutcome:
        started = self._monotonic()
        with self._claims.claim(run_id):
            remaining = self._budgets.load(run_id)
            if remaining is None:
                raise ValueError("run has no persisted timeout budget")
            if remaining <= 0:
                raise BudgetExceeded("total timeout budget exceeded")

            async def invoke() -> Mapping[str, Any]:
                graph = await self.build_graph()
                snapshot = await graph.aget_state(_config(run_id))
                pending = _pending_from_snapshot(snapshot, self._policy)
                if pending is None:
                    raise ValueError("run has no pending approval")
                _validate_resume_decision(decision, pending)
                if decision.arguments is not None:
                    self._validate_arguments(
                        pending.proposal.tool_name,
                        decision.arguments,
                    )
                    edited = ToolProposal(
                        pending.proposal.call_id,
                        pending.proposal.tool_name,
                        decision.arguments,
                    )
                    if self._policy.classify(edited) is not Risk.APPROVAL:
                        raise ValueError("edited proposal is not approvable")
                return await graph.ainvoke(
                    Command(resume=_decision_to_dict(decision)),
                    _config(run_id),
                )

            result = await self._run_active_interval(
                run_id,
                remaining,
                started,
                invoke,
            )
            return _to_outcome(result, run_id, self._policy)

    async def pending_approval(self, run_id: str) -> ApprovalRequest | None:
        graph = await self.build_graph()
        return await self._pending_from_graph(graph, run_id)

    async def _run_active_interval(
        self,
        run_id: str,
        remaining: float,
        started: float,
        operation: Callable[[], Awaitable[Mapping[str, Any]]],
    ) -> Mapping[str, Any]:
        if remaining <= 0:
            raise BudgetExceeded("total timeout budget exceeded")
        elapsed_before_async = max(0.0, self._monotonic() - started)
        available = max(0.0, remaining - elapsed_before_async)
        if available <= 0:
            await self._persist_active_budget(run_id, 0.0)
            raise BudgetExceeded("total timeout budget exceeded")
        result: Mapping[str, Any] | None = None
        failure: BaseException | None = None
        timed_out = False
        try:
            async with asyncio.timeout(available):
                result = await operation()
        except TimeoutError as error:
            timed_out = True
            failure = BudgetExceeded("total timeout budget exceeded")
            failure.__cause__ = error
        except BaseException as error:
            failure = error

        # The measured interval stops here. Charging the run for the write
        # that records the measurement could never terminate, so the budget
        # bookkeeping itself is the one excluded step; it is never retried
        # or back-filled.
        elapsed = max(0.0, self._monotonic() - started)
        updated_remaining = (
            0.0 if timed_out else max(0.0, remaining - elapsed)
        )
        cancelled: asyncio.CancelledError | None = None
        try:
            await self._persist_active_budget(run_id, updated_remaining)
        except asyncio.CancelledError as error:
            cancelled = error
        except BaseException as error:
            if failure is not None:
                raise error from failure
            raise
        if cancelled is not None:
            # The budget is safely on disk, so the external cancellation is
            # reported unchanged instead of a successful outcome.
            if failure is not None:
                raise cancelled from failure
            raise cancelled
        if failure is not None:
            raise failure
        if updated_remaining <= 0:
            raise BudgetExceeded("total timeout budget exceeded")
        if result is None:
            raise RuntimeError("graph invocation produced no result")
        return result

    async def _persist_active_budget(
        self,
        run_id: str,
        remaining: float,
    ) -> None:
        async def save() -> None:
            self._budgets.save(run_id, remaining)

        task = asyncio.create_task(save())
        cancelled: asyncio.CancelledError | None = None
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError as error:
                # Cancelling mid-write would lose the budget, so the write is
                # shielded to completion and the cancellation is kept.
                if cancelled is None:
                    cancelled = error
        task.result()
        if cancelled is not None:
            raise cancelled

    async def build_graph(self) -> Any:
        definitions = validate_function_tools(
            await self._mcp.list_function_tools()
        )
        self._definitions = {
            _required_string(definition, "name"): definition
            for definition in definitions
        }
        self._bound_model = self._model.bind_tools(definitions)

        builder = StateGraph(GraphState)
        builder.add_node("call_model", self._call_model)
        builder.add_node("route_response", self._route_response)
        builder.add_node("request_approval", self._request_approval)
        builder.add_node("execute_tools", self._execute_tools)
        builder.add_node("record_observation", self._record_observation)
        builder.add_node("finish", self._finish)
        builder.add_edge(START, "call_model")
        builder.add_conditional_edges(
            "call_model",
            lambda state: "finish" if state.get("halt") else "route_response",
            {
                "route_response": "route_response",
                "finish": "finish",
            },
        )
        builder.add_conditional_edges(
            "route_response",
            _route_after_response,
            {
                "request_approval": "request_approval",
                "execute_tools": "execute_tools",
                "finish": "finish",
            },
        )
        builder.add_conditional_edges(
            "request_approval",
            _route_after_approval,
            {
                "request_approval": "request_approval",
                "execute_tools": "execute_tools",
            },
        )
        builder.add_edge("execute_tools", "record_observation")
        builder.add_edge("record_observation", "call_model")
        builder.add_edge("finish", END)
        return builder.compile(
            checkpointer=JsonMemorySaver(self._checkpoint_path)
        )

    async def _call_model(self, state: GraphState) -> dict[str, Any]:
        model_calls = state.get("model_calls", 0)
        if model_calls >= self._max_model_calls:
            return {
                "final_text": "model call budget exceeded",
                "halt": True,
            }
        last_error: Exception | None = None
        response: AIMessage | None = None
        for attempt in range(self._max_model_retries + 1):
            try:
                response = await self._bound_model.ainvoke(
                    state.get("messages", [])
                )
                break
            except Exception as error:
                last_error = error
                if attempt < self._max_model_retries:
                    await self._sleep(
                        self._retry_initial_delay * (2**attempt)
                    )
        if response is None:
            attempts = self._max_model_retries + 1
            raise ResponsesRetryError(
                f"model call failed after {attempts} attempts"
            ) from last_error
        usage_units = state.get("usage_units", 0)
        usage = response.usage_metadata
        if usage is not None:
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            if type(input_tokens) is int and type(output_tokens) is int:
                usage_units += input_tokens + output_tokens
                if usage_units > self._max_token_budget:
                    raise BudgetExceeded("model token budget exceeded")
        return {
            "messages": [response],
            "model_calls": model_calls + 1,
            "usage_units": usage_units,
            "calls": [],
            "observations": [],
            "final_text": "",
            "halt": False,
        }

    async def _route_response(self, state: GraphState) -> dict[str, Any]:
        message = _last_ai_message(state.get("messages", []))
        if not message.tool_calls and not message.invalid_tool_calls:
            return {
                "final_text": _message_text(message.content),
                "calls": [],
                "halt": True,
            }

        seen: set[str] = set()
        calls: list[dict[str, Any]] = []
        for index, raw_call in enumerate(message.tool_calls):
            raw_call_id = raw_call.get("id")
            raw_name = raw_call.get("name")
            call_id = (
                raw_call_id
                if isinstance(raw_call_id, str) and raw_call_id
                else f"invalid-call-{index + 1}"
            )
            name = raw_name if isinstance(raw_name, str) and raw_name else "invalid_tool"
            if (
                not isinstance(raw_call_id, str)
                or not raw_call_id
                or not isinstance(raw_name, str)
                or not raw_name
            ):
                calls.append(
                    _errored_call(
                        call_id,
                        name,
                        {},
                        "malformed_tool_call",
                        "call id and tool name must be non-empty strings",
                    )
                )
                continue
            if call_id in seen:
                continue
            seen.add(call_id)
            arguments = raw_call.get("args")
            if not isinstance(arguments, Mapping):
                calls.append(
                    _errored_call(
                        call_id,
                        name,
                        {},
                        "malformed_arguments",
                        "arguments must be a JSON object",
                    )
                )
                continue
            proposal = ToolProposal(call_id, name, arguments)
            risk = self._policy.classify(proposal)
            if risk is Risk.DENY:
                calls.append(
                    _errored_call(
                        call_id,
                        name,
                        arguments,
                        "tool_denied",
                        "local policy denied this tool",
                    )
                )
                continue
            try:
                self._validate_arguments(name, arguments)
            except ValueError as error:
                calls.append(
                    _errored_call(
                        call_id,
                        name,
                        arguments,
                        "malformed_arguments",
                        str(error),
                    )
                )
                continue
            calls.append(
                {
                    "call_id": call_id,
                    "tool_name": name,
                    "arguments": to_json_value(arguments),
                    "risk": risk.value,
                    "approval_status": (
                        "pending" if risk is Risk.APPROVAL else "not_required"
                    ),
                    "rejection_reason": "",
                }
            )

        for index, invalid_call in enumerate(message.invalid_tool_calls):
            raw_call_id = invalid_call.get("id")
            raw_name = invalid_call.get("name")
            call_id = (
                raw_call_id
                if isinstance(raw_call_id, str)
                and raw_call_id
                and raw_call_id not in seen
                else f"invalid-call-{len(calls) + index + 1}"
            )
            seen.add(call_id)
            name = (
                raw_name
                if isinstance(raw_name, str) and raw_name
                else "invalid_tool"
            )
            calls.append(
                _errored_call(
                    call_id,
                    name,
                    {},
                    "malformed_tool_call",
                    str(
                        invalid_call.get("error")
                        or "model returned an invalid tool call"
                    ),
                )
            )

        tool_calls = state.get("tool_calls", 0)
        if tool_calls + len(calls) > self._max_tool_calls:
            return {
                "final_text": "tool call budget exceeded",
                "calls": [],
                "halt": True,
            }
        return {
            "calls": calls,
            "tool_calls": tool_calls + len(calls),
        }

    async def _request_approval(self, state: GraphState) -> dict[str, Any]:
        calls = [dict(call) for call in state.get("calls", [])]
        index = next(
            (
                offset
                for offset, call in enumerate(calls)
                if call["risk"] == Risk.APPROVAL.value
                and call["approval_status"] == "pending"
            ),
            None,
        )
        if index is None:
            return {"calls": calls}

        call = calls[index]
        proposal = _proposal_from_call(call)
        approval = self._policy.approval_for(proposal)
        # LangGraph may restart this node on resume. Nothing before interrupt()
        # dispatches a tool or mutates an external target.
        decision = interrupt({"approval": _approval_to_dict(approval)})
        if not isinstance(decision, Mapping):
            raise ValueError("approval decision must be an object")
        if not digests_match(str(decision.get("digest", "")), approval.digest):
            raise ValueError("approval digest does not match pending proposal")
        action = decision.get("action")
        if action not in {"approve", "reject"}:
            raise ValueError("decision action must be approve or reject")

        if action == "reject":
            if decision.get("arguments") is not None:
                raise ValueError("a rejection cannot edit arguments")
            call["approval_status"] = "rejected"
            call["rejection_reason"] = str(decision.get("reason", ""))
        else:
            edited_arguments = decision.get("arguments")
            approved_request = approval
            if edited_arguments is not None:
                if not isinstance(edited_arguments, Mapping):
                    raise ValueError("edited arguments must be an object")
                self._validate_arguments(call["tool_name"], edited_arguments)
                edited = ToolProposal(
                    call["call_id"],
                    call["tool_name"],
                    edited_arguments,
                )
                if self._policy.classify(edited) is not Risk.APPROVAL:
                    raise ValueError("edited proposal is not approvable")
                approved_request = self._policy.approval_for(edited)
                call["arguments"] = to_json_value(edited_arguments)
            call["approval_status"] = "approved"
            call["approved_approval"] = _approval_to_dict(approved_request)
        calls[index] = call
        return {"calls": calls}

    async def _execute_tools(
        self,
        state: GraphState,
        config: RunnableConfig,
    ) -> dict[str, Any]:
        observations: list[dict[str, Any]] = []
        run_id = _required_string(
            config.get("configurable", {}),
            "thread_id",
        )
        for call in state.get("calls", []):
            observations.append(await self._execute_call(run_id, call))
        return {"observations": observations}

    async def _execute_call(
        self,
        run_id: str,
        call: Mapping[str, Any],
    ) -> dict[str, Any]:
        raw_call_id = call.get("call_id")
        raw_name = call.get("tool_name")
        call_id = (
            raw_call_id
            if isinstance(raw_call_id, str) and raw_call_id
            else "invalid-call"
        )
        name = (
            raw_name
            if isinstance(raw_name, str) and raw_name
            else "invalid_tool"
        )
        if (
            not isinstance(raw_call_id, str)
            or not raw_call_id
            or not isinstance(raw_name, str)
            or not raw_name
        ):
            return _observation(
                call_id,
                name,
                {
                    "error": "malformed_tool_call",
                    "detail": "call id and tool name must be non-empty strings",
                },
                error=True,
            )
        arguments = call.get("arguments")
        if not isinstance(arguments, Mapping):
            return _observation(
                call_id,
                name,
                {"error": "malformed_arguments"},
                error=True,
            )
        if "error" in call:
            return _observation(
                call_id,
                name,
                {"error": call["error"], "detail": call.get("detail", "")},
                error=True,
            )
        proposal = ToolProposal(call_id, name, arguments)
        try:
            self._validate_arguments(name, arguments)
        except ValueError as error:
            return _observation(
                call_id,
                name,
                {
                    "error": "malformed_arguments",
                    "detail": str(error),
                },
                error=True,
            )
        risk = self._policy.classify(proposal)
        if risk is Risk.DENY:
            return _observation(
                call_id,
                name,
                {
                    "error": "malformed_arguments",
                    "detail": "tool has no dispatchable local policy and schema",
                },
                error=True,
            )
        if call.get("approval_status") == "rejected":
            reason = str(call.get("rejection_reason", ""))
            return _observation(
                call_id,
                name,
                {
                    "error": "tool_call_rejected",
                    "detail": (
                        f"User rejected the tool call with reason: {reason}"
                        if reason
                        else "User rejected the tool call."
                    ),
                },
                error=True,
            )

        if risk is Risk.APPROVAL:
            try:
                rebound = self._policy.approval_for(proposal)
            except ValueError as error:
                return _observation(
                    call_id,
                    name,
                    {
                        "error": "approval_binding_invalid",
                        "detail": str(error),
                    },
                    error=True,
                )
            stored_approval = call.get("approved_approval")
            if (
                call.get("approval_status") != "approved"
                or not isinstance(stored_approval, Mapping)
                or stored_approval.get("digest") != rebound.digest
            ):
                return _observation(
                    call_id,
                    name,
                    {
                        "error": "approval_binding_invalid",
                        "detail": (
                            "current arguments do not match the approved proposal"
                        ),
                    },
                    error=True,
                )
            claim = self._side_effects.claim(run_id, call_id)
            if claim.outcome is ClaimOutcome.FINISHED:
                return _observation(
                    call_id,
                    name,
                    {
                        "error": "duplicate_side_effect_call",
                        "status": claim.status,
                        "detail": "this call already finished and is not repeated",
                    },
                    error=True,
                )
            if claim.outcome is ClaimOutcome.UNCONFIRMED:
                return _observation(
                    call_id,
                    name,
                    {
                        "error": "side_effect_status_uncertain",
                        "status": claim.status,
                        "detail": (
                            "the call is claimed but never finished, so whether "
                            "the side effect ran is unconfirmed"
                        ),
                        "action_required": (
                            "check the target system by hand and reconcile the "
                            "ledger; this call is never dispatched again automatically"
                        ),
                    },
                    error=True,
                )
            try:
                result = await self._mcp.call(name, dict(arguments))
                (
                    is_error,
                    parsed_result,
                    truncated,
                    marker_too_large,
                ) = self._parse_mcp_result(result)
            except Exception as error:
                self._side_effects.finish(run_id, call_id, "failed")
                return _observation(
                    call_id,
                    name,
                    {
                        "error": "side_effect_outcome_uncertain",
                        "status": "failed",
                        "detail": str(error),
                        "action_required": (
                            "check the target system by hand; this call is not "
                            "retried automatically"
                        ),
                    },
                    error=True,
                )
            if truncated:
                durable = self._side_effects.finish(
                    run_id,
                    call_id,
                    "failed" if is_error else "executed",
                )
                if not durable:
                    return _observation(
                        call_id,
                        name,
                        {
                            "error": "side_effect_status_uncertain",
                            "status": "failed" if is_error else "executed",
                            "detail": (
                                "the bounded tool result was recorded but ledger "
                                "durability is unconfirmed"
                            ),
                            "action_required": (
                                "check the target system and ledger by hand; this "
                                "call is not retried automatically"
                            ),
                        },
                        error=True,
                    )
                if marker_too_large:
                    raise BudgetExceeded("tool output budget exceeded")
                return _observation(
                    call_id,
                    name,
                    parsed_result,
                    error=True,
                )
            if is_error:
                if not self._side_effects.finish(run_id, call_id, "failed"):
                    return _observation(
                        call_id,
                        name,
                        {
                            "error": "side_effect_status_uncertain",
                            "status": "failed",
                            "detail": (
                                "the tool reported failure but its ledger record "
                                "is not confirmed durable"
                            ),
                            "action_required": (
                                "check the target system and ledger by hand; this "
                                "call is not retried automatically"
                            ),
                        },
                        error=True,
                    )
                return _observation(
                    call_id,
                    name,
                    {
                        "error": "side_effect_tool_error",
                        "status": "failed",
                        "content": parsed_result,
                        "action_required": (
                            "check the target system by hand; this call is not "
                            "retried automatically"
                        ),
                    },
                    error=True,
                )
            if not self._side_effects.finish(run_id, call_id, "executed"):
                return _observation(
                    call_id,
                    name,
                    {
                        "error": "side_effect_status_uncertain",
                        "status": "executed",
                        "detail": (
                            "the side effect ran but its finished ledger record "
                            "is not confirmed durable"
                        ),
                        "action_required": (
                            "check the ledger by hand; this call is not retried "
                            "automatically"
                        ),
                    },
                    error=True,
                )
            return _observation(call_id, name, parsed_result)

        try:
            result = await self._mcp.call(name, dict(arguments))
            (
                is_error,
                parsed_result,
                truncated,
                marker_too_large,
            ) = self._parse_mcp_result(result)
            if marker_too_large:
                raise BudgetExceeded("tool output budget exceeded")
            return _observation(
                call_id,
                name,
                parsed_result,
                error=is_error or truncated,
            )
        except BudgetExceeded:
            raise
        except Exception as error:
            return _observation(
                call_id,
                name,
                {"error": "tool_error", "detail": str(error)},
                error=True,
            )

    async def _record_observation(self, state: GraphState) -> dict[str, Any]:
        messages = [
            ToolMessage(
                content=observation["content"],
                name=observation["name"],
                tool_call_id=observation["call_id"],
                status="error" if observation["error"] else "success",
            )
            for observation in state.get("observations", [])
        ]
        return {
            "messages": messages,
            "calls": [],
            "observations": [],
        }

    async def _finish(self, state: GraphState) -> dict[str, Any]:
        return {}

    def _parse_mcp_result(
        self,
        result: Any,
    ) -> tuple[bool, Any, bool, bool]:
        decoded = decode_mcp_tool_result(result)
        is_error = decoded.is_error
        payload = decoded.envelope
        if len(result) <= self._max_output_chars:
            return is_error, payload, False, False
        marker = {
            "error": "tool_output_truncated",
            "status": "error" if is_error else "success",
            "truncated": True,
        }
        rendered = json.dumps(
            marker,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return (
            is_error,
            marker,
            True,
            len(rendered) > self._max_output_chars,
        )

    def _validate_arguments(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> None:
        definition = self._definitions.get(tool_name)
        if definition is None:
            raise ValueError(f"no strict schema for tool {tool_name!r}")
        schema = definition["parameters"]
        try:
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(to_json_value(arguments))
        except (SchemaError, ValidationError) as error:
            raise ValueError(
                f"arguments do not match schema for {tool_name!r}: {error.message}"
            ) from error

    async def _pending_from_graph(
        self,
        graph: Any,
        run_id: str,
    ) -> ApprovalRequest | None:
        snapshot = await graph.aget_state(_config(run_id))
        return _pending_from_snapshot(snapshot, self._policy)


def _config(run_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": run_id}}


def _valid_remaining(remaining: Any) -> float:
    if (
        type(remaining) not in {int, float}
        or not math.isfinite(remaining)
        or remaining < 0
    ):
        raise ValueError("remaining timeout budget must be a finite non-negative number")
    return float(remaining)


def _pending_from_snapshot(
    snapshot: Any,
    policy: ToolPolicy,
) -> ApprovalRequest | None:
    interrupts = getattr(snapshot, "interrupts", ())
    if interrupts:
        return _approval_from_interrupt(interrupts[0], policy)
    values = getattr(snapshot, "values", {})
    for call in values.get("calls", []):
        if (
            isinstance(call, Mapping)
            and call.get("risk") == Risk.APPROVAL.value
            and call.get("approval_status") == "pending"
        ):
            return policy.approval_for(_proposal_from_call(call))
    return None


def _route_after_response(state: GraphState) -> str:
    if state.get("halt"):
        return "finish"
    if any(
        call.get("risk") == Risk.APPROVAL.value
        and call.get("approval_status") == "pending"
        for call in state.get("calls", [])
    ):
        return "request_approval"
    return "execute_tools"


def _route_after_approval(state: GraphState) -> str:
    if any(
        call.get("risk") == Risk.APPROVAL.value
        and call.get("approval_status") == "pending"
        for call in state.get("calls", [])
    ):
        return "request_approval"
    return "execute_tools"


def _last_ai_message(messages: list[Any]) -> AIMessage:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return message
    raise ValueError("model node produced no AI message")


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


def _proposal_from_call(call: Mapping[str, Any]) -> ToolProposal:
    arguments = call.get("arguments")
    if not isinstance(arguments, Mapping):
        raise ValueError("tool arguments must be an object")
    return ToolProposal(
        _required_string(call, "call_id"),
        _required_string(call, "tool_name"),
        arguments,
    )


def _approval_to_dict(request: ApprovalRequest) -> dict[str, Any]:
    return {
        "proposal": {
            "call_id": request.proposal.call_id,
            "tool_name": request.proposal.tool_name,
            "arguments": to_json_value(request.proposal.arguments),
        },
        "risk": request.risk.value,
        "normalized_arguments": request.normalized_arguments,
        "preview": to_json_value(request.preview),
        "digest": request.digest,
    }


def _approval_from_interrupt(value: Any, policy: ToolPolicy) -> ApprovalRequest:
    payload = getattr(value, "value", value)
    approval = payload.get("approval") if isinstance(payload, Mapping) else None
    if not isinstance(approval, Mapping):
        raise ValueError("invalid approval interrupt payload")
    proposal_data = approval.get("proposal")
    if not isinstance(proposal_data, Mapping):
        raise ValueError("invalid approval proposal")
    arguments = proposal_data.get("arguments")
    if not isinstance(arguments, Mapping):
        raise ValueError("approval arguments must be an object")
    proposal = ToolProposal(
        _required_string(proposal_data, "call_id"),
        _required_string(proposal_data, "tool_name"),
        arguments,
    )
    request = policy.approval_for(proposal)
    if approval.get("digest") != request.digest:
        raise ValueError("persisted approval digest is invalid")
    return request


def _validate_resume_decision(
    decision: ResumeDecision,
    pending: ApprovalRequest,
) -> None:
    if decision.action not in {"approve", "reject"}:
        raise ValueError("decision action must be approve or reject")
    if not digests_match(decision.digest, pending.digest):
        raise ValueError("approval digest does not match pending proposal")
    if decision.action == "reject" and decision.arguments is not None:
        raise ValueError("a rejection cannot edit arguments")


def _decision_to_dict(decision: ResumeDecision) -> dict[str, Any]:
    return {
        "action": decision.action,
        "digest": decision.digest,
        "reason": decision.reason,
        "arguments": (
            to_json_value(decision.arguments)
            if decision.arguments is not None
            else None
        ),
    }


def _errored_call(
    call_id: str,
    name: str,
    arguments: Mapping[str, Any],
    error: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "call_id": call_id,
        "tool_name": name,
        "arguments": to_json_value(arguments),
        "risk": Risk.DENY.value,
        "approval_status": "not_required",
        "rejection_reason": "",
        "error": error,
        "detail": detail,
    }


def _observation(
    call_id: str,
    name: str,
    content: Any,
    *,
    error: bool = False,
) -> dict[str, Any]:
    if isinstance(content, str):
        rendered = content
    else:
        rendered = json.dumps(
            content,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    return {
        "call_id": call_id,
        "name": name,
        "content": rendered,
        "error": error,
    }


def _to_outcome(
    result: Mapping[str, Any],
    run_id: str,
    policy: ToolPolicy,
) -> RunOutcome:
    interrupts = result.get("__interrupt__", ())
    if interrupts:
        return RunOutcome(
            pending_approval=_approval_from_interrupt(interrupts[0], policy),
            run_id=run_id,
        )
    return RunOutcome(
        final_text=str(result.get("final_text", "")),
        run_id=run_id,
    )
