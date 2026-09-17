from __future__ import annotations

import os
import stat

import pytest

from agent_core.checkpoints import JsonCheckpointStore
from agent_core.contracts import ApprovalRequest, Risk, RunState, ToolProposal


def sample_state(run_id: str = "run-1", *, turn: int = 2) -> RunState:
    proposal = ToolProposal(
        "call-1",
        "write_file",
        {"path": "a.py", "content": "print('ok')"},
    )
    request = ApprovalRequest(
        proposal=proposal,
        risk=Risk.APPROVAL,
        normalized_arguments='{"content":"print(\'ok\')","path":"a.py"}',
        preview="print('ok')",
        digest="abc123",
    )
    return RunState(
        run_id=run_id,
        response_state={"response_id": "resp-1", "messages": ["hello"]},
        turn=turn,
        max_turns=8,
        tool_calls=1,
        max_tool_calls=12,
        pending_approval=request,
        executed_call_ids=frozenset({"call-0"}),
    )


def test_checkpoint_round_trip(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    state = sample_state()

    store.save(state)

    assert store.load(state.run_id) == state


def test_unknown_run_id_returns_none_and_delete_is_idempotent(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")

    assert store.load("missing") is None
    store.delete("missing")
    store.delete("missing")


@pytest.mark.parametrize("run_id", ["", ".", "..", "../escape", "a/b", "has space"])
def test_invalid_run_id_characters_are_rejected(tmp_path, run_id: str) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")

    with pytest.raises(ValueError, match="run_id"):
        store.load(run_id)


def test_save_atomically_replaces_existing_checkpoint(tmp_path, monkeypatch) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    store.save(sample_state(turn=1))
    replacements: list[tuple[os.PathLike[str] | str, os.PathLike[str] | str]] = []
    real_replace = os.replace

    def recording_replace(
        source: os.PathLike[str] | str,
        destination: os.PathLike[str] | str,
    ) -> None:
        replacements.append((source, destination))
        real_replace(source, destination)

    monkeypatch.setattr("agent_core.checkpoints.os.replace", recording_replace)
    store.save(sample_state(turn=3))

    assert len(replacements) == 1
    assert store.load("run-1") == sample_state(turn=3)
    assert list((tmp_path / ".runs").glob("*.tmp")) == []


def test_checkpoint_file_permissions_are_owner_only(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    store.save(sample_state())

    mode = stat.S_IMODE((tmp_path / ".runs" / "run-1.json").stat().st_mode)

    assert mode == 0o600


def test_checkpoint_rejects_secret_bearing_state(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    state = RunState(
        run_id="run-secret",
        response_state={"api_key": "must-not-be-persisted"},
    )

    with pytest.raises(ValueError, match="secret"):
        store.save(state)

    assert store.load(state.run_id) is None
