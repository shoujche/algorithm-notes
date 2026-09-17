from __future__ import annotations

import os
import signal
import socket
import stat
import sys
import time
from pathlib import Path

import pytest

from agent_core.workspace import WorkspaceTools


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()
    return workspace, skills


def make_tools(
    roots: tuple[Path, Path],
    *,
    timeout_seconds: float = 1,
    max_output_bytes: int = 128,
) -> WorkspaceTools:
    workspace, skills = roots
    return WorkspaceTools(
        root=workspace,
        skills_root=skills,
        command_allowlist={sys.executable},
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )


@pytest.mark.asyncio
async def test_reads_lists_and_writes_relative_to_workspace(
    roots: tuple[Path, Path],
) -> None:
    workspace, _ = roots
    (workspace / "notes").mkdir()
    (workspace / "notes" / "input.txt").write_text("hello", encoding="utf-8")
    tools = make_tools(roots)

    listing = await tools.list_files("notes")
    read = await tools.read_file("notes/input.txt")
    written = await tools.write_file("notes/output.txt", "你好")

    assert listing == {
        "path": "/workspace/notes",
        "entries": [
            {"name": "input.txt", "path": "/workspace/notes/input.txt", "type": "file"}
        ],
    }
    assert read == {
        "path": "/workspace/notes/input.txt",
        "content": "hello",
        "size_bytes": 5,
    }
    assert written == {
        "path": "/workspace/notes/output.txt",
        "bytes_written": 6,
    }
    assert (workspace / "notes" / "output.txt").read_text(encoding="utf-8") == "你好"


@pytest.mark.asyncio
async def test_lists_and_reads_skills_through_existing_loader(
    roots: tuple[Path, Path],
) -> None:
    _, skills = roots
    skill_dir = skills / "workspace-helper"
    skill_dir.mkdir()
    document = (
        "---\n"
        "name: workspace-helper\n"
        "description: Keep work inside the workspace.\n"
        "---\n\n"
        "Read before writing.\n"
    )
    (skill_dir / "SKILL.md").write_text(document, encoding="utf-8")
    tools = make_tools(roots)

    assert await tools.list_skills() == {
        "skills": [
            {
                "name": "workspace-helper",
                "description": "Keep work inside the workspace.",
            }
        ]
    }
    assert await tools.read_skill("workspace-helper") == {
        "name": "workspace-helper",
        "content": document,
    }


@pytest.mark.asyncio
async def test_list_files_rejects_more_than_maximum_entries(
    roots: tuple[Path, Path],
) -> None:
    workspace, _ = roots
    for index in range(1_001):
        (workspace / f"item-{index:04d}").touch()
    tools = make_tools(roots, max_output_bytes=2_000_000)

    with pytest.raises(ValueError, match="more than 1000 entries"):
        await tools.list_files(".")


@pytest.mark.asyncio
async def test_list_skills_rejects_more_than_maximum_entries(
    roots: tuple[Path, Path],
) -> None:
    _, skills = roots
    for index in range(1_001):
        skill_dir = skills / f"skill-{index:04d}"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            f"name: skill-{index:04d}\n"
            "description: Test Skill.\n"
            "---\n",
            encoding="utf-8",
        )
    tools = make_tools(roots, max_output_bytes=2_000_000)

    with pytest.raises(ValueError, match="more than 1000 entries"):
        await tools.list_skills()


@pytest.mark.asyncio
async def test_list_files_rejects_serialized_output_over_budget(
    roots: tuple[Path, Path],
) -> None:
    workspace, _ = roots
    (workspace / ("x" * 80)).touch()
    tools = make_tools(roots, max_output_bytes=64)

    with pytest.raises(ValueError, match="serialized output.*64-byte limit"):
        await tools.list_files(".")


@pytest.mark.asyncio
async def test_list_skills_rejects_serialized_output_over_budget(
    roots: tuple[Path, Path],
) -> None:
    _, skills = roots
    skill_dir = skills / "large-summary"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: large-summary\n"
        f"description: {'x' * 100}\n"
        "---\n",
        encoding="utf-8",
    )
    tools = make_tools(roots, max_output_bytes=64)

    with pytest.raises(ValueError, match="serialized output.*64-byte limit"):
        await tools.list_skills()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/etc/passwd", "/workspace/notes.txt", "../x"])
async def test_rejects_absolute_and_traversal_paths(
    roots: tuple[Path, Path],
    path: str,
) -> None:
    tools = make_tools(roots)

    with pytest.raises(ValueError, match="relative|workspace"):
        await tools.read_file(path)


@pytest.mark.asyncio
async def test_rejects_oversized_path_input(roots: tuple[Path, Path]) -> None:
    tools = make_tools(roots)

    with pytest.raises(ValueError, match="path.*4096-byte limit"):
        await tools.read_file("x" * 4_097)


@pytest.mark.asyncio
async def test_rejects_symlinks_even_when_target_stays_inside_workspace(
    roots: tuple[Path, Path],
) -> None:
    workspace, _ = roots
    (workspace / "target.txt").write_text("safe target", encoding="utf-8")
    (workspace / "linked.txt").symlink_to(workspace / "target.txt")
    tools = make_tools(roots)

    with pytest.raises(ValueError, match="symlink"):
        await tools.read_file("linked.txt")


@pytest.mark.asyncio
async def test_rejects_symlink_to_file_outside_workspace(
    roots: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    workspace, _ = roots
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (workspace / "escaped.txt").symlink_to(outside)
    tools = make_tools(roots)

    with pytest.raises(ValueError, match="symlink|workspace"):
        await tools.read_file("escaped.txt")


@pytest.mark.asyncio
async def test_read_race_cannot_replace_validated_file_with_symlink(
    roots: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, _ = roots
    victim = workspace / "victim.txt"
    victim.write_text("safe", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    tools = make_tools(roots)
    real_open = os.open
    raced = False

    def racing_open(
        path: str | bytes,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal raced
        if path == "victim.txt" and dir_fd is not None and not raced:
            victim.unlink()
            victim.symlink_to(outside)
            raced = True
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", racing_open)

    with pytest.raises(ValueError, match="symlink|regular file"):
        await tools.read_file("victim.txt")
    assert raced is True


@pytest.mark.asyncio
async def test_write_race_replaces_symlink_itself_not_its_target(
    roots: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, _ = roots
    victim = workspace / "victim.txt"
    victim.write_text("old", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    tools = make_tools(roots)
    real_replace = os.replace
    raced = False

    def racing_replace(
        src: str,
        dst: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal raced
        victim.unlink()
        victim.symlink_to(outside)
        raced = True
        real_replace(
            src,
            dst,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(os, "replace", racing_replace)

    await tools.write_file("victim.txt", "new")

    assert raced is True
    assert victim.read_text(encoding="utf-8") == "new"
    assert outside.read_text(encoding="utf-8") == "secret"


@pytest.mark.asyncio
async def test_failed_atomic_write_preserves_original_file(
    roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, _ = roots
    victim = workspace / "victim.txt"
    victim.write_text("old", encoding="utf-8")
    tools = make_tools(roots)

    def fail_write(descriptor: int, payload: bytes) -> int:
        assert stat.S_ISREG(os.fstat(descriptor).st_mode)
        raise OSError("controlled write failure")

    monkeypatch.setattr(os, "write", fail_write)

    with pytest.raises(OSError, match="controlled write failure"):
        await tools.write_file("victim.txt", "new")
    assert victim.read_text(encoding="utf-8") == "old"
    assert sorted(path.name for path in workspace.iterdir()) == ["victim.txt"]


@pytest.mark.asyncio
async def test_rejects_file_over_byte_limit(roots: tuple[Path, Path]) -> None:
    workspace, _ = roots
    (workspace / "large.txt").write_bytes(b"x" * 129)
    tools = make_tools(roots)

    with pytest.raises(ValueError, match="128-byte limit"):
        await tools.read_file("large.txt")


@pytest.mark.asyncio
async def test_rejects_invalid_utf8_file(roots: tuple[Path, Path]) -> None:
    workspace, _ = roots
    (workspace / "binary.bin").write_bytes(b"\xff")
    tools = make_tools(roots)

    with pytest.raises(ValueError, match="UTF-8"):
        await tools.read_file("binary.bin")


@pytest.mark.asyncio
async def test_special_files_are_identified_and_never_opened_as_regular_files(
    roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, _ = roots
    fifo = workspace / "events.fifo"
    os.mkfifo(fifo)
    socket_path = workspace / "service.sock"
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    monkeypatch.chdir(workspace)
    try:
        listener.bind(socket_path.name)
    except PermissionError:
        listener.close()
        listener = None
    tools = make_tools(roots, max_output_bytes=512)

    try:
        listing = await tools.list_files(".")
        expected_entries = [
            {
                "name": "events.fifo",
                "path": "/workspace/events.fifo",
                "type": "other",
            }
        ]
        if listener is not None:
            expected_entries.append(
                {
                    "name": "service.sock",
                    "path": "/workspace/service.sock",
                    "type": "other",
                }
            )
        assert listing["entries"] == expected_entries
        with pytest.raises(ValueError, match="regular file"):
            await tools.read_file("events.fifo")
        if listener is not None:
            with pytest.raises(ValueError, match="regular file|unavailable"):
                await tools.read_file("service.sock")
        with pytest.raises(ValueError, match="regular file"):
            await tools.write_file("events.fifo", "blocked")
        assert stat.S_ISFIFO(fifo.lstat().st_mode)
    finally:
        if listener is not None:
            listener.close()


@pytest.mark.asyncio
async def test_rejects_oversized_write_content(roots: tuple[Path, Path]) -> None:
    tools = make_tools(roots)

    with pytest.raises(ValueError, match="128-byte limit"):
        await tools.write_file("large.txt", "é" * 65)


@pytest.mark.asyncio
async def test_rejects_empty_argv(roots: tuple[Path, Path]) -> None:
    tools = make_tools(roots)

    with pytest.raises(ValueError, match="argv"):
        await tools.run_command([], ".")


@pytest.mark.asyncio
async def test_rejects_disallowed_executable(roots: tuple[Path, Path]) -> None:
    tools = make_tools(roots)

    with pytest.raises(ValueError, match="allowlist"):
        await tools.run_command(["definitely-not-allowed"], ".")


@pytest.mark.asyncio
async def test_rejects_invalid_command_cwd(roots: tuple[Path, Path]) -> None:
    tools = make_tools(roots)

    with pytest.raises(ValueError, match="directory"):
        await tools.run_command([sys.executable, "-c", "print('no')"], "missing")


@pytest.mark.asyncio
async def test_rejects_oversized_command_input(roots: tuple[Path, Path]) -> None:
    tools = make_tools(roots)

    with pytest.raises(ValueError, match="input.*16384-byte limit"):
        await tools.run_command([sys.executable, *(["x" * 1_000] * 17)], ".")


@pytest.mark.asyncio
async def test_command_uses_minimal_environment(roots: tuple[Path, Path]) -> None:
    tools = make_tools(roots, max_output_bytes=512)
    os.environ["WORKSPACE_SECRET_SENTINEL"] = "must-not-leak"

    result = await tools.run_command(
        [
            sys.executable,
            "-c",
            "import os; print(os.environ.get('WORKSPACE_SECRET_SENTINEL', 'absent'))",
        ],
        ".",
    )

    assert result["stdout"] == "absent\n"


@pytest.mark.asyncio
async def test_command_timeout_is_structured(roots: tuple[Path, Path]) -> None:
    tools = make_tools(roots, timeout_seconds=0.01)

    result = await tools.run_command(
        [sys.executable, "-c", "import time; time.sleep(1)"],
        ".",
    )

    assert result == {
        "argv": [sys.executable, "-c", "import time; time.sleep(1)"],
        "cwd": "/workspace",
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "timed_out": True,
        "truncated": False,
    }


@pytest.mark.asyncio
async def test_timeout_kills_grandchild_before_it_can_write(
    roots: tuple[Path, Path],
) -> None:
    workspace, _ = roots
    tools = make_tools(roots, timeout_seconds=0.15, max_output_bytes=4_096)
    grandchild = (
        "import pathlib,time;"
        "time.sleep(.4);"
        "pathlib.Path('grandchild-survived').write_text('unsafe')"
    )
    child = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{grandchild!r}]);"
        "time.sleep(5)"
    )
    parent = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{child!r}]);"
        "time.sleep(5)"
    )

    result = await tools.run_command([sys.executable, "-c", parent], ".")
    time.sleep(0.6)

    assert result["timed_out"] is True
    assert not (workspace / "grandchild-survived").exists()


@pytest.mark.asyncio
async def test_timeout_kills_descendant_with_sustained_output(
    roots: tuple[Path, Path],
) -> None:
    workspace, _ = roots
    tools = make_tools(roots, timeout_seconds=0.2, max_output_bytes=64_000)
    child = (
        "import os,pathlib,signal,time;"
        "signal.signal(signal.SIGPIPE,signal.SIG_IGN);"
        "pathlib.Path('child.pid').write_text(str(os.getpid()));"
        "end=time.monotonic()+5;"
        "\nwhile time.monotonic()<end:\n"
        " try: os.write(1,b'x'*64); time.sleep(.001)\n"
        " except BrokenPipeError: time.sleep(.01)\n"
    )
    parent = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{child!r}]);"
        "time.sleep(5)"
    )

    result = await tools.run_command([sys.executable, "-c", parent], ".")
    child_pid = int((workspace / "child.pid").read_text(encoding="utf-8"))
    try:
        os.kill(child_pid, 0)
    except ProcessLookupError:
        child_alive = False
    else:
        child_alive = True
        os.kill(child_pid, signal.SIGKILL)

    assert result["timed_out"] is True
    assert child_alive is False
    assert (
        len(result["stdout"].encode("utf-8"))
        + len(result["stderr"].encode("utf-8"))
        <= 64_000
    )


@pytest.mark.asyncio
async def test_command_output_is_bounded_and_marked_truncated(
    roots: tuple[Path, Path],
) -> None:
    tools = make_tools(roots, max_output_bytes=16)

    result = await tools.run_command(
        [sys.executable, "-c", "print('x' * 100, end='')"],
        ".",
    )

    assert result["exit_code"] is None
    assert result["stdout"] == "x" * 16
    assert result["stderr"] == ""
    assert result["timed_out"] is False
    assert result["truncated"] is True
    assert len(result["stdout"].encode("utf-8")) <= 16


@pytest.mark.asyncio
async def test_sustained_output_stops_at_combined_byte_budget(
    roots: tuple[Path, Path],
) -> None:
    tools = make_tools(roots, timeout_seconds=5, max_output_bytes=4_096)
    script = (
        "import os,time\n"
        "while True:\n"
        " os.write(1,b'o'*512); os.write(2,b'e'*512); time.sleep(.01)\n"
    )

    started = time.monotonic()
    result = await tools.run_command([sys.executable, "-c", script], ".")
    elapsed = time.monotonic() - started

    captured = len(result["stdout"].encode("utf-8")) + len(
        result["stderr"].encode("utf-8")
    )
    assert elapsed < 1
    assert captured <= 4_096
    assert result["truncated"] is True
    assert result["timed_out"] is False


@pytest.mark.asyncio
async def test_command_invalid_utf8_output_is_json_safe(
    roots: tuple[Path, Path],
) -> None:
    tools = make_tools(roots)

    result = await tools.run_command(
        [sys.executable, "-c", "import os; os.write(1, b'\\xff')"],
        ".",
    )

    assert result["stdout"] == "�"


@pytest.mark.asyncio
async def test_invalid_utf8_output_still_respects_encoded_byte_budget(
    roots: tuple[Path, Path],
) -> None:
    tools = make_tools(roots, max_output_bytes=4)

    result = await tools.run_command(
        [sys.executable, "-c", "import os; os.write(1, b'\\xff' * 100)"],
        ".",
    )

    assert result["truncated"] is True
    assert (
        len(result["stdout"].encode("utf-8"))
        + len(result["stderr"].encode("utf-8"))
        <= 4
    )
