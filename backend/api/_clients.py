"""Singleton clients for external services (GenAI, GCS)."""

import threading

_genai_client = None
_genai_lock = threading.Lock()

_gcs_client = None
_gcs_lock = threading.Lock()


def get_genai_client():
    global _genai_client
    if _genai_client is None:
        with _genai_lock:
            if _genai_client is None:
                from google import genai
                _genai_client = genai.Client(vertexai=True)
    return _genai_client


def get_gcs_client():
    global _gcs_client
    if _gcs_client is None:
        with _gcs_lock:
            if _gcs_client is None:
                from google.cloud import storage
                _gcs_client = storage.Client()
    return _gcs_client
