"""The MCP client wrapper must accept the agents' calling convention on the
installed mcp release, whichever function name that release exposes.

Regression for 2026-11-10: the shim preferred ``streamable_http_client`` and
forwarded ``auth=`` to it, which that function does not take.
"""

import asyncio
import inspect

import httpx

from agents import _mcp_client


class _FakeTransport:
    """Stands in for either mcp function: records how it was called."""

    calls: list[dict] = []

    def __init__(self, url, **kwargs):
        _FakeTransport.calls.append({"url": url, **kwargs})

    async def __aenter__(self):
        return ("read", "write", lambda: "sid")

    async def __aexit__(self, *exc):
        return False


def _open(auth):
    async def run():
        async with _mcp_client.streamable_http_client(url="http://x/mcp", auth=auth) as streams:
            return streams

    return asyncio.run(run())


def test_wrapper_accepts_auth_headers_and_timeout():
    params = inspect.signature(_mcp_client.streamable_http_client).parameters
    assert {"url", "auth", "headers", "timeout"} <= set(params)


def test_installed_mcp_exposes_a_usable_function():
    assert _mcp_client._legacy is not None or _mcp_client._modern is not None


def test_legacy_function_receives_auth_directly(monkeypatch):
    _FakeTransport.calls = []
    monkeypatch.setattr(_mcp_client, "_legacy", _FakeTransport)
    monkeypatch.setattr(_mcp_client, "_modern", None)
    auth = httpx.BasicAuth("u", "p")

    read, write, get_sid = _open(auth)

    assert (read, write, get_sid()) == ("read", "write", "sid")
    assert _FakeTransport.calls[0]["url"] == "http://x/mcp"
    assert _FakeTransport.calls[0]["auth"] is auth


def test_modern_function_gets_an_httpx_client_carrying_auth(monkeypatch):
    _FakeTransport.calls = []
    monkeypatch.setattr(_mcp_client, "_legacy", None)
    monkeypatch.setattr(_mcp_client, "_modern", _FakeTransport)
    auth = httpx.BasicAuth("u", "p")

    _open(auth)

    client = _FakeTransport.calls[0]["http_client"]
    assert isinstance(client, httpx.AsyncClient)
    assert client.auth is auth
    assert client.is_closed
