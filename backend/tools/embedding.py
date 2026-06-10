import asyncio
import logging
import os
import time

import voyageai

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    return _client


def _embed_sync(text: str, input_type: str) -> list[float]:
    for attempt in range(3):
        try:
            result = _get_client().embed([text], model="voyage-3", input_type=input_type)
            return result.embeddings[0]
        except Exception as e:
            if attempt < 2 and ("rate" in str(e).lower() or "429" in str(e)):
                delay = 20 * (attempt + 1)
                logger.warning("Voyage rate limited, waiting %ds... (%s)", delay, e)
                time.sleep(delay)
            else:
                raise


async def generate_embedding(text: str) -> list[float]:
    """Generate 1024-dim embedding using Voyage AI (MongoDB-provided)."""
    return await asyncio.to_thread(_embed_sync, text, "document")


async def generate_query_embedding(query: str) -> list[float]:
    """Same model but with input_type='query' for search."""
    return await asyncio.to_thread(_embed_sync, query, "query")
