#!/usr/bin/env -S uv run python -m
"""Entry point for the sidecar. Run with: uv run python -m sidecar.server"""

import os

import uvicorn


def main():
    host = os.environ.get("OS_SIDECAR_HOST", "127.0.0.1")
    port = int(os.environ.get("OS_SIDECAR_PORT", "7100"))
    uvicorn.run(
        "sidecar.server:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()