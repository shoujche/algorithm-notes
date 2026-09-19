from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import cli
from agent_core.contracts import ApprovalRequest, Risk, RunOutcome, ToolProposal


class RecordingRunner:
    def __init__(self, outcome: RunOutcome) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, object]] = []

    async def __call__(self, command: str, args: object) -> RunOutcome:
        self.calls.append((command, args))
        return self.outcome


class RaisingRunner:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def __call__(self, command: str, args: object) -> RunOutcome:
        raise self.error


class SyntheticSchemaError(ValueError):
    pass


class ExplodingOutcome:
    @property
    def pending_approval(self) -> object:
        raise ValueError("render sentinel-do-not-echo")


def invoke(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    arguments: list[str],
    *,
    outcome: RunOutcome | None = None,
    api_key: str = "test-only-key",
    docker: str | None = "/usr/bin/docker",
) -> tuple[int, RecordingRunner, str, str]:
    runner = RecordingRunner(outcome or RunOutcome(final_text="done", run_id="run-1"))
    monkeypatch.setattr(cli, "_run_entrypoint", runner)
    monkeypatch.setattr(cli.shutil, "which", lambda _: docker)
    monkeypatch.setenv("OPENAI_API_KEY", api_key)

    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()
    code = cli.main(
        [
            *arguments,
            "--workspace",
            str(workspace),
            "--skills",
            str(skills),
            "--runs",
            str(tmp_path / "runs"),
        ]
    )
    captured = capsys.readouterr()
    return code, runner, captured.out, captured.err


def test_decisions_are_mutually_exclusive() -> None:
    parser = cli.build_parser()

    with pytest.raises(cli.SafeCliError, match="invalid command-line arguments"):
        parser.parse_args(
            ["openai", "--resume", "run-1", "--approve", "--reject", "no"]
        )


@pytest.mark.parametrize("run_id", ["../escape", "nested/run", ".", "run id"])
def test_unsafe_run_id_is_rejected_before_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    run_id: str,
) -> None:
    code, runner, _, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "--resume", run_id, "--approve"],
    )

    assert code == 2
    assert "run_id" in error
    assert runner.calls == []


def test_resume_requires_an_explicit_decision_before_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    code, runner, _, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["langgraph", "--resume", "run-1"],
    )

    assert code == 2
    assert "--approve, --reject, or --edit-json" in error
    assert runner.calls == []


def test_edit_json_is_an_approval_decision_and_reject_cannot_edit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    edit = tmp_path / "edit.json"
    edit.write_text('{"path":"answer.py","content":"42"}', encoding="utf-8")

    code, runner, _, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        [
            "langchain",
            "--resume",
            "run-1",
            "--reject",
            "no",
            "--edit-json",
            str(edit),
        ],
    )

    assert code == 2
    assert error.strip() == "error: invalid command-line arguments"
    assert runner.calls == []


def test_paused_outcome_has_readable_redacted_preview_and_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    secret = "sk-" + "x" * 30
    proposal = ToolProposal(
        "call-write",
        "write_file",
        {"path": "answer.py", "content": f"OPENAI_API_KEY={secret}"},
    )
    approval = ApprovalRequest(
        proposal=proposal,
        risk=Risk.APPROVAL,
        normalized_arguments="{}",
        preview=f"OPENAI_API_KEY={secret}",
        digest="digest",
    )

    code, _, output, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "write the answer"],
        outcome=RunOutcome(run_id="run-1", pending_approval=approval),
    )

    payload = json.loads(output)
    assert code == 3
    assert error == ""
    assert payload["event"] == "paused"
    assert payload["run_id"] == "run-1"
    assert payload["approval"]["tool"] == "write_file"
    assert payload["approval"]["target"] == "answer.py"
    assert payload["approval"]["risk"] == "approval"
    assert payload["approval"]["preview"] == "[REDACTED]"
    assert secret not in output


@pytest.mark.parametrize("implementation", ["openai", "langchain", "langgraph"])
def test_final_outcome_uses_same_event_and_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    implementation: str,
) -> None:
    code, runner, output, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        [implementation, "answer"],
    )

    assert code == 0
    assert error == ""
    assert json.loads(output) == {
        "event": "final",
        "run_id": "run-1",
        "text": "done",
    }
    assert runner.calls[0][0] == implementation


def test_missing_docker_is_reported_without_constructing_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    code, runner, _, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "answer"],
        docker=None,
    )

    assert code == 2
    assert error.strip() == "error: Docker is required but was not found on PATH"
    assert runner.calls == []


def test_missing_api_key_does_not_echo_environment_values(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    other_value = "do-not-print-this-value"
    monkeypatch.setenv("UNRELATED_SECRET", other_value)

    code, runner, output, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["langchain", "answer"],
        api_key="",
    )

    assert code == 2
    assert output == ""
    assert error.strip() == "error: OPENAI_API_KEY is required"
    assert other_value not in error
    assert runner.calls == []


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (
            RuntimeError("Docker executable 'private-wrapper-name' not found"),
            "error: implementation failed: dependency unavailable",
        ),
        (
            RuntimeError("api_key value was private-key-value"),
            "error: implementation failed: dependency unavailable",
        ),
    ],
)
def test_dependency_construction_errors_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    failure: Exception,
    expected: str,
) -> None:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()
    monkeypatch.setattr(cli, "_run_entrypoint", RaisingRunner(failure))
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setenv("OPENAI_API_KEY", "present-only-for-test")

    code = cli.main(
        [
            "openai",
            "answer",
            "--workspace",
            str(workspace),
            "--skills",
            str(skills),
        ]
    )
    captured = capsys.readouterr()

    assert code == 2
    assert captured.out == ""
    assert captured.err.strip() == expected
    assert "private" not in captured.err


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (
            SyntheticSchemaError(
                "schema rejected synthetic_api_key=sentinel-do-not-echo"
            ),
            "error: implementation failed: validation rejected",
        ),
        (
            Exception("runtime sentinel-do-not-echo"),
            "error: implementation failed: runtime failed",
        ),
    ],
)
def test_entrypoint_errors_never_echo_external_values(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    failure: Exception,
    expected: str,
) -> None:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()
    monkeypatch.setattr(cli, "_run_entrypoint", RaisingRunner(failure))
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setenv("OPENAI_API_KEY", "present-only-for-test")

    code = cli.main(
        [
            "openai",
            "answer",
            "--workspace",
            str(workspace),
            "--skills",
            str(skills),
        ]
    )
    captured = capsys.readouterr()

    assert code == 2
    assert captured.out == ""
    assert captured.err.strip() == expected
    assert "sentinel-do-not-echo" not in captured.err
    assert "synthetic_api_key" not in captured.err


def test_rendering_errors_are_also_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    code, _, output, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "answer"],
        outcome=ExplodingOutcome(),  # type: ignore[arg-type]
    )

    assert code == 2
    assert output == ""
    assert error.strip() == "error: implementation failed: validation rejected"
    assert "sentinel-do-not-echo" not in error


def test_import_cli_does_not_load_runtime_frameworks() -> None:
    script = """
import json
import sys
import cli

forbidden = {
    "agent_core.checkpoints",
    "agent_core.contracts",
    "langchain",
    "langgraph",
    "mcp",
    "openai",
    "pydantic",
}
loaded = sorted(
    name for name in sys.modules
    if name in forbidden or name.split(".", 1)[0] in forbidden
)
print(json.dumps(loaded))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(cli.__file__).parent,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == []


def test_bad_cli_argument_does_not_enter_runtime_wiring() -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(cli.__file__)), "--bad"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert completed.stderr.strip() == "error: invalid command-line arguments"


def test_argument_validation_precedes_dependency_checks(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    code, runner, _, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai"],
        api_key="",
        docker=None,
    )

    assert code == 2
    assert "user input is required" in error
    assert "Docker" not in error
    assert "OPENAI_API_KEY" not in error
    assert runner.calls == []
