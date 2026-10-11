from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_reports_execution_is_unavailable():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["execution"] == "execution_unavailable"


def test_invalid_repository_urls_are_rejected():
    for value in (
        "http://github.com/octocat/Hello-World",
        "https://evil.example/octocat/Hello-World",
        "https://user:secret@github.com/octocat/Hello-World",
        "https://github.com/octocat/Hello-World?token=secret",
        "https://github.com/octocat/../secret",
    ):
        response = client.post("/api/v1/repositories/inspect", json={"repository_url": value})
        assert response.status_code == 422


def test_job_boundaries_require_approval_and_report_unavailable(monkeypatch):
    from app import api
    from app.models import Plan, RepositorySummary

    job = api.Job(
        id="test-job",
        state=api.JobState.awaiting_approval,
        repository=RepositorySummary(
            url="https://github.com/octocat/Hello-World",
            owner="octocat",
            name="Hello-World",
            project_type="unknown",
            files=[],
            manifests={},
            plan=Plan(commands=[], rationale=[], warnings=[]),
        ),
    )
    api.jobs[job.id] = job
    try:
        assert client.post(f"/api/v1/jobs/{job.id}/start").status_code == 409
        approved = client.post(f"/api/v1/jobs/{job.id}/approve", json={"approved": True})
        assert approved.status_code == 200
        started = client.post(f"/api/v1/jobs/{job.id}/start")
        assert started.status_code == 200
        assert started.json()["state"] == "execution_unavailable"
        assert "unavailable" in started.json()["error"].lower()
    finally:
        api.jobs.pop(job.id, None)


def test_provider_reports_unavailable_without_explicit_configuration():
    from app.execution import DockerExecutionProvider

    available, reason = DockerExecutionProvider().availability()
    assert not available
    assert "unavailable" in reason.lower()


def test_provider_does_not_start_without_approval():
    from app import api
    from app.models import Plan, RepositorySummary

    job = api.Job(
        id="approval-required",
        state=api.JobState.awaiting_approval,
        repository=RepositorySummary(
            url="https://github.com/octocat/Hello-World",
            owner="octocat",
            name="Hello-World",
            project_type="python",
            files=[],
            manifests={},
            plan=Plan(commands=[], rationale=[], warnings=[]),
        ),
    )
    api.jobs[job.id] = job
    try:
        response = client.post(f"/api/v1/jobs/{job.id}/start")
        assert response.status_code == 409
    finally:
        api.jobs.pop(job.id, None)


def test_provider_timeout_cleans_workspace(monkeypatch, tmp_path):
    from app.execution import DockerExecutionProvider
    from app.config import settings

    monkeypatch.setattr(settings, "execution_enabled", True)
    monkeypatch.setattr(settings, "runtime_images", {"python": "approved/python@sha256:test"})
    monkeypatch.setattr(settings, "execution_workspace_root", tmp_path)
    provider = DockerExecutionProvider()
    monkeypatch.setattr(provider, "availability", lambda: (True, "ok"))

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[0] == "git":
            (tmp_path / next(path for path in command if str(path).startswith(str(tmp_path))) / "README.md").parent.mkdir(parents=True, exist_ok=True)
            return None
        raise __import__("subprocess").TimeoutExpired(command, 1)

    monkeypatch.setattr("app.execution.subprocess.run", fake_run)
    try:
        provider.start("timeout-job", "https://github.com/octocat/Hello-World", "python")
    except RuntimeError as exc:
        assert "timed out" in str(exc)
    assert not provider.containers
    assert not list(tmp_path.iterdir())


def test_provider_failure_cleans_workspace(monkeypatch, tmp_path):
    from app.execution import DockerExecutionProvider
    from app.config import settings

    monkeypatch.setattr(settings, "execution_enabled", True)
    monkeypatch.setattr(settings, "runtime_images", {"python": "approved/python@sha256:test"})
    monkeypatch.setattr(settings, "execution_workspace_root", tmp_path)
    provider = DockerExecutionProvider()
    monkeypatch.setattr(provider, "availability", lambda: (True, "ok"))

    def fake_run(command, **kwargs):
        if command[0] == "git":
            clone_target = next(path for path in command if str(path).startswith(str(tmp_path)))
            Path(clone_target).mkdir(parents=True)
            return None
        return type("Result", (), {"returncode": 23, "stdout": "", "stderr": "blocked"})()

    from pathlib import Path

    monkeypatch.setattr("app.execution.subprocess.run", fake_run)
    try:
        provider.start("failed-job", "https://github.com/octocat/Hello-World", "python")
    except RuntimeError as exc:
        assert "exit code 23" in str(exc)
    assert not provider.containers
    assert not list(tmp_path.iterdir())


def test_api_reports_container_failure_as_failed(monkeypatch):
    from app import api
    from app.execution import ExecutionFailedError
    from app.models import Plan, RepositorySummary

    job = api.Job(
        id="container-failed",
        state=api.JobState.awaiting_approval,
        approved=True,
        repository=RepositorySummary(
            url="https://github.com/octocat/Hello-World",
            owner="octocat",
            name="Hello-World",
            project_type="python",
            files=[],
            manifests={},
            plan=Plan(commands=[], rationale=[], warnings=[]),
        ),
    )
    api.jobs[job.id] = job
    monkeypatch.setattr(api.provider, "start", lambda *args: (_ for _ in ()).throw(ExecutionFailedError("container failed")))
    try:
        response = client.post(f"/api/v1/jobs/{job.id}/start")
        assert response.status_code == 200
        assert response.json()["state"] == "failed"
        assert response.json()["error"] == "container failed"
    finally:
        api.jobs.pop(job.id, None)


def test_missing_job_is_not_an_authorization_bypass():
    response = client.get("/api/v1/jobs/not-a-real-job")
    assert response.status_code == 404
