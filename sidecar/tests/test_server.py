"""Tests for FastAPI sidecar routes."""


import pytest
from fastapi.testclient import TestClient

from sidecar.server import app, state
from sidecar.repro.recorder import Recorder


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OS_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("OS_CONFIG_DIR", str(tmp_path / "config"))
    state["recorder"] = Recorder(str(tmp_path / "runs"))
    state["backends"] = {}
    state["ssh"] = None
    state["llm"] = None
    from sidecar.tools import uniprot, pdb, entrez, chembl  # noqa
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["tools"] > 0


def test_list_tools(client):
    r = client.get("/tools")
    assert r.status_code == 200
    tools = r.json()["tools"]
    names = [t["name"] for t in tools]
    assert "pdb.fetch" in names
    assert "uniprot.fetch" in names


def test_config_save_and_load(client):
    r = client.post("/config", json={"base_url": "http://x", "model": "m", "api_key": "sk-x"})
    assert r.status_code == 200
    r2 = client.get("/config")
    data = r2.json()
    assert data["base_url"] == "http://x"
    assert data["api_key"] == "sk-x"


def test_output_path_traversal_blocked(client):
    r = client.get("/runs/../etc/outputs/passwd")
    assert r.status_code in (404, 422)


def test_output_bad_run_id(client):
    r = client.get("/runs/../../etc/outputs/passwd")
    assert r.status_code in (404, 422)


def test_runs_list(client):
    r = client.get("/runs")
    assert r.status_code == 200
    assert "runs" in r.json()