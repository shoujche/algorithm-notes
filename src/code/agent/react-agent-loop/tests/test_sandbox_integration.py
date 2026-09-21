from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agent_core.sandbox import DockerMCPTransport

pytestmark = pytest.mark.docker


def test_container_enforces_runtime_isolation_and_persists_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()
    host_sentinel = tmp_path / "host-only.txt"
    host_sentinel.write_text("host secret", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-enter-container")

    probe = """
import errno
import json
import os
import socket
from pathlib import Path

result = {
    "uid": os.getuid(),
    "api_key_present": "OPENAI_API_KEY" in os.environ,
    "host_file_visible": Path(__HOST_SENTINEL__).exists(),
}
try:
    socket.create_connection(("1.1.1.1", 53), timeout=0.5)
except OSError as error:
    result["network_error"] = errno.errorcode.get(error.errno)
else:
    result["network_error"] = None

try:
    Path("/home/agent/rootfs-write.txt").write_text("forbidden")
except OSError as error:
    result["rootfs_read_only"] = error.errno == errno.EROFS
else:
    result["rootfs_read_only"] = False

Path("/workspace/persisted.txt").write_text("persisted", encoding="utf-8")
print(json.dumps(result))
""".replace("__HOST_SENTINEL__", repr(str(host_sentinel)))
    transport = DockerMCPTransport()
    argv = transport.build_argv(workspace, skills)
    argv[-1:-1] = [
        "--entrypoint",
        "python",
    ]
    completed = subprocess.run(
        [*argv, "-c", probe],
        check=True,
        capture_output=True,
        text=True,
        env={},
        timeout=30,
    )
    result = json.loads(completed.stdout)
    network_error = result.pop("network_error")

    assert result == {
        "uid": 10001,
        "api_key_present": False,
        "host_file_visible": False,
        "rootfs_read_only": True,
    }
    assert network_error in {
        "ENETDOWN",
        "ENETUNREACH",
        "EHOSTUNREACH",
    }
    assert (workspace / "persisted.txt").read_text(encoding="utf-8") == "persisted"


def test_every_default_allowlisted_command_really_runs_in_the_image(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()

    probe = """
import asyncio
import json
from pathlib import Path

from agent_core.workspace import WorkspaceTools
from mcp_server import _DEFAULT_COMMAND_ALLOWLIST

tools = WorkspaceTools(
    root=Path("/workspace"),
    skills_root=Path("/skills"),
    command_allowlist=set(_DEFAULT_COMMAND_ALLOWLIST),
    timeout_seconds=60,
    max_output_bytes=8_192,
)
invocations = {
    "python": ["python", "-c", "print('python-ok')"],
    "python3": ["python3", "-c", "print('python3-ok')"],
    "pytest": ["pytest", "--version"],
}
report = {}
for name, argv in invocations.items():
    outcome = asyncio.run(tools.run_command(argv, "."))
    report[name] = {
        "exit_code": outcome["exit_code"],
        "output": (outcome["stdout"] + outcome["stderr"]).strip(),
        "timed_out": outcome["timed_out"],
        "truncated": outcome["truncated"],
    }
report["resolved"] = {
    name: tools._commands[name] for name in _DEFAULT_COMMAND_ALLOWLIST
}
print(json.dumps(report))
"""
    argv = DockerMCPTransport().build_argv(workspace, skills)
    argv[-1:-1] = ["--entrypoint", "python"]
    completed = subprocess.run(
        [*argv, "-c", probe],
        check=True,
        capture_output=True,
        text=True,
        env={},
        timeout=120,
    )
    report = json.loads(completed.stdout)

    for name in ("python", "python3", "pytest"):
        assert report[name]["exit_code"] == 0, report[name]
        assert report[name]["timed_out"] is False
        assert report[name]["truncated"] is False
        assert report["resolved"][name].startswith("/")
    assert "python-ok" in report["python"]["output"]
    assert "python3-ok" in report["python3"]["output"]
    assert "pytest" in report["pytest"]["output"]


def test_image_entrypoint_serves_mcp_over_stdio(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()
    request = (
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":'
        '{"protocolVersion":"2025-06-18","capabilities":{},'
        '"clientInfo":{"name":"integration-test","version":"1"}}}\n'
    )

    parameters = DockerMCPTransport().parameters(workspace, skills)
    completed = subprocess.run(
        [parameters.command, *parameters.args],
        input=request,
        check=True,
        capture_output=True,
        text=True,
        env=parameters.env,
        timeout=30,
    )

    response = json.loads(completed.stdout.splitlines()[0])
    assert response["id"] == 1
    assert response["result"]["serverInfo"]["name"] == "react-agent-loop-workspace"
