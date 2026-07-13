"""Reproducibility recorder.

A Run is an append-only directory under runs_dir/<run_id>/ containing:
  - manifest.json    : env, config, start time, host
  - conversation.json: every message, tool call, tool result
  - outputs/         : artifacts written by tools, hash-named
  - review.json      : automated reviewer verdict (written last)

All writes are content-addressed (SHA-256) so a Run can be verified later.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any


def _git_hash() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=2)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _pip_freeze() -> list[str]:
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip().splitlines() if r.returncode == 0 else []
    except Exception:
        return []


class Recorder:
    def __init__(self, runs_dir: str) -> None:
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def start(self, config: dict) -> str:
        run_id = uuid.uuid4().hex[:12]
        run_dir = self.runs_dir / run_id
        (run_dir / "outputs").mkdir(parents=True, exist_ok=True)
        safe_config = {key: value for key, value in config.items() if key not in {"api_key", "apiKey"}}
        manifest = {
            "run_id": run_id,
            "started_at": time.time(),
            "host": platform.node(),
            "python": sys.version,
            "platform": platform.platform(),
            "git_commit": _git_hash(),
            "config": safe_config,
            "env": _pip_freeze(),
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        (run_dir / "conversation.json").write_text("[]")
        return run_id

    def append(self, run_id: str, role: str, payload: Any) -> None:
        run_dir = self.runs_dir / run_id
        conv_path = run_dir / "conversation.json"
        conv = json.loads(conv_path.read_text()) if conv_path.exists() else []
        conv.append({"role": role, "ts": time.time(), **({"message": payload} if role != "tool" else {"tool": payload.get("tool"), "result": payload.get("result")})})
        # Simpler: store unified
        conv[-1] = {"role": role, "ts": time.time(), "payload": payload}
        conv_path.write_text(json.dumps(conv, default=str, indent=2))

    def write_output(self, run_id: str, filename: str, data: bytes) -> str:
        run_dir = self.runs_dir / run_id / "outputs"
        run_dir.mkdir(parents=True, exist_ok=True)
        # Prepend hash to detect tampering
        digest = hashlib.sha256(data).hexdigest()[:8]
        name = f"{digest}_{Path(filename).name}"
        (run_dir / name).write_bytes(data)
        return name

    def write_review(self, run_id: str, review: dict) -> None:
        run_dir = self.runs_dir / run_id
        (run_dir / "review.json").write_text(json.dumps(review, default=str, indent=2))

    def finish(self, run_id: str) -> None:
        run_dir = self.runs_dir / run_id
        manifest_path = run_dir / "manifest.json"
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text())
            m["finished_at"] = time.time()
            manifest_path.write_text(json.dumps(m, indent=2))

    def list_runs(self) -> list[dict]:
        out = []
        if not self.runs_dir.exists():
            return out
        for d in self.runs_dir.iterdir():
            if not d.is_dir():
                continue
            mp = d / "manifest.json"
            if not mp.exists():
                continue
            try:
                m = json.loads(mp.read_text())
            except json.JSONDecodeError:
                continue
            rp = d / "review.json"
            review_verdict = None
            if rp.exists():
                try:
                    review_verdict = json.loads(rp.read_text()).get("verdict")
                except json.JSONDecodeError:
                    pass
            out.append({
                "run_id": d.name,
                "started_at": m.get("started_at"),
                "model": m.get("config", {}).get("model"),
                "review": review_verdict,
            })
        out.sort(key=lambda r: r.get("started_at") or 0, reverse=True)
        return out

    def read_run(self, run_id: str) -> dict | None:
        run_dir = self.runs_dir / run_id
        if not run_dir.exists():
            return None
        out = {}
        mp = run_dir / "manifest.json"
        if mp.exists():
            out["manifest"] = json.loads(mp.read_text())
        cp = run_dir / "conversation.json"
        if cp.exists():
            out["conversation"] = json.loads(cp.read_text())
        rp = run_dir / "review.json"
        if rp.exists():
            out["review"] = json.loads(rp.read_text())
        # List outputs
        op = run_dir / "outputs"
        if op.exists():
            out["outputs"] = [f.name for f in op.iterdir() if f.is_file()]
        return out

    def verify_run(self, run_id: str) -> dict:
        """Verify that content-addressed output filenames match their bytes."""
        outputs_dir = self.runs_dir / run_id / "outputs"
        if not outputs_dir.is_dir():
            return {"ok": False, "error": "run outputs not found", "outputs": []}
        outputs = []
        for path in sorted(outputs_dir.iterdir()):
            if not path.is_file():
                continue
            expected, separator, _ = path.name.partition("_")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
            outputs.append({"name": path.name, "valid": bool(separator) and expected == actual})
        return {"ok": all(output["valid"] for output in outputs), "outputs": outputs}
