# Architecture

## Overview

OpenScience is a local desktop application built as a Tauri 2.0 shell wrapping a
React UI and a Python FastAPI sidecar. The three layers communicate over HTTP/SSE
on localhost.

```
┌─────────────────────────────────────────────────────┐
│  Tauri Shell (Rust)                                  │
│  • spawns/supervises the Python sidecar              │
│  • discovers an open port (7100-7105 or ephemeral)   │
│  • exposes sidecar_port via Tauri IPC                │
│  • restrictive CSP: no inline scripts, localhost only │
└──────────────┬──────────────────────────────────────┘
               │ HTTP + SSE (127.0.0.1)
┌──────────────▼──────────────────────────────────────┐
│  Python Sidecar (FastAPI, uv-managed)                │
│                                                      │
│  Endpoints:                                          │
│    GET  /health          liveness + tool count        │
│    GET  /tools           list registered tools        │
│    POST /chat            SSE streaming agentic loop   │
│    POST /review           automated reviewer          │
│    GET  /runs             list runs                   │
│    GET  /runs/{id}        read run detail              │
│    GET  /runs/{id}/outputs/{file}   download artifact │
│    GET  /config           read persisted config        │
│    POST /config           persist config               │
│    GET  /compute          list compute backends        │
│    POST /compute/ssh      configure SSH backend       │
│                                                      │
│  Internal components:                                 │
│    LLMClient      streaming, tool dispatch, ReAct     │
│    ToolRegistry    @tool decorator, OpenAI schema     │
│    Recorder        per-run manifest, conversation,    │
│                    SHA-256 prefixed outputs           │
│    Reviewer        second-pass fact-checker           │
│    ComputeBackend  local + SSH/Slurm                  │
└──────────────────────────────────────────────────────┘
               ▲
               │ fetch + EventSource
┌──────────────┴──────────────────────────────────────┐
│  React UI (Vite + TypeScript + Mantine)              │
│                                                      │
│  Layout: 3-zone sidebar + 2-pane workspace           │
│    Sidebar top:   brand, new conversation, runs label │
│    Sidebar runs:  scrollable run history             │
│    Sidebar bottom: Settings (always visible)         │
│    Pane 1: Chat (markdown, tool blocks, stop button) │
│    Pane 2: Viewer / Run Inspector                     │
│                                                      │
│  State: Zustand store (persisted to localStorage)    │
│    • config (endpoint, model, temperature, tools)    │
│    • messages (last 250, no tool payloads)            │
│    • computeBackend                                   │
│    API key stored in ~/.openscience/config.json       │
│    via sidecar, not in browser storage               │
└──────────────────────────────────────────────────────┘
```

## Request flow

1. User types a message in the chat panel.
2. UI builds conversation history from existing messages + new user message.
3. UI POSTs to `/chat` with `{ messages, config, compute }`.
4. Sidecar starts a Run (manifest, conversation.json, outputs/).
5. Sidecar sends the request to the OpenAI-compatible endpoint via SSE streaming.
6. As tokens arrive, sidecar forwards `token` events to the UI.
7. If the model requests a tool call:
   - Sidecar executes the tool (may write to outputs/).
   - Emits `tool_call`, `tool_result`, and optionally `viewer` events.
   - Feeds the result back to the model for the next turn.
8. When the model finishes (no more tool calls), sidecar emits `done`.
9. UI refreshes the run list.

## Config persistence

| Setting        | Browser localStorage | ~/.openscience/config.json | Run manifest |
|----------------|----------------------|----------------------------|--------------|
| base_url       | Yes                  | Yes                        | Yes          |
| api_key        | No                   | Yes                        | No (redacted) |
| model          | Yes                  | Yes                        | Yes          |
| temperature    | Yes                  | Yes                        | Yes          |
| use_tools      | Yes                  | Yes                        | Yes          |
| compute        | Yes                  | Yes                        | Yes          |

The API key persists across rebuilds and relaunches via the sidecar config file.
It is never stored in browser localStorage or committed to the repository.