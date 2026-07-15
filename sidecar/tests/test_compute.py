"""Tests for the compute management tools."""

import pytest

from sidecar.compute.local import LocalBackend
from sidecar.tools.compute import compute_run, slurm_cancel, slurm_status, slurm_submit  # noqa: F401
from sidecar.tools import compute as compute_mod


@pytest.mark.asyncio
async def test_compute_run_local():
    result = await compute_run(command="echo hello && echo err 1>&2", backend=LocalBackend(), timeout=10)
    assert result["data"]["exit_code"] == 0
    assert "hello" in result["data"]["stdout"]
    assert result["data"]["backend"] == "local"


@pytest.mark.asyncio
async def test_compute_run_no_backend():
    result = await compute_run(command="echo hi", backend=None)
    assert "error" in result


class _LocalNamedAsSSH:
    """A local backend mislabeled as 'ssh' so we can exercise Slurm paths without a cluster."""

    name = "ssh"

    def __init__(self):
        self._inner = LocalBackend()
        self.submitted = None

    async def run(self, command, timeout=3600, cwd=None, env=None):
        return await self._inner.run(command, timeout=timeout, cwd=cwd, env=env)

    async def submit_slurm(self, script):
        self.submitted = script
        return {"job_id": "12345", "stdout": "Submitted batch job 12345", "stderr": ""}

    async def slurm_status(self, job_id):
        return {"job_id": job_id, "state": "RUNNING"}

    async def slurm_cancel(self, job_id):
        return {"exit_code": 0}


@pytest.mark.asyncio
async def test_slurm_submit_requires_ssh():
    result = await compute_mod.slurm_submit(script="#!/bin/bash\nhostname", backend=LocalBackend())
    assert "requires the SSH backend" in result["error"]


@pytest.mark.asyncio
async def test_slurm_submit_on_ssh():
    backend = _LocalNamedAsSSH()
    result = await compute_mod.slurm_submit(script="#!/bin/bash\nhostname", backend=backend)
    assert result["data"]["job_id"] == "12345"
    assert backend.submitted is not None


@pytest.mark.asyncio
async def test_slurm_status_and_cancel():
    backend = _LocalNamedAsSSH()
    s = await compute_mod.slurm_status(job_id="12345", backend=backend)
    assert s["data"]["state"] == "RUNNING"
    c = await compute_mod.slurm_cancel(job_id="12345", backend=backend)
    assert c["data"]["exit_code"] == 0