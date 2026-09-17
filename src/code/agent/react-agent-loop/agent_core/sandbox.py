from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from mcp import StdioServerParameters


@dataclass(frozen=True)
class DockerSandboxConfig:
    docker_command: str = "docker"
    image: str = "algorithm-notes-agent-tools"
    user: str = "10001:10001"
    pids_limit: int = 64
    memory_limit: str = "256m"
    cpu_limit: str = "1.0"
    tmpfs: str = "/tmp:rw,noexec,nosuid,nodev,size=64m"

    def build_argv(self, workspace: Path, skills_dir: Path) -> list[str]:
        resolved_workspace = self._resolve_directory(workspace, "workspace")
        resolved_skills = self._resolve_directory(skills_dir, "skills")
        if (
            resolved_workspace.is_relative_to(resolved_skills)
            or resolved_skills.is_relative_to(resolved_workspace)
        ):
            raise ValueError("workspace and skills directories must not overlap")
        return [
            self.docker_command,
            "run",
            "--rm",
            "-i",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            self.user,
            "--pids-limit",
            str(self.pids_limit),
            "--memory",
            self.memory_limit,
            "--cpus",
            self.cpu_limit,
            "--tmpfs",
            self.tmpfs,
            "--mount",
            f"type=bind,src={resolved_workspace},dst=/workspace",
            "--mount",
            f"type=bind,src={resolved_skills},dst=/skills,readonly",
            self.image,
        ]

    @staticmethod
    def _resolve_directory(path: Path, label: str) -> Path:
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise ValueError(f"{label} must be an existing directory") from error
        if not resolved.is_dir():
            raise ValueError(f"{label} must be an existing directory")
        if "," in str(resolved):
            raise ValueError(f"{label} path must not contain a comma")
        return resolved


@dataclass(frozen=True)
class DockerMCPTransport:
    config: DockerSandboxConfig = field(default_factory=DockerSandboxConfig)
    docker_command: str = field(init=False)

    def __post_init__(self) -> None:
        docker_command = shutil.which(self.config.docker_command)
        if docker_command is None:
            raise RuntimeError(
                f"Docker executable '{self.config.docker_command}' not found on PATH"
            )
        object.__setattr__(
            self,
            "docker_command",
            str(Path(docker_command).resolve()),
        )

    def build_argv(self, workspace: Path, skills_dir: Path) -> list[str]:
        argv = self.config.build_argv(workspace, skills_dir)
        argv[0] = self.docker_command
        return argv

    def parameters(
        self,
        workspace: Path,
        skills_dir: Path,
    ) -> StdioServerParameters:
        argv = self.build_argv(workspace, skills_dir)
        return StdioServerParameters(
            command=argv[0],
            args=argv[1:],
            env={},
        )
