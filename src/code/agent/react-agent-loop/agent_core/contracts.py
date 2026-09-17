from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Risk(str, Enum):
    READ_ONLY = "read_only"
    APPROVAL = "approval"
    DENY = "deny"


@dataclass(frozen=True)
class ToolProposal:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]


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
