"""OpenScience Python sidecar.

Started by the Tauri shell on app launch. Exposes:
  /health           liveness
  /chat             streaming chat (SSE) with tool dispatch
  /tools            list + describe registered tools
  /runs             list + read reproducibility runs
  /compute          list + configure compute backends
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .llm.client import LLMClient
from .repro.recorder import Recorder
from .tools.registry import registry
from .compute.base import ComputeBackend
from .compute.local import LocalBackend
from .compute.ssh import SSHBackend

# Globals (set in lifespan, read by routes)
state: dict = {}
SAFE_RUN_ID = re.compile(r"^[a-f0-9]{12}$")
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

CONFIG_DIR = Path(os.environ.get("OS_CONFIG_DIR", os.path.expanduser("~/.openscience")))
PERSISTED_CONFIG_KEYS = {"base_url", "model", "temperature", "use_tools", "compute", "require_approval"}
KEYCHAIN_SERVICE = "ai.openscience.workbench"
KEYCHAIN_ACCOUNT = "openai-api-key"


def _agents_file() -> Path:
    return Path(os.environ.get("OS_CONFIG_DIR", os.path.expanduser("~/.openscience"))) / "agents.json"


def _skills_file() -> Path:
    return Path(os.environ.get("OS_CONFIG_DIR", os.path.expanduser("~/.openscience"))) / "skills.json"


def _load_json_list(path: Path) -> list[dict]:
    if path.exists():
        try:
            data = json.loads(path.read_text())
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _save_json_list(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, indent=2))


def _upsert(items: list[dict], item: dict, key: str = "name") -> list[dict]:
    name = item.get(key)
    if not name:
        return items
    out = [i for i in items if i.get(key) != name]
    out.append(item)
    return out


def _remove(items: list[dict], name: str, key: str = "name") -> list[dict]:
    return [i for i in items if i.get(key) != name]


def _config_file() -> Path:
    config_dir = Path(os.environ.get("OS_CONFIG_DIR", os.path.expanduser("~/.openscience")))
    return config_dir / "config.json"


def _keychain_api_key() -> str:
    if os.uname().sysname != "Darwin":
        return ""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _save_keychain_api_key(api_key: str) -> None:
    if not api_key or os.uname().sysname != "Darwin":
        return
    subprocess.run(
        ["security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w", api_key],
        check=True,
        capture_output=True,
        text=True,
    )


def _delete_keychain_api_key() -> None:
    if os.uname().sysname != "Darwin":
        return
    subprocess.run(
        ["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT],
        capture_output=True,
        text=True,
    )


def load_config() -> dict:
    f = _config_file()
    config = {}
    if f.exists():
        try:
            config = json.loads(f.read_text())
        except json.JSONDecodeError:
            config = {}
    # Migrate legacy plaintext keys into the macOS Keychain on first read.
    legacy_key = str(config.pop("api_key", "")).strip()
    if legacy_key:
        _save_keychain_api_key(legacy_key)
        f.write_text(json.dumps({key: value for key, value in config.items() if key in PERSISTED_CONFIG_KEYS}, indent=2))
    config = {key: value for key, value in config.items() if key in PERSISTED_CONFIG_KEYS}
    api_key = _keychain_api_key()
    if api_key:
        config["api_key"] = api_key
    return config


def save_config(cfg: dict) -> None:
    config_dir = Path(os.environ.get("OS_CONFIG_DIR", os.path.expanduser("~/.openscience")))
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {key: value for key, value in cfg.items() if key in PERSISTED_CONFIG_KEYS}
    api_key = str(cfg.get("api_key", "")).strip()
    if api_key:
        _save_keychain_api_key(api_key)
    (config_dir / "config.json").write_text(json.dumps(config, indent=2))


@asynccontextmanager
async def lifespan(app: FastAPI):
    runs_dir = os.environ.get("OS_RUNS_DIR", os.path.expanduser("~/.openscience/runs"))
    os.makedirs(runs_dir, exist_ok=True)
    state["recorder"] = Recorder(runs_dir)
    state["backends"] = {"local": LocalBackend()}
    # SSH backend is lazy-configured via /compute endpoint
    state["ssh"] = None
    state["llm"] = LLMClient()
    state["require_approval"] = bool(load_config().get("require_approval", False))
    # import tools so they register
    from .tools import (  # noqa: F401
        uniprot, pdb, entrez, chembl, code, compute,
        ensembl, clinvar, geo, alphafold, pubmed, europepmc, crossref,
    )
    yield
    if state.get("ssh"):
        state["ssh"].close()


app = FastAPI(title="OpenScience Sidecar", version="0.3.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "OS_ALLOWED_ORIGINS", "http://localhost:1420,http://127.0.0.1:1420,tauri://localhost"
    ).split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"ok": True, "tools": len(registry.tools)}


@app.get("/tools")
async def list_tools():
    return {"tools": [t.schema() for t in registry.tools.values()]}


@app.post("/chat")
async def chat(req: dict):
    """SSE stream of assistant + tool events.

    Each event is a single line: data: <json>\n\n
    where <json> is {"event": "...", "data": ...}

    Optional `agent` (name) injects a specialist agent's system prompt and
    restricts the tool set. Optional `skill` (name) prepends a reusable skill
    prompt to the conversation.
    """
    from fastapi.responses import StreamingResponse
    llm: LLMClient = state["llm"]
    recorder: Recorder = state["recorder"]
    messages = [dict(m) for m in req.get("messages", [])]
    config = req.get("config", {})
    backend_name = req.get("compute", "local")
    # "slurm" runs on the SSH host (sbatch via the SSH backend); "ssh"/"slurm" both
    # resolve to the lazily-configured SSH backend, falling back to local.
    if backend_name in ("ssh", "slurm"):
        backend: ComputeBackend = state.get("ssh") or state["backends"]["local"]
    else:
        backend = state["backends"].get(backend_name) or state["backends"]["local"]

    tools = registry.tools
    agent_name = req.get("agent")
    if agent_name:
        agent = next((a for a in _load_json_list(_agents_file()) if a.get("name") == agent_name), None)
        if agent:
            sp = agent.get("system_prompt") or ""
            if sp and (not messages or messages[0].get("role") != "system"):
                messages.insert(0, {"role": "system", "content": sp})
            allowed = agent.get("tools")
            if isinstance(allowed, list) and allowed:
                tools = {n: t for n, t in registry.tools.items() if n in allowed}

    skill_name = req.get("skill")
    if skill_name:
        skill = next((s for s in _load_json_list(_skills_file()) if s.get("name") == skill_name), None)
        if skill and skill.get("prompt"):
            messages.insert(0, {"role": "system", "content": skill["prompt"]})

    async def event_stream():
        async for evt in llm.run(messages, config=config, tools=tools, backend=backend, recorder=recorder):
            yield f"data: {json.dumps(evt, default=str)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/review")
async def review(req: dict):
    """Run the automated reviewer on an existing run."""
    llm: LLMClient = state["llm"]
    recorder: Recorder = state["recorder"]
    run_id = req.get("run_id")
    config = req.get("config", {})
    if not run_id:
        return {"error": "run_id required"}
    return await llm.reviewer.review(run_id, recorder, config)


@app.get("/runs")
async def list_runs():
    recorder: Recorder = state["recorder"]
    return {"runs": recorder.list_runs()}


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    recorder: Recorder = state["recorder"]
    return recorder.read_run(run_id)


@app.get("/runs/{run_id}/verify")
async def verify_run(run_id: str):
    if not SAFE_RUN_ID.fullmatch(run_id):
        raise HTTPException(status_code=404, detail="run not found")
    recorder: Recorder = state["recorder"]
    return recorder.verify_run(run_id)


@app.get("/compute")
async def list_compute():
    out = {"backends": [{"name": "local", "type": "local"}]}
    if state.get("ssh"):
        out["backends"].append({"name": "ssh", "type": "ssh"})
        out["backends"].append({"name": "slurm", "type": "slurm"})
    return out


@app.post("/compute/ssh")
async def configure_ssh(req: dict):
    backend = SSHBackend(req["host"], req.get("user", os.getenv("USER")), req.get("port", 22), req.get("key_path"))
    state["ssh"] = backend
    return {"ok": True, "host": req["host"]}


@app.get("/runs/{run_id}/outputs/{filename}")
async def get_output(run_id: str, filename: str):
    recorder: Recorder = state["recorder"]
    if not SAFE_RUN_ID.fullmatch(run_id) or not SAFE_FILENAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="output not found")

    outputs_dir = recorder.runs_dir / run_id / "outputs"
    output = outputs_dir / filename
    if not output.is_file():
        # Runs written before content-addressed names were exposed in viewer events
        # referenced the original filename. Resolve that one legacy name safely.
        matches = [p for p in outputs_dir.glob(f"*_{filename}") if p.is_file()]
        output = matches[0] if len(matches) == 1 else output
    if not output.is_file():
        raise HTTPException(status_code=404, detail="output not found")
    return FileResponse(output)


@app.get("/config")
async def get_config():
    """Return persisted user config with the API key read from macOS Keychain."""
    return load_config()


@app.post("/config")
async def save_user_config(req: dict):
    """Persist preferences locally and save an API key in macOS Keychain."""
    save_config(req)
    state["require_approval"] = bool(req.get("require_approval", False))
    return {"ok": True}


@app.delete("/config")
async def clear_config():
    """Clear persisted config."""
    f = _config_file()
    if f.exists():
        f.unlink()
    _delete_keychain_api_key()
    state["require_approval"] = False
    return {"ok": True}


# --- Specialist agents (user-created) -----------------------------------------

@app.get("/agents")
async def list_agents():
    return {"agents": _load_json_list(_agents_file())}


@app.post("/agents")
async def save_agent(req: dict):
    name = str(req.get("name", "")).strip()
    if not name:
        return {"error": "name required"}
    agent = {
        "name": name,
        "system_prompt": str(req.get("system_prompt", "")),
        "tools": req.get("tools"),  # list[str] | None (None = all tools)
    }
    items = _upsert(_load_json_list(_agents_file()), agent)
    _save_json_list(_agents_file(), items)
    return {"ok": True, "agent": agent}


@app.delete("/agents/{name}")
async def delete_agent(name: str):
    items = _remove(_load_json_list(_agents_file()), name)
    _save_json_list(_agents_file(), items)
    return {"ok": True}


# --- Reusable skills (saved prompts / pipelines) ------------------------------

@app.get("/skills")
async def list_skills():
    return {"skills": _load_json_list(_skills_file())}


@app.post("/skills")
async def save_skill(req: dict):
    name = str(req.get("name", "")).strip()
    if not name:
        return {"error": "name required"}
    skill = {
        "name": name,
        "prompt": str(req.get("prompt", "")),
        "tools": req.get("tools"),
    }
    items = _upsert(_load_json_list(_skills_file()), skill)
    _save_json_list(_skills_file(), items)
    return {"ok": True, "skill": skill}


@app.delete("/skills/{name}")
async def delete_skill(name: str):
    items = _remove(_load_json_list(_skills_file()), name)
    _save_json_list(_skills_file(), items)
    return {"ok": True}


# --- Session branching (fork a run) -------------------------------------------

@app.post("/runs/{run_id}/fork")
async def fork_run(run_id: str):
    if not SAFE_RUN_ID.fullmatch(run_id):
        raise HTTPException(status_code=404, detail="run not found")
    recorder: Recorder = state["recorder"]
    new_id = recorder.fork(run_id, {})
    if not new_id:
        raise HTTPException(status_code=404, detail="parent run not found")
    return {"ok": True, "run_id": new_id, "parent_run_id": run_id}


@app.post("/manuscript/export")
async def export_manuscript(req: dict):
    """Assemble manuscript sections and export to Markdown/LaTeX/PDF.

    Body: { "markdown": str, "bib": str | None, "format": "markdown"|"latex"|"pdf", "run_id": str }
    The assembled manuscript (and bibliography) are saved to the run's outputs for
    reproducibility. LaTeX/PDF require `pandoc` on PATH (PDF also needs a LaTeX
    engine); otherwise the endpoint falls back to returning Markdown.
    """
    recorder: Recorder = state["recorder"]
    markdown = str(req.get("markdown", ""))
    bib = req.get("bib")
    fmt = req.get("format", "markdown")
    run_id = req.get("run_id")
    if not SAFE_RUN_ID.fullmatch(run_id or ""):
        return {"error": "a valid run_id is required"}

    md_name = recorder.write_output(run_id, "manuscript.md", markdown.encode())
    bib_name = None
    if bib:
        bib_name = recorder.write_output(run_id, "citations.bib", str(bib).encode())

    outputs_dir = recorder.runs_dir / run_id / "outputs"

    if fmt == "markdown":
        return {"ok": True, "file": md_name, "format": "markdown",
                "download": f"runs/{run_id}/outputs/{md_name}"}

    if not shutil.which("pandoc"):
        return {"ok": True, "file": md_name, "format": "markdown",
                "download": f"runs/{run_id}/outputs/{md_name}",
                "warning": "pandoc not installed; exported Markdown instead of " + fmt}

    out_ext = "tex" if fmt == "latex" else "pdf"
    out_name = f"manuscript_pandoc_{os.getpid()}.{out_ext}"
    md_path = outputs_dir / md_name
    out_path = outputs_dir / out_name
    cmd = ["pandoc", str(md_path), "-o", str(out_path)]
    if bib_name:
        cmd += ["--bibliography", str(outputs_dir / bib_name)]
    if fmt == "pdf":
        cmd += ["--pdf-engine=xelatex"]
    try:
        proc = await state["backends"]["local"].run(
            " ".join(shlex.quote(a) for a in cmd), timeout=120
        )
        if proc.exit_code != 0 or not out_path.is_file():
            return {"ok": True, "file": md_name, "format": "markdown",
                    "download": f"runs/{run_id}/outputs/{md_name}",
                    "warning": f"pandoc failed (exit {proc.exit_code}); exported Markdown. stderr: {proc.stderr[:300]}"}
        return {"ok": True, "file": out_name, "format": fmt,
                "download": f"runs/{run_id}/outputs/{out_name}"}
    except Exception as e:
        return {"ok": True, "file": md_name, "format": "markdown",
                "download": f"runs/{run_id}/outputs/{md_name}",
                "warning": f"export error: {e}; exported Markdown."}
