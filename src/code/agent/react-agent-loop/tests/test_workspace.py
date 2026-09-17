from __future__ import annotations

import os
import sys
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
async def test_command_output_is_bounded_and_marked_truncated(
    roots: tuple[Path, Path],
) -> None:
    tools = make_tools(roots, max_output_bytes=16)

    result = await tools.run_command(
        [sys.executable, "-c", "print('x' * 100, end='')"],
        ".",
    )

    assert result["exit_code"] == 0
    assert result["stdout"] == "x" * 16
    assert result["stderr"] == ""
    assert result["timed_out"] is False
    assert result["truncated"] is True
    assert len(result["stdout"].encode("utf-8")) <= 16


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
