from __future__ import annotations

from pathlib import Path

import pytest

from agent_core.sandbox import DockerMCPTransport, DockerSandboxConfig


def _option_value(argv: list[str], option: str) -> str:
    return argv[argv.index(option) + 1]


def test_build_argv_applies_required_container_isolation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()

    argv = DockerSandboxConfig().build_argv(workspace, skills)

    assert argv[:3] == ["docker", "run", "--rm"]
    assert "-i" in argv
    assert _option_value(argv, "--network") == "none"
    assert "--read-only" in argv
    assert _option_value(argv, "--cap-drop") == "ALL"
    assert _option_value(argv, "--security-opt") == "no-new-privileges"
    assert _option_value(argv, "--user") == "10001:10001"
    assert _option_value(argv, "--pids-limit") == "64"
    assert _option_value(argv, "--memory") == "256m"
    assert _option_value(argv, "--cpus") == "1.0"
    assert _option_value(argv, "--tmpfs") == (
        "/tmp:rw,noexec,nosuid,nodev,size=64m"
    )
    assert argv[-1] == "algorithm-notes-agent-tools"


def test_build_argv_mounts_only_resolved_workspace_and_skills(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()
    workspace_alias = tmp_path / "workspace-alias"
    skills_alias = tmp_path / "skills-alias"
    workspace_alias.symlink_to(workspace, target_is_directory=True)
    skills_alias.symlink_to(skills, target_is_directory=True)

    argv = DockerSandboxConfig().build_argv(workspace_alias, skills_alias)
    mounts = [
        argv[index + 1]
        for index, argument in enumerate(argv)
        if argument == "--mount"
    ]

    assert mounts == [
        f"type=bind,src={workspace.resolve()},dst=/workspace,rw",
        f"type=bind,src={skills.resolve()},dst=/skills,readonly",
    ]


def test_build_argv_rejects_missing_or_non_directory_mount_sources(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ValueError, match="skills"):
        DockerSandboxConfig().build_argv(workspace, skills)

    with pytest.raises(ValueError, match="workspace"):
        DockerSandboxConfig().build_argv(tmp_path / "missing", tmp_path)


@pytest.mark.parametrize("skills_location", ["same", "nested", "parent"])
def test_build_argv_rejects_overlapping_mount_sources(
    tmp_path: Path,
    skills_location: str,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    if skills_location == "same":
        skills = workspace
    elif skills_location == "nested":
        skills = workspace / "skills"
        skills.mkdir()
    else:
        skills = tmp_path

    with pytest.raises(ValueError, match="must not overlap"):
        DockerSandboxConfig().build_argv(workspace, skills)


def test_build_argv_rejects_mount_paths_docker_cannot_represent(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace,with-comma"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()

    with pytest.raises(ValueError, match="comma"):
        DockerSandboxConfig().build_argv(workspace, skills)


def test_transport_exposes_stdio_parameters_without_host_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-enter-container")
    monkeypatch.setenv("UNRELATED_HOST_VARIABLE", "also-not-forwarded")

    parameters = DockerMCPTransport().parameters(workspace, skills)

    assert parameters.command == "docker"
    assert parameters.args[:2] == ["run", "--rm"]
    assert parameters.env == {}
    serialized = "\0".join([parameters.command, *parameters.args])
    assert "--env" not in parameters.args
    assert "-e" not in parameters.args
    assert "OPENAI_API_KEY" not in serialized
    assert "must-not-enter-container" not in serialized
    assert "UNRELATED_HOST_VARIABLE" not in serialized
    assert "also-not-forwarded" not in serialized
