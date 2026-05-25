import asyncio
import os

import voyageai

_client = None


def _get_client() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    return _client


def _embed_sync(text: str, input_type: str) -> list[float]:
    result = _get_client().embed([text], model="voyage-3", input_type=input_type)
    return result.embeddings[0]


async def generate_embedding(text: str) -> list[float]:
    """Generate 1024-dim embedding using Voyage AI (MongoDB-provided)."""
    return await asyncio.to_thread(_embed_sync, text, "document")


async def generate_query_embedding(query: str) -> list[float]:
    """Same model but with input_type='query' for search."""
    return await asyncio.to_thread(_embed_sync, query, "query")
