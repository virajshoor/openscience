"""Compute management tools.

Expose the already-implemented compute backends (local / SSH / Slurm) to the
agent so it can run commands and manage HPC jobs from the chat loop. These are
thin wrappers over `ComputeBackend.run` and the Slurm helpers on `SSHBackend`
(`submit_slurm` / `slurm_status` / `slurm_cancel`).

Slurm requires the SSH backend: set `compute=ssh` (or `slurm`) in settings and
configure an SSH connection. No API keys are involved — SSH uses the user's
existing `~/.ssh` keys via paramiko.
"""

from __future__ import annotations

import shlex

from .registry import tool


def _backend_name(backend) -> str:
    return getattr(backend, "name", "local")


@tool(
    "compute.run",
    "Run an arbitrary shell command on the selected compute backend (local or SSH) "
    "and return stdout/stderr. Use this for running existing scripts or CLI tools, "
    "e.g. `python3 train.py` or `samtools index aligned.bam`. For writing and running "
    "new Python code with figures, prefer code.run.",
    {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "integer", "description": "Seconds (default 300, max 1800)"},
            "cwd": {"type": "string", "description": "Working directory for the command (optional)"},
        },
        "required": ["command"],
    },
)
async def compute_run(command: str, timeout: int = 300, cwd: str | None = None, backend=None) -> dict:
    if backend is None:
        return {"error": "no compute backend available"}
    timeout = max(1, min(int(timeout or 300), 1800))
    result = await backend.run(command, timeout=timeout, cwd=cwd)
    stdout = (result.stdout or "")[:8000]
    stderr = (result.stderr or "")[:4000]
    return {
        "summary": f"Ran command on {_backend_name(backend)} (exit {result.exit_code}). stdout: {stdout[:300]}",
        "data": {"exit_code": result.exit_code, "stdout": stdout, "stderr": stderr, "backend": _backend_name(backend)},
    }


@tool(
    "slurm.submit",
    "Submit a Slurm batch script on the SSH compute backend. Requires compute=ssh. "
    "Returns the Slurm job id. Submission is non-blocking; poll with slurm.status.",
    {
        "type": "object",
        "properties": {
            "script": {"type": "string", "description": "Slurm batch script body (with #SBATCH headers)"},
        },
        "required": ["script"],
    },
)
async def slurm_submit(script: str, backend=None) -> dict:
    if backend is None or _backend_name(backend) != "ssh":
        return {"error": "Slurm requires the SSH backend. Set compute=ssh in Settings and configure an SSH connection."}
    if not hasattr(backend, "submit_slurm"):
        return {"error": "backend does not support Slurm"}
    res = await backend.submit_slurm(script)
    job_id = res.get("job_id")
    return {
        "summary": f"Submitted Slurm job {job_id}" if job_id else "Slurm submission returned no job id",
        "data": {"job_id": job_id, "stdout": (res.get("stdout") or "")[:2000], "stderr": (res.get("stderr") or "")[:2000]},
    }


@tool(
    "slurm.status",
    "Check the state of a Slurm job (e.g. PENDING, RUNNING, COMPLETED) on the SSH backend.",
    {
        "type": "object",
        "properties": {"job_id": {"type": "string", "description": "Slurm job id"}},
        "required": ["job_id"],
    },
)
async def slurm_status(job_id: str, backend=None) -> dict:
    if backend is None or _backend_name(backend) != "ssh":
        return {"error": "Slurm requires the SSH backend."}
    res = await backend.slurm_status(shlex.quote(job_id))
    return {"summary": f"Slurm job {job_id}: {res.get('state')}", "data": res}


@tool(
    "slurm.cancel",
    "Cancel a Slurm job on the SSH backend (runs scancel).",
    {
        "type": "object",
        "properties": {"job_id": {"type": "string", "description": "Slurm job id"}},
        "required": ["job_id"],
    },
)
async def slurm_cancel(job_id: str, backend=None) -> dict:
    if backend is None or _backend_name(backend) != "ssh":
        return {"error": "Slurm requires the SSH backend."}
    res = await backend.slurm_cancel(shlex.quote(job_id))
    return {"summary": f"Cancelled Slurm job {job_id}", "data": res}