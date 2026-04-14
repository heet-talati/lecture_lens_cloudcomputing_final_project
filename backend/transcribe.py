"""
Azure Speech-to-Text transcription module.

Supports WAV (native) and compressed formats (MP3, M4A, etc.).
Uses continuous recognition so it handles files longer than ~60 seconds.
"""

import os
import threading
from typing import List

import azure.cognitiveservices.speech as speechsdk

AZURE_SPEECH_KEY    = os.environ.get('AZURE_SPEECH_KEY', '')
AZURE_SPEECH_REGION = os.environ.get('AZURE_SPEECH_REGION', '')


def transcribe_audio(file_path: str) -> str:
    """Transcribe an audio file using Azure Speech-to-Text.

    Args:
        file_path: Absolute path to the audio file.

    Returns:
        Full transcript as a single string (sentences joined by spaces).

    Raises:
        RuntimeError: If credentials are missing or the Azure service reports an error.
    """
    if not AZURE_SPEECH_KEY or not AZURE_SPEECH_REGION:
        raise RuntimeError('Azure Speech credentials are not configured.')

    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_SPEECH_KEY,
        region=AZURE_SPEECH_REGION,
    )
    speech_config.speech_recognition_language = 'en-US'

    ext = os.path.splitext(file_path)[1].lower()

    if ext != '.wav':
        raise RuntimeError(f'Unsupported audio format: {ext}')

    audio_config = speechsdk.audio.AudioConfig(filename=file_path)

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    results: List[str] = []
    errors: List[str] = []
    done = threading.Event()

    def on_recognized(evt):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            results.append(evt.result.text)

    def on_canceled(evt):
        if evt.result.reason == speechsdk.ResultReason.Canceled:
            details = evt.result.cancellation_details
            if details.reason == speechsdk.CancellationReason.Error:
                errors.append(details.error_details)
        done.set()

    def on_stopped(_evt):
        done.set()

    recognizer.recognized.connect(on_recognized)
    recognizer.session_stopped.connect(on_stopped)
    recognizer.canceled.connect(on_canceled)

    recognizer.start_continuous_recognition()
    done.wait(timeout=300)  # 5-minute ceiling
    recognizer.stop_continuous_recognition()

    if errors:
        raise RuntimeError(f'Speech recognition error: {errors[0]}')

    return ' '.join(results)
