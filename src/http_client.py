"""Shared HTTP client builder with corporate-CA support.

On networks that do SSL inspection (Cisco Secure Access, Zscaler, Netskope),
Python's bundled CA list does not include the corporate root, so direct HTTPS
calls fail with CERTIFICATE_VERIFY_FAILED. truststore makes Python use the
system keychain, which already trusts the corporate CA. Harmless on networks
without inspection.
"""
from __future__ import annotations

import httpx


def build_http_client(timeout_s: float = 120.0) -> httpx.Client:
    try:
        import ssl
        import truststore

        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        return httpx.Client(verify=ctx, timeout=httpx.Timeout(timeout_s))
    except ImportError:
        return httpx.Client(timeout=httpx.Timeout(timeout_s))
