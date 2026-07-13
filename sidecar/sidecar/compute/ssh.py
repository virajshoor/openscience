"""SSH compute backend with Slurm convenience wrappers.

Uses paramiko to execute commands on a remote host. Slurm jobs are submitted
via sbatch and polled via squeue — no special client library needed.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

from .base import ComputeBackend, RunResult


class SSHBackend(ComputeBackend):
    name = "ssh"

    def __init__(self, host: str, user: str, port: int = 22, key_path: Optional[str] = None) -> None:
        import paramiko  # local import so app boots even if paramiko not yet installed

        self.host = host
        self.user = user
        self.port = port
        self.key_path = key_path or os.path.expanduser("~/.ssh/id_rsa")
        self._client = paramiko.SSHClient()
        self._client.load_system_host_keys()
        self._client.set_missing_host_key_policy(paramiko.RejectPolicy())
        try:
            self._client.connect(host, port=port, username=user, key_filename=key_path, timeout=10)
        except Exception:
            # Lazy: will retry on first run
            self._client = None

    def _ensure(self):
        if self._client is None:
            import paramiko

            self._client = paramiko.SSHClient()
            self._client.load_system_host_keys()
            self._client.set_missing_host_key_policy(paramiko.RejectPolicy())
            self._client.connect(self.host, port=self.port, username=self.user, key_filename=self.key_path, timeout=10)

    async def run(self, command: str, timeout: int = 3600) -> RunResult:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_sync, command, timeout)

    def _run_sync(self, command: str, timeout: int) -> RunResult:
        self._ensure()
        stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        return RunResult(exit_code, stdout.read().decode(errors="replace"), stderr.read().decode(errors="replace"))

    async def submit_slurm(self, script: str) -> dict:
        """Submit a Slurm batch script. Returns job_id."""
        # Write script to a temp file on remote, then sbatch
        remote_path = f"/tmp/os_slurm_{int(time.time())}.sh"
        await self.run(f"cat > {remote_path} <<'EOF'\n{script}\nEOF")
        result = await self.run(f"sbatch {remote_path}")
        # sbatch prints "Submitted batch job 12345"
        job_id = None
        for tok in result.stdout.split():
            if tok.isdigit():
                job_id = tok
                break
        return {"job_id": job_id, "stdout": result.stdout, "stderr": result.stderr}

    async def slurm_status(self, job_id: str) -> dict:
        result = await self.run(f"squeue -j {job_id} --noheader -o '%T'")
        state = result.stdout.strip()
        return {"job_id": job_id, "state": state or "UNKNOWN"}

    async def slurm_cancel(self, job_id: str) -> dict:
        result = await self.run(f"scancel {job_id}")
        return {"exit_code": result.exit_code}

    async def upload(self, local_path: str, remote_path: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._upload_sync, local_path, remote_path)

    def _upload_sync(self, local_path: str, remote_path: str) -> None:
        self._ensure()
        sftp = self._client.open_sftp()
        try:
            sftp.put(local_path, remote_path)
        finally:
            sftp.close()

    async def download(self, remote_path: str, local_path: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._download_sync, remote_path, local_path)

    def _download_sync(self, remote_path: str, local_path: str) -> None:
        self._ensure()
        sftp = self._client.open_sftp()
        try:
            sftp.get(remote_path, local_path)
        finally:
            sftp.close()

    def close(self) -> None:
        if self._client:
            self._client.close()
