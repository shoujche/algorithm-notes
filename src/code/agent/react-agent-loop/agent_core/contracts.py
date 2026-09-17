from __future__ import annotations

import math
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any


class FrozenMapping(Mapping[str, Any]):
    __slots__ = ("_data",)

    def __init__(self, source: Mapping[str, Any]) -> None:
        frozen = {key: _freeze_json(value) for key, value in source.items()}
        object.__setattr__(self, "_data", MappingProxyType(frozen))

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"FrozenMapping({dict(self._data)!r})"


def _freeze_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("JSON values must not contain NaN or infinity")
        return value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("JSON object keys must be strings")
        return FrozenMapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    raise TypeError(f"unsupported JSON value: {type(value).__name__}")


def to_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: to_json_value(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_value(child) for child in value]
    return value


class Risk(str, Enum):
    READ_ONLY = "read_only"
    APPROVAL = "approval"
    DENY = "deny"


@dataclass(frozen=True)
class ToolProposal:
    call_id: str
    tool_name: str
    arguments: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", FrozenMapping(self.arguments))


@dataclass(frozen=True)
class ApprovalRequest:
    proposal: ToolProposal
    risk: Risk
    normalized_arguments: str
    preview: str | list[str]
    digest: str


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    success: bool
    output: Any
    retryable: bool = False


@dataclass(frozen=True)
class RunState:
    run_id: str
    response_state: dict[str, Any] = field(default_factory=dict)
    turn: int = 0
    max_turns: int = 0
    tool_calls: int = 0
    max_tool_calls: int = 0
    pending_approval: ApprovalRequest | None = None
    executed_call_ids: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class RunOutcome:
    final_text: str | None = None
    pending_approval: ApprovalRequest | None = None
    run_id: str | None = None
