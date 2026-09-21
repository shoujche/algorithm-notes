"""Decision plumbing shared by the three executable entrypoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .contracts import RunOutcome, to_json_value
from .openai_loop import ResumeDecision
from .policy import digests_match, is_approval_digest

DIGEST_FORMAT_ERROR = "--expect-digest must be 64 lowercase hexadecimal characters"
DIGEST_REQUIRED_ERROR = "--expect-digest is required to approve a paused approval"
DIGEST_MISMATCH_ERROR = "--expect-digest does not match the pending approval"


def add_decision_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("user_input", nargs="?")
    parser.add_argument(
        "--resume",
        metavar="RUN_ID",
        help="resume the paused run printed by an earlier invocation",
    )
    decision = parser.add_mutually_exclusive_group()
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
    parser.add_argument(
        "--edit-arguments",
        metavar="JSON",
        help="replacement arguments for --approve, as a JSON object",
    )
    parser.add_argument(
        "--expect-digest",
        metavar="SHA256",
        help=(
            "digest printed with the paused approval; "
            "required to approve or edit, optional to reject"
        ),
    )


def add_sandbox_arguments(
    parser: argparse.ArgumentParser,
    entrypoint: str,
) -> None:
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(entrypoint).with_name("workspace"),
    )
    parser.add_argument(
        "--skills",
        type=Path,
        default=Path(entrypoint).with_name("skills"),
    )


def validated_decision(args: argparse.Namespace) -> dict[str, Any] | None:
    """Check every argument before any Docker or model dependency is built."""
    if args.resume is None:
        if not args.user_input:
            raise ValueError("user_input is required for a new run")
        if args.approve or args.reject is not None:
            raise ValueError("--approve and --reject require --resume")
        if args.edit_arguments is not None:
            raise ValueError("--edit-arguments requires --resume")
        if args.expect_digest is not None:
            raise ValueError("--expect-digest requires --resume")
        return None
    if args.user_input:
        raise ValueError("user_input cannot be combined with --resume")
    if not args.approve and args.reject is None:
        raise ValueError("--approve or --reject is required with --resume")
    if args.edit_arguments is not None and not args.approve:
        raise ValueError("--edit-arguments requires --approve")
    if args.expect_digest is None:
        if args.approve:
            raise ValueError(DIGEST_REQUIRED_ERROR)
    elif not is_approval_digest(args.expect_digest):
        raise ValueError(DIGEST_FORMAT_ERROR)
    if args.edit_arguments is None:
        return None
    return _json_object(args.edit_arguments)


def resume_decision(
    args: argparse.Namespace,
    pending_digest: str,
    arguments: dict[str, Any] | None,
) -> ResumeDecision:
    """Bind a decision only to the approval the reviewer actually saw."""
    expected = args.expect_digest
    if expected is not None and not digests_match(expected, pending_digest):
        raise ValueError(DIGEST_MISMATCH_ERROR)
    return ResumeDecision(
        action="approve" if args.approve else "reject",
        digest=pending_digest if expected is None else expected,
        reason=args.reject or "",
        arguments=arguments,
    )


def outcome_json(outcome: RunOutcome) -> str:
    payload: dict[str, Any] = {
        "run_id": outcome.run_id,
        "final_text": outcome.final_text,
    }
    if outcome.pending_approval is not None:
        request = outcome.pending_approval
        payload["pending_approval"] = {
            "tool": request.proposal.tool_name,
            "arguments": to_json_value(request.proposal.arguments),
            "risk": request.risk.value,
            "preview": request.preview,
            "digest": request.digest,
        }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _json_object(raw: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("edited arguments must be a JSON object")
    return value
