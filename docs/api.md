# API Reference

The sidecar exposes a REST + SSE API on `http://127.0.0.1:<port>`.

## Health

```
GET /health
```

Returns:
```json
{"ok": true, "tools": 25}
```

## Tools

```
GET /tools
```

Returns:
```json
{
  "tools": [
    {
      "name": "pdb.fetch",
      "description": "Fetch a PDB structure by 4-character ID...",
      "openai": {
        "type": "function",
        "function": {
          "name": "pdb.fetch",
          "description": "...",
          "parameters": {"type": "object", "properties": {...}, "required": [...]}
        }
      }
    }
  ]
}
```

## Chat (streaming)

```
POST /chat
Content-Type: application/json

{
  "messages": [{"role": "user", "content": "Show me 1CRN"}],
  "config": {
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-...",
    "model": "gpt-4o-mini",
    "temperature": 0.2,
    "use_tools": true
  },
  "compute": "local"
}
```

Response: `text/event-stream`

Each line: `data: {"event": "...", "data": ...}\n\n`

Events:
| Event | Data | Description |
|-------|------|-------------|
| `token` | `{"text": "..."}` | Streaming content token |
| `tool_call` | `{"id": "...", "name": "...", "arguments": {...}}` | Tool invoked |
| `tool_result` | `{"id": "...", "name": "...", "result": {...}}` | Tool result |
| `viewer` | `{"type": "protein", "src": "...", "label": "..."}` | Viewer artifact (one event per artifact; `code.run` emits several) |
| `error` | `{"message": "..."}` | Error occurred |
| `done` | `{"run_id": "..."}` | Run complete |

`compute` accepts `local`, `ssh`, or `slurm` (Slurm runs over the SSH transport).

## Review

```
POST /review
Content-Type: application/json

{"run_id": "abc123", "config": {...}}
```

Returns:
```json
{
  "verdict": "pass",
  "issues": [],
  "summary": "All claims verified."
}
```

## Runs

```
GET /runs
```

Returns:
```json
{
  "runs": [
    {"run_id": "abc123", "started_at": 1783940000, "model": "gpt-4o-mini", "review": null}
  ]
}
```

```
GET /runs/{run_id}
```

Returns:
```json
{
  "manifest": {...},
  "conversation": [...],
  "review": {...},
  "outputs": ["42199a30_1CRN.pdb"]
}
```

```
GET /runs/{run_id}/outputs/{filename}
```

Returns the raw file content (e.g. PDB file).

## Config

```
GET /config
```

Returns:
```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-...",
  "model": "gpt-4o-mini",
  "temperature": 0.2,
  "use_tools": true,
  "compute": "local"
}
```

```
POST /config
Content-Type: application/json

{"base_url": "http://localhost:11434/v1", "model": "llama3.1"}
```

When an `api_key` is supplied, OpenScience stores it in the macOS Keychain rather than in `config.json`.

```
DELETE /config
```

## Compute

```
GET /compute
```

Returns:
```json
{
  "backends": [
    {"name": "local", "type": "local"}
  ]
}
```

```
POST /compute/ssh
Content-Type: application/json

{"host": "lab-box.university.edu", "user": "me", "port": 22, "key_path": "~/.ssh/id_rsa"}
```

## Manuscript export

```
POST /manuscript/export
Content-Type: application/json

{"markdown": "# Title\n\nBody.", "bib": "@article{...}", "format": "markdown", "run_id": "abc123def456"}
```

`format` is `markdown`, `latex`, or `pdf`. The assembled manuscript (and
bibliography, when supplied) are saved to the run's `outputs/` for
reproducibility. LaTeX/PDF require `pandoc` on PATH (PDF also needs a LaTeX
engine such as `xelatex`); if absent, the endpoint falls back to Markdown with
a `warning`.

Returns:
```json
{"ok": true, "file": "9f8e..._manuscript.md", "format": "markdown", "download": "runs/abc123def456/outputs/9f8e..._manuscript.md"}
```

## Agents & skills (specialist agents / reusable skills)

```
GET /agents                       → {"agents": [{"name","system_prompt","tools"}]}
POST /agents                      {"name","system_prompt","tools": [..]|null}
DELETE /agents/{name}
GET /skills                       → {"skills": [{"name","prompt","tools"}]}
POST /skills                      {"name","prompt","tools": [..]|null}
DELETE /skills/{name}
```

`POST /chat` accepts optional `agent` (name) — injects the agent's system prompt
and restricts the tool set to `tools` (null = all) — and optional `skill` (name),
which prepends the skill's prompt as a system message.

## Session branching

```
POST /runs/{run_id}/fork
```

Creates a new run seeded with the parent's conversation and a `parent_run_id` in
its manifest. Returns `{"ok": true, "run_id": "...", "parent_run_id": "..."}`.

## Approval before spending compute

When `require_approval` is set in config (`POST /config`), `compute.run` and
`slurm.submit` return a draft plan with `approval_required: true` instead of
executing. Re-invoke with `approved: true` (after the user confirms) to execute.
