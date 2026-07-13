"""HTTP client helpers using the macOS system trust store."""

import ssl
import httpx
import truststore


def async_client(timeout: float | httpx.Timeout) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=timeout,
        verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
    )
