"""
Azure OpenAI summarization module.

Sends a lecture transcript to GPT and returns a structured markdown summary
with an overview, topic headings (##), and bullet points (-).
"""

import os
import json
from urllib import error, request

AZURE_OPENAI_KEY        = os.environ.get('AZURE_OPENAI_KEY', '')
AZURE_OPENAI_ENDPOINT   = os.environ.get('AZURE_OPENAI_ENDPOINT', '')
AZURE_OPENAI_DEPLOYMENT = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o-mini')
AZURE_OPENAI_API_VERSION = os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-01')

_SYSTEM_PROMPT = (
    'You are an academic note-taking assistant. '
    'Given a lecture transcript, produce a structured summary with:\n'
    '- A brief overview (2–3 sentences)\n'
    '- Key topics as ## headings\n'
    '- The main points under each heading as bullet points (- )\n\n'
    'Be concise and factual. Preserve technical terms exactly as spoken.'
)


def summarize_text(transcript: str) -> str:
    """Summarize a lecture transcript using Azure OpenAI.

    Args:
        transcript: Raw transcript string.

    Returns:
        Structured markdown-style summary string.

    Raises:
        RuntimeError: If credentials are missing or the API call fails.
    """
    if not AZURE_OPENAI_KEY or not AZURE_OPENAI_ENDPOINT:
        raise RuntimeError('Azure OpenAI credentials are not configured.')

    endpoint = AZURE_OPENAI_ENDPOINT.rstrip('/')
    url = (
        f'{endpoint}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}'
        f'/chat/completions?api-version={AZURE_OPENAI_API_VERSION}'
    )

    payload = {
        'messages': [
            {'role': 'system', 'content': _SYSTEM_PROMPT},
            {'role': 'user', 'content': f'Transcript:\n\n{transcript}'},
        ],
        'temperature': 0.3,
        'max_tokens': 1024,
    }

    req = request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'api-key': AZURE_OPENAI_KEY,
        },
        method='POST',
    )

    try:
        with request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode('utf-8'))
    except error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        if exc.code == 404 and 'DeploymentNotFound' in body:
            raise RuntimeError(
                'Azure OpenAI deployment not found. Set AZURE_OPENAI_DEPLOYMENT to the exact deployment name in your Azure OpenAI resource.'
            ) from exc
        raise RuntimeError(f'Azure OpenAI request failed: HTTP {exc.code} {body}') from exc
    except Exception as exc:
        raise RuntimeError(f'Azure OpenAI request failed: {exc}') from exc

    try:
        return data['choices'][0]['message']['content'].strip()
    except (KeyError, IndexError, AttributeError) as exc:
        raise RuntimeError(f'Unexpected Azure OpenAI response: {data}') from exc
