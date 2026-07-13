# Reproducibility

Every chat exchange is captured into an append-only Run directory:

```
~/.openscience/runs/<run_id>/
├── manifest.json      # model, params, pip freeze, git hash, host, config (no api_key)
├── conversation.json   # every message, tool call, tool result
├── outputs/            # artifacts — SHA-256 prefixed filenames
│   └── a1b2c3d4_1CRN.pdb
└── review.json        # automated reviewer verdict (written last)
```

## Manifest

```json
{
  "run_id": "a1b2c3d4e5f6",
  "started_at": 1783940000.0,
  "finished_at": 1783940005.0,
  "host": "laptop.local",
  "python": "3.12.9",
  "platform": "macOS-15.0-arm64",
  "git_commit": "abc1234",
  "config": {
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "temperature": 0.2,
    "use_tools": true
  },
  "env": ["fastapi==0.115.0", "httpx==0.27.0", "..."]
}
```

API keys are redacted from the manifest before it is written.

## Outputs

Tool-produced artifacts (PDB files, FASTA sequences, etc.) are written to
`outputs/` with an 8-character SHA-256 prefix to detect tampering:

```
42199a30_1CRN.pdb
```

The viewer event references this exact filename so the UI can download it.

For backward compatibility, requests for the original (un-prefixed) filename
are resolved to the single matching hash-prefixed file if exactly one exists.

## Automated reviewer

A second LLM pass (no tools) walks the conversation and verifies every numeric
claim and citation against tool outputs.

Verdicts:
- `pass` — everything traces to a tool result
- `flag` — some claims unverified
- `fail` — claims contradicted by tool results
- `error` — reviewer could not run

Trigger via the Run Inspector "Run reviewer" button or:

```
POST /review
{ "run_id": "abc123", "config": { ... } }
```

## Verify outputs

Use **Verify outputs** in the Run Inspector to recompute SHA-256 prefixes for every saved artifact. A run passes when every output filename prefix matches its current file content. The same check is available at `GET /runs/{run_id}/verify`.

## Run restoration

Clicking a past run in the sidebar loads its conversation into the chat pane,
restoring user messages, assistant responses, and tool call summaries.
