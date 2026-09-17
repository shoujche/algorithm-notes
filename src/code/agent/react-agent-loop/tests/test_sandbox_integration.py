from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from agent_core.sandbox import DockerSandboxConfig

pytestmark = pytest.mark.docker


def _with_absolute_docker(argv: list[str]) -> list[str]:
    docker = shutil.which(argv[0])
    if docker is None:
        pytest.fail(f"Docker executable is unavailable: {argv[0]}")
    return [docker, *argv[1:]]


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
except OSError:
    result["network_blocked"] = True
else:
    result["network_blocked"] = False

try:
    Path("/home/agent/rootfs-write.txt").write_text("forbidden")
except OSError as error:
    result["rootfs_read_only"] = error.errno == errno.EROFS
else:
    result["rootfs_read_only"] = False

Path("/workspace/persisted.txt").write_text("persisted", encoding="utf-8")
print(json.dumps(result))
""".replace("__HOST_SENTINEL__", repr(str(host_sentinel)))
    config = DockerSandboxConfig()
    argv = config.build_argv(workspace, skills)
    argv[-1:-1] = [
        "--entrypoint",
        "python",
    ]
    completed = subprocess.run(
        [*_with_absolute_docker(argv), "-c", probe],
        check=True,
        capture_output=True,
        text=True,
        env={},
        timeout=30,
    )
    result = json.loads(completed.stdout)

    assert result == {
        "uid": 10001,
        "api_key_present": False,
        "host_file_visible": False,
        "network_blocked": True,
        "rootfs_read_only": True,
    }
    assert (workspace / "persisted.txt").read_text(encoding="utf-8") == "persisted"


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

    completed = subprocess.run(
        _with_absolute_docker(
            DockerSandboxConfig().build_argv(workspace, skills)
        ),
        input=request,
        check=True,
        capture_output=True,
        text=True,
        env={},
        timeout=30,
    )

    response = json.loads(completed.stdout.splitlines()[0])
    assert response["id"] == 1
    assert response["result"]["serverInfo"]["name"] == "react-agent-loop-workspace"
