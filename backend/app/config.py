import os
from pathlib import Path


class Settings:
    workspace_root = Path(os.getenv("REPORUNNER_WORKSPACE_ROOT", "/tmp/reporunner-workspaces")).resolve()
    max_clone_seconds = int(os.getenv("REPORUNNER_MAX_CLONE_SECONDS", "45"))
    max_files = int(os.getenv("REPORUNNER_MAX_FILES", "10000"))
    max_read_bytes = int(os.getenv("REPORUNNER_MAX_READ_BYTES", "200000"))
    max_repo_bytes = int(os.getenv("REPORUNNER_MAX_REPO_BYTES", "100000000"))
    cors_origins = [item.strip() for item in os.getenv("REPORUNNER_CORS_ORIGINS", "*").split(",") if item.strip()]
    execution_status = "execution_unavailable"


settings = Settings()
