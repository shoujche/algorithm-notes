"""Unified command-line interface for the three ReAct implementations."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from agent_core.checkpoints import contains_secret
from agent_core.contracts import RunOutcome, to_json_value

PAUSED_EXIT_CODE = 3
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_IMPLEMENTATIONS = ("openai", "langchain", "langgraph")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run any of the three resumable ReAct implementations."
    )
    subparsers = parser.add_subparsers(dest="implementation", required=True)
    for implementation in _IMPLEMENTATIONS:
        command = subparsers.add_parser(implementation)
        command.add_argument("user_input", nargs="?")
        command.add_argument("--resume", metavar="RUN_ID")
        decision = command.add_mutually_exclusive_group()
        decision.add_argument("--approve", action="store_true")
        decision.add_argument("--reject", metavar="REASON")
        decision.add_argument("--edit-json", type=Path, metavar="FILE")
        command.add_argument("--workspace", type=Path, default=Path.cwd())
        command.add_argument(
            "--skills",
            type=Path,
            default=Path(__file__).with_name("skills"),
        )
        command.add_argument("--runs", type=Path, default=Path(".runs"))
        command.add_argument(
            "--model",
            default=(
                "gpt-5" if implementation == "openai" else "openai:gpt-5"
            ),
        )
    return parser


def _validated_arguments(args: argparse.Namespace) -> argparse.Namespace:
    if args.resume is None:
        if not args.user_input:
            raise ValueError("user input is required for a new run")
        if args.approve or args.reject is not None or args.edit_json is not None:
            raise ValueError("decision flags require --resume")
    else:
        if not _RUN_ID_PATTERN.fullmatch(args.resume):
            raise ValueError(
                "run_id may contain only letters, digits, '-' and '_'"
            )
        if args.user_input:
            raise ValueError("user input cannot be combined with --resume")
        if not (args.approve or args.reject is not None or args.edit_json):
            raise ValueError(
                "--approve, --reject, or --edit-json is required with --resume"
            )

    args.workspace = _existing_directory(args.workspace, "workspace")
    args.skills = _existing_directory(args.skills, "skills")
    if args.edit_json is not None:
        try:
            edited = json.loads(args.edit_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("--edit-json must name a readable JSON file") from error
        if not isinstance(edited, dict):
            raise ValueError("--edit-json must contain a JSON object")
        args.edit_arguments = json.dumps(
            edited,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        args.approve = True
    else:
        args.edit_arguments = None
    return args


def _existing_directory(path: Path, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError(f"{label} must be an existing directory") from error
    if not resolved.is_dir():
        raise ValueError(f"{label} must be an existing directory")
    return resolved


def _check_dependencies() -> None:
    if shutil.which("docker") is None:
        raise RuntimeError("Docker is required but was not found on PATH")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required")


def _safe_execution_error(error: Exception) -> RuntimeError:
    description = str(error).lower()
    if "docker" in description:
        return RuntimeError("Docker is required or unavailable")
    if "api_key" in description or "api key" in description:
        return RuntimeError("OPENAI_API_KEY is required")
    return RuntimeError("agent execution failed")


async def _run_entrypoint(
    implementation: str,
    args: argparse.Namespace,
) -> RunOutcome:
    if implementation == "openai":
        from pure_openai import _run

        args.runs = args.runs / "openai"
    elif implementation == "langchain":
        from langchain_agent import _run

        args.checkpoints = args.runs / "langchain.json"
    else:
        from langgraph_agent import _run

        args.checkpoints = args.runs / "langgraph.json"
    return await _run(args)


def _redacted(value: Any) -> Any:
    converted = to_json_value(value)
    return "[REDACTED]" if contains_secret(converted) else converted


def render_outcome(outcome: RunOutcome) -> dict[str, Any]:
    if outcome.pending_approval is None:
        return {
            "event": "final",
            "run_id": outcome.run_id,
            "text": outcome.final_text,
        }

    request = outcome.pending_approval
    arguments = to_json_value(request.proposal.arguments)
    target = arguments.get("path") or arguments.get("cwd")
    return {
        "event": "paused",
        "run_id": outcome.run_id,
        "approval": {
            "tool": request.proposal.tool_name,
            "target": _redacted(target),
            "risk": request.risk.value,
            "arguments": _redacted(arguments),
            "preview": _redacted(request.preview),
            "digest": request.digest,
        },
    }


def main(argv: list[str] | None = None) -> int:
    try:
        try:
            args = build_parser().parse_args(argv)
        except SystemExit as error:
            return int(error.code)
        args = _validated_arguments(args)
        _check_dependencies()
        try:
            outcome = asyncio.run(_run_entrypoint(args.implementation, args))
        except ValueError:
            raise
        except Exception as error:
            raise _safe_execution_error(error) from error
    except (ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            render_outcome(outcome),
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
    )
    return PAUSED_EXIT_CODE if outcome.pending_approval is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
