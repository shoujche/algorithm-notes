from dataclasses import FrozenInstanceError

import pytest

from agent_core.contracts import Risk, ToolProposal
from agent_core.policy import ToolPolicy, approval_digest


def test_policy_classifies_only_known_read_tools_as_automatic() -> None:
    policy = ToolPolicy()

    for tool_name in ("list_files", "read_file", "list_skills", "read_skill"):
        proposal = ToolProposal("c1", tool_name, {"path": "a.py"})
        assert policy.classify(proposal) is Risk.READ_ONLY


def test_policy_requires_approval_for_known_side_effects() -> None:
    policy = ToolPolicy()

    write = ToolProposal("c2", "write_file", {"path": "a.py", "content": "x"})
    command = ToolProposal("c3", "run_command", {"argv": ["python", "-V"]})

    assert policy.classify(write) is Risk.APPROVAL
    assert policy.classify(command) is Risk.APPROVAL


def test_policy_denies_unknown_tools() -> None:
    proposal = ToolProposal("c4", "delete_everything", {})

    assert ToolPolicy().classify(proposal) is Risk.DENY


def test_approval_digest_is_stable_and_binds_all_proposal_fields() -> None:
    proposal = ToolProposal(
        "c5",
        "write_file",
        {"content": "你好", "path": "a.py"},
    )
    changed_proposal = ToolProposal(
        "c5",
        "write_file",
        {"content": "changed", "path": "a.py"},
    )

    assert approval_digest(proposal) == approval_digest(proposal)
    assert approval_digest(proposal) != approval_digest(changed_proposal)
    assert approval_digest(proposal) != approval_digest(
        ToolProposal("other", proposal.tool_name, proposal.arguments)
    )


def test_approval_request_contains_canonical_arguments_and_digest() -> None:
    proposal = ToolProposal(
        "c6",
        "write_file",
        {"content": "x", "path": "a.py"},
    )

    request = ToolPolicy().approval_for(proposal)

    assert request.risk is Risk.APPROVAL
    assert request.normalized_arguments == '{"content":"x","path":"a.py"}'
    assert request.preview == "x"
    assert request.digest == approval_digest(proposal)


def test_approval_request_rejects_non_approvable_tools() -> None:
    proposal = ToolProposal("c7", "read_file", {"path": "a.py"})

    with pytest.raises(ValueError, match="does not require approval"):
        ToolPolicy().approval_for(proposal)


def test_tool_proposal_is_immutable() -> None:
    proposal = ToolProposal("c8", "read_file", {"path": "a.py"})

    with pytest.raises(FrozenInstanceError):
        proposal.tool_name = "write_file"  # type: ignore[misc]
