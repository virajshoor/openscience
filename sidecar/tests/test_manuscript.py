"""Tests for the /manuscript/export route."""

import pytest
from fastapi.testclient import TestClient

import sidecar.server as server
from sidecar.repro.recorder import Recorder
from sidecar.server import app, state


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OS_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("OS_CONFIG_DIR", str(tmp_path / "config"))
    state["recorder"] = Recorder(str(tmp_path / "runs"))
    state["backends"] = {"local": server.LocalBackend()}
    state["ssh"] = None
    state["llm"] = None
    with TestClient(app) as c:
        yield c


def test_manuscript_export_markdown(client):
    run_id = state["recorder"].start({"model": "t"})
    r = client.post("/manuscript/export", json={
        "markdown": "# Title\n\nBody text.",
        "format": "markdown",
        "run_id": run_id,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["format"] == "markdown"
    assert data["file"].endswith("manuscript.md")


def test_manuscript_export_rejects_bad_run_id(client):
    r = client.post("/manuscript/export", json={
        "markdown": "# x", "format": "markdown", "run_id": "not-a-run-id",
    })
    assert r.status_code == 200
    assert "error" in r.json()


def test_manuscript_export_latex_falls_back_without_pandoc(client, monkeypatch):
    run_id = state["recorder"].start({"model": "t"})
    monkeypatch.setattr(server.shutil, "which", lambda name: None)
    r = client.post("/manuscript/export", json={
        "markdown": "# Title\n\nBody.", "format": "latex", "run_id": run_id,
    })
    data = r.json()
    assert data["ok"] is True
    # Without pandoc we fall back to markdown with a warning.
    assert data["format"] == "markdown"
    assert "warning" in data