import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Job = {
  id: string;
  state: string;
  approved: boolean;
  error?: string;
  logs: string[];
  repository?: {
    owner: string;
    name: string;
    language?: string;
    project_type: string;
    readme?: string;
    files: string[];
    plan: { commands: string[]; rationale: string[]; warnings: string[] };
  };
};

const API = (import.meta.env.VITE_API_URL?.trim() || "/api/v1").replace(/\/+$/, "");

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error("Network error: unable to reach the RepoRunner backend. Check that the backend is running.");
  }

  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const detail = data && typeof data.detail === "string" ? data.detail : response.statusText || "Request failed";
    throw new Error(`Backend error (${response.status}): ${detail}`);
  }
  return data as T;
}

function App() {
  const [url, setUrl] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const inspect = async () => {
    setBusy(true); setError("");
    try { setJob(await request<Job>("/repositories/inspect", { method: "POST", body: JSON.stringify({ repository_url: url }) })); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Inspection failed"); }
    finally { setBusy(false); }
  };
  const approve = async (approved: boolean) => {
    if (!job) return;
    setBusy(true); setError("");
    try { setJob(await request<Job>(`/jobs/${job.id}/approve`, { method: "POST", body: JSON.stringify({ approved }) })); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Approval failed"); }
    finally { setBusy(false); }
  };
  const start = async () => {
    if (!job) return;
    setBusy(true); setError("");
    try { setJob(await request<Job>(`/jobs/${job.id}/start`, { method: "POST" })); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Start failed"); }
    finally { setBusy(false); }
  };

  return <main>
    <header><p className="eyebrow">REPORUNNER</p><h1>Run a repository, safely.</h1><p className="muted">Inspect first. Approve explicitly. Execute only with verified isolation.</p></header>
    <section className="card">
      <label htmlFor="repo-url">Public GitHub repository URL</label>
      <div className="url-row"><input id="repo-url" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://github.com/owner/repository" inputMode="url" /><button onClick={inspect} disabled={busy || !url.trim()}>{busy ? "Inspecting…" : "Inspect"}</button></div>
      {error && <p className="error" role="alert">{error}</p>}
    </section>
    {job && <section className="card">
      <div className="status-row"><div><p className="eyebrow">JOB {job.id.slice(0, 8)}</p><h2>{job.repository?.owner}/{job.repository?.name}</h2></div><span className={`status ${job.state}`}>{job.state.replaceAll("_", " ")}</span></div>
      {job.repository && <><div className="summary"><strong>{job.repository.language ?? "Unknown language"}</strong><span>{job.repository.project_type}</span><span>{job.repository.files.length} files sampled</span></div>
        <h3>Execution plan</h3><ul>{job.repository.plan.commands.map((command) => <li key={command}><code>{command}</code></li>)}</ul>
        <p className="muted">{job.repository.plan.warnings.join(" ")}</p>
        {!job.approved && job.state === "awaiting_approval" && <div className="actions"><button onClick={() => approve(true)} disabled={busy}>Approve plan</button><button className="secondary" onClick={() => approve(false)} disabled={busy}>Reject</button></div>}
        {job.approved && job.state === "awaiting_approval" && <button onClick={start} disabled={busy}>Start approved plan</button>}
      </>}
      {job.error && <p className="error" role="alert">{job.error}</p>}
      {job.logs.length > 0 && <><h3>Activity</h3><pre>{job.logs.join("\n")}</pre></>}
    </section>}
  </main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
