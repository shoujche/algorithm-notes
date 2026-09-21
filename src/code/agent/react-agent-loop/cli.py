"""Unified command-line interface for the three ReAct implementations."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_core.contracts import RunOutcome

PAUSED_EXIT_CODE = 3
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_IMPLEMENTATIONS = ("openai", "langchain", "langgraph")
# Mirrors agent_core.policy so that argument checks stay import-free.
_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_DIGEST_FORMAT_ERROR = "--expect-digest must be 64 lowercase hexadecimal characters"
_DIGEST_REQUIRED_ERROR = "--expect-digest is required to approve a paused approval"
_REDACTION = "[REDACTED]"
_SECRET_PATTERN = re.compile(
    r"(?:\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b|"
    r"\bgh[pousr]_[A-Za-z0-9]{20,}\b|"
    r"\bAIza[A-Za-z0-9_-]{35}\b|"
    r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|"
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b|"
    r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{16,}\b|"
    r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|"
    r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,})",
    re.IGNORECASE,
)
_SENSITIVE_KEY_PARTS = frozenset(
    {
        "authorization",
        "credential",
        "credentials",
        "password",
        "passwd",
        "secret",
        "secrets",
        "token",
        "tokens",
    }
)
_LABEL_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
_ASSIGNED_VALUE_PATTERN = re.compile(
    r"""["']?[ \t]*[:=][ \t]*"""
    r"""(?:"(?P<quoted>[^"\n]*)"|'(?P<apostrophe>[^'\n]*)'|(?P<bare>[^,;)\]}'"\n]+))"""
)


class SafeCliError(Exception):
    """A fixed, reviewed message that is safe to print to stderr."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise SafeCliError("invalid command-line arguments")


def build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        description="Run any of the three resumable ReAct implementations."
    )
    subparsers = parser.add_subparsers(dest="implementation", required=True)
    for implementation in _IMPLEMENTATIONS:
        command = subparsers.add_parser(implementation)
        command.add_argument("user_input", nargs="?")
        command.add_argument(
            "--resume",
            metavar="RUN_ID",
            help="resume the paused run printed by an earlier invocation",
        )
        decision = command.add_mutually_exclusive_group()
        decision.add_argument(
            "--approve",
            action="store_true",
            help="approve the pending proposal exactly as shown",
        )
        decision.add_argument(
            "--reject",
            metavar="REASON",
            help="reject the pending proposal and return REASON to the model",
        )
        decision.add_argument(
            "--edit-json",
            type=Path,
            metavar="FILE",
            help="approve with the replacement arguments held in FILE",
        )
        command.add_argument(
            "--expect-digest",
            metavar="SHA256",
            help=(
                "digest printed with the paused approval; "
                "required to approve or edit, optional to reject"
            ),
        )
        command.add_argument(
            "--workspace",
            type=Path,
            default=Path(__file__).with_name("workspace"),
        )
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


def _valid_digest(value: str) -> bool:
    return _DIGEST_PATTERN.fullmatch(value) is not None


def _validated_arguments(args: argparse.Namespace) -> argparse.Namespace:
    approving = args.approve or args.edit_json is not None
    if args.resume is None:
        if not args.user_input:
            raise SafeCliError("user input is required for a new run")
        if approving or args.reject is not None:
            raise SafeCliError("decision flags require --resume")
        if args.expect_digest is not None:
            raise SafeCliError("--expect-digest requires --resume")
    else:
        if not _RUN_ID_PATTERN.fullmatch(args.resume):
            raise SafeCliError(
                "run_id may contain only letters, digits, '-' and '_'"
            )
        if args.user_input:
            raise SafeCliError("user input cannot be combined with --resume")
        if not (approving or args.reject is not None):
            raise SafeCliError(
                "--approve, --reject, or --edit-json is required with --resume"
            )
        if args.expect_digest is None:
            if approving:
                raise SafeCliError(_DIGEST_REQUIRED_ERROR)
        elif not _valid_digest(args.expect_digest):
            raise SafeCliError(_DIGEST_FORMAT_ERROR)

    args.workspace = _existing_directory(args.workspace, "workspace")
    args.skills = _existing_directory(args.skills, "skills")
    if args.edit_json is not None:
        try:
            edited = json.loads(args.edit_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise SafeCliError(
                "--edit-json must name a readable JSON file"
            ) from error
        if not isinstance(edited, dict):
            raise SafeCliError("--edit-json must contain a JSON object")
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
        raise SafeCliError(f"{label} must be an existing directory") from error
    if not resolved.is_dir():
        raise SafeCliError(f"{label} must be an existing directory")
    return resolved


def _check_dependencies() -> None:
    if shutil.which("docker") is None:
        raise SafeCliError("Docker is required but was not found on PATH")
    if not os.environ.get("OPENAI_API_KEY"):
        raise SafeCliError("OPENAI_API_KEY is required")


def _implementation_error(error: Exception) -> SafeCliError:
    error_name = type(error).__name__
    if isinstance(error, ValueError) or error_name in {
        "SchemaError",
        "ValidationError",
    }:
        category = "validation rejected"
    elif isinstance(
        error,
        (ImportError, FileNotFoundError, RuntimeError),
    ):
        category = "dependency unavailable"
    else:
        category = "runtime failed"
    return SafeCliError(f"implementation failed: {category}")


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


def _normalized_key(key: str) -> str:
    snake_case = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    return re.sub(r"[^a-z0-9]+", "_", snake_case.lower()).strip("_")


def _sensitive_key(key: str) -> bool:
    normalized = _normalized_key(key)
    parts = set(normalized.split("_"))
    return bool(
        parts & _SENSITIVE_KEY_PARTS
        or {"api", "key"} <= parts
        or {"private", "key"} <= parts
        or normalized in {"apikey", "privatekey"}
    )


def _redaction_spans(text: str) -> list[tuple[int, int]]:
    spans = [match.span() for match in _SECRET_PATTERN.finditer(text)]
    for label in _LABEL_PATTERN.finditer(text):
        if not _sensitive_key(label.group()):
            continue
        assignment = _ASSIGNED_VALUE_PATTERN.match(text, label.end())
        if assignment is None:
            continue
        group = next(
            name
            for name in ("quoted", "apostrophe", "bare")
            if assignment.group(name) is not None
        )
        start, end = assignment.span(group)
        if group == "bare" and text[start] in "{[":
            # A structured value cannot be delimited safely, so take the line.
            line_end = text.find("\n", start)
            end = len(text) if line_end < 0 else line_end
        while end > start and text[end - 1] in " \t":
            end -= 1
        if end > start:
            spans.append((start, end))
    return spans


def _sanitized_text(text: str) -> str:
    """Mask only the secret-bearing spans so the rest stays reviewable."""
    merged: list[list[int]] = []
    for start, end in sorted(_redaction_spans(text)):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    if not merged:
        return text

    pieces: list[str] = []
    cursor = 0
    for start, end in merged:
        pieces.append(text[cursor:start])
        pieces.append(_REDACTION)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def _sanitized(value: Any) -> Any:
    if value is None or type(value) in {bool, int, float}:
        return value
    if isinstance(value, str):
        return _sanitized_text(value)
    if isinstance(value, Mapping):
        return {
            _sanitized_text(str(key)): (
                _REDACTION if _sensitive_key(str(key)) else _sanitized(child)
            )
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitized(child) for child in value]
    return _REDACTION


def render_outcome(outcome: RunOutcome) -> dict[str, Any]:
    if outcome.pending_approval is None:
        return {
            "event": "final",
            "run_id": outcome.run_id,
            "text": outcome.final_text,
        }

    request = outcome.pending_approval
    arguments = _sanitized(request.proposal.arguments)
    target = arguments.get("path") or arguments.get("cwd")
    return {
        "event": "paused",
        "run_id": outcome.run_id,
        "approval": {
            "tool": request.proposal.tool_name,
            "target": target,
            "risk": request.risk.value,
            "arguments": arguments,
            "preview": _sanitized(request.preview),
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
            paused = outcome.pending_approval is not None
            rendered = json.dumps(
                render_outcome(outcome),
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
            )
        except asyncio.CancelledError:
            raise SafeCliError("operation cancelled") from None
        except Exception as error:
            raise _implementation_error(error) from error
    except SafeCliError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(rendered)
    return PAUSED_EXIT_CODE if paused else 0


if __name__ == "__main__":
    raise SystemExit(main())
