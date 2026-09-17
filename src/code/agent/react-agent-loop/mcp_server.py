from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

import anyio
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from agent_core.workspace import WorkspaceTools

_READ_ONLY = types.ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
_WRITE = types.ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=False,
)
_COMMAND = types.ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=False,
)


def create_server(workspace: WorkspaceTools) -> Server[Any]:
    server: Server[Any] = Server("react-agent-loop-workspace")
    tool_definitions = _tool_definitions(workspace.max_output_bytes)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return tool_definitions

    @server.call_tool(validate_input=True)
    async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
        status = "ok"
        try:
            if name == "list_files":
                return await workspace.list_files(arguments["path"])
            if name == "read_file":
                return await workspace.read_file(arguments["path"])
            if name == "write_file":
                return await workspace.write_file(
                    arguments["path"],
                    arguments["content"],
                )
            if name == "run_command":
                return await workspace.run_command(
                    arguments["argv"],
                    arguments["cwd"],
                )
            if name == "list_skills":
                return await workspace.list_skills()
            if name == "read_skill":
                return await workspace.read_skill(arguments["name"])
            raise ValueError(f"unknown tool: {name}")
        except Exception:
            status = "error"
            raise
        finally:
            event = {
                "event": "tool_call",
                "tool": name,
                "call_id": server.request_context.request_id,
                "duration_ms": round((perf_counter() - started) * 1_000, 3),
                "status": status,
            }
            print(json.dumps(event, separators=(",", ":")), file=sys.stderr)

    return server


def _tool_definitions(max_content_bytes: int) -> list[types.Tool]:
    path_schema = {"type": "string", "maxLength": 4_096}
    return [
        types.Tool(
            name="list_files",
            description="List one directory beneath /workspace.",
            inputSchema=_strict_schema({"path": path_schema}, ["path"]),
            annotations=_READ_ONLY,
        ),
        types.Tool(
            name="read_file",
            description="Read one UTF-8 file beneath /workspace.",
            inputSchema=_strict_schema({"path": path_schema}, ["path"]),
            annotations=_READ_ONLY,
        ),
        types.Tool(
            name="write_file",
            description="Write one UTF-8 file beneath /workspace.",
            inputSchema=_strict_schema(
                {
                    "path": path_schema,
                    "content": {"type": "string", "maxLength": max_content_bytes},
                },
                ["path", "content"],
            ),
            annotations=_WRITE,
        ),
        types.Tool(
            name="run_command",
            description="Run an allowlisted argv command beneath /workspace.",
            inputSchema=_strict_schema(
                {
                    "argv": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 4_096},
                        "minItems": 1,
                        "maxItems": 128,
                    },
                    "cwd": path_schema,
                },
                ["argv", "cwd"],
            ),
            annotations=_COMMAND,
        ),
        types.Tool(
            name="list_skills",
            description="List trusted Skill summaries.",
            inputSchema=_strict_schema({}, []),
            annotations=_READ_ONLY,
        ),
        types.Tool(
            name="read_skill",
            description="Read one trusted Skill document.",
            inputSchema=_strict_schema(
                {"name": {"type": "string", "maxLength": 64}},
                ["name"],
            ),
            annotations=_READ_ONLY,
        ),
    ]


def _strict_schema(
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    schema["additionalProperties"] = False
    return schema


def _default_workspace() -> WorkspaceTools:
    allowlist = frozenset(
        executable.strip()
        for executable in os.environ.get(
            "MCP_COMMAND_ALLOWLIST",
            "python,python3,pytest",
        ).split(",")
        if executable.strip()
    )
    return WorkspaceTools(
        root=Path("/workspace"),
        skills_root=Path("/skills"),
        command_allowlist=allowlist,
        timeout_seconds=30,
        max_output_bytes=32_768,
    )


async def run_stdio() -> None:
    server = create_server(_default_workspace())
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    anyio.run(run_stdio)
