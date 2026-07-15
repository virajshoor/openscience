# Security

## Threat model

OpenScience is a local desktop application. The sidecar listens on `127.0.0.1`
only. The primary attack surface is other local processes or browser pages
attempting to interact with the sidecar.

## API key handling

- API keys are persisted in the macOS Keychain under the `ai.openscience.workbench` service.
- They are NOT stored in browser localStorage.
- They are redacted from run manifests before writing to disk.
- They are never committed to the repository.

## CORS

The sidecar restricts allowed origins to:
- `http://localhost:1420` (Vite dev server)
- `http://127.0.0.1:1420`
- `tauri://localhost` (Tauri production webview)

Override via the `OS_ALLOWED_ORIGINS` environment variable (comma-separated).

## Tauri security

- CSP is set to: `default-src 'self'; connect-src 'self' http://127.0.0.1:* http://localhost:*`
- Shell permissions are removed from capabilities (core-only).
- The `withGlobalTauri` flag is enabled for IPC but capabilities are scoped.

## SSH

- Uses `RejectPolicy` for host key verification by default.
- Does NOT auto-accept unknown host keys.
- Host keys must be present in `~/.ssh/known_hosts`.

## Code execution (`code.run`)

`code.run` executes arbitrary Python/R on the selected compute backend.

- This is a **trusted single-user desktop application**, not a multi-tenant
  service. User code runs under your own OS account on your own machine (or,
  over SSH, on a host you configured). There is **no OS-level sandbox**
  (no seccomp, no container) around executed code.
- A timeout is enforced via `asyncio.wait_for`; the matplotlib backend is
  forced to `Agg` so GUI backends cannot hang the process; outputs are scoped
  to a per-run `work/` directory under `~/.openscience/runs/<id>/`.
- Executed code can make network calls and read files your account can access.
  If you need isolation, run the sidecar inside a container or VM.
- The full source, stdout/stderr, and produced figures are recorded in the run
  for reproducibility and verified via content-addressed hashes.

## Path traversal protection

- Run IDs are validated against `^[a-f0-9]{12}$`.
- Output filenames are validated against `^[A-Za-z0-9][A-Za-z0-9._-]*$`.
- Paths are resolved and checked to be within the runs directory.

## Reporting vulnerabilities

See [SECURITY.md](../SECURITY.md).
