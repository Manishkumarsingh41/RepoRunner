import logging
import uuid

from fastapi import APIRouter, HTTPException

from app.execution import ExecutionFailedError, ExecutionUnavailableError, provider
from app.inspection import inspect_repository
from app.models import ApprovalRequest, InspectRequest, Job, JobState

router = APIRouter()
jobs: dict[str, Job] = {}
logger = logging.getLogger(__name__)


@router.post("/repositories/inspect", response_model=Job, status_code=201)
def inspect(request: InspectRequest):
    job = Job(id=uuid.uuid4().hex, state=JobState.inspecting)
    jobs[job.id] = job
    try:
        job.repository = inspect_repository(request.repository_url)
        job.state = JobState.awaiting_approval
        job.logs.append("Inspection completed; no repository code was executed.")
    except HTTPException:
        jobs.pop(job.id, None)
        raise
    except Exception as exc:
        logger.exception("Repository inspection failed for job %s", job.id)
        job.state = JobState.failed
        job.error = str(exc) or "repository inspection failed"
        job.logs.append(f"Inspection failed: {job.error}")
    return job


def get_job(job_id: str) -> Job:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}", response_model=Job)
def status(job_id: str):
    return get_job(job_id)


@router.post("/jobs/{job_id}/approve", response_model=Job)
def approve(job_id: str, request: ApprovalRequest):
    job = get_job(job_id)
    if job.state != JobState.awaiting_approval:
        raise HTTPException(status_code=409, detail="Job is not awaiting approval")
    if not request.approved:
        job.state = JobState.stopped
        job.logs.append("Execution plan rejected by user.")
    else:
        job.approved = True
        job.logs.append("Execution plan explicitly approved by user.")
    return job


@router.post("/jobs/{job_id}/start", response_model=Job)
def start(job_id: str):
    job = get_job(job_id)
    if not job.approved:
        raise HTTPException(status_code=409, detail="Approve the execution plan first")
    if job.state != JobState.awaiting_approval:
        raise HTTPException(status_code=409, detail="Job cannot be started in its current state")
    try:
        if not job.repository:
            raise RuntimeError("Execution unavailable: repository details are missing")
        output = provider.start(job.id, job.repository.url, job.repository.project_type)
        job.state = JobState.succeeded
        job.logs.append(output)
    except ExecutionUnavailableError as exc:
        job.state = JobState.execution_unavailable
        job.error = str(exc)
        job.logs.append(job.error)
    except ExecutionFailedError as exc:
        job.state = JobState.failed
        job.error = str(exc)
        job.logs.append(job.error)
    return job


@router.post("/jobs/{job_id}/stop", response_model=Job)
def stop(job_id: str):
    job = get_job(job_id)
    provider.stop(job.id)
    if job.state in (JobState.running, JobState.awaiting_approval):
        job.state = JobState.stopped
        job.logs.append("Job stopped.")
    return job


@router.get("/jobs/{job_id}/logs")
def logs(job_id: str):
    job = get_job(job_id)
    return {"job_id": job_id, "state": job.state, "logs": job.logs}


@router.get("/jobs/{job_id}/preview")
def preview(job_id: str):
    job = get_job(job_id)
    if job.state != JobState.succeeded:
        raise HTTPException(status_code=404, detail="Preview is not available")
    raise HTTPException(status_code=404, detail="Preview is not available")
