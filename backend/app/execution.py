import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from app.config import settings
from app.security import validate_github_url

logger = logging.getLogger(__name__)


class ExecutionUnavailableError(RuntimeError):
    pass


class ExecutionFailedError(RuntimeError):
    pass


class ExecutionProvider(Protocol):
    def availability(self) -> tuple[bool, str]: ...
    def start(self, job_id: str, repository_url: str, project_type: str) -> str: ...
    def stop(self, job_id: str) -> None: ...


class UnavailableExecutionProvider:
    reason = "Execution unavailable: no verified isolated execution provider is configured"

    def availability(self) -> tuple[bool, str]:
        return False, self.reason

    def start(self, job_id: str, repository_url: str, project_type: str) -> str:
        raise ExecutionUnavailableError(self.reason)

    def stop(self, job_id: str) -> None:
        return None


class DockerExecutionProvider:
    """Run only fixed, policy-selected checks in disposable Docker containers."""

    def __init__(self) -> None:
        self.containers: dict[str, str] = {}

    def availability(self) -> tuple[bool, str]:
        if not settings.execution_enabled:
            return False, "Execution unavailable: execution is disabled by configuration"
        if shutil.which(settings.docker_binary) is None:
            return False, "Execution unavailable: Docker CLI is not installed"
        try:
            info = subprocess.run(
                [settings.docker_binary, "info", "--format", "{{json .SecurityOptions}}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            security_options = info.stdout
            required = ('name=seccomp', 'name=apparmor', 'name=cgroupns')
            if any(option not in security_options for option in required):
                return False, "Execution unavailable: Docker security profiles are not all enabled"
            for image in settings.runtime_images.values():
                if not image:
                    continue
                subprocess.run(
                    [settings.docker_binary, "image", "inspect", image],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False, "Execution unavailable: approved runtime images are not available locally"
        return True, "Docker execution provider is available"

    def start(self, job_id: str, repository_url: str, project_type: str) -> str:
        available, reason = self.availability()
        if not available:
            raise ExecutionUnavailableError(reason)
        if project_type not in settings.runtime_images:
            raise ExecutionUnavailableError(f"Execution unavailable: unsupported project type {project_type}")

        _, _, name = validate_github_url(repository_url)
        settings.execution_workspace_root.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix=f"reporunner-{job_id}-", dir=settings.execution_workspace_root))
        container_name = f"reporunner-{job_id}"
        self.containers[job_id] = container_name
        try:
            subprocess.run(
                [
                    "git", "clone", "--depth", "1", "--no-tags", "--single-branch",
                    repository_url, str(workspace / name),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=settings.max_clone_seconds,
            )
            command = self._command(project_type)
            result = subprocess.run(
                [
                    settings.docker_binary, "run", "--name", container_name, "--rm",
                    "--network", "none", "--read-only", "--init",
                    "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                    "--security-opt", "seccomp=default",
                    "--user", "65532:65532", "--cpus", str(settings.execution_cpus),
                    "--memory", str(settings.execution_memory),
                    "--pids-limit", str(settings.execution_pids_limit),
                    "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
                    "--mount", f"type=bind,src={workspace / name},dst=/workspace,readonly",
                    "--workdir", "/workspace", settings.runtime_images[project_type],
                    *command,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=settings.execution_timeout_seconds,
            )
            output = (result.stdout + result.stderr)[-settings.execution_output_bytes:]
            if result.returncode != 0:
                raise ExecutionFailedError(f"Execution failed with exit code {result.returncode}: {output}")
            return output or "Execution completed successfully."
        except subprocess.TimeoutExpired as exc:
            raise ExecutionFailedError("Execution timed out and was terminated") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr[-1000:] if exc.stderr else "repository preparation failed"
            raise ExecutionFailedError(detail) from exc
        finally:
            try:
                try:
                    subprocess.run(
                        [settings.docker_binary, "rm", "--force", container_name],
                        check=False, capture_output=True, text=True, timeout=5,
                    )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    logger.warning("Container cleanup failed for %s: %s", container_name, exc)
            finally:
                self.containers.pop(job_id, None)
                shutil.rmtree(workspace, ignore_errors=True)

    def stop(self, job_id: str) -> None:
        container_name = self.containers.get(job_id)
        if container_name:
            try:
                subprocess.run(
                    [settings.docker_binary, "rm", "--force", container_name],
                    check=False, capture_output=True, text=True, timeout=5,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                logger.warning("Container stop failed for %s: %s", container_name, exc)

    @staticmethod
    def _command(project_type: str) -> list[str]:
        if project_type == "python":
            return ["python", "-m", "compileall", "-q", "."]
        if project_type == "node":
            return ["node", "--check", "index.js"]
        raise ExecutionUnavailableError(f"Execution unavailable: no controlled command for {project_type}")


provider: ExecutionProvider = DockerExecutionProvider()
