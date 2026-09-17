from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Sequence

from .skills import list_skills as discover_skills
from .skills import read_skill as load_skill

_VIRTUAL_ROOT = Path("/workspace")
_MAX_PATH_BYTES = 4_096
_MAX_ARGUMENT_BYTES = 4_096
_MAX_COMMAND_INPUT_BYTES = 16_384
_MINIMAL_ENV = {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
    "PATH": os.defpath,
}


class WorkspaceTools:
    def __init__(
        self,
        root: Path,
        skills_root: Path,
        command_allowlist: set[str] | frozenset[str],
        timeout_seconds: float,
        max_output_bytes: int,
    ) -> None:
        if root.is_symlink() or not root.is_dir():
            raise ValueError("workspace root must be a non-symlink directory")
        if skills_root.is_symlink() or not skills_root.is_dir():
            raise ValueError("Skill root must be a non-symlink directory")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")

        self._root = root.resolve()
        self._skills_root = skills_root.resolve()
        self._command_allowlist = frozenset(command_allowlist)
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max_output_bytes

    @property
    def max_output_bytes(self) -> int:
        return self._max_output_bytes

    async def list_files(self, path: str = ".") -> dict[str, Any]:
        target = self._resolve_workspace_path(path, must_exist=True)
        if not target.is_dir():
            raise ValueError("workspace path must be a directory")

        entries: list[dict[str, str]] = []
        for entry in sorted(target.iterdir(), key=lambda item: item.name):
            if entry.is_symlink():
                raise ValueError(f"workspace symlink path is forbidden: {entry.name}")
            kind = "directory" if entry.is_dir() else "file"
            entries.append(
                {
                    "name": entry.name,
                    "path": self._virtual_path(entry),
                    "type": kind,
                }
            )
        return {"path": self._virtual_path(target), "entries": entries}

    async def read_file(self, path: str) -> dict[str, Any]:
        target = self._resolve_workspace_path(path, must_exist=True)
        if not target.is_file():
            raise ValueError("workspace path must be a file")
        payload = self._read_bounded(target)
        try:
            content = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("workspace file is not valid UTF-8") from error
        return {
            "path": self._virtual_path(target),
            "content": content,
            "size_bytes": len(payload),
        }

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        if not isinstance(content, str):
            raise ValueError("content must be a string")
        payload = content.encode("utf-8")
        if len(payload) > self._max_output_bytes:
            raise ValueError(
                f"write content exceeds {self._max_output_bytes}-byte limit"
            )

        target = self._resolve_workspace_path(path, must_exist=False)
        parent = self._resolve_workspace_path(
            str(Path(path).parent),
            must_exist=True,
        )
        if not parent.is_dir():
            raise ValueError("workspace parent path must be a directory")
        if target.exists() and not target.is_file():
            raise ValueError("workspace path must be a file")

        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(target, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
        return {
            "path": self._virtual_path(target),
            "bytes_written": len(payload),
        }

    async def run_command(
        self,
        argv: Sequence[str],
        cwd: str = ".",
    ) -> dict[str, Any]:
        normalized_argv = self._validate_argv(argv)
        try:
            command_cwd = self._resolve_workspace_path(cwd, must_exist=True)
        except ValueError as error:
            raise ValueError("command cwd must be a workspace directory") from error
        if not command_cwd.is_dir():
            raise ValueError("command cwd must be a workspace directory")

        try:
            completed = subprocess.run(
                normalized_argv,
                shell=False,
                cwd=command_cwd,
                timeout=self._timeout_seconds,
                capture_output=True,
                env=_MINIMAL_ENV,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            stdout, stdout_truncated = self._bounded_text(error.stdout or b"")
            stderr, stderr_truncated = self._bounded_text(error.stderr or b"")
            return self._command_result(
                normalized_argv,
                command_cwd,
                exit_code=None,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
                truncated=stdout_truncated or stderr_truncated,
            )

        stdout, stdout_truncated = self._bounded_text(completed.stdout)
        stderr, stderr_truncated = self._bounded_text(completed.stderr)
        return self._command_result(
            normalized_argv,
            command_cwd,
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
            truncated=stdout_truncated or stderr_truncated,
        )

    async def list_skills(self) -> dict[str, Any]:
        return {
            "skills": [
                {"name": summary.name, "description": summary.description}
                for summary in discover_skills(self._skills_root)
            ]
        }

    async def read_skill(self, name: str) -> dict[str, Any]:
        content = load_skill(
            self._skills_root,
            name,
            max_bytes=self._max_output_bytes,
        )
        return {"name": name, "content": content}

    def _resolve_workspace_path(self, path: str, *, must_exist: bool) -> Path:
        if not isinstance(path, str) or not path or "\0" in path:
            raise ValueError("workspace path must be a non-empty string")
        if len(path.encode("utf-8")) > _MAX_PATH_BYTES:
            raise ValueError(
                f"workspace path exceeds {_MAX_PATH_BYTES}-byte limit"
            )
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("workspace path must be relative to /workspace")

        candidate = self._root / relative
        self._reject_symlink_components(candidate)
        try:
            resolved = candidate.resolve(strict=must_exist)
        except OSError as error:
            raise ValueError(f"workspace path is unavailable: {path}") from error
        try:
            resolved.relative_to(self._root)
        except ValueError as error:
            raise ValueError("workspace path resolves outside /workspace") from error
        return resolved

    def _reject_symlink_components(self, candidate: Path) -> None:
        current = self._root
        try:
            relative = candidate.relative_to(self._root)
        except ValueError as error:
            raise ValueError("workspace path resolves outside /workspace") from error
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError(f"workspace symlink path is forbidden: {part}")

    def _read_bounded(self, target: Path) -> bytes:
        with target.open("rb") as stream:
            payload = stream.read(self._max_output_bytes + 1)
        if len(payload) > self._max_output_bytes:
            raise ValueError(
                f"workspace file exceeds {self._max_output_bytes}-byte limit"
            )
        return payload

    def _validate_argv(self, argv: Sequence[str]) -> list[str]:
        if isinstance(argv, (str, bytes)) or not argv:
            raise ValueError("argv must be a non-empty array of strings")
        normalized = list(argv)
        if any(not isinstance(argument, str) or "\0" in argument for argument in normalized):
            raise ValueError("argv must contain only strings without NUL bytes")
        if any(
            len(argument.encode("utf-8")) > _MAX_ARGUMENT_BYTES
            for argument in normalized
        ):
            raise ValueError(
                f"command argument exceeds {_MAX_ARGUMENT_BYTES}-byte limit"
            )
        if normalized[0] not in self._command_allowlist:
            raise ValueError("executable is not in the command allowlist")
        input_size = sum(len(argument.encode("utf-8")) for argument in normalized)
        if input_size > _MAX_COMMAND_INPUT_BYTES:
            raise ValueError(
                f"command input exceeds {_MAX_COMMAND_INPUT_BYTES}-byte limit"
            )
        return normalized

    def _bounded_text(self, payload: bytes) -> tuple[str, bool]:
        truncated = len(payload) > self._max_output_bytes
        bounded = payload[: self._max_output_bytes]
        return bounded.decode("utf-8", errors="replace"), truncated

    def _virtual_path(self, path: Path) -> str:
        relative = path.relative_to(self._root)
        return str(_VIRTUAL_ROOT / relative)

    def _command_result(
        self,
        argv: list[str],
        cwd: Path,
        *,
        exit_code: int | None,
        stdout: str,
        stderr: str,
        timed_out: bool,
        truncated: bool,
    ) -> dict[str, Any]:
        return {
            "argv": argv,
            "cwd": self._virtual_path(cwd),
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
            "truncated": truncated,
        }
