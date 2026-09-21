from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

import cli
from agent_core.contracts import ApprovalRequest, Risk, RunOutcome, ToolProposal

DIGEST = "0123456789abcdef" * 4
FAKE_API_KEY = "sk-" + "0" * 32
FAKE_BEARER = "Bearer " + "z" * 24
FAKE_TOKEN = "not-a-real-token-value"


class RecordingRunner:
    def __init__(self, outcome: RunOutcome) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, object]] = []

    async def __call__(self, command: str, args: object) -> RunOutcome:
        self.calls.append((command, args))
        return self.outcome


class RaisingRunner:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    async def __call__(self, command: str, args: object) -> RunOutcome:
        raise self.error


class CancellingRunner:
    async def __call__(self, command: str, args: object) -> RunOutcome:
        try:
            raise RuntimeError("cause-sentinel-do-not-echo")
        except RuntimeError as cause:
            raise asyncio.CancelledError(
                "cancel-sentinel-do-not-echo"
            ) from cause


class SyntheticSchemaError(ValueError):
    pass


class ExplodingOutcome:
    @property
    def pending_approval(self) -> object:
        raise ValueError("render sentinel-do-not-echo")


class CancelledRenderingOutcome:
    @property
    def pending_approval(self) -> object:
        try:
            raise RuntimeError("render-cause-sentinel-do-not-echo")
        except RuntimeError as cause:
            raise asyncio.CancelledError(
                "render-cancel-sentinel-do-not-echo"
            ) from cause


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


def paused(
    tool_name: str,
    arguments: dict[str, object],
    preview: object,
) -> RunOutcome:
    approval = ApprovalRequest(
        proposal=ToolProposal("call-1", tool_name, arguments),
        risk=Risk.APPROVAL,
        normalized_arguments="{}",
        preview=preview,  # type: ignore[arg-type]
        digest=DIGEST,
    )
    return RunOutcome(run_id="run-1", pending_approval=approval)


def test_paused_outcome_has_readable_redacted_preview_and_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    content = f"OPENAI_API_KEY={FAKE_API_KEY}"

    code, _, output, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "write the answer"],
        outcome=paused(
            "write_file",
            {"path": "answer.py", "content": content},
            content,
        ),
    )

    payload = json.loads(output)
    assert code == 3
    assert error == ""
    assert payload["event"] == "paused"
    assert payload["run_id"] == "run-1"
    assert payload["approval"]["tool"] == "write_file"
    assert payload["approval"]["target"] == "answer.py"
    assert payload["approval"]["risk"] == "approval"
    assert payload["approval"]["digest"] == DIGEST
    assert payload["approval"]["preview"] == "OPENAI_API_KEY=[REDACTED]"
    assert FAKE_API_KEY not in output


def test_write_content_stays_reviewable_around_an_embedded_secret(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    content = f"import os\ntoken: {FAKE_TOKEN}\nos.remove('/workspace/notes.md')"

    code, _, output, _ = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "write the answer"],
        outcome=paused(
            "write_file",
            {"path": "payload.py", "content": content},
            content,
        ),
    )

    approval = json.loads(output)["approval"]
    assert code == 3
    assert approval["target"] == "payload.py"
    assert approval["arguments"]["path"] == "payload.py"
    assert approval["arguments"]["content"] == (
        "import os\ntoken: [REDACTED]\nos.remove('/workspace/notes.md')"
    )
    assert approval["preview"] == approval["arguments"]["content"]
    assert FAKE_TOKEN not in output


def test_run_command_argv_keeps_its_structure_and_surrounding_context(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    script = f"curl -H 'Authorization: {FAKE_BEARER}' https://example.invalid/x"
    argv = ["bash", "-lc", script]

    code, _, output, _ = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "run the command"],
        outcome=paused(
            "run_command",
            {"argv": argv, "cwd": "/workspace"},
            argv,
        ),
    )

    approval = json.loads(output)["approval"]
    assert code == 3
    assert approval["target"] == "/workspace"
    assert approval["arguments"]["argv"] == [
        "bash",
        "-lc",
        "curl -H 'Authorization: [REDACTED]' https://example.invalid/x",
    ]
    assert approval["preview"] == approval["arguments"]["argv"]
    assert FAKE_BEARER not in output


def test_an_unlabelled_secret_literal_is_masked_span_by_span(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    content = f"# rotate {FAKE_API_KEY} before the demo"

    code, _, output, _ = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "write the answer"],
        outcome=paused(
            "write_file",
            {"path": "notes.md", "content": content},
            content,
        ),
    )

    approval = json.loads(output)["approval"]
    assert code == 3
    assert approval["preview"] == "# rotate [REDACTED] before the demo"
    assert FAKE_API_KEY not in output


def test_a_structured_value_behind_a_sensitive_key_is_masked_to_end_of_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    content = (
        "region = 'eu'\n"
        f'credentials: {{"user": "sre", "pass": "{FAKE_TOKEN}"}}\n'
        "retries = 3"
    )

    code, _, output, _ = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "write the answer"],
        outcome=paused(
            "write_file",
            {"path": "deploy.py", "content": content},
            content,
        ),
    )

    approval = json.loads(output)["approval"]
    assert code == 3
    assert approval["arguments"]["content"] == (
        "region = 'eu'\ncredentials: [REDACTED]\nretries = 3"
    )
    assert FAKE_TOKEN not in output


def test_sensitive_keys_mask_only_their_own_value(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    code, _, output, _ = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "write the answer"],
        outcome=paused(
            "write_file",
            {
                "path": "deploy.json",
                "content": "keep this visible",
                "api_key": FAKE_API_KEY,
                "nested": {"authorization": FAKE_BEARER, "retries": 3},
            },
            "keep this visible",
        ),
    )

    arguments = json.loads(output)["approval"]["arguments"]
    assert code == 3
    assert arguments["path"] == "deploy.json"
    assert arguments["content"] == "keep this visible"
    assert arguments["api_key"] == "[REDACTED]"
    assert arguments["nested"] == {"authorization": "[REDACTED]", "retries": 3}
    assert FAKE_API_KEY not in output
    assert FAKE_BEARER not in output


def test_unsupported_preview_values_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    code, _, output, _ = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "write the answer"],
        outcome=paused(
            "write_file",
            {"path": "answer.py", "content": "hello"},
            ["visible", object()],
        ),
    )

    approval = json.loads(output)["approval"]
    assert code == 3
    assert approval["preview"] == ["visible", "[REDACTED]"]


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


@pytest.mark.parametrize(
    "outcome",
    [
        None,
        CancelledRenderingOutcome(),
    ],
    ids=["entrypoint", "rendering"],
)
def test_cancellation_suppresses_secret_exception_chain(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    outcome: object | None,
) -> None:
    if outcome is None:
        runner: object = CancellingRunner()
    else:
        runner = RecordingRunner(outcome)  # type: ignore[arg-type]

    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()
    monkeypatch.setattr(cli, "_run_entrypoint", runner)
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

    assert code != 0
    assert captured.out == ""
    assert captured.err.strip() == "error: operation cancelled"
    assert "sentinel-do-not-echo" not in captured.err
    assert "cause" not in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), SystemExit(7)])
def test_process_control_exceptions_still_propagate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    interrupt: BaseException,
) -> None:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()
    monkeypatch.setattr(cli, "_run_entrypoint", RaisingRunner(interrupt))
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/docker")
    monkeypatch.setenv("OPENAI_API_KEY", "present-only-for-test")

    with pytest.raises(type(interrupt)):
        cli.main(
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
    assert captured.out == ""
    assert captured.err == ""


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


@pytest.mark.parametrize("implementation", ["openai", "langchain", "langgraph"])
def test_approval_requires_an_expected_digest(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    implementation: str,
) -> None:
    code, runner, output, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        [implementation, "--resume", "run-1", "--approve"],
    )

    assert code == 2
    assert output == ""
    assert error.strip() == (
        "error: --expect-digest is required to approve a paused approval"
    )
    assert runner.calls == []


def test_edit_resume_requires_an_expected_digest(
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
        ["langgraph", "--resume", "run-1", "--edit-json", str(edit)],
    )

    assert code == 2
    assert error.strip() == (
        "error: --expect-digest is required to approve a paused approval"
    )
    assert runner.calls == []


@pytest.mark.parametrize(
    "digest",
    [
        "0123456789abcdef" * 3,
        "0123456789ABCDEF" * 4,
        "z" * 64,
        ("0123456789abcdef" * 4) + "0",
        "",
    ],
)
def test_malformed_expected_digests_are_rejected_without_echoing_them(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    digest: str,
) -> None:
    code, runner, output, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "--resume", "run-1", "--approve", "--expect-digest", digest],
    )

    assert code == 2
    assert output == ""
    assert error.strip() == (
        "error: --expect-digest must be 64 lowercase hexadecimal characters"
    )
    assert not digest or digest not in error
    assert runner.calls == []


def test_a_malformed_expected_digest_is_also_rejected_for_a_rejection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    code, runner, _, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "--resume", "run-1", "--reject", "no", "--expect-digest", "abc"],
    )

    assert code == 2
    assert error.strip() == (
        "error: --expect-digest must be 64 lowercase hexadecimal characters"
    )
    assert runner.calls == []


def test_expected_digest_requires_resume(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    code, runner, _, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "answer", "--expect-digest", DIGEST],
    )

    assert code == 2
    assert error.strip() == "error: --expect-digest requires --resume"
    assert runner.calls == []


def test_rejection_may_omit_the_expected_digest(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    code, runner, _, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "--resume", "run-1", "--reject", "too risky"],
    )

    assert code == 0
    assert error == ""
    assert len(runner.calls) == 1
    assert runner.calls[0][1].expect_digest is None


@pytest.mark.parametrize("implementation", ["openai", "langchain", "langgraph"])
def test_expected_digest_reaches_the_entrypoint_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    implementation: str,
) -> None:
    edit = tmp_path / "edit.json"
    edit.write_text('{"path":"answer.py","content":"42"}', encoding="utf-8")

    code, runner, _, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        [
            implementation,
            "--resume",
            "run-1",
            "--edit-json",
            str(edit),
            "--expect-digest",
            DIGEST,
        ],
    )

    forwarded = runner.calls[0][1]
    assert code == 0
    assert error == ""
    assert forwarded.expect_digest == DIGEST
    assert forwarded.approve is True
    assert forwarded.edit_arguments == '{"content":"42","path":"answer.py"}'


def test_expected_digest_validation_precedes_dependency_checks(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    code, runner, _, error = invoke(
        monkeypatch,
        capsys,
        tmp_path,
        ["openai", "--resume", "run-1", "--approve"],
        api_key="",
        docker=None,
    )

    assert code == 2
    assert "--expect-digest is required" in error
    assert "Docker" not in error
    assert "OPENAI_API_KEY" not in error
    assert runner.calls == []


@pytest.mark.parametrize("implementation", ["openai", "langchain", "langgraph"])
def test_usage_spells_out_what_each_decision_flag_means(
    implementation: str,
) -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(cli.__file__)), implementation, "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    usage = " ".join(completed.stdout.split())

    assert completed.returncode == 0
    for phrase in (
        "--approve approve the pending proposal exactly as shown",
        "--reject REASON reject the pending proposal and return REASON",
        "--edit-json FILE approve with the replacement arguments held in FILE",
        "--expect-digest SHA256 digest printed with the paused approval;",
        "required to approve or edit, optional to reject",
    ):
        assert phrase in usage


def test_cli_digest_rule_matches_the_shared_policy_rule() -> None:
    from agent_core.policy import is_approval_digest

    samples = [
        DIGEST,
        DIGEST.upper(),
        DIGEST[:63],
        DIGEST + "0",
        "",
        "z" * 64,
        " " + DIGEST[1:],
    ]

    assert [cli._valid_digest(sample) for sample in samples] == [
        is_approval_digest(sample) for sample in samples
    ]
