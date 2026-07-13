# API Reference

The sidecar exposes a REST + SSE API on `http://127.0.0.1:<port>`.

## Health

```
GET /health
```

Returns:
```json
{"ok": true, "tools": 7}
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
| `viewer` | `{"type": "protein", "src": "...", "label": "..."}` | Viewer artifact |
| `error` | `{"message": "..."}` | Error occurred |
| `done` | `{"run_id": "..."}` | Run complete |

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