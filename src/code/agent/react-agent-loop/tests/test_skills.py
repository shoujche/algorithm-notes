from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_core.skills import SkillSummary, list_skills, read_skill


def write_skill(
    root: Path,
    directory: str,
    *,
    name: str | None = None,
    description: str | None = "A test Skill.",
    body: str = "Follow these instructions.",
) -> Path:
    skill_dir = root / directory
    skill_dir.mkdir(parents=True)
    fields = [f"name: {name or directory}"]
    if description is not None:
        fields.append(f"description: {description}")
    content = f"---\n{'\n'.join(fields)}\n---\n\n{body}\n"
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")
    return skill_file


def test_list_skills_parses_frontmatter_and_sorts_by_name(tmp_path: Path) -> None:
    write_skill(
        tmp_path,
        "zeta-directory",
        name="zeta",
        description="Use the zeta workflow.",
        body="This body must remain progressively undisclosed.",
    )
    write_skill(
        tmp_path,
        "alpha-directory",
        name="alpha",
        description="Use the alpha workflow.",
    )

    assert list_skills(tmp_path) == [
        SkillSummary(name="alpha", description="Use the alpha workflow."),
        SkillSummary(name="zeta", description="Use the zeta workflow."),
    ]


def test_read_skill_returns_the_complete_utf8_document(tmp_path: Path) -> None:
    skill_file = write_skill(
        tmp_path,
        "workspace-helper",
        description="安全地协助工作区。",
        body="先检查，再编辑。",
    )

    assert read_skill(tmp_path, "workspace-helper") == skill_file.read_text(
        encoding="utf-8"
    )


def test_every_discovered_name_can_be_read_when_directory_name_differs(
    tmp_path: Path,
) -> None:
    skill_file = write_skill(
        tmp_path,
        "implementation-directory",
        name="declared-name",
        body="Load me by my declared name.",
    )

    summaries = list_skills(tmp_path)

    assert [summary.name for summary in summaries] == ["declared-name"]
    assert read_skill(tmp_path, summaries[0].name) == skill_file.read_text(
        encoding="utf-8"
    )


def test_list_skills_rejects_missing_description(tmp_path: Path) -> None:
    write_skill(tmp_path, "missing-description", description=None)

    with pytest.raises(ValueError, match="description"):
        list_skills(tmp_path)


def test_list_skills_rejects_duplicate_declared_names(tmp_path: Path) -> None:
    write_skill(tmp_path, "first", name="duplicate")
    write_skill(tmp_path, "second", name="duplicate")

    with pytest.raises(ValueError, match="duplicate"):
        list_skills(tmp_path)


@pytest.mark.parametrize(
    "name",
    [
        "Uppercase",
        "-leading-hyphen",
        "contains_underscore",
        "contains space",
        "a" * 65,
    ],
)
def test_list_skills_rejects_invalid_frontmatter_names(
    tmp_path: Path,
    name: str,
) -> None:
    write_skill(tmp_path, "invalid", name=name)

    with pytest.raises(ValueError, match="name"):
        list_skills(tmp_path)


def test_list_skills_uses_safe_yaml_parsing(tmp_path: Path) -> None:
    skill_dir = tmp_path / "unsafe-yaml"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: unsafe-yaml\n"
        "description: !!python/object/apply:builtins.str [unsafe]\n"
        "---\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="frontmatter"):
        list_skills(tmp_path)


def test_list_skills_rejects_missing_frontmatter_delimiter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "unterminated"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: unterminated\ndescription: Missing closing delimiter.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unterminated"):
        list_skills(tmp_path)


def test_list_skills_rejects_oversized_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "oversized-frontmatter"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: oversized-frontmatter\n"
        f"description: {'x' * 9_000}\n"
        "---\n"
        "Small body.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="frontmatter.*8192-byte limit"):
        list_skills(tmp_path)


def test_read_skill_rejects_files_over_the_byte_limit(tmp_path: Path) -> None:
    write_skill(tmp_path, "large", body="é" * 100)

    with pytest.raises(ValueError, match="byte limit"):
        read_skill(tmp_path, "large", max_bytes=100)


def test_read_skill_rejects_large_file_at_default_byte_limit(tmp_path: Path) -> None:
    write_skill(tmp_path, "default-limit", body="x" * 33_000)

    with pytest.raises(ValueError, match="32768-byte limit"):
        read_skill(tmp_path, "default-limit")


def test_read_skill_honors_custom_limit_above_default(tmp_path: Path) -> None:
    skill_file = write_skill(tmp_path, "custom-limit", body="x" * 33_000)

    assert read_skill(tmp_path, "custom-limit", max_bytes=40_000) == (
        skill_file.read_text(encoding="utf-8")
    )


def test_unrelated_large_skill_does_not_block_small_target_read(
    tmp_path: Path,
) -> None:
    target_file = write_skill(tmp_path, "target", body="Small target.")
    write_skill(tmp_path, "unrelated-large", body="x" * 33_000)

    assert read_skill(tmp_path, "target", max_bytes=256) == target_file.read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("name", ["/tmp/escape", "../escape", "nested/escape", "."])
def test_read_skill_rejects_absolute_and_traversal_names(
    tmp_path: Path,
    name: str,
) -> None:
    with pytest.raises(ValueError, match="name"):
        read_skill(tmp_path, name)


@pytest.mark.skipif(
    not hasattr(os, "symlink"),
    reason="symbolic links are unavailable",
)
def test_read_skill_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    outside = tmp_path / "outside"
    write_skill(outside, "escaped")
    (root / "escaped").symlink_to(outside / "escaped", target_is_directory=True)

    with pytest.raises(ValueError, match="outside"):
        read_skill(root, "escaped")


@pytest.mark.skipif(
    not hasattr(os, "symlink"),
    reason="symbolic links are unavailable",
)
def test_list_skills_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    root.mkdir()
    outside = tmp_path / "outside"
    write_skill(outside, "escaped")
    (root / "escaped").symlink_to(outside / "escaped", target_is_directory=True)

    with pytest.raises(ValueError, match="outside"):
        list_skills(root)


@pytest.mark.skipif(
    not hasattr(os, "symlink"),
    reason="symbolic links are unavailable",
)
@pytest.mark.parametrize("operation", ["list", "read"])
def test_skill_directory_symlink_is_rejected_even_within_root(
    tmp_path: Path,
    operation: str,
) -> None:
    write_skill(tmp_path, "real-directory", name="linked-directory")
    (tmp_path / "linked-directory").symlink_to(
        tmp_path / "real-directory",
        target_is_directory=True,
    )

    with pytest.raises(ValueError, match="symlink"):
        if operation == "list":
            list_skills(tmp_path)
        else:
            read_skill(tmp_path, "linked-directory")


@pytest.mark.skipif(
    not hasattr(os, "symlink"),
    reason="symbolic links are unavailable",
)
@pytest.mark.parametrize("operation", ["list", "read"])
def test_skill_file_symlink_is_rejected_even_within_root(
    tmp_path: Path,
    operation: str,
) -> None:
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    target_file = target_dir / "metadata.md"
    target_file.write_text(
        "---\nname: linked-file\ndescription: Linked file.\n---\n",
        encoding="utf-8",
    )
    linked_dir = tmp_path / "linked-file"
    linked_dir.mkdir()
    (linked_dir / "SKILL.md").symlink_to(target_file)

    with pytest.raises(ValueError, match="symlink"):
        if operation == "list":
            list_skills(tmp_path)
        else:
            read_skill(tmp_path, "linked-file")
