from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_MAX_BYTES = 32_768
_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class SkillSummary:
    name: str
    description: str


def list_skills(root: Path) -> list[SkillSummary]:
    skills = _discover_skills(root)
    return sorted(
        (summary for summary, _ in skills.values()),
        key=lambda summary: summary.name,
    )


def read_skill(root: Path, name: str, max_bytes: int = _DEFAULT_MAX_BYTES) -> str:
    _validate_name(name)
    if max_bytes < 0:
        raise ValueError("max_bytes must be non-negative")

    skills = _discover_skills(root)
    try:
        _, skill_file = skills[name]
    except KeyError as error:
        raise ValueError(f"unknown Skill name: {name}") from error
    return _read_utf8(skill_file, max_bytes)


def _discover_skills(root: Path) -> dict[str, tuple[SkillSummary, Path]]:
    if root.is_symlink():
        raise ValueError("Skill symlink path is forbidden")
    trusted_root = root.resolve()
    if not trusted_root.is_dir():
        raise ValueError("Skill root must be a directory")

    skills: dict[str, tuple[SkillSummary, Path]] = {}
    for entry in root.iterdir():
        if entry.is_symlink():
            raise ValueError(
                "Skill symlink path is forbidden and may resolve outside trusted root"
            )
        skill_file = entry / "SKILL.md"
        if not skill_file.exists():
            continue
        if skill_file.is_symlink():
            raise ValueError(
                "Skill symlink path is forbidden and may resolve outside trusted root"
            )

        safe_file = _resolve_beneath(trusted_root, skill_file)
        content = _read_utf8(safe_file, _DEFAULT_MAX_BYTES)
        summary = _parse_summary(content, safe_file)
        if summary.name in skills:
            raise ValueError(f"duplicate Skill name: {summary.name}")
        skills[summary.name] = (summary, safe_file)
    return skills


def _parse_summary(content: str, source: Path) -> SkillSummary:
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"{source} has no YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise ValueError(f"{source} has unterminated YAML frontmatter") from error

    try:
        metadata: Any = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as error:
        raise ValueError(f"{source} has invalid YAML frontmatter") from error
    if not isinstance(metadata, dict):
        raise ValueError(f"{source} frontmatter must be a mapping")

    name = metadata.get("name")
    description = metadata.get("description")
    if not isinstance(name, str):
        raise ValueError(f"{source} must define a string name")
    _validate_name(name)
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"{source} must define a non-empty description")
    return SkillSummary(name=name, description=description)


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or _NAME_PATTERN.fullmatch(name) is None:
        raise ValueError("invalid Skill name")


def _resolve_beneath(trusted_root: Path, candidate: Path) -> Path:
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"Skill file is unavailable: {candidate}") from error
    if not resolved.is_relative_to(trusted_root):
        raise ValueError(f"Skill path resolves outside trusted root: {candidate}")
    if not resolved.is_file():
        raise ValueError(f"Skill path is not a file: {candidate}")
    return resolved


def _read_utf8(path: Path, max_bytes: int) -> str:
    with path.open("rb") as stream:
        payload = stream.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError(f"Skill file exceeds {max_bytes}-byte limit")
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"Skill file is not valid UTF-8: {path}") from error
