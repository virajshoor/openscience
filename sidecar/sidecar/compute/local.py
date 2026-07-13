"""Local compute backend. Runs commands via asyncio subprocess."""

from __future__ import annotations

import asyncio
import shutil

from .base import ComputeBackend, RunResult


class LocalBackend(ComputeBackend):
    name = "local"

    async def run(self, command: str, timeout: int = 3600) -> RunResult:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return RunResult(-1, "", "timeout")
        return RunResult(proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace"))

    async def upload(self, local_path: str, remote_path: str) -> None:
        if local_path != remote_path:
            shutil.copy(local_path, remote_path)

    async def download(self, remote_path: str, local_path: str) -> None:
        if remote_path != local_path:
            shutil.copy(remote_path, local_path)