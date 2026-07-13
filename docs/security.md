# Security

## Threat model

OpenScience is a local desktop application. The sidecar listens on `127.0.0.1`
only. The primary attack surface is other local processes or browser pages
attempting to interact with the sidecar.

## API key handling

- API keys are persisted in `~/.openscience/config.json` (gitignored).
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

## Path traversal protection

- Run IDs are validated against `^[a-f0-9]{12}$`.
- Output filenames are validated against `^[A-Za-z0-9][A-Za-z0-9._-]*$`.
- Paths are resolved and checked to be within the runs directory.

## Reporting vulnerabilities

See [SECURITY.md](../SECURITY.md).