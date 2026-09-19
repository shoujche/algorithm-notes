from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
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
)
from .mcp_adapter import validate_function_tools
from .openai_loop import ResumeDecision
from .policy import ToolPolicy


class GraphState(TypedDict, total=False):
    messages: Annotated[list[Any], add_messages]
    calls: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    model_calls: int
    tool_calls: int
    final_text: str
    halt: bool


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
        run_id_factory: Callable[[], str] | None = None,
    ) -> None:
        if min(max_model_calls, max_tool_calls) < 1:
            raise ValueError("call budgets must be positive")
        self._model = model
        self._mcp = mcp
        self._checkpoint_path = Path(checkpoint_path)
        self._policy = policy or ToolPolicy()
        self._max_model_calls = max_model_calls
        self._max_tool_calls = max_tool_calls
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

    @property
    def side_effect_ledger(self) -> SideEffectLedger:
        return self._side_effects

    async def start(self, user_input: str) -> RunOutcome:
        run_id = self._run_id_factory()
        graph = await self.build_graph()
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
        with self._claims.claim(run_id):
            graph = await self.build_graph()
            pending = await self._pending_from_graph(graph, run_id)
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
            result = await graph.ainvoke(
                Command(resume=_decision_to_dict(decision)),
                _config(run_id),
            )
            return _to_outcome(result, run_id, self._policy)

    async def pending_approval(self, run_id: str) -> ApprovalRequest | None:
        graph = await self.build_graph()
        return await self._pending_from_graph(graph, run_id)

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
        response = await self._bound_model.ainvoke(state.get("messages", []))
        return {
            "messages": [response],
            "model_calls": model_calls + 1,
            "calls": [],
            "observations": [],
            "final_text": "",
            "halt": False,
        }

    async def _route_response(self, state: GraphState) -> dict[str, Any]:
        message = _last_ai_message(state.get("messages", []))
        if not message.tool_calls:
            return {
                "final_text": _message_text(message.content),
                "calls": [],
                "halt": True,
            }

        seen: set[str] = set()
        calls: list[dict[str, Any]] = []
        for raw_call in message.tool_calls:
            call_id = _required_string(raw_call, "id")
            if call_id in seen:
                continue
            seen.add(call_id)
            name = _required_string(raw_call, "name")
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
        if decision.get("digest") != approval.digest:
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
                call["arguments"] = to_json_value(edited_arguments)
            call["approval_status"] = "approved"
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
        call_id = _required_string(call, "call_id")
        name = _required_string(call, "tool_name")
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

        if call.get("risk") == Risk.APPROVAL.value:
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
            return _observation(call_id, name, result)

        try:
            result = await self._mcp.call(name, dict(arguments))
            return _observation(call_id, name, result)
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
        interrupts = getattr(snapshot, "interrupts", ())
        if not interrupts:
            return None
        return _approval_from_interrupt(interrupts[0], self._policy)


def _config(run_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": run_id}}


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
    if decision.digest != pending.digest:
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
