from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import agent_core.workspace as workspace_module
from agent_core.workspace import WorkspaceTools


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()
    return workspace, skills


@pytest.fixture
def trusted_bin(tmp_path: Path) -> Path:
    directory = tmp_path / "trusted-bin"
    directory.mkdir()
    return directory


def make_tools(
    roots: tuple[Path, Path],
    allowlist: set[str],
    command_path: str,
    *,
    timeout_seconds: float = 10,
    max_output_bytes: int = 512,
) -> WorkspaceTools:
    workspace, skills = roots
    return WorkspaceTools(
        root=workspace,
        skills_root=skills,
        command_allowlist=allowlist,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        command_path=command_path,
    )


def link_interpreter(directory: Path, name: str = "python") -> Path:
    link = directory / name
    link.symlink_to(sys.executable)
    return link


def shell_executable(directory: Path, name: str, output: str) -> Path:
    script = directory / name
    script.write_text(f"#!/bin/sh\necho {output}\n", encoding="utf-8")
    script.chmod(0o755)
    return script


def recorder(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[list[str], dict[str, str]]]:
    captured: list[tuple[list[str], dict[str, str]]] = []
    real_popen = subprocess.Popen

    def recording_popen(argv, **kwargs):  # type: ignore[no-untyped-def]
        captured.append((list(argv), dict(kwargs["env"])))
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(workspace_module.subprocess, "Popen", recording_popen)
    return captured


def test_trusted_command_path_is_explicit_and_never_the_platform_default() -> None:
    trusted = workspace_module._TRUSTED_COMMAND_PATH
    entries = trusted.split(os.pathsep)

    assert trusted == "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin"
    assert entries == ["/app/.venv/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    assert "" not in entries
    assert all(Path(entry).is_absolute() for entry in entries)
    assert trusted != os.defpath


def test_platform_default_path_cannot_reach_the_directories_the_image_uses() -> None:
    """The concrete reason os.defpath is unusable here: the image installs
    CPython into /usr/local/bin and pytest into the venv, neither of which
    os.defpath ("/bin:/usr/bin") contains."""
    default_entries = os.defpath.split(os.pathsep)

    assert "/usr/local/bin" not in default_entries
    assert "/app/.venv/bin" not in default_entries


def test_minimal_environment_never_carries_the_platform_default_path() -> None:
    assert "PATH" not in workspace_module._MINIMAL_ENV


def test_an_empty_path_entry_really_executes_out_of_the_current_directory(
    tmp_path: Path,
) -> None:
    """Grounds the guard below: this is what an empty entry actually does."""
    current = tmp_path / "current"
    current.mkdir()
    shell_executable(current, "probecmd", "from-current-directory")

    with_empty_entry = subprocess.run(
        ["probecmd"],
        cwd=current,
        env={"PATH": f"{os.pathsep}/bin{os.pathsep}/usr/bin"},
        capture_output=True,
        text=True,
        check=True,
    )

    assert with_empty_entry.stdout == "from-current-directory\n"
    with pytest.raises(FileNotFoundError):
        subprocess.run(
            ["probecmd"],
            cwd=current,
            env={"PATH": f"/bin{os.pathsep}/usr/bin"},
            capture_output=True,
            check=False,
        )


@pytest.mark.asyncio
async def test_bare_command_dispatches_the_canonical_absolute_executable(
    roots: tuple[Path, Path],
    trusted_bin: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    link_interpreter(trusted_bin)
    tools = make_tools(roots, {"python"}, str(trusted_bin))
    captured = recorder(monkeypatch)

    result = await tools.run_command(["python", "-c", "print('ok')"], ".")

    dispatched_argv, environment = captured[0]
    assert dispatched_argv[0] == str(Path(sys.executable).resolve())
    assert Path(dispatched_argv[0]).is_absolute()
    assert dispatched_argv[1:] == ["-c", "print('ok')"]
    assert environment["PATH"] == str(trusted_bin)
    assert result["argv"] == ["python", "-c", "print('ok')"]
    assert result["exit_code"] == 0
    assert result["stdout"] == "ok\n"


@pytest.mark.asyncio
async def test_workspace_executable_never_preempts_an_allowlisted_command(
    roots: tuple[Path, Path],
    trusted_bin: Path,
) -> None:
    workspace, _ = roots
    shell_executable(trusted_bin, "shim", "trusted")
    shell_executable(workspace, "shim", "workspace")
    tools = make_tools(roots, {"shim"}, str(trusted_bin))

    result = await tools.run_command(["shim"], ".")

    assert result["exit_code"] == 0
    assert result["stdout"] == "trusted\n"


@pytest.mark.parametrize("command_path", [":/bin", "/bin:", "/bin::/usr/bin"])
def test_empty_path_entries_are_rejected(
    roots: tuple[Path, Path],
    command_path: str,
) -> None:
    with pytest.raises(ValueError, match="empty entries"):
        make_tools(roots, {"sh"}, command_path)


def test_relative_path_entries_are_rejected(roots: tuple[Path, Path]) -> None:
    with pytest.raises(ValueError, match="absolute"):
        make_tools(roots, {"python"}, "relative/bin")


def test_allowlisted_command_missing_from_the_trusted_path_is_rejected(
    roots: tuple[Path, Path],
    trusted_bin: Path,
) -> None:
    link_interpreter(trusted_bin)

    with pytest.raises(ValueError, match="definitely-missing"):
        make_tools(roots, {"definitely-missing"}, str(trusted_bin))


def test_non_regular_candidate_on_the_trusted_path_is_rejected(
    roots: tuple[Path, Path],
    trusted_bin: Path,
) -> None:
    (trusted_bin / "python").mkdir()

    with pytest.raises(ValueError, match="regular file"):
        make_tools(roots, {"python"}, str(trusted_bin))


def test_non_executable_candidate_on_the_trusted_path_is_rejected(
    roots: tuple[Path, Path],
    trusted_bin: Path,
) -> None:
    candidate = trusted_bin / "python"
    candidate.write_text("#!/bin/sh\n", encoding="utf-8")
    candidate.chmod(0o644)

    with pytest.raises(ValueError, match="executable"):
        make_tools(roots, {"python"}, str(trusted_bin))


def test_relative_allowlist_entries_must_be_bare_names(
    roots: tuple[Path, Path],
    trusted_bin: Path,
) -> None:
    link_interpreter(trusted_bin)

    with pytest.raises(ValueError, match="bare name"):
        make_tools(roots, {"nested/python"}, str(trusted_bin))


@pytest.mark.asyncio
async def test_absolute_allowlist_entry_is_canonicalized_before_dispatch(
    roots: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alias = tmp_path / "python-alias"
    alias.symlink_to(sys.executable)
    tools = make_tools(roots, {str(alias)}, workspace_module._TRUSTED_COMMAND_PATH)
    captured = recorder(monkeypatch)

    result = await tools.run_command([str(alias), "-c", "print('ok')"], ".")

    dispatched_argv, _ = captured[0]
    assert dispatched_argv[0] == str(Path(sys.executable).resolve())
    assert result["argv"][0] == str(alias)
    assert result["stdout"] == "ok\n"


def test_absolute_allowlist_entry_must_exist_and_be_executable(
    roots: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-interpreter"

    with pytest.raises(ValueError, match="missing-interpreter"):
        make_tools(roots, {str(missing)}, workspace_module._TRUSTED_COMMAND_PATH)


def test_allowlisted_executable_inside_the_workspace_is_rejected(
    roots: tuple[Path, Path],
) -> None:
    workspace, _ = roots
    shell_executable(workspace, "planted", "workspace")

    with pytest.raises(ValueError, match="workspace"):
        make_tools(
            roots,
            {str(workspace / "planted")},
            workspace_module._TRUSTED_COMMAND_PATH,
        )
