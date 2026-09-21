from __future__ import annotations

import json
import multiprocessing
import os
import stat
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from agent_core.checkpoints import JsonCheckpointStore
from agent_core.contracts import ApprovalRequest, Risk, RunState, ToolProposal
from agent_core.side_effects import ClaimOutcome, SideEffectLedger


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


@pytest.mark.parametrize(
    "secret_key",
    [
        "github_token",
        "service-token",
        "serviceToken",
        "client_secret",
        "client-secret",
        "clientSecret",
        "db_password",
        "db-password",
        "dbPassword",
        "cloud_credential",
        "cloud-credential",
        "cloudCredential",
        "request_authorization",
        "request-authorization",
        "requestAuthorization",
        "openai_api_key",
        "openai-api-key",
        "openaiApiKey",
        "signing_private_key",
        "signing-private-key",
        "signingPrivateKey",
    ],
)
def test_checkpoint_rejects_nested_secret_key_variants(
    tmp_path,
    secret_key: str,
) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    state = RunState(
        run_id="run-secret-key",
        response_state={"provider": {"configuration": {secret_key: "replace-me"}}},
    )

    with pytest.raises(ValueError, match="secret"):
        store.save(state)

    assert store.load(state.run_id) is None


@pytest.mark.parametrize(
    "content",
    [
        "TOKEN=opaque-value-1234567890",
        "SECRET: opaque-value-1234567890",
        'PASSWORD = "opaque-value-1234567890"',
        "CREDENTIAL: opaque-value-1234567890",
        "AUTHORIZATION='opaque-value-1234567890'",
        "API_KEY: opaque-value-1234567890",
        "PRIVATE_KEY = opaque-value-1234567890",
        "githubToken = opaque-value-1234567890",
        "service-token: opaque-value-1234567890",
        '"Authorization": "Bearer opaque-value-1234567890"',
    ],
)
def test_checkpoint_rejects_sensitive_assignments_in_nested_write_content(
    tmp_path,
    content: str,
) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    proposal = ToolProposal(
        "call-sensitive-label",
        "write_file",
        {"path": "notes.txt", "content": content},
    )
    request = ApprovalRequest(
        proposal=proposal,
        risk=Risk.APPROVAL,
        normalized_arguments="synthetic",
        preview="synthetic",
        digest="digest",
    )
    state = replace(sample_state("run-sensitive-label"), pending_approval=request)

    with pytest.raises(ValueError, match="secret"):
        store.save(state)

    assert store.load(state.run_id) is None


def test_checkpoint_allows_placeholder_assignments_in_nested_strings(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    state = RunState(
        run_id="run-placeholders",
        response_state={
            "messages": [
                {
                    "content": (
                        "OPENAI_API_KEY=\n"
                        "CLIENT_SECRET=your-key-here\n"
                        "TOKEN=replace-me"
                    )
                }
            ]
        },
    )

    store.save(state)

    assert store.load(state.run_id) == state


@pytest.mark.parametrize(
    ("metric_key", "metric_value"),
    [
        ("input_tokens", 12),
        ("output_tokens", 8),
        ("total_tokens", 20),
        ("token_count", 20),
        ("token_budget", 100),
        ("max_tokens", 200),
    ],
)
def test_checkpoint_allows_non_negative_token_metrics(
    tmp_path,
    metric_key: str,
    metric_value: int,
) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    state = RunState(
        run_id="run-token-metric",
        response_state={
            "usage": {metric_key: metric_value},
            "history": [{"metrics": {metric_key: metric_value}}],
        },
    )

    store.save(state)

    assert store.load(state.run_id) == state


@pytest.mark.parametrize("invalid_value", [-1, 1.5, "12", True])
def test_checkpoint_rejects_invalid_token_metric_values(
    tmp_path,
    invalid_value: object,
) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    state = RunState(
        run_id="run-invalid-token-metric",
        response_state={"usage": {"input_tokens": invalid_value}},
    )

    with pytest.raises(ValueError, match="secret"):
        store.save(state)


@pytest.mark.parametrize(
    "text",
    [
        "token budget exceeded",
        "password policy",
        "credential rotation guide",
        "authorization overview",
    ],
)
def test_checkpoint_allows_sensitive_words_in_ordinary_text(
    tmp_path,
    text: str,
) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    state = RunState(
        run_id="run-ordinary-text",
        response_state={"messages": [{"content": text}]},
    )

    store.save(state)

    assert store.load(state.run_id) == state


def test_checkpoint_rejects_credentials_inside_pending_write_content(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    synthetic_token = "sk-" + "proj-" + ("A" * 48)
    proposal = ToolProposal(
        "call-secret",
        "write_file",
        {
            "path": ".env",
            "content": f"OPENAI_API_KEY={synthetic_token}",
        },
    )
    request = ApprovalRequest(
        proposal=proposal,
        risk=Risk.APPROVAL,
        normalized_arguments="not-persistable",
        preview="not-persistable",
        digest="digest",
    )
    state = replace(sample_state("run-write-secret"), pending_approval=request)

    with pytest.raises(ValueError, match="secret"):
        store.save(state)

    assert store.load(state.run_id) is None


@pytest.mark.parametrize(
    "synthetic_token",
    [
        "sk-" + "proj-" + ("B" * 48),
        "gh" + "p_" + ("C" * 36),
        "eyJ" + ("D" * 20) + "." + ("E" * 24) + "." + ("F" * 24),
    ],
)
def test_checkpoint_rejects_common_token_shapes(
    tmp_path,
    synthetic_token: str,
) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    state = RunState(
        run_id="run-token-shape",
        response_state={"messages": [{"role": "tool", "content": synthetic_token}]},
    )

    with pytest.raises(ValueError, match="secret"):
        store.save(state)

    assert store.load(state.run_id) is None


def test_checkpoint_rejects_non_whitelisted_persisted_fields(tmp_path) -> None:
    store = JsonCheckpointStore(tmp_path / ".runs")
    state = sample_state()
    store.save(state)
    checkpoint_path = tmp_path / ".runs" / "run-1.json"
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    payload["unexpected"] = "not part of RunState"
    checkpoint_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="field"):
        store.load(state.run_id)


def claim_in_process(ledger_path: str, barrier: Any, results: Any) -> None:
    ledger = SideEffectLedger(ledger_path)
    barrier.wait(10)
    results.put(ledger.claim("run-1", "call-write").outcome.value)


def test_cross_process_claims_grant_exactly_one_winner(tmp_path) -> None:
    context = multiprocessing.get_context("spawn")
    contenders = 4
    barrier = context.Barrier(contenders)
    results = context.Queue()
    ledger_path = tmp_path / "side-effects.json"
    processes = [
        context.Process(
            target=claim_in_process,
            args=(str(ledger_path), barrier, results),
        )
        for _ in range(contenders)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(30)

    assert [process.exitcode for process in processes] == [0] * contenders
    outcomes = sorted(results.get(timeout=5) for _ in range(contenders))
    assert outcomes == [ClaimOutcome.GRANTED.value] + [
        ClaimOutcome.UNCONFIRMED.value
    ] * (contenders - 1)
    assert SideEffectLedger(ledger_path).status("run-1", "call-write") == "claimed"


def test_checkpoint_store_imports_no_agent_framework() -> None:
    project = Path(__file__).parents[1]
    program = (
        "import sys\n"
        "import agent_core.checkpoints\n"
        "import agent_core.side_effects\n"
        "frameworks = {'langchain', 'langchain_core', 'langgraph'}\n"
        "print(','.join(sorted({n.split('.')[0] for n in sys.modules} & frameworks)))\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )

    assert completed.stdout.strip() == ""
