from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

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
        with self._checkpoints.claim(run_id):
            return await self._resume_claimed(run_id, decision)

    async def _resume_claimed(
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
        proposal = pending.proposal

        if decision.action == "reject":
            state = replace(
                state,
                pending_approval=None,
                rejected_call_reasons={
                    **to_json_value(state.rejected_call_reasons),
                    proposal.call_id: decision.reason,
                },
            )
        else:
            arguments = (
                decision.arguments
                if decision.arguments is not None
                else proposal.arguments
            )
            self._validate_tool_arguments(proposal.tool_name, arguments)
            proposal = ToolProposal(
                proposal.call_id,
                proposal.tool_name,
                arguments,
            )
            if self._policy.classify(proposal) is not Risk.APPROVAL:
                raise ValueError("edited proposal is not approvable")
            rebound = self._policy.approval_for(proposal)
            for call in calls:
                if call["call_id"] == proposal.call_id:
                    call["arguments"] = rebound.normalized_arguments
            state = replace(
                state,
                pending_approval=None,
                approved_call_digests={
                    **to_json_value(state.approved_call_digests),
                    proposal.call_id: rebound.digest,
                },
            )

        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await self._process_calls(state, response_id, calls)
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
        state = replace(
            state,
            turn=state.turn + 1,
            approved_call_digests={},
            rejected_call_reasons={},
        )
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
        return await self._process_calls(state, response_id, calls)

    async def _process_calls(
        self,
        state: RunState,
        response_id: str,
        calls: list[dict[str, str]],
    ) -> RunOutcome:
        parsed: dict[str, ToolProposal | None] = {}
        parse_errors: dict[str, dict[str, str]] = {}
        seen: set[str] = set()
        for call in calls:
            call_id = call["call_id"]
            if call_id in seen:
                continue
            seen.add(call_id)
            try:
                arguments = json.loads(call["arguments"])
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be a JSON object")
                if self._policy.classify(
                    ToolProposal(call_id, call["name"], arguments)
                ) is not Risk.DENY:
                    self._validate_tool_arguments(call["name"], arguments)
                parsed[call_id] = ToolProposal(call_id, call["name"], arguments)
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                parsed[call_id] = None
                parse_errors[call_id] = {
                    "error": "malformed_arguments",
                    "detail": str(error),
                }

        for call in calls:
            call_id = call["call_id"]
            proposal = parsed.get(call_id)
            if proposal is None or self._policy.classify(proposal) is not Risk.APPROVAL:
                continue
            if (
                call_id in state.approved_call_digests
                or call_id in state.rejected_call_reasons
            ):
                continue
            approval = self._policy.approval_for(proposal)
            paused = replace(state, pending_approval=approval)
            self._save_paused_state(paused, response_id, calls)
            return RunOutcome(
                pending_approval=approval,
                run_id=state.run_id,
            )

        outputs: dict[str, str] = {
            call_id: _json_output(error)
            for call_id, error in parse_errors.items()
        }
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
            if call_id in state.rejected_call_reasons:
                outputs[call_id] = _json_output(
                    {
                        "error": "rejected",
                        "reason": state.rejected_call_reasons[call_id],
                    }
                )
                continue
            if call_id in state.executed_call_ids:
                outputs[call_id] = _json_output({"error": "duplicate_call_id"})
                continue
            if risk is Risk.APPROVAL:
                self._validate_tool_arguments(
                    proposal.tool_name,
                    proposal.arguments,
                )
                rebound = self._policy.approval_for(proposal)
                if state.approved_call_digests.get(call_id) != rebound.digest:
                    raise ValueError("approved proposal digest binding is invalid")
                state = replace(
                    state,
                    executed_call_ids=state.executed_call_ids | {call_id},
                )
                self._save_paused_state(state, response_id, calls)
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
    ) -> None:
        self._checkpoints.save(
            replace(
                state,
                response_state={
                    "response_id": response_id,
                    "calls": calls,
                },
            )
        )

    def _validate_tool_arguments(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> None:
        matching = [
            tool
            for tool in self._tools
            if tool.get("type") == "function" and tool.get("name") == tool_name
        ]
        if len(matching) != 1:
            raise ValueError(f"no unique function schema for tool {tool_name!r}")
        tool = matching[0]
        if tool.get("strict") is not True:
            raise ValueError(f"function schema for {tool_name!r} is not strict")
        schema = tool.get("parameters")
        if not isinstance(schema, Mapping) or schema.get("type") != "object":
            raise ValueError(f"function schema for {tool_name!r} must be an object")
        try:
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(to_json_value(arguments))
        except (SchemaError, ValidationError) as error:
            raise ValueError(
                f"arguments do not match function schema for {tool_name!r}: "
                f"{error.message}"
            ) from error


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


def _json_output(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
