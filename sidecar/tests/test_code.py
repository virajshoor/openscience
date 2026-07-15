"""Tests for the code.run tool (local execution + figure extraction)."""

import pytest

from sidecar.compute.local import LocalBackend
from sidecar.repro.recorder import Recorder
from sidecar.tools.code import code_run


@pytest.fixture
def recorder(tmp_path, monkeypatch):
    monkeypatch.setenv("OS_RUNS_DIR", str(tmp_path / "runs"))
    return Recorder(str(tmp_path / "runs"))


@pytest.mark.asyncio
async def test_code_run_produces_figure(recorder):
    run_id = recorder.start({"model": "test"})
    code = (
        "import os, matplotlib\n"
        "matplotlib.use('Agg')\n"
        "import matplotlib.pyplot as plt\n"
        "plt.plot([1, 2, 3], [1, 4, 9])\n"
        "plt.savefig(os.path.join(os.environ['OPENSCIENCE_FIG_DIR'], 'line.png'))\n"
    )
    result = await code_run(
        code=code, backend=LocalBackend(), recorder=recorder, run_id=run_id
    )
    assert result["data"]["exit_code"] == 0
    assert result["data"]["backend"] == "local"
    assert "line.png" in result["data"]["figures"]
    assert result["viewer"] and result["viewer"]["type"] == "figure"
    assert result["viewer"]["format"] == "png"
    assert result["viewers"] and len(result["viewers"]) == 1
    # The figure file was content-addressed into outputs/
    outputs = (recorder.runs_dir / run_id / "outputs").iterdir()
    assert any(p.name.endswith("_line.png") for p in outputs)
    # The source script was persisted too.
    assert any("script.py" in p.name for p in outputs)


@pytest.mark.asyncio
async def test_code_run_captures_stdout_and_errors(recorder):
    run_id = recorder.start({"model": "test"})
    result = await code_run(
        code="print('hello world')\n1/0",
        backend=LocalBackend(),
        recorder=recorder,
        run_id=run_id,
    )
    assert "hello world" in result["data"]["stdout"]
    assert result["data"]["exit_code"] != 0
    assert "ZeroDivisionError" in result["data"]["stderr"]
    assert result["viewer"] is None
    assert result["viewers"] == []


@pytest.mark.asyncio
async def test_code_run_missing_backend(recorder):
    run_id = recorder.start({"model": "test"})
    result = await code_run(code="print(1)", recorder=recorder, run_id=run_id)
    assert "error" in result