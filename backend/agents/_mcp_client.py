"""Streamable-HTTP MCP client under one name across mcp releases.

mcp 1.x exported `streamablehttp_client`; newer releases renamed it to
`streamable_http_client` and dropped the old alias, which raised ImportError
in production on 2026-10-24. Import the new name first, fall back to the old.
"""

try:
    from mcp.client.streamable_http import streamable_http_client
except ImportError:  # mcp < 1.? only had the old spelling
    from mcp.client.streamable_http import streamablehttp_client as streamable_http_client

__all__ = ["streamable_http_client"]
