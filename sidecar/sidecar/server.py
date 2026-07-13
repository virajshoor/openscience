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
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


@asynccontextmanager
async def lifespan(app: FastAPI):
    runs_dir = os.environ.get("OS_RUNS_DIR", os.path.expanduser("~/.openscience/runs"))
    os.makedirs(runs_dir, exist_ok=True)
    state["recorder"] = Recorder(runs_dir)
    state["backends"] = {"local": LocalBackend()}
    # SSH backend is lazy-configured via /compute endpoint
    state["ssh"] = None
    state["llm"] = LLMClient()
    # import tools so they register
    from .tools import uniprot, pdb, entrez, chembl  # noqa: F401
    yield
    if state.get("ssh"):
        state["ssh"].close()


app = FastAPI(title="OpenScience Sidecar", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    """
    from fastapi.responses import StreamingResponse
    llm: LLMClient = state["llm"]
    recorder: Recorder = state["recorder"]
    messages = req.get("messages", [])
    config = req.get("config", {})
    backend_name = req.get("compute", "local")
    backend: ComputeBackend = state["backends"].get(backend_name) or state.get("ssh") or state["backends"]["local"]

    async def event_stream():
        async for evt in llm.run(messages, config=config, tools=registry.tools, backend=backend, recorder=recorder):
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


@app.get("/compute")
async def list_compute():
    out = {"backends": [{"name": "local", "type": "local"}]}
    if state.get("ssh"):
        out["backends"].append({"name": "ssh", "type": "ssh"})
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
    """Return persisted user config (endpoint, model, API key, etc.)."""
    return load_config()


@app.post("/config")
async def save_user_config(req: dict):
    """Persist user config to ~/.openscience/config.json. Survives reinstalls."""
    save_config(req)
    return {"ok": True}


@app.delete("/config")
async def clear_config():
    """Clear persisted config."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    return {"ok": True}
