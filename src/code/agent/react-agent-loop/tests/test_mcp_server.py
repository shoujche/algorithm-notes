from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from agent_core.workspace import WorkspaceTools
from mcp_server import create_server


@pytest.fixture
def tools(tmp_path: Path) -> WorkspaceTools:
    workspace = tmp_path / "workspace"
    skills = tmp_path / "skills"
    workspace.mkdir()
    skills.mkdir()
    (workspace / "note.txt").write_text("hello", encoding="utf-8")
    return WorkspaceTools(
        root=workspace,
        skills_root=skills,
        command_allowlist={"python"},
        timeout_seconds=1,
        max_output_bytes=1_024,
    )


@pytest.mark.asyncio
async def test_server_exposes_exactly_six_strict_tool_schemas(
    tools: WorkspaceTools,
) -> None:
    server = create_server(tools)

    async with create_connected_server_and_client_session(server) as session:
        listed = await session.list_tools()

    schemas = {tool.name: tool.inputSchema for tool in listed.tools}
    assert schemas == {
        "list_files": {
            "type": "object",
            "properties": {"path": {"type": "string", "maxLength": 4_096}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "read_file": {
            "type": "object",
            "properties": {"path": {"type": "string", "maxLength": 4_096}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "write_file": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "maxLength": 4_096},
                "content": {"type": "string", "maxLength": 1_024},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        "run_command": {
            "type": "object",
            "properties": {
                "argv": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 4_096},
                    "minItems": 1,
                    "maxItems": 128,
                },
                "cwd": {"type": "string", "maxLength": 4_096},
            },
            "required": ["argv", "cwd"],
            "additionalProperties": False,
        },
        "list_skills": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "read_skill": {
            "type": "object",
            "properties": {"name": {"type": "string", "maxLength": 64}},
            "required": ["name"],
            "additionalProperties": False,
        },
    }


@pytest.mark.asyncio
async def test_tool_annotations_match_effects(tools: WorkspaceTools) -> None:
    server = create_server(tools)

    async with create_connected_server_and_client_session(server) as session:
        listed = await session.list_tools()

    annotations = {
        tool.name: tool.annotations.model_dump(by_alias=True, exclude_none=True)
        for tool in listed.tools
    }
    read_only = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    assert annotations == {
        "list_files": read_only,
        "read_file": read_only,
        "write_file": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "run_command": {
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
        "list_skills": read_only,
        "read_skill": read_only,
    }


@pytest.mark.asyncio
async def test_server_dispatches_tools_and_rejects_unknown_fields(
    tools: WorkspaceTools,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = create_server(tools)

    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("read_file", {"path": "note.txt"})
        invalid = await session.call_tool(
            "read_file",
            {"path": "note.txt", "unexpected": True},
        )

    assert result.isError is False
    assert result.structuredContent == {
        "path": "/workspace/note.txt",
        "content": "hello",
        "size_bytes": 5,
    }
    assert invalid.isError is True
    assert "Additional properties are not allowed" in invalid.content[0].text
    event = json.loads(capsys.readouterr().err)
    assert set(event) == {
        "event",
        "tool",
        "call_id",
        "duration_ms",
        "status",
    }
    assert event["event"] == "tool_call"
    assert event["tool"] == "read_file"
    assert event["call_id"] is not None
    assert event["duration_ms"] >= 0
    assert event["status"] == "ok"
