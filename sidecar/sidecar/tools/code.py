"""Code execution tool.

Runs Python (or R, if Rscript is available) on the selected compute backend,
captures stdout/stderr, and persists any figures written to the run's figure
directory as `figure` viewer artifacts. The executed source is recorded in the
run for the audit trail.

This is the first tool to consume the `backend` kwarg plumbed through
`registry.invoke` -> `LLMClient.run`, so it works on local, SSH, or (via the
SSH transport) Slurm clusters.

Figures: the tool points the environment variable `OPENSCIENCE_FIG_DIR` at a
per-run directory and asks the model (via the tool description) to save figures
there with matplotlib/plotly. After execution the tool collects every file in
that directory, content-addresses it through the recorder, and emits one
`figure` viewer event per file so the UI can render it.
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys
from pathlib import Path

from .registry import tool

# Figure file extensions we surface as viewer artifacts (lowercased, no dot).
FIGURE_EXTS = {"png", "svg", "html", "jpg", "jpeg", "pdf"}
MAX_FIGURES = 20
MAX_STDOUT = 8000
MAX_STDERR = 4000


def _remote_python() -> str:
    return os.environ.get("OS_REMOTE_PYTHON", "python3")


def _interpreter(language: str, backend_name: str) -> str | None:
    """Resolve the interpreter command for the given language/backend."""
    if language == "r":
        candidate = "Rscript"
        if backend_name == "local":
            return shutil.which(candidate) and candidate
        return candidate  # assume present on the remote
    # python
    if backend_name == "local":
        return sys.executable or "python3"
    return _remote_python()


def _figure_viewers(run_id: str, fig_dir: Path, recorder) -> list[dict]:
    """Collect figure files from fig_dir, persist them, and build viewer dicts."""
    viewers: list[dict] = []
    if not fig_dir.is_dir():
        return viewers
    files = sorted(p for p in fig_dir.iterdir() if p.is_file())
    for p in files:
        ext = p.suffix.lower().lstrip(".")
        if ext not in FIGURE_EXTS:
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        output_name = recorder.write_output(run_id, p.name, data)
        fmt = "jpg" if ext == "jpeg" else ext
        viewers.append(
            {
                "type": "figure",
                "src": f"runs/{run_id}/outputs/{output_name}",
                "label": p.name,
                "format": fmt,
            }
        )
        if len(viewers) >= MAX_FIGURES:
            break
    return viewers


@tool(
    "code.run",
    "Execute Python (or R) code on the selected compute backend and capture stdout/stderr. "
    "Save any figures to the directory given by os.environ['OPENSCIENCE_FIG_DIR'] "
    "(matplotlib: call matplotlib.use('Agg') then plt.savefig(path); plotly: "
    "fig.write_image(path) or fig.write_html(path)). Figures are rendered in the UI. "
    "The executed code is recorded in the run for reproducibility.",
    {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Source code to execute"},
            "language": {
                "type": "string",
                "enum": ["python", "r"],
                "description": "Language (default python). R requires Rscript on PATH.",
            },
            "timeout": {"type": "integer", "description": "Seconds (default 120, max 1800)"},
        },
        "required": ["code"],
    },
)
async def code_run(
    code: str,
    language: str = "python",
    timeout: int = 120,
    backend=None,
    recorder=None,
    run_id=None,
) -> dict:
    if backend is None or recorder is None or run_id is None:
        return {"error": "code.run requires a compute backend and active run"}
    timeout = max(1, min(int(timeout or 120), 1800))
    backend_name = getattr(backend, "name", "local")

    interp = _interpreter(language, backend_name)
    if not interp:
        return {"error": f"{language} interpreter not found on the {backend_name} backend"}

    work_dir = recorder.runs_dir / run_id / "work"
    fig_dir = work_dir / "figures"
    work_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    suffix = ".py" if language == "python" else ".R"
    script_path = work_dir / f"script{suffix}"
    script_path.write_text(code)
    # Persist the source itself (content-addressed) so it is downloadable & verified.
    script_output = recorder.write_output(run_id, f"script{suffix}", code.encode())

    env = {
        "MPLBACKEND": "Agg",
        "OPENSCIENCE_FIG_DIR": str(fig_dir),
    }

    if backend_name == "local":
        cmd = f"{shlex.quote(interp)} {shlex.quote(str(script_path))}"
        result = await backend.run(cmd, timeout=timeout, cwd=str(work_dir), env=env)
        viewers = _figure_viewers(run_id, fig_dir, recorder)
    else:
        # SSH/remote: stage the script, run remotely, pull figures back.
        remote_script = f"/tmp/os_{run_id}_script{suffix}"
        remote_figdir = f"/tmp/os_{run_id}_figdir"
        # Clean and recreate the remote figure directory.
        await backend.run(f"rm -rf {shlex.quote(remote_figdir)} && mkdir -p {shlex.quote(remote_figdir)}")
        await backend.upload(str(script_path), remote_script)
        run_cmd = (
            f"{shlex.quote(_remote_python() if language == 'python' else interp)} "
            f"{shlex.quote(remote_script)}"
        )
        result = await backend.run(run_cmd, timeout=timeout, env={**env, "OPENSCIENCE_FIG_DIR": remote_figdir})
        # Enumerate remote figures (null-delimited to survive spaces) and download them.
        listing = await backend.run(f"find {shlex.quote(remote_figdir)} -type f -print0")
        remote_files = [f for f in listing.stdout.split("\x00") if f]
        for rf in remote_files[:MAX_FIGURES]:
            local_path = fig_dir / Path(rf).name
            try:
                await backend.download(rf, str(local_path))
            except Exception:
                continue
        viewers = _figure_viewers(run_id, fig_dir, recorder)

    stdout = (result.stdout or "")[:MAX_STDOUT]
    stderr = (result.stderr or "")[:MAX_STDERR]
    summary = (
        f"Executed {language} on {backend_name} (exit {result.exit_code}). "
        f"{len(viewers)} figure(s). "
        f"stdout: {stdout[:500]}{'...' if len(result.stdout or '') > 500 else ''}"
    )
    return {
        "summary": summary,
        "data": {
            "exit_code": result.exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "language": language,
            "backend": backend_name,
            "figures": [v["label"] for v in viewers],
            "script": script_output,
        },
        "viewer": viewers[0] if viewers else None,
        "viewers": viewers,
    }