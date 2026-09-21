from __future__ import annotations

import asyncio
import hashlib
from types import ModuleType

import pytest

import langchain_agent
import langgraph_agent
import pure_openai
from agent_core import approval_cli
from agent_core.contracts import ApprovalRequest, Risk, ToolProposal
from agent_core.policy import digests_match, is_approval_digest

_ENTRYPOINTS = (pure_openai, langchain_agent, langgraph_agent)
_PENDING_DIGEST = hashlib.sha256(b"pending-proposal").hexdigest()
_STALE_DIGEST = hashlib.sha256(b"proposal-shown-earlier").hexdigest()


def _pending() -> ApprovalRequest:
    return ApprovalRequest(
        proposal=ToolProposal("call-1", "write_file", {"path": "answer.py"}),
        risk=Risk.APPROVAL,
        normalized_arguments='{"path":"answer.py"}',
        preview="42",
        digest=_PENDING_DIGEST,
    )


def _arguments(module: ModuleType, argv: list[str]):
    return module._parser().parse_args(argv)


def _explode(*args: object, **kwargs: object) -> object:
    raise AssertionError("dependency constructed before argument validation")


@pytest.mark.parametrize("module", _ENTRYPOINTS, ids=lambda m: m.__name__)
def test_every_entrypoint_shares_one_decision_helper(module: ModuleType) -> None:
    assert module.approval_cli is approval_cli


@pytest.mark.parametrize("module", _ENTRYPOINTS, ids=lambda m: m.__name__)
def test_approval_without_an_expected_digest_never_builds_dependencies(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "DockerMCPTransport", _explode)
    args = _arguments(module, ["--resume", "run-1", "--approve"])

    with pytest.raises(ValueError, match="--expect-digest is required"):
        asyncio.run(module._run(args))


@pytest.mark.parametrize("module", _ENTRYPOINTS, ids=lambda m: m.__name__)
def test_malformed_expected_digests_never_build_dependencies(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "DockerMCPTransport", _explode)
    args = _arguments(
        module,
        ["--resume", "run-1", "--approve", "--expect-digest", "not-a-digest"],
    )

    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        asyncio.run(module._run(args))


@pytest.mark.parametrize("module", _ENTRYPOINTS, ids=lambda m: m.__name__)
def test_editing_arguments_is_only_allowed_while_approving(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "DockerMCPTransport", _explode)
    args = _arguments(
        module,
        ["--resume", "run-1", "--reject", "no", "--edit-arguments", "{}"],
    )

    with pytest.raises(ValueError, match="--edit-arguments requires --approve"):
        asyncio.run(module._run(args))


@pytest.mark.parametrize("module", _ENTRYPOINTS, ids=lambda m: m.__name__)
def test_an_expected_digest_needs_a_run_to_resume(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "DockerMCPTransport", _explode)
    args = _arguments(module, ["do the task", "--expect-digest", _PENDING_DIGEST])

    with pytest.raises(ValueError, match="--expect-digest requires --resume"):
        asyncio.run(module._run(args))


def test_a_matching_digest_produces_an_approval_decision() -> None:
    args = _arguments(
        pure_openai,
        ["--resume", "run-1", "--approve", "--expect-digest", _PENDING_DIGEST],
    )
    edited = approval_cli.validated_decision(args)

    decision = approval_cli.resume_decision(args, _pending().digest, edited)

    assert decision.action == "approve"
    assert decision.digest == _PENDING_DIGEST
    assert decision.reason == ""
    assert decision.arguments is None


def test_a_stale_digest_fails_closed_before_a_decision_exists() -> None:
    args = _arguments(
        pure_openai,
        ["--resume", "run-1", "--approve", "--expect-digest", _STALE_DIGEST],
    )
    edited = approval_cli.validated_decision(args)

    with pytest.raises(ValueError) as failure:
        approval_cli.resume_decision(args, _pending().digest, edited)

    message = str(failure.value)
    assert message == "--expect-digest does not match the pending approval"
    assert _STALE_DIGEST not in message
    assert _PENDING_DIGEST not in message


def test_a_rejection_without_a_digest_binds_the_pending_one() -> None:
    args = _arguments(pure_openai, ["--resume", "run-1", "--reject", "too risky"])
    edited = approval_cli.validated_decision(args)

    decision = approval_cli.resume_decision(args, _pending().digest, edited)

    assert decision.action == "reject"
    assert decision.digest == _PENDING_DIGEST
    assert decision.reason == "too risky"
    assert decision.arguments is None


def test_a_rejection_with_a_stale_digest_is_still_refused() -> None:
    args = _arguments(
        pure_openai,
        ["--resume", "run-1", "--reject", "no", "--expect-digest", _STALE_DIGEST],
    )
    edited = approval_cli.validated_decision(args)

    with pytest.raises(ValueError, match="does not match the pending approval"):
        approval_cli.resume_decision(args, _pending().digest, edited)


def test_an_edited_approval_carries_the_expected_digest() -> None:
    args = _arguments(
        pure_openai,
        [
            "--resume",
            "run-1",
            "--approve",
            "--edit-arguments",
            '{"path": "safe.py", "content": "42"}',
            "--expect-digest",
            _PENDING_DIGEST,
        ],
    )
    edited = approval_cli.validated_decision(args)

    decision = approval_cli.resume_decision(args, _pending().digest, edited)

    assert decision.arguments == {"path": "safe.py", "content": "42"}
    assert decision.digest == _PENDING_DIGEST


def test_the_digest_comparison_is_constant_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compared: list[tuple[bytes, bytes]] = []
    original = approval_cli.digests_match

    def recording(expected: str, actual: str) -> bool:
        compared.append((expected.encode(), actual.encode()))
        return original(expected, actual)

    monkeypatch.setattr(approval_cli, "digests_match", recording)
    args = _arguments(
        pure_openai,
        ["--resume", "run-1", "--approve", "--expect-digest", _PENDING_DIGEST],
    )

    approval_cli.resume_decision(args, _pending().digest, None)

    assert compared == [
        (_PENDING_DIGEST.encode(), _PENDING_DIGEST.encode()),
    ]


def test_digests_match_tolerates_hostile_input() -> None:
    assert digests_match(_PENDING_DIGEST, _PENDING_DIGEST)
    assert not digests_match(_STALE_DIGEST, _PENDING_DIGEST)
    assert not digests_match("", _PENDING_DIGEST)
    assert not digests_match("\udc80", _PENDING_DIGEST)
    assert not digests_match("ünïcode", _PENDING_DIGEST)


def test_only_lowercase_sha256_hex_is_an_approval_digest() -> None:
    assert is_approval_digest(_PENDING_DIGEST)
    assert not is_approval_digest(_PENDING_DIGEST.upper())
    assert not is_approval_digest(_PENDING_DIGEST[:63])
    assert not is_approval_digest(_PENDING_DIGEST + "0")
    assert not is_approval_digest(f"{_PENDING_DIGEST[:63]}\n")
    assert not is_approval_digest("")
