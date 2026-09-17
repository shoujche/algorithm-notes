from __future__ import annotations

import hashlib
import json
from typing import Any

from .contracts import ApprovalRequest, Risk, ToolProposal, to_json_value

_READ_ONLY_TOOLS = frozenset({"list_files", "read_file", "list_skills", "read_skill"})
_APPROVABLE_TOOLS = frozenset({"write_file", "run_command"})


def _canonical_json(value: Any) -> str:
    return json.dumps(
        to_json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def approval_digest(proposal: ToolProposal) -> str:
    payload = {
        "arguments": proposal.arguments,
        "call_id": proposal.call_id,
        "tool_name": proposal.tool_name,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


class ToolPolicy:
    def classify(self, proposal: ToolProposal) -> Risk:
        if proposal.tool_name in _READ_ONLY_TOOLS:
            return Risk.READ_ONLY
        if proposal.tool_name in _APPROVABLE_TOOLS:
            return Risk.APPROVAL
        return Risk.DENY

    def approval_for(self, proposal: ToolProposal) -> ApprovalRequest:
        if self.classify(proposal) is not Risk.APPROVAL:
            raise ValueError(f"{proposal.tool_name} does not require approval")

        if proposal.tool_name == "write_file":
            preview: str | list[str] = str(proposal.arguments.get("content", ""))
        else:
            argv = proposal.arguments.get("argv", [])
            preview = (
                [str(argument) for argument in argv]
                if isinstance(argv, (list, tuple))
                else []
            )

        return ApprovalRequest(
            proposal=proposal,
            risk=Risk.APPROVAL,
            normalized_arguments=_canonical_json(proposal.arguments),
            preview=preview,
            digest=approval_digest(proposal),
        )
