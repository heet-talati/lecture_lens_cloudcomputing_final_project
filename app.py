import os
import tempfile
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables from .env file
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(ROOT_DIR, '.env'), override=True)

# Lazy-load Azure modules only when needed to avoid startup timeout
_transcribe_audio = None
_summarize_text = None
_check_content_safety = None
_ContentSafetyError = None

def _init_modules():
    """Lazy initialize backend modules on first use."""
    global _transcribe_audio, _summarize_text, _check_content_safety, _ContentSafetyError
    
    if _transcribe_audio is not None:
        return  # Already initialized
    
    try:
        from transcribe import transcribe_audio as ta
        from summarize import summarize_text as st
        from content_safety import check_content_safety as cs, ContentSafetyError as cse
        
        _transcribe_audio = ta
        _summarize_text = st
        _check_content_safety = cs
        _ContentSafetyError = cse
    except Exception as e:
        raise RuntimeError(f"Failed to load backend modules: {e}")

# Initialize Flask app and enable Cross-Origin Resource Sharing (CORS)
app = Flask(__name__)
CORS(app)

# Allowed audio file extensions for upload validation
ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.webm', '.ogg'}

# Maximum allowed file size (25 MB)
MAX_FILE_BYTES = 25 * 1024 * 1024


def save_temp_file(file_storage):
    """Save an uploaded FileStorage to a named temp file; return its path."""
    ext = os.path.splitext(file_storage.filename or '')[1].lower() or '.wav'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    file_storage.save(tmp.name)
    tmp.close()
    return tmp.name


# ── Health ────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/', methods=['GET'])
def root():
    return jsonify({'status': 'ok'})


# ── Transcribe ────────────────────────────────────────────────────────────────

@app.route('/transcribe', methods=['POST'])
def transcribe():
    try:
        _init_modules()
    except Exception as e:
        return jsonify({'error': f'Backend not ready: {e}'}), 503
    
    audio_file = request.files.get('audio') or request.files.get('file')
    if audio_file is None:
        return jsonify({'error': 'No audio file provided.'}), 400

    ext = os.path.splitext(audio_file.filename or '')[1].lower() or '.wav'
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'Unsupported audio format: {ext}'}), 400

    tmp_path = save_temp_file(audio_file)
    try:
        transcript = _transcribe_audio(tmp_path)
    except Exception as e:
        return jsonify({'error': f'Transcription failed: {e}'}), 500
    finally:
        os.unlink(tmp_path)

    try:
        _check_content_safety(transcript)
    except _ContentSafetyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        pass

    return jsonify({'transcript': transcript})


# ── Summarize ─────────────────────────────────────────────────────────────────

@app.route('/summarize', methods=['POST'])
def summarize():
    try:
        _init_modules()
    except Exception as e:
        return jsonify({'error': f'Backend not ready: {e}'}), 503
    
    data = request.get_json(silent=True)
    if not data or ('transcript' not in data and 'text' not in data):
        return jsonify({'error': 'Missing transcript in request body.'}), 400

    transcript = (data.get('transcript') or data.get('text') or '').strip()
    if not transcript:
        return jsonify({'error': 'Transcript is empty.'}), 400

    try:
        summary = _summarize_text(transcript)
    except Exception as e:
        return jsonify({'error': f'Summarization failed: {e}'}), 500

    try:
        _check_content_safety(summary)
    except _ContentSafetyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        pass

    return jsonify({'summary': summary})


# ── Process (combined) ────────────────────────────────────────────────────────

@app.route('/process', methods=['POST'])
def process():
    try:
        _init_modules()
    except Exception as e:
        return jsonify({'error': f'Backend not ready: {e}'}), 503
    
    audio_file = request.files.get('audio') or request.files.get('file')
    if audio_file is None:
        return jsonify({'error': 'No audio file provided.'}), 400

    ext = os.path.splitext(audio_file.filename or '')[1].lower() or '.wav'
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'Unsupported audio format: {ext}'}), 400

    tmp_path = save_temp_file(audio_file)
    try:
        transcript = _transcribe_audio(tmp_path)
    except Exception as e:
        return jsonify({'error': f'Transcription failed: {e}'}), 500
    finally:
        os.unlink(tmp_path)

    try:
        _check_content_safety(transcript)
    except _ContentSafetyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        pass

    try:
        summary = _summarize_text(transcript)
    except Exception as e:
        return jsonify({'error': f'Summarization failed: {e}'}), 500

    try:
        _check_content_safety(summary)
    except _ContentSafetyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        pass

    return jsonify({'transcript': transcript, 'summary': summary})


if __name__ == '__main__':
    app.run(debug=True)
