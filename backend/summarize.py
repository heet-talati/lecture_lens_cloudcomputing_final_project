"""
Azure OpenAI summarization module.

Sends a lecture transcript to GPT and returns a structured markdown summary
with an overview, topic headings (##), and bullet points (-).
"""

import os
import json
from urllib import error, request

# Load Azure OpenAI credentials and configuration from environment variables
AZURE_OPENAI_KEY        = os.environ.get('AZURE_OPENAI_KEY', '')
AZURE_OPENAI_ENDPOINT   = os.environ.get('AZURE_OPENAI_ENDPOINT', '')
AZURE_OPENAI_DEPLOYMENT = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o-mini')
AZURE_OPENAI_API_VERSION = os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-01')

# System prompt that defines how the model should structure the summary output
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

    # Validate that required Azure credentials are set
    if not AZURE_OPENAI_KEY or not AZURE_OPENAI_ENDPOINT:
        raise RuntimeError('Azure OpenAI credentials are not configured.')

    # Normalize endpoint URL (remove trailing slash if present)
    endpoint = AZURE_OPENAI_ENDPOINT.rstrip('/')

    # Construct Azure OpenAI chat completions endpoint URL
    url = (
        f'{endpoint}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}'
        f'/chat/completions?api-version={AZURE_OPENAI_API_VERSION}'
    )

    # Define request payload including system + user messages and generation parameters
    payload = {
        'messages': [
            {'role': 'system', 'content': _SYSTEM_PROMPT},  # Instruction to model
            {'role': 'user', 'content': f'Transcript:\n\n{transcript}'},  # Input transcript
        ],
        'temperature': 0.3,  # Low temperature for more deterministic output
        'max_tokens': 1024,  # Limit response length
    }

    # Create HTTP request with JSON payload and required headers
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
        # Send request to Azure OpenAI and parse JSON response
        with request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode('utf-8'))

    except error.HTTPError as exc:
        # Handle HTTP-specific errors (e.g., bad deployment name)
        body = exc.read().decode('utf-8', errors='replace')

        # Special case: deployment not found (common misconfiguration)
        if exc.code == 404 and 'DeploymentNotFound' in body:
            raise RuntimeError(
                'Azure OpenAI deployment not found. Set AZURE_OPENAI_DEPLOYMENT to the exact deployment name in your Azure OpenAI resource.'
            ) from exc

        # General HTTP error handling
        raise RuntimeError(f'Azure OpenAI request failed: HTTP {exc.code} {body}') from exc

    except Exception as exc:
        # Catch-all for network/timeouts/other unexpected failures
        raise RuntimeError(f'Azure OpenAI request failed: {exc}') from exc

    try:
        # Extract and return the generated summary text from response
        return data['choices'][0]['message']['content'].strip()

    except (KeyError, IndexError, AttributeError) as exc:
        # Handle unexpected response structure
        raise RuntimeError(f'Unexpected Azure OpenAI response: {data}') from exc
