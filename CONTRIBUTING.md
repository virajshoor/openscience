# Contributing to OpenScience

Thank you for your interest in contributing! OpenScience is an open-source scientific AI workbench licensed under AGPL-3.0.

## Getting Started

```bash
# Clone and install
git clone https://github.com/virajshoor/openscience.git
cd openscience
pnpm install
cd sidecar && uv sync && cd ..
```

## Development

```bash
# Run both sidecar and UI
pnpm dev:all

# Or run separately:
pnpm sidecar   # terminal 1
pnpm dev       # terminal 2 → http://localhost:1420

# Type-check
pnpm lint

# Frontend tests
pnpm test

# Sidecar tests
cd sidecar && uv run pytest

# Rust checks
cd src-tauri && cargo fmt --check && cargo clippy -- -D warnings
```

## Adding a Tool

Drop a file in `sidecar/sidecar/tools/`, decorate with `@tool`, and it auto-registers:

```python
from .registry import tool

@tool("my_tool.do_thing", "Does the thing", {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]})
async def do_thing(x: str) -> dict:
    return {"summary": f"Did thing to {x}."}
```

## Pull Request Checklist

- [ ] Code builds: `pnpm build` and `cd sidecar && uv run python -m compileall sidecar`
- [ ] Tests pass: `pnpm test` and `cd sidecar && uv run pytest`
- [ ] No secrets, API keys, or credentials in commits
- [ ] License is AGPL-3.0 — all contributions are under the same license