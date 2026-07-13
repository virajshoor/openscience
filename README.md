# OpenScience

An open-source scientific AI workbench. An open alternative to proprietary
research assistants: connects to scientific databases, renders 3D protein
structures / genome tracks / chemical structures, orchestrates compute across
local + SSH + Slurm, and tracks every result for reproducibility.

Works with **any OpenAI-compatible endpoint** — bring your own model: OpenAI,
Ollama, vLLM, Together, Groq, OpenRouter, Azure OpenAI, local Llama, etc.

Licensed under **AGPL-3.0**.

> **Platform support:** OpenScience currently supports **macOS on Apple Silicon (M1 or later)** only. Windows, Linux, and Intel Mac releases are not available yet.

![OpenScience UI with 3D protein viewer](preview.png)

---

## Architecture (v0.1)

```
┌──────────────────────────────────────────────────────────────┐
│ Tauri shell (Rust)                                            │
│  • spawns/manages Python sidecar on app launch                │
│  • window + IPC bridge                                        │
└──────────┬───────────────────────────────────────────────────┘
           │ HTTP/SSE on localhost
┌──────────▼───────────────────────────────────────────────────┐
│ Python sidecar (FastAPI, uv-managed)                          │
│  • /chat       streaming agentic loop with tool dispatch      │
│  • /tools      list registered scientific tools               │
│  • /runs       list + read reproducibility runs               │
│  • /review     automated reviewer (fact-check pass)          │
│  • /compute    list + configure compute backends             │
│                                                               │
│  LLM client      OpenAI-compatible; ReAct fallback           │
│  Tools           UniProt, PDB, NCBI Entrez, ChEMBL            │
│  Compute         Local + SSH (paramiko) + Slurm wrappers      │
│  Recorder        per-run manifest + conversation + outputs   │
└───────────────────────────────────────────────────────────────┘
           ▲
           │ fetch + SSE
┌──────────┴───────────────────────────────────────────────────┐
│ React UI (Vite + TypeScript + Mantine)                        │
│  • 3-pane: Conversation | Viewer / Run Inspector              │
│  • Sidebar: New conversation + run history + Settings         │
│  • Viewers: NGL (protein), FASTA/GC (genome), RDKit (chem)    │
│  • Settings: endpoint URL, API key, model, tool toggle, SSH   │
└───────────────────────────────────────────────────────────────┘
```

### Reproducibility — the "Run"

Every chat exchange is captured into an append-only Run:

```
~/.openscience/runs/<run_id>/
├── manifest.json     # model, params, pip freeze, git hash, host
├── conversation.json # every user msg, assistant msg, tool call+result
├── outputs/          # artifacts (PDB files, FASTA, etc.) — SHA-256 prefixed
└── review.json       # automated reviewer verdict (written last)
```

Anyone on a team can verify a result by reading the Run and re-executing
the recorded tool calls.

### Automated reviewer

A second LLM pass (no tools) walks the conversation and verifies every
numeric claim and citation against tool outputs. Verdicts:
`pass` (everything traces), `flag` (some claims unverified), `fail`
(claims contradicted). Stored in `review.json`.

---

## Quick start

### Install the macOS app

Download the Apple Silicon DMG or `.app` ZIP from the [GitHub release](https://github.com/virajshoor/openscience/releases/tag/v0.1.0). Drag OpenScience into Applications and open it. The release contains its own sidecar, so it does not require Python or `uv`.

The current release is unsigned. On first launch, control-click OpenScience and choose **Open** if macOS displays a Gatekeeper warning.

### Prerequisites

- macOS 14+ on Apple Silicon (M1 or later)
- [Node.js](https://nodejs.org) 20+
- [pnpm](https://pnpm.io) (`npm i -g pnpm`)
- [Rust](https://rustup.rs) stable
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Xcode CLI tools (`xcode-select --install`)

### Install

```bash
# from repo root
pnpm install              # JS deps
cd sidecar && uv sync && cd ..   # Python deps
```

### Run the full app (Tauri + sidecar together)

```bash
pnpm tauri dev
```

The Tauri shell launches the Vite dev server, spawns the Python sidecar,
and waits for it to report healthy before showing the window. Sidecar
logs go to your terminal; UI logs to the browser devtools.

### Run pieces individually (recommended for first test)

You can run the sidecar standalone to verify the backend, then point the
UI at it. This is the fastest way to test without a full Tauri build:

```bash
# Terminal 1 — start the sidecar
cd sidecar
OS_SIDECAR_PORT=7100 OS_RUNS_DIR=~/.openscience/runs uv run python -m sidecar.__main__
```

```bash
# Terminal 2 — quick sanity check
curl http://127.0.0.1:7100/health
# {"ok":true,"tools":7}

curl http://127.0.0.1:7100/tools | python -m json.tool
```

```bash
# Terminal 2 — run the UI in dev mode (Vite, opens in browser)
pnpm dev
# → http://localhost:1420
```

The UI talks to the sidecar over HTTP at `http://127.0.0.1:7100`. Configure
your model endpoint in the Settings modal (gear icon in the sidebar):

| Field             | Example                                                          |
|-------------------|------------------------------------------------------------------|
| Endpoint          | `https://api.openai.com/v1` (or `http://localhost:11434/v1` for Ollama) |
| API key           | `sk-...` (any non-empty string for local providers)              |
| Model             | `gpt-5.4-mini` (or `llama3.1`, `qwen2.5`, etc.)                  |
| Use tool-calling  | ✓ for OpenAI/Together/Groq; ✗ for some Ollama models (auto ReAct) |

### Configuration and security

Endpoint, model, and tool preferences are stored in `~/.openscience/config.json`.
Your API key is stored separately in the macOS Keychain and is not committed,
included in run manifests, or written to browser localStorage.

### Try it

In the chat box, type things like:

- `Fetch UniProt P12345 and find any PDB structures for it`
- `Show me the 3D structure of 1CRN` (loads NGL protein viewer)
- `Look up aspirin on ChEMBL and render it` (loads RDKit 2D viewer)
- `Search NCBI for BRCA1 human and fetch the first hit as FASTA` (genome viewer)

Each exchange creates a Run. Click a run in the sidebar to open the
Run Inspector, then click **Run reviewer** to fact-check it.

---

## Project layout

```
openscience/
├── src/                          # React UI
│   ├── App.tsx                   # 3-pane layout + sidebar
│   ├── components/
│   │   ├── ChatPanel.tsx
│   │   ├── ViewerPanel.tsx        # routes to protein/genome/chem viewer
│   │   ├── RunInspector.tsx       # manifest + conversation + review
│   │   ├── RunHistory.tsx
│   │   ├── SettingsModal.tsx      # endpoint + SSH config
│   │   └── viewers/
│   │       ├── ProteinViewer.tsx  # NGL
│   │       ├── GenomeViewer.tsx   # FASTA + GC tracks (v0.2: igv.js)
│   │       └── ChemViewer.tsx     # RDKit-JS from CDN
│   ├── lib/
│   │   ├── api.ts                 # sidecar client + SSE stream
│   │   └── types.ts
│   └── stores/session.ts         # zustand (persisted config)
├── sidecar/                       # Python package
│   ├── sidecar/
│   │   ├── server.py              # FastAPI app
│   │   ├── llm/
│   │   │   ├── client.py           # streaming + tool dispatch
│   │   │   ├── react.py            # ReAct text-loop fallback
│   │   │   └── reviewer.py        # automated fact-checker
│   │   ├── tools/
│   │   │   ├── registry.py        # @tool decorator
│   │   │   ├── uniprot.py
│   │   │   ├── pdb.py
│   │   │   ├── entrez.py
│   │   │   └── chembl.py
│   │   ├── repro/
│   │   │   └── recorder.py        # Run persistence
│   │   └── compute/
│   │       ├── base.py
│   │       ├── local.py
│   │       └── ssh.py             # paramiko + sbatch/squeue
│   └── pyproject.toml
├── src-tauri/                     # Rust shell
│   ├── src/
│   │   ├── main.rs
│   │   ├── lib.rs                 # app entry + IPC commands
│   │   └── sidecar.rs             # spawn/supervise Python process
│   └── tauri.conf.json
└── package.json
```

---

## Adding tools

A tool is just an async function with a JSON schema. Drop a file in
`sidecar/sidecar/tools/`, decorate with `@tool`, and it auto-registers:

```python
from .registry import tool

@tool(
    "my_tool.do_thing",
    "Does the thing to X.",
    {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
)
async def do_thing(x: str, recorder=None, run_id=None) -> dict:
    return {"summary": f"Did thing to {x}.", "data": {"x": x}}
```

If you return a `viewer` field, the UI renders it:

```python
return {
    "summary": "...",
    "viewer": {"type": "protein", "src": "runs/<id>/outputs/foo.pdb", "label": "Foo"},
}
```

Viewer types: `protein` (NGL), `genome` (FASTA), `chem` (RDKit, SMILES).

---

## Build a release binary

```bash
pnpm tauri build
# → bundle in src-tauri/target/release/bundle/
```

---

## Roadmap

v0.1 (this release):
- ✓ OpenAI-compatible chat with streaming + tool dispatch
- ✓ ReAct text-loop fallback for providers without tool-calling
- ✓ 4 DB connectors: UniProt, PDB, NCBI Entrez, ChEMBL
- ✓ 3 viewers: NGL protein, FASTA+GC genome, RDKit chemistry
- ✓ Local + SSH/Slurm compute backends
- ✓ Reproducibility recorder with manifest + conversation + outputs
- ✓ Automated reviewer

v0.2 (planned):
- Plugin system (DBs + viewers as drop-in modules)
- Full igv.js genome browser
- More databases (AlphaFold DB, Ensembl, STRING, KEGG)
- Jupyter kernel backend for arbitrary code execution
- Multi-run diffing

---

## License

AGPL-3.0-only. See [LICENSE](./LICENSE).
