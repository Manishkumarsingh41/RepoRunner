from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobState(str, Enum):
    queued = "queued"
    inspecting = "inspecting"
    awaiting_approval = "awaiting_approval"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    stopped = "stopped"
    execution_unavailable = "execution_unavailable"


class InspectRequest(BaseModel):
    repository_url: str = Field(min_length=1, max_length=300)


class ApprovalRequest(BaseModel):
    approved: bool


class Plan(BaseModel):
    commands: list[str]
    rationale: list[str]
    warnings: list[str]
    requires_network: bool = False
    execution_available: bool = False


class RepositorySummary(BaseModel):
    url: str
    owner: str
    name: str
    default_branch: str | None = None
    language: str | None = None
    project_type: str
    files: list[str]
    manifests: dict[str, Any]
    readme: str | None = None
    plan: Plan


class Job(BaseModel):
    id: str
    state: JobState
    repository: RepositorySummary | None = None
    approved: bool = False
    logs: list[str] = Field(default_factory=list)
    error: str | None = None
