"""Streamable-HTTP MCP client with one calling convention across mcp releases.

The agents open the MongoDB MCP server as
``streamable_http_client(url=..., auth=...)``. mcp 1.x spelled the function
``streamablehttp_client`` and takes ``auth``/``headers``/``timeout`` directly;
mcp 1.27 added ``streamable_http_client``, which takes a ready-made
``httpx.AsyncClient`` instead, and mcp 2.x keeps only that spelling. An
earlier shim preferred the new name whenever it existed and then passed
``auth=`` to it, which raised TypeError in production on 2026-11-10 and
failed every memory and producer agent run. This wrapper keeps the old
calling convention and adapts to whichever function the installed mcp has.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
from mcp.client import streamable_http as _impl

_legacy = getattr(_impl, "streamablehttp_client", None)
_modern = getattr(_impl, "streamable_http_client", None)

if _legacy is None and _modern is None:  # pragma: no cover - broken install
    raise ImportError("mcp.client.streamable_http exposes no streamable HTTP client")


@asynccontextmanager
async def streamable_http_client(
    url: str,
    *,
    auth: httpx.Auth | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    sse_read_timeout: float = 300.0,
) -> AsyncIterator[tuple]:
    """Yield ``(read_stream, write_stream, get_session_id)`` for ``url``."""
    if _legacy is not None:
        async with _legacy(
            url,
            headers=headers,
            timeout=timeout,
            sse_read_timeout=sse_read_timeout,
            auth=auth,
        ) as streams:
            yield streams
        return

    # mcp >= 2: the transport takes an httpx client that carries auth, headers
    # and timeouts. Mirror the legacy defaults (long read timeout for SSE).
    client = httpx.AsyncClient(
        auth=auth,
        headers=headers,
        timeout=httpx.Timeout(timeout, read=timedelta(seconds=sse_read_timeout).total_seconds()),
        follow_redirects=True,
    )
    try:
        async with _modern(url, http_client=client) as streams:
            yield streams
    finally:
        await client.aclose()


__all__ = ["streamable_http_client"]
