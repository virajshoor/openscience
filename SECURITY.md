# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in OpenScience, please report it responsibly:

1. Do not open a public GitHub issue.
2. Email the maintainer directly or use GitHub's private vulnerability reporting.
3. Include a clear description of the issue, steps to reproduce, and potential impact.

We will acknowledge receipt within 48 hours and aim to provide a fix or mitigation within 7 days.

## Security Model

- API keys are stored locally and never committed to the repository or sent to third parties.
- The sidecar listens on `127.0.0.1` only. CORS is restricted to the app and dev origins.
- SSH connections use system known_hosts verification by default.
- Run manifests redact API keys before persistence.
- Tauri capabilities are limited to core APIs only.