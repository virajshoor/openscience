#!/bin/bash
# Start both the Python sidecar and the Vite dev server.
# Usage: ./dev.sh

set -e
cd "$(dirname "$0")"

# Start sidecar
echo "Starting sidecar on port 7100..."
cd sidecar
OS_SIDECAR_PORT=7100 OS_RUNS_DIR="$HOME/.openscience/runs" uv run python -m sidecar.__main__ &
SIDECAR_PID=$!
cd ..

# Wait for sidecar to be ready
echo "Waiting for sidecar..."
for i in $(seq 1 15); do
  if curl -s http://127.0.0.1:7100/health | grep -q '"ok"'; then
    echo "Sidecar is up."
    break
  fi
  sleep 1
done

# Start Vite
echo "Starting UI on port 1420..."
pnpm dev &
VITE_PID=$!

# Cleanup on exit
trap "kill $SIDECAR_PID $VITE_PID 2>/dev/null; exit" INT TERM EXIT

echo ""
echo "=== OpenScience is running ==="
echo "  UI:       http://localhost:1420"
echo "  Sidecar:  http://127.0.0.1:7100"
echo "  Press Ctrl+C to stop both."
echo ""

wait