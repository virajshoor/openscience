# Development

## Prerequisites

- [Node.js](https://nodejs.org) 20+
- [pnpm](https://pnpm.io) (`npm i -g pnpm`)
- [Rust](https://rustup.rs) stable
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Tauri 2 system deps — see https://tauri.app/start/prerequisites/
  - macOS: Xcode CLI tools (`xcode-select --install`)

## Setup

```bash
git clone https://github.com/virajshoor/openscience.git
cd openscience
pnpm install
cd sidecar && uv sync --extra dev && cd ..
```

## Running

### Full app (Tauri + sidecar)

```bash
pnpm tauri dev
```

### Sidecar + UI separately (fastest for development)

```bash
# Terminal 1
cd sidecar
OS_SIDECAR_PORT=7100 uv run python -m sidecar.__main__

# Terminal 2
pnpm dev
# → http://localhost:1420
```

### One-command launcher

```bash
pnpm dev:all
```

## Testing

```bash
# Frontend tests (Vitest)
pnpm test

# Sidecar tests (pytest)
cd sidecar && uv run pytest

# Rust tests
cd src-tauri && cargo test

# Type check
pnpm lint

# Python lint
cd sidecar && uv run ruff check .
```

## Building

```bash
# Frontend production build
pnpm build

# Tauri release bundle
pnpm tauri build
# → src-tauri/target/release/bundle/
```

## Project structure

```
openscience/
├── src/                      # React UI
│   ├── App.tsx               # Main layout + send/stop logic
│   ├── components/
│   │   ├── ChatPanel.tsx     # Chat with markdown + ArrowUp history
│   │   ├── ViewerPanel.tsx   # Routes to protein/genome/chem viewers
│   │   ├── RunInspector.tsx  # Manifest + conversation + review
│   │   ├── RunHistory.tsx    # Clickable run list (semantic buttons)
│   │   ├── SettingsModal.tsx # Accessible dialog (focus trap, Escape)
│   │   └── viewers/
│   │       ├── ProteinViewer.tsx   # NGL 3D
│   │       ├── GenomeViewer.tsx     # FASTA + GC tracks
│   │       └── ChemViewer.tsx       # RDKit-JS
│   ├── lib/
│   │   ├── api.ts            # Sidecar client + SSE stream + config
│   │   └── types.ts
│   ├── stores/session.ts     # Zustand (persisted config + messages)
│   ├── assets/               # Logo
│   └── styles.css
├── sidecar/                  # Python package
│   ├── sidecar/
│   │   ├── server.py         # FastAPI app
│   │   ├── llm/
│   │   │   ├── client.py     # Streaming + tool dispatch + ReAct
│   │   │   ├── react.py      # ReAct parser
│   │   │   └── reviewer.py   # Automated fact-checker
│   │   ├── tools/
│   │   │   ├── registry.py   # @tool decorator
│   │   │   ├── uniprot.py
│   │   │   ├── pdb.py
│   │   │   ├── entrez.py
│   │   │   └── chembl.py
│   │   ├── repro/
│   │   │   └── recorder.py   # Run persistence
│   │   └── compute/
│   │       ├── base.py
│   │       ├── local.py
│   │       └── ssh.py        # paramiko + Slurm
│   ├── tests/                # pytest tests
│   └── pyproject.toml
├── src-tauri/                # Rust shell
│   ├── src/
│   │   ├── main.rs
│   │   ├── lib.rs            # IPC commands
│   │   └── sidecar.rs        # Spawn/supervise sidecar
│   ├── capabilities/
│   │   └── default.json      # Core-only permissions
│   └── tauri.conf.json       # Restrictive CSP
├── docs/                     # Documentation
├── .github/
│   ├── workflows/ci.yml      # Lint, test, build
│   └── dependabot.yml
├── dev.sh                    # One-command launcher
├── package.json
└── README.md
```