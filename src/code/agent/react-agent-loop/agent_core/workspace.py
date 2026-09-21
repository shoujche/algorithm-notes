from __future__ import annotations

import json
import os
import selectors
import secrets
import signal
import stat
import subprocess
import time
from pathlib import Path
from typing import Any, Sequence

from .skills import list_skills as discover_skills
from .skills import read_skill as load_skill

_VIRTUAL_ROOT = Path("/workspace")
_MAX_PATH_BYTES = 4_096
_MAX_ARGUMENT_BYTES = 4_096
_MAX_COMMAND_INPUT_BYTES = 16_384
_MAX_LIST_ENTRIES = 1_000
# The directories the sandbox image really ships, in trust order. Not
# `os.defpath` ("/bin:/usr/bin"), which contains neither the image's virtualenv
# nor the /usr/local/bin the base image installs CPython into, so every
# allowlisted command would fail to launch. Entries must stay absolute and
# non-empty: an empty entry is "the current directory", and the current
# directory of a command is the agent's own workspace.
_TRUSTED_COMMAND_PATH = "/app/.venv/bin:/usr/local/bin:/usr/bin:/bin"
_MINIMAL_ENV = {
    "LANG": "C.UTF-8",
    "LC_ALL": "C.UTF-8",
}


class WorkspaceTools:
    def __init__(
        self,
        root: Path,
        skills_root: Path,
        command_allowlist: set[str] | frozenset[str],
        timeout_seconds: float,
        max_output_bytes: int,
        command_path: str = _TRUSTED_COMMAND_PATH,
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
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max_output_bytes
        self._command_path = command_path
        self._commands = self._resolve_commands(command_allowlist, command_path)

    @property
    def max_output_bytes(self) -> int:
        return self._max_output_bytes

    def _resolve_commands(
        self,
        command_allowlist: set[str] | frozenset[str],
        command_path: str,
    ) -> dict[str, str]:
        entries = command_path.split(os.pathsep)
        if any(not entry for entry in entries):
            raise ValueError("command PATH must not contain empty entries")
        directories = [Path(entry) for entry in entries]
        if any(not directory.is_absolute() for directory in directories):
            raise ValueError("command PATH must contain only absolute directories")
        return {
            name: self._resolve_command(name, directories)
            for name in command_allowlist
        }

    def _resolve_command(self, name: str, directories: list[Path]) -> str:
        if not isinstance(name, str) or not name or "\0" in name:
            raise ValueError("command allowlist entries must be non-empty strings")
        candidate = Path(name)
        if candidate.is_absolute():
            candidates = [candidate]
        elif "/" in name:
            raise ValueError(
                f"relative command allowlist entry must be a bare name: {name}"
            )
        else:
            candidates = [directory / name for directory in directories]

        for entry in candidates:
            if not entry.is_symlink() and not entry.exists():
                continue
            return self._checked_executable(name, entry)
        raise ValueError(
            f"allowlisted command is not available on the trusted PATH: {name}"
        )

    def _checked_executable(self, name: str, candidate: Path) -> str:
        try:
            resolved = candidate.resolve(strict=True)
            metadata = resolved.stat()
        except OSError as error:
            raise ValueError(
                f"allowlisted command is not available on the trusted PATH: {name}"
            ) from error
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"allowlisted command is not a regular file: {name}")
        if not os.access(resolved, os.X_OK):
            raise ValueError(f"allowlisted command is not executable: {name}")
        if resolved == self._root or resolved.is_relative_to(self._root):
            raise ValueError(
                f"allowlisted command must not resolve inside the workspace: {name}"
            )
        # Dispatching the canonical target, not the name or the link, is what
        # makes the checks above binding at exec time. The cost: a virtualenv
        # `python` symlink canonicalizes to the base interpreter and so loses
        # the virtualenv, which is why `pytest` is allowlisted in its own right
        # rather than reached through `python -m pytest`.
        return str(resolved)

    async def list_files(self, path: str = ".") -> dict[str, Any]:
        parts = self._workspace_parts(path)
        directory_fd = self._open_directory_fd(parts)
        try:
            names = sorted(os.listdir(directory_fd))
            if len(names) > _MAX_LIST_ENTRIES:
                raise ValueError(
                    f"workspace directory has more than {_MAX_LIST_ENTRIES} entries"
                )
            entries: list[dict[str, str]] = []
            for name in names:
                metadata = os.stat(
                    name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
                if stat.S_ISLNK(metadata.st_mode):
                    raise ValueError(
                        f"workspace symlink path is forbidden: {name}"
                    )
                if stat.S_ISDIR(metadata.st_mode):
                    kind = "directory"
                elif stat.S_ISREG(metadata.st_mode):
                    kind = "file"
                else:
                    kind = "other"
                entries.append(
                    {
                        "name": name,
                        "path": self._virtual_parts((*parts, name)),
                        "type": kind,
                    }
                )
        finally:
            os.close(directory_fd)
        return self._bounded_json_result(
            {"path": self._virtual_parts(parts), "entries": entries}
        )

    async def read_file(self, path: str) -> dict[str, Any]:
        parts = self._workspace_parts(path)
        parent_fd, name = self._open_parent_directory(parts)
        try:
            descriptor = self._open_regular_file(parent_fd, name)
        finally:
            os.close(parent_fd)
        try:
            payload = self._read_bounded_descriptor(descriptor)
        finally:
            os.close(descriptor)
        try:
            content = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("workspace file is not valid UTF-8") from error
        return {
            "path": self._virtual_parts(parts),
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

        parts = self._workspace_parts(path)
        parent_fd, name = self._open_parent_directory(parts)
        temporary_name = f".workspace-write-{secrets.token_hex(8)}"
        temporary_created = False
        try:
            self._validate_existing_destination(parent_fd, name)
            descriptor = os.open(
                temporary_name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | os.O_CLOEXEC,
                0o600,
                dir_fd=parent_fd,
            )
            temporary_created = True
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise ValueError("temporary workspace path is not a regular file")
                self._write_all(descriptor, payload)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            os.replace(
                temporary_name,
                name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            temporary_created = False
        finally:
            if temporary_created:
                try:
                    os.unlink(temporary_name, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass
            os.close(parent_fd)
        return {
            "path": self._virtual_parts(parts),
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

        dispatch_argv = [self._commands[normalized_argv[0]], *normalized_argv[1:]]
        stdout_bytes, stderr_bytes, exit_code, timed_out, truncated = (
            self._run_bounded_process(dispatch_argv, command_cwd)
        )
        stdout, stderr = self._decode_bounded_outputs(stdout_bytes, stderr_bytes)
        return self._command_result(
            normalized_argv,
            command_cwd,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            truncated=truncated,
        )

    async def list_skills(self) -> dict[str, Any]:
        summaries = discover_skills(self._skills_root)
        if len(summaries) > _MAX_LIST_ENTRIES:
            raise ValueError(
                f"Skill catalog has more than {_MAX_LIST_ENTRIES} entries"
            )
        return self._bounded_json_result({
            "skills": [
                {"name": summary.name, "description": summary.description}
                for summary in summaries
            ]
        })

    async def read_skill(self, name: str) -> dict[str, Any]:
        content = load_skill(
            self._skills_root,
            name,
            max_bytes=self._max_output_bytes,
        )
        return {"name": name, "content": content}

    def _resolve_workspace_path(self, path: str, *, must_exist: bool) -> Path:
        self._workspace_parts(path)
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

    def _workspace_parts(self, path: str) -> tuple[str, ...]:
        if not isinstance(path, str) or not path or "\0" in path:
            raise ValueError("workspace path must be a non-empty string")
        if len(path.encode("utf-8")) > _MAX_PATH_BYTES:
            raise ValueError(
                f"workspace path exceeds {_MAX_PATH_BYTES}-byte limit"
            )
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("workspace path must be relative to /workspace")
        return tuple(part for part in relative.parts if part not in ("", "."))

    def _open_parent_directory(
        self,
        parts: tuple[str, ...],
    ) -> tuple[int, str]:
        if not parts:
            raise ValueError("workspace path must identify a file")
        return self._open_directory_fd(parts[:-1]), parts[-1]

    def _open_directory_fd(self, parts: tuple[str, ...]) -> int:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            descriptor = os.open(self._root, flags)
            for part in parts:
                try:
                    child = os.open(part, flags, dir_fd=descriptor)
                finally:
                    os.close(descriptor)
                descriptor = child
        except OSError as error:
            raise ValueError(
                "workspace directory is unavailable or contains a symlink"
            ) from error
        return descriptor

    @staticmethod
    def _open_regular_file(parent_fd: int, name: str) -> int:
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
        except OSError as error:
            raise ValueError(
                "workspace path is unavailable, a symlink, or not a regular file"
            ) from error
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise ValueError("workspace path is not a regular file")
        return descriptor

    @staticmethod
    def _validate_existing_destination(parent_fd: int, name: str) -> None:
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent_fd,
            )
        except FileNotFoundError:
            return
        except OSError as error:
            raise ValueError(
                "workspace destination is unavailable or a symlink"
            ) from error
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("workspace destination is not a regular file")
        finally:
            os.close(descriptor)

    @staticmethod
    def _write_all(descriptor: int, payload: bytes) -> None:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("workspace write made no progress")
            offset += written

    @staticmethod
    def _virtual_parts(parts: tuple[str, ...]) -> str:
        return str(_VIRTUAL_ROOT.joinpath(*parts))

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

    def _read_bounded_descriptor(self, descriptor: int) -> bytes:
        payload = os.read(descriptor, self._max_output_bytes + 1)
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
        if normalized[0] not in self._commands:
            raise ValueError("executable is not in the command allowlist")
        input_size = sum(len(argument.encode("utf-8")) for argument in normalized)
        if input_size > _MAX_COMMAND_INPUT_BYTES:
            raise ValueError(
                f"command input exceeds {_MAX_COMMAND_INPUT_BYTES}-byte limit"
            )
        return normalized

    def _bounded_json_result(self, result: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(
            result,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > self._max_output_bytes:
            raise ValueError(
                "serialized output exceeds "
                f"{self._max_output_bytes}-byte limit"
            )
        return result

    def _decode_bounded_outputs(
        self,
        stdout: bytes,
        stderr: bytes,
    ) -> tuple[str, str]:
        remaining = self._max_output_bytes
        decoded: list[str] = []
        for payload in (stdout, stderr):
            characters: list[str] = []
            for character in payload.decode("utf-8", errors="replace"):
                size = len(character.encode("utf-8"))
                if size > remaining:
                    break
                characters.append(character)
                remaining -= size
            decoded.append("".join(characters))
        return decoded[0], decoded[1]

    def _run_bounded_process(
        self,
        argv: list[str],
        cwd: Path,
    ) -> tuple[bytes, bytes, int | None, bool, bool]:
        process = subprocess.Popen(
            argv,
            shell=False,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**_MINIMAL_ENV, "PATH": self._command_path},
            start_new_session=True,
            close_fds=True,
        )
        assert process.stdout is not None
        assert process.stderr is not None

        stdout_fd = process.stdout.fileno()
        stderr_fd = process.stderr.fileno()
        streams = {
            stdout_fd: bytearray(),
            stderr_fd: bytearray(),
        }
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        selector.register(process.stderr, selectors.EVENT_READ)
        deadline = time.monotonic() + self._timeout_seconds
        timed_out = False
        truncated = False

        try:
            while selector.get_map():
                remaining_time = deadline - time.monotonic()
                if remaining_time <= 0:
                    timed_out = True
                    self._kill_process_group(process)
                    break

                events = selector.select(remaining_time)
                if not events:
                    timed_out = True
                    self._kill_process_group(process)
                    break

                for key, _ in events:
                    try:
                        chunk = os.read(key.fd, 65_536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue

                    consumed = sum(len(buffer) for buffer in streams.values())
                    available = self._max_output_bytes - consumed
                    streams[key.fd].extend(chunk[:available])
                    if len(chunk) >= available:
                        truncated = True
                        self._kill_process_group(process)
                        break
                if truncated:
                    break
        finally:
            selector.close()
            for stream in (process.stdout, process.stderr):
                if not stream.closed:
                    stream.close()

        if not timed_out and not truncated:
            remaining_time = max(0.0, deadline - time.monotonic())
            try:
                process.wait(timeout=remaining_time)
            except subprocess.TimeoutExpired:
                timed_out = True
                self._kill_process_group(process)

        exit_code = None if timed_out or truncated else process.returncode
        return (
            bytes(streams[stdout_fd]),
            bytes(streams[stderr_fd]),
            exit_code,
            timed_out,
            truncated,
        )

    @staticmethod
    def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("command process could not be reaped") from error

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
