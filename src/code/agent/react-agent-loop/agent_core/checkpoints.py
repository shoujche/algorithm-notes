from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
from collections import deque
from dataclasses import fields as dataclass_fields
from dataclasses import is_dataclass
from enum import Enum
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import attrs
from langgraph.types import Send
from pydantic import BaseModel

from .contracts import ApprovalRequest, Risk, RunState, ToolProposal, to_json_value

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_STATE_FIELDS = frozenset(
    {
        "run_id",
        "response_state",
        "turn",
        "max_turns",
        "tool_calls",
        "max_tool_calls",
        "pending_approval",
        "executed_call_ids",
        "approved_call_digests",
        "rejected_call_reasons",
    }
)
_APPROVAL_FIELDS = frozenset(
    {"proposal", "risk", "normalized_arguments", "preview", "digest"}
)
_PROPOSAL_FIELDS = frozenset({"call_id", "tool_name", "arguments"})
_SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b"),
    re.compile(
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
    ),
    re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{16,}"),
)
_SENSITIVE_KEY_PARTS = frozenset(
    {
        "authorization",
        "credential",
        "credentials",
        "password",
        "passwd",
        "secret",
        "secrets",
        "token",
        "tokens",
    }
)
_PLACEHOLDER_VALUES = frozenset({"", "replace-me", "your-key-here"})
_STRING_LABEL_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
_ALLOWED_TOKEN_METRICS = frozenset(
    {
        "input_tokens",
        "max_tokens",
        "output_tokens",
        "token_budget",
        "token_count",
        "total_tokens",
    }
)


class RunClaimedError(RuntimeError):
    pass


def _normalize_key(key: str) -> str:
    snake_case = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return re.sub(r"[^a-z0-9]+", "_", snake_case.lower()).strip("_")


def _key_may_hold_secret(key: str) -> bool:
    normalized = _normalize_key(key)
    parts = set(normalized.split("_"))
    if parts & _SENSITIVE_KEY_PARTS:
        return True
    if {"api", "key"} <= parts or {"private", "key"} <= parts:
        return True
    return normalized in {"apikey", "privatekey"}


def _contains_sensitive_assignment(value: str) -> bool:
    for label in _STRING_LABEL_PATTERN.finditer(value):
        if not _key_may_hold_secret(label.group()):
            continue

        remainder_lines = value[label.end() :].splitlines()
        if not remainder_lines:
            continue
        remainder = remainder_lines[0]
        assignment = re.match(r"""^\s*["']?\s*[:=]\s*(.*)$""", remainder)
        if assignment is None:
            continue
        assigned = assignment.group(1)
        normalized_value = assigned.strip().strip("'\"").strip().lower()
        if normalized_value not in _PLACEHOLDER_VALUES:
            return True
    return False


def _value_looks_like_secret(value: str) -> bool:
    return _contains_sensitive_assignment(value) or any(
        pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS
    )


def contains_secret(value: Any) -> bool:
    """Fail closed on secret-like or unsupported checkpoint values."""
    return _contains_secret_value(value, set())


def _contains_secret_value(value: Any, active_ids: set[int]) -> bool:
    if value is None or type(value) in {bool, int, float}:
        return False
    if isinstance(value, str):
        return _value_looks_like_secret(value)
    if isinstance(value, Enum):
        return _contains_secret_value(
            object.__getattribute__(value, "_value_"),
            active_ids,
        )

    identity = id(value)
    if identity in active_ids:
        return True
    active_ids.add(identity)
    try:
        if isinstance(value, Mapping):
            for key, child in value.items():
                normalized_key = _normalize_key(str(key))
                if normalized_key in _ALLOWED_TOKEN_METRICS:
                    if type(child) is int and child >= 0:
                        continue
                    return True
                if _key_may_hold_secret(str(key)) or _contains_secret_value(
                    child,
                    active_ids,
                ):
                    return True
            return False

        namedtuple_fields = getattr(type(value), "_fields", None)
        if (
            isinstance(value, tuple)
            and isinstance(namedtuple_fields, tuple)
            and all(isinstance(name, str) for name in namedtuple_fields)
        ):
            for index, name in enumerate(namedtuple_fields):
                if _key_may_hold_secret(name) or _contains_secret_value(
                    tuple.__getitem__(value, index),
                    active_ids,
                ):
                    return True
            return False

        if isinstance(value, (list, tuple, deque)):
            return any(
                _contains_secret_value(child, active_ids) for child in value
            )

        if isinstance(value, BaseModel):
            return _contains_secret_value(
                value.model_dump(mode="json", by_alias=True, exclude_none=True),
                active_ids,
            )

        if isinstance(value, Send):
            return any(
                _contains_secret_value(
                    object.__getattribute__(value, field_name),
                    active_ids,
                )
                for field_name in ("node", "arg", "timeout")
            )

        if is_dataclass(value) and not isinstance(value, type):
            for field in dataclass_fields(value):
                if _key_may_hold_secret(field.name) or _contains_secret_value(
                    object.__getattribute__(value, field.name),
                    active_ids,
                ):
                    return True
            return False

        if attrs.has(type(value)):
            for field in attrs.fields(type(value)):
                if _key_may_hold_secret(field.name) or _contains_secret_value(
                    object.__getattribute__(value, field.name),
                    active_ids,
                ):
                    return True
            return False

        return True
    finally:
        active_ids.remove(identity)


_contains_secret = contains_secret


def _proposal_to_dict(proposal: ToolProposal) -> dict[str, Any]:
    return {
        "call_id": proposal.call_id,
        "tool_name": proposal.tool_name,
        "arguments": to_json_value(proposal.arguments),
    }


def _approval_to_dict(request: ApprovalRequest) -> dict[str, Any]:
    return {
        "proposal": _proposal_to_dict(request.proposal),
        "risk": request.risk.value,
        "normalized_arguments": request.normalized_arguments,
        "preview": to_json_value(request.preview),
        "digest": request.digest,
    }


def _state_to_dict(state: RunState) -> dict[str, Any]:
    return {
        "run_id": state.run_id,
        "response_state": to_json_value(state.response_state),
        "turn": state.turn,
        "max_turns": state.max_turns,
        "tool_calls": state.tool_calls,
        "max_tool_calls": state.max_tool_calls,
        "pending_approval": (
            _approval_to_dict(state.pending_approval)
            if state.pending_approval is not None
            else None
        ),
        "executed_call_ids": sorted(state.executed_call_ids),
        "approved_call_digests": to_json_value(state.approved_call_digests),
        "rejected_call_reasons": to_json_value(state.rejected_call_reasons),
    }


def _require_exact_fields(
    data: Any,
    expected: frozenset[str],
    context: str,
) -> Mapping[str, Any]:
    if not isinstance(data, Mapping):
        raise ValueError(f"{context} must be a JSON object")
    actual = set(data)
    if actual != expected:
        unknown = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise ValueError(
            f"{context} field whitelist mismatch; unknown={unknown}, missing={missing}"
        )
    return data


def _validate_checkpoint_schema(data: Any) -> Mapping[str, Any]:
    state_data = _require_exact_fields(data, _STATE_FIELDS, "checkpoint")
    if not isinstance(state_data["response_state"], Mapping):
        raise ValueError("response_state must be a JSON object")
    if not isinstance(state_data["executed_call_ids"], list):
        raise ValueError("executed_call_ids must be a JSON array")
    for field_name in ("approved_call_digests", "rejected_call_reasons"):
        values = state_data[field_name]
        if not isinstance(values, Mapping) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in values.items()
        ):
            raise ValueError(f"{field_name} must map strings to strings")

    approval_data = state_data["pending_approval"]
    if approval_data is not None:
        approval = _require_exact_fields(
            approval_data,
            _APPROVAL_FIELDS,
            "approval",
        )
        proposal = _require_exact_fields(
            approval["proposal"],
            _PROPOSAL_FIELDS,
            "proposal",
        )
        if not isinstance(proposal["arguments"], Mapping):
            raise ValueError("proposal arguments must be a JSON object")
    return state_data


def _state_from_dict(data: dict[str, Any]) -> RunState:
    data = dict(_validate_checkpoint_schema(data))
    approval_data = data.get("pending_approval")
    approval = None
    if approval_data is not None:
        proposal_data = approval_data["proposal"]
        proposal = ToolProposal(
            call_id=proposal_data["call_id"],
            tool_name=proposal_data["tool_name"],
            arguments=proposal_data["arguments"],
        )
        approval = ApprovalRequest(
            proposal=proposal,
            risk=Risk(approval_data["risk"]),
            normalized_arguments=approval_data["normalized_arguments"],
            preview=approval_data["preview"],
            digest=approval_data["digest"],
        )

    return RunState(
        run_id=data["run_id"],
        response_state=data.get("response_state", {}),
        turn=data.get("turn", 0),
        max_turns=data.get("max_turns", 0),
        tool_calls=data.get("tool_calls", 0),
        max_tool_calls=data.get("max_tool_calls", 0),
        pending_approval=approval,
        executed_call_ids=frozenset(data.get("executed_call_ids", [])),
        approved_call_digests=data.get("approved_call_digests", {}),
        rejected_call_reasons=data.get("rejected_call_reasons", {}),
    )


class JsonCheckpointStore:
    def __init__(self, directory: str | Path = ".runs") -> None:
        self.directory = Path(directory)

    def _path_for(self, run_id: str) -> Path:
        if not _RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError("run_id may contain only letters, digits, '-' and '_'")
        return self.directory / f"{run_id}.json"

    @contextmanager
    def claim(self, run_id: str) -> Iterator[None]:
        self._path_for(run_id)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        lock_path = self.directory / f"{run_id}.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        os.chmod(lock_path, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RunClaimedError(
                    f"run {run_id!r} is already claimed"
                ) from error
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def save(self, state: RunState) -> None:
        destination = self._path_for(state.run_id)
        payload = _state_to_dict(state)
        if _contains_secret(payload):
            raise ValueError("checkpoint state contains a secret-bearing field")

        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.directory,
                prefix=f"{state.run_id}.",
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
            os.replace(temporary_path, destination)
            os.chmod(destination, 0o600)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def load(self, run_id: str) -> RunState | None:
        path = self._path_for(run_id)
        try:
            with path.open(encoding="utf-8") as checkpoint:
                data = json.load(checkpoint)
        except FileNotFoundError:
            return None
        _validate_checkpoint_schema(data)
        if _contains_secret(data):
            raise ValueError("checkpoint state contains a secret-bearing field")
        state = _state_from_dict(data)
        if state.run_id != run_id:
            raise ValueError("checkpoint run_id does not match its filename")
        return state

    def delete(self, run_id: str) -> None:
        self._path_for(run_id).unlink(missing_ok=True)
