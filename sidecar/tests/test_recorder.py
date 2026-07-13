"""Tests for the recorder: path safety, output naming, secret redaction."""

import json
import tempfile
from pathlib import Path

from sidecar.repro.recorder import Recorder


def test_write_output_returns_hashed_basename():
    with tempfile.TemporaryDirectory() as d:
        r = Recorder(d)
        run_id = r.start({"model": "test", "api_key": "secret"})
        name = r.write_output(run_id, "1CRN.pdb", b"fake pdb data")
        assert name.startswith("/") is False
        assert "1CRN.pdb" in name
        assert "_" in name
        assert len(name.split("_")[0]) == 8


def test_manifest_redacts_api_key():
    with tempfile.TemporaryDirectory() as d:
        r = Recorder(d)
        r.start({"model": "test", "api_key": "sk-supersecret", "base_url": "http://x"})
        manifest = json.loads((Path(d) / r.list_runs()[0]["run_id"] / "manifest.json").read_text())
        assert "api_key" not in manifest["config"]
        assert manifest["config"]["model"] == "test"


def test_run_id_is_hex():
    with tempfile.TemporaryDirectory() as d:
        r = Recorder(d)
        run_id = r.start({})
        assert len(run_id) == 12
        assert all(c in "0123456789abcdef" for c in run_id)


def test_list_runs_sorted_recent_first():
    with tempfile.TemporaryDirectory() as d:
        r = Recorder(d)
        r.start({})
        r.start({})
        runs = r.list_runs()
        assert len(runs) == 2
        assert runs[0]["started_at"] >= runs[1]["started_at"]


def test_read_run_returns_outputs():
    with tempfile.TemporaryDirectory() as d:
        r = Recorder(d)
        run_id = r.start({})
        r.write_output(run_id, "test.pdb", b"data")
        run = r.read_run(run_id)
        assert "outputs" in run
        assert len(run["outputs"]) == 1