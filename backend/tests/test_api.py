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


def test_missing_job_is_not_an_authorization_bypass():
    response = client.get("/api/v1/jobs/not-a-real-job")
    assert response.status_code == 404
