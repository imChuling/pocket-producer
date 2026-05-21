import os

import voyageai

_client = None


def _get_client() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
    return _client


def generate_embedding(text: str) -> list[float]:
    """Generate 1024-dim embedding using Voyage AI (MongoDB-provided)."""
    result = _get_client().embed([text], model="voyage-3", input_type="document")
    return result.embeddings[0]


def generate_query_embedding(query: str) -> list[float]:
    """Same model but with input_type='query' for search."""
    result = _get_client().embed([query], model="voyage-3", input_type="query")
    return result.embeddings[0]
