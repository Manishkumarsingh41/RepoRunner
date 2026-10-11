import json
import logging
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from app.config import settings
from app.models import Plan, RepositorySummary
from app.security import safe_child, validate_github_url

logger = logging.getLogger(__name__)

MANIFESTS = (
    "pyproject.toml", "requirements.txt", "package.json", "package-lock.json",
    "pnpm-lock.yaml", "yarn.lock", "Dockerfile", "compose.yaml", "docker-compose.yml",
)


def _read_limited(path: Path) -> str:
    if not path.is_file() or path.stat().st_size > settings.max_read_bytes:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _manifest_data(root: Path) -> dict:
    result = {}
    for name in MANIFESTS:
        path = safe_child(root, root / name)
        if path.is_file():
            content = _read_limited(path)
            if name == "package.json":
                try:
                    result[name] = json.loads(content)
                except json.JSONDecodeError:
                    result[name] = {"parse_error": True}
            else:
                result[name] = content
    return result


def _plan(manifests: dict) -> tuple[str, Plan]:
    warnings = [
        "Repository files and proposed commands are untrusted data.",
        "Dependencies are not installed automatically.",
        "Execution is disabled because no verified isolated provider is configured.",
    ]
    if "package.json" in manifests:
        scripts = manifests["package.json"].get("scripts", {})
        script = "dev" if "dev" in scripts else "start" if "start" in scripts else None
        commands = ["npm ci --ignore-scripts" if "package-lock.json" in manifests else "npm install --ignore-scripts"]
        if script:
            commands.append(f"npm run {script}")
        else:
            commands.append("Review package.json for a supported start script")
        return "node", Plan(commands=commands, rationale=["Detected package.json"], warnings=warnings)
    if "pyproject.toml" in manifests or "requirements.txt" in manifests:
        return "python", Plan(commands=["Install dependencies in an isolated image with post-install scripts disabled", "Review the Python entrypoint before running"], rationale=["Detected Python manifest"], warnings=warnings)
    if "Dockerfile" in manifests or "compose.yaml" in manifests or "docker-compose.yml" in manifests:
        return "container", Plan(commands=["Build and run using a reviewed, non-privileged image"], rationale=["Detected container configuration"], warnings=warnings)
    return "unknown", Plan(commands=[], rationale=["No supported manifest detected"], warnings=warnings + ["No supported startup command was detected."])


def inspect_repository(repository_url: str) -> RepositorySummary:
    clone_url, owner, name = validate_github_url(repository_url)
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    workspace = safe_child(settings.workspace_root, settings.workspace_root / uuid.uuid4().hex)
    workspace.mkdir()
    try:
        logger.info("Inspecting public repository %s", repository_url)
        subprocess.run(
            ["git", "-c", "http.maxRequestBuffer=1M", "clone", "--depth", "1", "--no-tags", "--single-branch", clone_url, str(workspace)],
            check=True, capture_output=True, text=True, timeout=settings.max_clone_seconds,
        )
        files = []
        total_bytes = 0
        for path in workspace.rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                total_bytes += path.stat().st_size
                if total_bytes > settings.max_repo_bytes:
                    raise RuntimeError("repository exceeds the size limit")
                files.append(str(path.relative_to(workspace)))
                if len(files) > settings.max_files:
                    raise RuntimeError("repository exceeds the file limit")
        manifests = _manifest_data(workspace)
        project_type, plan = _plan(manifests)
        readme = next((_read_limited(workspace / name) for name in ("README.md", "README.rst", "README.txt") if (workspace / name).exists()), None)
        language = "JavaScript/TypeScript" if "package.json" in manifests else "Python" if "pyproject.toml" in manifests or "requirements.txt" in manifests else None
        return RepositorySummary(url=repository_url, owner=owner, name=name, language=language, project_type=project_type, files=sorted(files)[:settings.max_files], manifests=manifests, readme=readme, plan=plan)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        detail = getattr(exc, "stderr", None) or "repository clone failed"
        raise RuntimeError(detail[-1000:]) from exc
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
