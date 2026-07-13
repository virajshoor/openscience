#!/bin/bash
# Cross-platform launcher. Prefer `pnpm dev:all` on every platform.
exec node "$(dirname "$0")/scripts/dev.mjs"
