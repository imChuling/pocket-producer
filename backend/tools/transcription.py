import asyncio
import logging
import os

from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech

logger = logging.getLogger(__name__)

_client = None


def _get_speech_client() -> speech_v2.SpeechClient:
    global _client
    if _client is None:
        location = os.environ.get("SPEECH_LOCATION", "us-central1")
        _client = speech_v2.SpeechClient(
            client_options={"api_endpoint": f"{location}-speech.googleapis.com"},
        )
    return _client


_SYNC_MAX_BYTES = 10 * 1024 * 1024  # 10 MB — Google sync API limit


def _get_gcs_blob_size(gcs_uri: str) -> int | None:
    """Return blob size in bytes, or None if lookup fails."""
    try:
        from google.cloud import storage as gcs_storage
        parts = gcs_uri.replace("gs://", "").split("/", 1)
        bucket_name, blob_name = parts[0], parts[1]
        blob = gcs_storage.Client().bucket(bucket_name).get_blob(blob_name)
        return blob.size if blob else None
    except Exception:
        return None


def _transcribe_sync(audio_url: str, language_code: str) -> str:
    location = os.environ.get("SPEECH_LOCATION", "us-central1")
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    client = _get_speech_client()
    recognizer = f"projects/{project}/locations/{location}/recognizers/_"

    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=[language_code],
        model="chirp_2",
    )

    # Check file size — use fast sync API for ≤10MB, batch for larger
    blob_size = _get_gcs_blob_size(audio_url)
    use_batch = blob_size is not None and blob_size > _SYNC_MAX_BYTES

    if use_batch:
        logger.info("Using batch_recognize for %s (%s bytes)", audio_url, blob_size)
        file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=audio_url)
        request = cloud_speech.BatchRecognizeRequest(
            recognizer=recognizer,
            config=config,
            files=[file_metadata],
            recognition_output_config=cloud_speech.RecognitionOutputConfig(
                inline_response_config=cloud_speech.InlineOutputConfig(),
            ),
        )
        operation = client.batch_recognize(request=request)
        response = operation.result(timeout=180)

        parts: list[str] = []
        for file_result in response.results.values():
            for result in file_result.transcript.results:
                if result.alternatives:
                    parts.append(result.alternatives[0].transcript)
        return " ".join(parts).strip()

    # Fast synchronous path for files ≤10MB
    logger.info("Using sync recognize for %s (%s bytes)", audio_url, blob_size)
    try:
        request = cloud_speech.RecognizeRequest(
            recognizer=recognizer,
            config=config,
            uri=audio_url,
        )
        response = client.recognize(request=request)

        transcript = " ".join(
            result.alternatives[0].transcript
            for result in response.results
            if result.alternatives
        )
        return transcript.strip()
    except Exception as sync_err:
        # Sync API fails for audio >60s — fallback to batch
        logger.warning("Sync recognize failed (%s), falling back to batch", sync_err)
        file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=audio_url)
        request = cloud_speech.BatchRecognizeRequest(
            recognizer=recognizer,
            config=config,
            files=[file_metadata],
            recognition_output_config=cloud_speech.RecognitionOutputConfig(
                inline_response_config=cloud_speech.InlineOutputConfig(),
            ),
        )
        operation = client.batch_recognize(request=request)
        response = operation.result(timeout=180)

        parts: list[str] = []
        for file_result in response.results.values():
            for result in file_result.transcript.results:
                if result.alternatives:
                    parts.append(result.alternatives[0].transcript)
        return " ".join(parts).strip()


async def transcribe_audio(audio_url: str, language_code: str = "en-US") -> str:
    """Transcribe audio using Google Cloud Speech-to-Text v2 (Chirp 2)."""
    return await asyncio.to_thread(_transcribe_sync, audio_url, language_code)
