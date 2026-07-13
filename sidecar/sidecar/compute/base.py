"""Compute backend interface."""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class RunResult:
    exit_code: int
    stdout: str
    stderr: str


class ComputeBackend(abc.ABC):
    """A place where code/commands can be executed."""

    name: str = "base"

    @abc.abstractmethod
    async def run(self, command: str, timeout: int = 3600) -> RunResult:
        ...

    @abc.abstractmethod
    async def upload(self, local_path: str, remote_path: str) -> None:
        ...

    @abc.abstractmethod
    async def download(self, remote_path: str, local_path: str) -> None:
        ...

    def close(self) -> None:
        pass