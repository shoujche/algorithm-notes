"""Durable side-effect bookkeeping shared by all three orchestration layers.

This module is deliberately framework-free: the hand-written Responses loop
must be able to reuse the exact same ledger as the LangChain and LangGraph
loops without importing an agent framework.
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import tempfile
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterator


class CheckpointDurabilityError(OSError):
    """The replacement landed on disk but could not be confirmed durable.

    Raised only after ``os.replace`` has already committed the new file, so a
    caller must treat the new content as the current on-disk state and must not
    assume the previous file survived.
    """


class ClaimOutcome(Enum):
    """What a caller is allowed to conclude from a claim attempt.

    A side-effect call moves from missing to ``claimed`` and only then to a
    terminal status. ``claimed`` alone never proves the effect ran, so the only
    outcome that may be described to the model as already executed is
    ``FINISHED``.
    """

    GRANTED = "granted"
    UNCONFIRMED = "unconfirmed"
    FINISHED = "finished"


@dataclass(frozen=True)
class SideEffectClaim:
    outcome: ClaimOutcome
    status: str


class SideEffectLedger:
    """Persist side-effect claims so replay cannot dispatch a call twice."""

    _TERMINAL_STATUSES = frozenset({"executed", "failed"})
    _STATUSES = frozenset({"claimed"}) | _TERMINAL_STATUSES

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def claim(self, run_id: str, tool_call_id: str) -> SideEffectClaim:
        """Reserve a side-effect call, reporting whether it may be dispatched.

        ``GRANTED`` is returned only for a fresh claim whose record is
        confirmed durable. Every other path leaves a ``claimed`` record whose
        execution nobody can vouch for: the durability flush after the rename
        may have failed here, an earlier process may have died between the
        claim and the dispatch, or a replay may be re-entering a call whose
        outcome was never recorded.
        """
        with exclusive_file_lock(self.lock_path):
            data = self._load()
            calls = data.setdefault(run_id, {})
            existing = calls.get(tool_call_id)
            if existing in self._TERMINAL_STATUSES:
                return SideEffectClaim(ClaimOutcome.FINISHED, existing)
            if existing == "claimed":
                return SideEffectClaim(ClaimOutcome.UNCONFIRMED, existing)
            calls[tool_call_id] = "claimed"
            try:
                atomic_json_replace(self.path, data)
            except CheckpointDurabilityError:
                return SideEffectClaim(ClaimOutcome.UNCONFIRMED, "claimed")
            return SideEffectClaim(ClaimOutcome.GRANTED, "claimed")

    def finish(self, run_id: str, tool_call_id: str, status: str) -> bool:
        """Record a terminal status, returning whether it is confirmed durable.

        A ``False`` return means the record is already on disk but its flush
        could not be confirmed. The side effect has happened either way, so the
        record is kept rather than rolled back.
        """
        if status not in self._TERMINAL_STATUSES:
            raise ValueError("side-effect result must be executed or failed")
        with exclusive_file_lock(self.lock_path):
            data = self._load()
            calls = data.get(run_id, {})
            if calls.get(tool_call_id) != "claimed":
                raise ValueError("side-effect call has no active claim")
            calls[tool_call_id] = status
            try:
                atomic_json_replace(self.path, data)
            except CheckpointDurabilityError:
                return False
            return True

    def status(self, run_id: str, tool_call_id: str) -> str | None:
        with exclusive_file_lock(self.lock_path):
            return self._load().get(run_id, {}).get(tool_call_id)

    def _load(self) -> dict[str, dict[str, str]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict):
            raise ValueError("invalid side-effect ledger")
        for run_id, calls in data.items():
            if not isinstance(run_id, str) or not isinstance(calls, dict):
                raise ValueError("invalid side-effect ledger")
            if not all(
                isinstance(call_id, str) and status in self._STATUSES
                for call_id, status in calls.items()
            ):
                raise ValueError("invalid side-effect ledger")
        return data


@contextmanager
def exclusive_file_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.chmod(path, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def atomic_json_replace(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.fchmod(temporary.fileno(), 0o600)
            json.dump(
                payload,
                temporary,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            temporary.flush()
            os.fsync(temporary.fileno())
        # The rename is the commit point. The temporary file already carries
        # the final 0600 mode, so no fallible step is left between it and the
        # caller adopting the new state in memory.
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    _fsync_directory(path.parent)


def _fsync_directory(directory: Path) -> None:
    """Flush a completed rename so it survives a crash."""
    descriptor: int | None = None
    try:
        descriptor = os.open(directory, os.O_RDONLY)
        os.fsync(descriptor)
    except OSError as error:
        raise CheckpointDurabilityError(
            errno.EIO, "checkpoint rename durability uncertain"
        ) from error
    finally:
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
