import asyncio
import logging
import os
import time

import voyageai

logger = logging.getLogger(__name__)

_client = None
_query_client = None

# The rank path calls Voyage from a two-thread pool under a 2 s budget; the
# library default is a 600 s timeout, so one outage could pin both workers
# for half an hour while every /rank fell back to rules.
QUERY_TIMEOUT_SECS = 5.0


def _get_client() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    return _client


def _get_query_client() -> voyageai.Client:
    global _query_client
    if _query_client is None:
        _query_client = voyageai.Client(
            api_key=os.environ["VOYAGE_API_KEY"], max_retries=0, timeout=QUERY_TIMEOUT_SECS
        )
    return _query_client


def embed_query(text: str) -> list[float]:
    """One attempt, short timeout: for ranking, where failure means rules."""
    result = _get_query_client().embed([text], model="voyage-3", input_type="query")
    return result.embeddings[0]


def _embed_sync(text: str, input_type: str) -> list[float]:
    for attempt in range(3):
        try:
            result = _get_client().embed([text], model="voyage-3", input_type=input_type)
            return result.embeddings[0]
        except Exception as e:
            err = str(e)
            rate_limited = "rate" in err.lower() or "429" in err
            transient = any(
                code in err for code in ("500", "502", "503", "504", "timeout", "Timeout")
            )
            if attempt < 2 and (rate_limited or transient):
                delay = (20 if rate_limited else 5) * (attempt + 1)
                kind = "rate limited" if rate_limited else "transient error"
                logger.warning("Voyage %s, waiting %ds... (%s)", kind, delay, e)
                time.sleep(delay)
            else:
                raise


async def generate_embedding(text: str) -> list[float]:
    """Generate 1024-dim embedding using Voyage AI (MongoDB-provided)."""
    return await asyncio.to_thread(_embed_sync, text, "document")
