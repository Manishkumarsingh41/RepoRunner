# RepoRunner

Mobile-first GitHub repository inspection and guarded runner MVP.

## What works

The FastAPI service accepts a public GitHub HTTPS URL, shallow-clones it into a
unique temporary workspace, reads bounded README and manifest content, detects
Python/Node/container projects, and returns an execution plan. Repository
content is treated as untrusted data: dependencies and scripts are never
installed or run during inspection. The web UI lets a user review and
explicitly approve the plan.

Execution currently returns `execution_unavailable`. Docker access is detected
on the development machine, but no trusted image policy, network isolation
policy, preview proxy, or lifecycle manager has been implemented yet. It would
be unsafe to run arbitrary repositories on the API host, so this feature is
disabled intentionally.

## Run in GitHub Codespaces

Start the backend and frontend in separate terminals. The backend must listen
on `0.0.0.0:8000` and the Vite server on `0.0.0.0:5173` so Codespaces can
forward both ports:

```bash
# Terminal 1
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# Terminal 2
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Forward port 5173 as **Private** and open its forwarded URL. The frontend
calls `/api/v1` on that same origin by default, and Vite proxies those requests
to `http://localhost:8000` inside the Codespace. This avoids using
`localhost:8000` in the browser, which would refer to the device running the
browser. The backend health endpoint remains available inside the Codespace at
`http://localhost:8000/health`.

`VITE_API_URL` remains supported for deployments without the Vite proxy. For
example, set `VITE_API_URL=https://<backend-forwarded-host>/api/v1` before
building or starting the frontend when the API is intentionally served from a
different origin. Do not replace `<backend-forwarded-host>` with a guessed
Codespaces hostname. If using a different origin, configure
`REPORUNNER_CORS_ORIGINS` on the backend with the exact frontend origin.

The backend supports optional limits including
`REPORUNNER_MAX_CLONE_SECONDS`, `REPORUNNER_MAX_FILES`,
`REPORUNNER_MAX_REPO_BYTES`, and `REPORUNNER_WORKSPACE_ROOT`.

## Run the frontend

```bash
cd frontend
npm run dev -- --host 0.0.0.0
```

The Vite development server runs on port 5173. The app is responsive for
Android Chrome and uses touch-sized controls. A production bundle can be built
with `npm run build`.

## Test

```bash
cd backend
source .venv/bin/activate
pytest -q
cd ../frontend
npm run build
```

## Open on an Android phone

In Codespaces, open the **Ports** panel, make port 5173 visible as **Private**,
then copy its forwarded URL. Open that URL in Chrome on the Nothing Phone 2
and sign in to GitHub if prompted. Use the frontend URL, not the backend
forwarded URL. Keep the backend process running on port 8000 in the Codespace.

If the app reports **Failed to fetch**, confirm that the frontend URL is the
port 5173 forwarded URL, port 5173 is still forwarded and accessible to the
phone, and the backend is running on port 8000. Check the Codespace terminal
with `curl -i http://localhost:8000/health`; it should return HTTP 200. A
message beginning with `Network error` means the browser could not reach the
frontend/proxy, while `Backend error (4xx/5xx)` means the request reached the
API and was rejected or failed.

## API flow

1. `POST /api/v1/repositories/inspect` with
   `{"repository_url":"https://github.com/owner/repository"}`.
2. Review the returned `awaiting_approval` job and its plan.
3. `POST /api/v1/jobs/{job_id}/approve` with `{"approved":true}`.
4. `POST /api/v1/jobs/{job_id}/start` reports
   `execution_unavailable` until a verified provider is configured.
5. `GET /api/v1/jobs/{job_id}`, `/logs`, and `/preview` expose status, activity,
   and only an actually available preview (currently none).

## Security and limitations

- Only public `https://github.com/<owner>/<repo>` URLs are accepted; credentials,
  query strings, alternate hosts, and traversal-like paths are rejected.
- Cloning is shallow, time-limited, size-limited, file-count-limited, and
  cleaned up after inspection.
- No repository commands, dependency installation, post-install hooks, or
  README instructions are executed.
- Approval only records explicit consent for the proposed plan. Starting a
  job currently returns `execution_unavailable`; arbitrary repository
  execution and previews are intentionally disabled.
- There is no authentication or multi-user authorization layer yet; deploy the
  API behind an authenticated gateway before exposing it publicly.
- A future execution provider must use non-root, non-privileged short-lived
  containers, no Docker socket, no host secrets, read-only base filesystems,
  bounded CPU/memory/process/disk/time, and disabled network by default.
- Android local execution is deliberately not implemented by this browser app.
  A later Android client could integrate with Termux through an explicit,
  user-mediated intent/API, with Android sandbox and permission restrictions;
  it must remain a separate adapter and must not imply arbitrary browser shell
  access.