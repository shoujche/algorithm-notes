from __future__ import annotations

import argparse
import asyncio
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

import cli
import langchain_agent
import langgraph_agent
import pure_openai
from agent_core.sandbox import DockerSandboxConfig

_CHAPTER = Path(cli.__file__).resolve().parent
_WORKSPACE = _CHAPTER / "workspace"
_SKILLS = _CHAPTER / "skills"
_PLACEHOLDER = _WORKSPACE / ".gitkeep"
_ENTRYPOINTS = (pure_openai, langchain_agent, langgraph_agent)


def _entrypoint_defaults(module: ModuleType) -> argparse.Namespace:
    return module._parser().parse_args(["do the task"])


def _cli_defaults(implementation: str) -> argparse.Namespace:
    return cli.build_parser().parse_args([implementation, "do the task"])


@pytest.mark.parametrize("module", _ENTRYPOINTS, ids=lambda m: m.__name__)
def test_entrypoint_workspace_defaults_to_the_chapter_directory(
    module: ModuleType,
) -> None:
    defaults = _entrypoint_defaults(module)

    assert defaults.workspace == _WORKSPACE
    assert defaults.workspace != Path.cwd()
    assert defaults.skills == _SKILLS


@pytest.mark.parametrize("implementation", ["openai", "langchain", "langgraph"])
def test_cli_workspace_defaults_to_the_chapter_directory(
    implementation: str,
) -> None:
    defaults = _cli_defaults(implementation)

    assert defaults.workspace == _WORKSPACE
    assert defaults.workspace != Path.cwd()
    assert defaults.skills == _SKILLS


def test_default_workspace_is_tracked_so_it_survives_a_fresh_checkout() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(_PLACEHOLDER)],
        cwd=_CHAPTER,
        check=False,
        capture_output=True,
        text=True,
    )

    assert _WORKSPACE.is_dir()
    assert _PLACEHOLDER.is_file()
    assert tracked.returncode == 0


def test_default_workspace_is_the_only_writable_mount_and_never_overlaps() -> None:
    argv = DockerSandboxConfig().build_argv(_WORKSPACE, _SKILLS)
    mounts = [
        argv[index + 1]
        for index, argument in enumerate(argv)
        if argument == "--mount"
    ]

    assert mounts == [
        f"type=bind,src={_WORKSPACE},dst=/workspace",
        f"type=bind,src={_SKILLS},dst=/skills,readonly",
    ]
    assert not _WORKSPACE.is_relative_to(_SKILLS)
    assert not _SKILLS.is_relative_to(_WORKSPACE)


def test_default_workspace_never_exposes_the_whole_chapter() -> None:
    with pytest.raises(ValueError, match="must not overlap"):
        DockerSandboxConfig().build_argv(_CHAPTER, _SKILLS)


@pytest.mark.parametrize("module", _ENTRYPOINTS, ids=lambda m: m.__name__)
def test_missing_user_input_is_rejected_before_dependencies_are_built(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*args: object, **kwargs: object) -> object:
        raise AssertionError("dependency constructed before argument validation")

    monkeypatch.setattr(module, "DockerMCPTransport", explode)
    args = module._parser().parse_args([])

    with pytest.raises(ValueError, match="user_input is required"):
        asyncio.run(module._run(args))


@pytest.mark.parametrize("module", _ENTRYPOINTS, ids=lambda m: m.__name__)
def test_resume_without_a_decision_is_rejected_before_dependencies_are_built(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*args: object, **kwargs: object) -> object:
        raise AssertionError("dependency constructed before argument validation")

    monkeypatch.setattr(module, "DockerMCPTransport", explode)
    args = module._parser().parse_args(["--resume", "run-1"])

    with pytest.raises(ValueError, match="--approve or --reject"):
        asyncio.run(module._run(args))


@pytest.mark.parametrize("module", _ENTRYPOINTS, ids=lambda m: m.__name__)
def test_malformed_edit_arguments_are_rejected_before_dependencies_are_built(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*args: object, **kwargs: object) -> object:
        raise AssertionError("dependency constructed before argument validation")

    monkeypatch.setattr(module, "DockerMCPTransport", explode)
    args = module._parser().parse_args(
        ["--resume", "run-1", "--approve", "--edit-arguments", "[]"]
    )

    with pytest.raises(ValueError, match="JSON object"):
        asyncio.run(module._run(args))
