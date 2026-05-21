import os

from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech


def transcribe_audio(audio_url: str, language_code: str = "en-US") -> str:
    """Transcribe audio using Google Cloud Speech-to-Text v2."""
    client = speech_v2.SpeechClient()

    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=[language_code],
        model="chirp_2",
    )

    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    request = cloud_speech.RecognizeRequest(
        recognizer=f"projects/{project}/locations/global/recognizers/_",
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
