from __future__ import annotations

import re
import tomllib
from pathlib import Path

import mcp_server
from agent_core.workspace import _TRUSTED_COMMAND_PATH

_CHAPTER = Path(mcp_server.__file__).resolve().parent
_DOCKERFILE = (_CHAPTER / "sandbox" / "Dockerfile").read_text(encoding="utf-8")
_PYPROJECT = tomllib.loads(
    (_CHAPTER / "pyproject.toml").read_text(encoding="utf-8")
)
_LOCKFILE = (_CHAPTER / "uv.lock").read_text(encoding="utf-8")


def _runtime_stage() -> str:
    return _DOCKERFILE.rsplit("\nFROM ", 1)[-1]


def test_default_allowlist_is_three_bare_sandbox_commands() -> None:
    assert mcp_server._DEFAULT_COMMAND_ALLOWLIST == ("python", "python3", "pytest")
    assert all("/" not in name for name in mcp_server._DEFAULT_COMMAND_ALLOWLIST)


def test_image_path_is_the_first_entry_of_the_trusted_command_path() -> None:
    assert 'ENV PATH="/app/.venv/bin:${PATH}"' in _DOCKERFILE
    assert _TRUSTED_COMMAND_PATH.split(":")[0] == "/app/.venv/bin"


def test_image_installs_pytest_from_the_locked_dev_dependencies() -> None:
    sync = next(
        line for line in _DOCKERFILE.splitlines() if "uv sync" in line
    )
    dev_dependencies = _PYPROJECT["dependency-groups"]["dev"]

    assert "--frozen" in sync
    assert "--no-dev" not in sync
    assert any(entry.startswith("pytest") for entry in dev_dependencies)
    assert 'name = "pytest"' in _LOCKFILE


def test_every_default_allowlisted_command_is_shipped_by_the_image() -> None:
    dev_dependencies = " ".join(_PYPROJECT["dependency-groups"]["dev"])
    providers = {
        "python": "python:3.12" in _DOCKERFILE,
        "python3": "python:3.12" in _DOCKERFILE,
        "pytest": "pytest" in dev_dependencies,
    }

    assert set(providers) == set(mcp_server._DEFAULT_COMMAND_ALLOWLIST)
    assert all(providers.values())


def test_runtime_stage_adds_no_shell_or_package_manager() -> None:
    runtime = _runtime_stage()

    assert re.search(r"\buv\b", runtime) is None
    assert re.search(r"\b(pip|apt-get|apt|apk)\b", runtime) is None
    assert "--shell /usr/sbin/nologin" in runtime
