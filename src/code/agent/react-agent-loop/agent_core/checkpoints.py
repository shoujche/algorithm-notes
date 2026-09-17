from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from .contracts import ApprovalRequest, Risk, RunState, ToolProposal

_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "auth_token",
        "authorization",
        "credentials",
        "password",
        "private_key",
        "refresh_token",
        "secret",
    }
)


def _contains_secret(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).lower().replace("-", "_")
            if normalized_key in _SECRET_KEYS or _contains_secret(child):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_secret(child) for child in value)
    return False


def _proposal_to_dict(proposal: ToolProposal) -> dict[str, Any]:
    return {
        "call_id": proposal.call_id,
        "tool_name": proposal.tool_name,
        "arguments": proposal.arguments,
    }


def _approval_to_dict(request: ApprovalRequest) -> dict[str, Any]:
    return {
        "proposal": _proposal_to_dict(request.proposal),
        "risk": request.risk.value,
        "normalized_arguments": request.normalized_arguments,
        "preview": request.preview,
        "digest": request.digest,
    }


def _state_to_dict(state: RunState) -> dict[str, Any]:
    return {
        "run_id": state.run_id,
        "response_state": state.response_state,
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
    }


def _state_from_dict(data: dict[str, Any]) -> RunState:
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
    )


class JsonCheckpointStore:
    def __init__(self, directory: str | Path = ".runs") -> None:
        self.directory = Path(directory)

    def _path_for(self, run_id: str) -> Path:
        if not _RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError("run_id may contain only letters, digits, '-' and '_'")
        return self.directory / f"{run_id}.json"

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
        state = _state_from_dict(data)
        if state.run_id != run_id:
            raise ValueError("checkpoint run_id does not match its filename")
        return state

    def delete(self, run_id: str) -> None:
        self._path_for(run_id).unlink(missing_ok=True)
