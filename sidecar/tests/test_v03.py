"""Tests for v0.3 features: session branching, agents, skills, approval gate, provenance."""

import pytest
from fastapi.testclient import TestClient

from sidecar.repro.recorder import Recorder
from sidecar.server import app, state
from sidecar.tools import compute as compute_mod
from sidecar.compute.local import LocalBackend


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OS_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("OS_CONFIG_DIR", str(tmp_path / "config"))
    state["recorder"] = Recorder(str(tmp_path / "runs"))
    state["backends"] = {"local": LocalBackend()}
    state["ssh"] = None
    state["llm"] = None
    state["require_approval"] = False
    from sidecar.tools import uniprot, pdb, entrez, chembl, code, compute  # noqa: F401
    with TestClient(app) as c:
        yield c


# --- Session branching (fork) ---

def test_fork_run_seeds_conversation(client):
    recorder: Recorder = state["recorder"]
    parent = recorder.start({"model": "t"})
    recorder.append(parent, "user", {"content": "hello"})
    r = client.post(f"/runs/{parent}/fork")
    assert r.status_code == 200
    new_id = r.json()["run_id"]
    assert new_id != parent
    forked = recorder.read_run(new_id)
    assert forked["manifest"]["parent_run_id"] == parent
    assert len(forked["conversation"]) == 1
    assert forked["conversation"][0]["payload"]["content"] == "hello"


def test_fork_bad_run_id(client):
    r = client.post("/runs/not-a-run-id/fork")
    assert r.status_code == 404


# --- Agents ---

def test_agent_crud_and_chat_injection(client, monkeypatch):
    # Create an agent
    r = client.post("/agents", json={"name": "struct", "system_prompt": "You are a structural biologist.", "tools": ["pdb.fetch", "alphafold.fetch"]})
    assert r.status_code == 200
    listed = client.get("/agents").json()["agents"]
    assert any(a["name"] == "struct" for a in listed)

    # /chat with the agent should inject the system prompt and filter tools.
    captured = {}

    class FakeLLM:
        async def run(self, messages, config, tools, backend, recorder):
            captured["messages"] = messages
            captured["tool_names"] = list(tools.keys())
            run_id = recorder.start(config)
            recorder.finish(run_id)
            yield {"event": "done", "data": {"run_id": run_id}}

    state["llm"] = FakeLLM()
    client.post("/chat", json={
        "messages": [{"role": "user", "content": "hi"}],
        "config": {"model": "t"},
        "agent": "struct",
    })
    assert captured["messages"][0]["role"] == "system"
    assert "structural biologist" in captured["messages"][0]["content"]
    assert set(captured["tool_names"]) == {"pdb.fetch", "alphafold.fetch"}

    # Delete
    client.delete("/agents/struct")
    assert not any(a["name"] == "struct" for a in client.get("/agents").json()["agents"])


# --- Skills ---

def test_skill_prepends_prompt(client):
    captured = {}

    class FakeLLM:
        async def run(self, messages, config, tools, backend, recorder):
            captured["messages"] = messages
            run_id = recorder.start(config)
            recorder.finish(run_id)
            yield {"event": "done", "data": {"run_id": run_id}}

    client.post("/skills", json={"name": "qc", "prompt": "Run QC steps: 1) ... 2) ..."})
    state["llm"] = FakeLLM()
    client.post("/chat", json={
        "messages": [{"role": "user", "content": "do qc"}],
        "config": {"model": "t"},
        "skill": "qc",
    })
    assert captured["messages"][0]["role"] == "system"
    assert "QC steps" in captured["messages"][0]["content"]


# --- Approval gate ---

@pytest.mark.asyncio
async def test_approval_gate_blocks_then_allows(client, monkeypatch):
    # Enable approval via the compute module's helper
    monkeypatch.setattr(compute_mod, "_approval_required", lambda: True)

    # First call without approval -> plan, not executed
    r = await compute_mod.compute_run(command="echo should-not-run", backend=LocalBackend())
    assert r["approval_required"] is True
    assert "plan" in r["data"]

    # Second call with approved=True -> executes
    r2 = await compute_mod.compute_run(command="echo hello-approved", approved=True, backend=LocalBackend())
    assert r2["data"]["exit_code"] == 0
    assert "hello-approved" in r2["data"]["stdout"]


# --- Provenance ---

@pytest.mark.asyncio
async def test_code_run_records_provenance(client):
    recorder = state["recorder"]
    run_id = recorder.start({"model": "t"})
    code = (
        "import os, matplotlib\nmatplotlib.use('Agg')\n"
        "import matplotlib.pyplot as plt\nplt.plot([1,2,3])\n"
        "plt.savefig(os.path.join(os.environ['OPENSCIENCE_FIG_DIR'], 'p.png'))\n"
    )
    from sidecar.tools.code import code_run
    r = await code_run(code=code, backend=LocalBackend(), recorder=recorder, run_id=run_id)
    run = recorder.read_run(run_id)
    assert "provenance" in run
    fig_name = r["viewers"][0]["src"].split("/")[-1]
    assert fig_name in run["provenance"]
    assert run["provenance"][fig_name]["tool"] == "code.run"
    assert "source" in run["provenance"][fig_name]