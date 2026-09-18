from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from .checkpoints import JsonCheckpointStore
from .contracts import Risk, RunOutcome, RunState, ToolProposal, to_json_value
from .policy import ToolPolicy


class BudgetExceeded(RuntimeError):
    pass


class ResponsesRetryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResumeDecision:
    action: str
    digest: str
    reason: str = ""
    arguments: Mapping[str, Any] | None = None


class OpenAIReActAgent:
    def __init__(
        self,
        *,
        client: Any,
        mcp: Any,
        checkpoints: JsonCheckpointStore,
        model: str,
        policy: ToolPolicy | None = None,
        max_turns: int = 8,
        max_tool_calls: int = 12,
        max_retries: int = 2,
        max_output_chars: int = 32_768,
        timeout_seconds: float = 120,
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if min(max_turns, max_tool_calls, max_output_chars) < 1:
            raise ValueError("budgets must be positive")
        if max_retries < 0 or timeout_seconds <= 0:
            raise ValueError("retry and timeout budgets are invalid")
        self._client = client
        self._mcp = mcp
        self._checkpoints = checkpoints
        self._model = model
        self._policy = policy or ToolPolicy()
        self._max_turns = max_turns
        self._max_tool_calls = max_tool_calls
        self._max_retries = max_retries
        self._max_output_chars = max_output_chars
        self._timeout_seconds = timeout_seconds
        self._run_id_factory = run_id_factory or (lambda: uuid.uuid4().hex)
        self._tools: list[dict[str, Any]] = []

    async def start(self, user_input: str) -> RunOutcome:
        self._tools = await self._mcp.list_function_tools()
        state = RunState(
            run_id=self._run_id_factory(),
            max_turns=self._max_turns,
            max_tool_calls=self._max_tool_calls,
        )
        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await self._continue(state, user_input, None)
        except TimeoutError as error:
            raise BudgetExceeded("total timeout budget exceeded") from error

    async def resume(
        self,
        run_id: str,
        decision: ResumeDecision,
    ) -> RunOutcome:
        state = self._checkpoints.load(run_id)
        if state is None:
            raise ValueError(f"run {run_id!r} was not found")
        pending = state.pending_approval
        if pending is None:
            raise ValueError("run has no pending approval")
        if decision.action not in {"approve", "reject"}:
            raise ValueError("decision action must be approve or reject")
        if decision.digest != pending.digest:
            raise ValueError("approval digest does not match pending proposal")
        if decision.action == "reject" and decision.arguments is not None:
            raise ValueError("a rejection cannot edit arguments")

        self._tools = await self._mcp.list_function_tools()
        response_state = state.response_state
        response_id = _required_string(response_state, "response_id")
        calls = _stored_calls(response_state)
        outputs = _stored_outputs(response_state)
        proposal = pending.proposal

        if decision.action == "reject":
            outputs[proposal.call_id] = _json_output(
                {"error": "rejected", "reason": decision.reason}
            )
            state = replace(state, pending_approval=None)
            approved_call_ids: frozenset[str] = frozenset()
        else:
            if decision.arguments is not None:
                proposal = ToolProposal(
                    proposal.call_id,
                    proposal.tool_name,
                    decision.arguments,
                )
            if self._policy.classify(proposal) is not Risk.APPROVAL:
                raise ValueError("edited proposal is not approvable")
            if decision.arguments is not None:
                for call in calls:
                    if call["call_id"] == proposal.call_id:
                        call["arguments"] = _json_output(decision.arguments)
            state = replace(state, pending_approval=None)
            approved_call_ids = frozenset({proposal.call_id})

        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await self._process_calls(
                    state,
                    response_id,
                    calls,
                    outputs,
                    approved_call_ids,
                )
        except TimeoutError as error:
            raise BudgetExceeded("total timeout budget exceeded") from error

    async def _continue(
        self,
        state: RunState,
        model_input: Any,
        previous_response_id: str | None,
    ) -> RunOutcome:
        if state.turn >= state.max_turns:
            raise BudgetExceeded("model turn budget exceeded")
        response = await self._create_response(model_input, previous_response_id)
        state = replace(state, turn=state.turn + 1)
        response_id = _required_string(response, "id")
        calls = [
            _call_to_stored(item)
            for item in _items(response)
            if _value(item, "type") == "function_call"
        ]
        if not calls:
            final_text = "".join(_output_texts(response))
            final_state = replace(
                state,
                response_state={"response_id": response_id},
                pending_approval=None,
            )
            self._checkpoints.save(final_state)
            return RunOutcome(final_text=final_text, run_id=state.run_id)

        unique_count = len({call["call_id"] for call in calls})
        if state.tool_calls + unique_count > state.max_tool_calls:
            raise BudgetExceeded("tool call budget exceeded")
        state = replace(state, tool_calls=state.tool_calls + unique_count)
        return await self._process_calls(state, response_id, calls, {})

    async def _process_calls(
        self,
        state: RunState,
        response_id: str,
        calls: list[dict[str, str]],
        outputs: dict[str, str],
        approved_call_ids: frozenset[str] = frozenset(),
    ) -> RunOutcome:
        parsed: dict[str, ToolProposal | None] = {}
        seen: set[str] = set()
        for call in calls:
            call_id = call["call_id"]
            if call_id in seen:
                continue
            seen.add(call_id)
            if call_id in outputs:
                continue
            try:
                arguments = json.loads(call["arguments"])
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be a JSON object")
                parsed[call_id] = ToolProposal(call_id, call["name"], arguments)
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                parsed[call_id] = None
                outputs[call_id] = _json_output(
                    {"error": "malformed_arguments", "detail": str(error)}
                )

        if not approved_call_ids:
            for call in calls:
                call_id = call["call_id"]
                proposal = parsed.get(call_id)
                if (
                    proposal is not None
                    and self._policy.classify(proposal) is Risk.APPROVAL
                ):
                    approval = self._policy.approval_for(proposal)
                    paused = replace(state, pending_approval=approval)
                    self._save_paused_state(paused, response_id, calls, outputs)
                    return RunOutcome(
                        pending_approval=approval,
                        run_id=state.run_id,
                    )

        for call in calls:
            call_id = call["call_id"]
            if call_id in outputs:
                continue
            proposal = parsed.get(call_id)
            if proposal is None:
                continue
            risk = self._policy.classify(proposal)
            if risk is Risk.DENY:
                outputs[call_id] = _json_output(
                    {"error": "tool_denied", "tool": proposal.tool_name}
                )
                continue
            if risk is Risk.APPROVAL and call_id not in approved_call_ids:
                approval = self._policy.approval_for(proposal)
                paused = replace(state, pending_approval=approval)
                self._save_paused_state(paused, response_id, calls, outputs)
                return RunOutcome(
                    pending_approval=approval,
                    run_id=state.run_id,
                )
            if call_id in state.executed_call_ids:
                outputs[call_id] = _json_output({"error": "duplicate_call_id"})
                continue
            if risk is Risk.APPROVAL:
                state = replace(
                    state,
                    executed_call_ids=state.executed_call_ids | {call_id},
                )
                self._save_paused_state(state, response_id, calls, outputs)
            outputs[call_id] = await self._bounded_tool_call(proposal)
            if risk is Risk.READ_ONLY:
                state = replace(
                    state,
                    executed_call_ids=state.executed_call_ids | {call_id},
                )

        ordered_outputs: list[dict[str, str]] = []
        emitted: set[str] = set()
        for call in calls:
            call_id = call["call_id"]
            if call_id in emitted:
                continue
            emitted.add(call_id)
            ordered_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": outputs[call_id],
                }
            )
        return await self._continue(state, ordered_outputs, response_id)

    async def _bounded_tool_call(self, proposal: ToolProposal) -> str:
        output = await self._mcp.call(
            proposal.tool_name,
            to_json_value(proposal.arguments),
        )
        if not isinstance(output, str):
            raise TypeError("MCP adapter results must be JSON strings")
        if len(output) > self._max_output_chars:
            raise BudgetExceeded("tool output budget exceeded")
        return output

    async def _create_response(
        self,
        model_input: Any,
        previous_response_id: str | None,
    ) -> Any:
        request: dict[str, Any] = {
            "model": self._model,
            "tools": self._tools,
            "input": model_input,
        }
        if previous_response_id is not None:
            request["previous_response_id"] = previous_response_id
        last_error: Exception | None = None
        for _ in range(self._max_retries + 1):
            try:
                return await self._client.responses.create(**request)
            except Exception as error:
                last_error = error
        attempts = self._max_retries + 1
        raise ResponsesRetryError(
            f"Responses API failed after {attempts} attempts"
        ) from last_error

    def _save_paused_state(
        self,
        state: RunState,
        response_id: str,
        calls: list[dict[str, str]],
        outputs: dict[str, str],
    ) -> None:
        self._checkpoints.save(
            replace(
                state,
                response_state={
                    "response_id": response_id,
                    "calls": calls,
                    "outputs": outputs,
                },
            )
        )


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _items(response: Any) -> list[Any]:
    output = _value(response, "output", [])
    return list(output) if output is not None else []


def _output_texts(response: Any):
    for item in _items(response):
        if _value(item, "type") != "message":
            continue
        for content in _value(item, "content", []):
            if _value(content, "type") == "output_text":
                text = _value(content, "text")
                if isinstance(text, str):
                    yield text


def _call_to_stored(item: Any) -> dict[str, str]:
    call_id = _required_string(item, "call_id")
    name = _required_string(item, "name")
    arguments = _required_string(item, "arguments")
    return {"call_id": call_id, "name": name, "arguments": arguments}


def _required_string(item: Any, name: str) -> str:
    value = _value(item, name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _stored_calls(response_state: Mapping[str, Any]) -> list[dict[str, str]]:
    calls = response_state.get("calls")
    if not isinstance(calls, (list, tuple)):
        raise ValueError("checkpoint has no pending function calls")
    return [
        {
            "call_id": _required_string(call, "call_id"),
            "name": _required_string(call, "name"),
            "arguments": _required_string(call, "arguments"),
        }
        for call in calls
    ]


def _stored_outputs(response_state: Mapping[str, Any]) -> dict[str, str]:
    outputs = response_state.get("outputs", {})
    if not isinstance(outputs, Mapping):
        raise ValueError("checkpoint outputs must be an object")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in outputs.items()):
        raise ValueError("checkpoint outputs must map strings to strings")
    return dict(outputs)


def _json_output(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
