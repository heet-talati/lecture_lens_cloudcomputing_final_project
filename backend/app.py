import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Determine root directory and load environment variables from .env file
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, '.env'), override=True)

# Lazy-load Azure modules after startup so health probes can pass quickly.
_transcribe_audio = None
_summarize_text = None
_check_content_safety = None
_content_safety_error = None


def _init_backend_modules():
    global _transcribe_audio, _summarize_text, _check_content_safety, _content_safety_error
    if _transcribe_audio is not None:
        return

    from transcribe import transcribe_audio as ta
    from summarize import summarize_text as st
    from content_safety import check_content_safety as cs, ContentSafetyError as cse

    _transcribe_audio = ta
    _summarize_text = st
    _check_content_safety = cs
    _content_safety_error = cse

# Initialize Flask app and enable Cross-Origin Resource Sharing (CORS)
app = Flask(__name__)
CORS(app)

# Allowed audio file extensions for upload validation
ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.webm', '.ogg'}

# Maximum allowed file size (25 MB) — currently defined but not enforced
MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB


def save_temp_file(file_storage):
    """Save an uploaded FileStorage to a named temp file; return its path."""
    # Extract file extension or default to .wav if missing
    ext = os.path.splitext(file_storage.filename)[1].lower() or '.wav'
    
    # Create a temporary file with the same extension
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    
    # Save uploaded file contents to the temp file
    file_storage.save(tmp.name)
    tmp.close()
    
    # Return path to the temporary file
    return tmp.name


# ── Health ────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    # Simple health check endpoint to verify server is running
    return jsonify({'status': 'ok'})


@app.route('/', methods=['GET'])
def root():
    # App Service warmup probes commonly hit '/'.
    return jsonify({'status': 'ok'})


# ── Transcribe ────────────────────────────────────────────────────────────────

@app.route('/transcribe', methods=['POST'])
def transcribe():
    try:
        _init_backend_modules()
    except Exception as e:
        return jsonify({'error': f'Backend initialization failed: {e}'}), 503

    # Ensure an audio file is included in the request
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided.'}), 400

    audio_file = request.files['audio']

    # Validate file extension
    ext = os.path.splitext(audio_file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'Unsupported audio format: {ext}'}), 400

    # Save uploaded file to temporary storage
    tmp_path = save_temp_file(audio_file)
    try:
        # Perform transcription using external module
        transcript = _transcribe_audio(tmp_path)
    except Exception as e:
        return jsonify({'error': f'Transcription failed: {e}'}), 500
    finally:
        # Always clean up temp file after processing
        os.unlink(tmp_path)

    try:
        # Run content safety check on transcript
        _check_content_safety(transcript)
    except _content_safety_error as e:
        # Block response if unsafe content is detected
        return jsonify({'error': str(e)}), 400
    except Exception:
        # Ignore safety service failures (best-effort approach)
        pass

    # Return transcription result
    return jsonify({'transcript': transcript})


# ── Summarize ─────────────────────────────────────────────────────────────────

@app.route('/summarize', methods=['POST'])
def summarize():
    try:
        _init_backend_modules()
    except Exception as e:
        return jsonify({'error': f'Backend initialization failed: {e}'}), 503

    # Parse JSON request body safely
    data = request.get_json(silent=True)
    
    # Validate that transcript exists in request body
    if not data or 'transcript' not in data:
        return jsonify({'error': 'Missing transcript in request body.'}), 400

    # Clean and validate transcript content
    transcript = data['transcript'].strip()
    if not transcript:
        return jsonify({'error': 'Transcript is empty.'}), 400

    try:
        # Generate summary from transcript
        summary = _summarize_text(transcript)
    except Exception as e:
        return jsonify({'error': f'Summarization failed: {e}'}), 500

    try:
        # Run content safety check on summary
        _check_content_safety(summary)
    except _content_safety_error as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        # Ignore safety service failures
        pass

    # Return summarized result
    return jsonify({'summary': summary})


# ── Process (combined) ────────────────────────────────────────────────────────

@app.route('/process', methods=['POST'])
def process():
    try:
        _init_backend_modules()
    except Exception as e:
        return jsonify({'error': f'Backend initialization failed: {e}'}), 503

    # Ensure an audio file is included
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided.'}), 400

    audio_file = request.files['audio']

    # Validate file extension
    ext = os.path.splitext(audio_file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'Unsupported audio format: {ext}'}), 400

    # Save file temporarily
    tmp_path = save_temp_file(audio_file)
    try:
        # Step 1: Transcribe audio
        transcript = _transcribe_audio(tmp_path)
    except Exception as e:
        return jsonify({'error': f'Transcription failed: {e}'}), 500
    finally:
        # Clean up temp file
        os.unlink(tmp_path)

    try:
        # Safety check on transcript
        _check_content_safety(transcript)
    except _content_safety_error as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        pass

    try:
        # Step 2: Summarize transcript
        summary = _summarize_text(transcript)
    except Exception as e:
        return jsonify({'error': f'Summarization failed: {e}'}), 500

    try:
        # Safety check on summary
        _check_content_safety(summary)
    except _content_safety_error as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        pass

    # Return both transcript and summary
    return jsonify({'transcript': transcript, 'summary': summary})


if __name__ == '__main__':
    # Run Flask app in debug mode (auto-reload + detailed errors)
    app.run(debug=True)
