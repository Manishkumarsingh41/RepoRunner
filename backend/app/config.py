import os
from pathlib import Path


class Settings:
    workspace_root = Path(os.getenv("REPORUNNER_WORKSPACE_ROOT", "/tmp/reporunner-workspaces")).resolve()
    max_clone_seconds = int(os.getenv("REPORUNNER_MAX_CLONE_SECONDS", "45"))
    max_files = int(os.getenv("REPORUNNER_MAX_FILES", "10000"))
    max_read_bytes = int(os.getenv("REPORUNNER_MAX_READ_BYTES", "200000"))
    max_repo_bytes = int(os.getenv("REPORUNNER_MAX_REPO_BYTES", "100000000"))
    cors_origins = [item.strip() for item in os.getenv("REPORUNNER_CORS_ORIGINS", "*").split(",") if item.strip()]
    execution_enabled = os.getenv("REPORUNNER_EXECUTION_ENABLED", "false").lower() == "true"
    docker_binary = os.getenv("REPORUNNER_DOCKER_BINARY", "docker")
    execution_workspace_root = Path(os.getenv("REPORUNNER_EXECUTION_WORKSPACE_ROOT", "/tmp/reporunner-execution")).resolve()
    execution_timeout_seconds = int(os.getenv("REPORUNNER_EXECUTION_TIMEOUT_SECONDS", "30"))
    execution_cpus = float(os.getenv("REPORUNNER_EXECUTION_CPUS", "1"))
    execution_memory = os.getenv("REPORUNNER_EXECUTION_MEMORY", "512m")
    execution_pids_limit = int(os.getenv("REPORUNNER_EXECUTION_PIDS_LIMIT", "128"))
    execution_output_bytes = int(os.getenv("REPORUNNER_EXECUTION_OUTPUT_BYTES", "20000"))
    runtime_images = {
        "python": os.getenv("REPORUNNER_PYTHON_RUNTIME_IMAGE", ""),
        "node": os.getenv("REPORUNNER_NODE_RUNTIME_IMAGE", ""),
    }
    execution_status = "execution_unavailable"


settings = Settings()
