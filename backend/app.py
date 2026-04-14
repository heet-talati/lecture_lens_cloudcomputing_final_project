import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Determine root directory and load environment variables from .env file
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, '.env'), override=True)

# Import core functionality for transcription, summarization, and safety checks
try:
    from .transcribe import transcribe_audio
    from .summarize import summarize_text
    from .content_safety import check_content_safety, ContentSafetyError
except ImportError:
    from transcribe import transcribe_audio
    from summarize import summarize_text
    from content_safety import check_content_safety, ContentSafetyError

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

def health_response():
    return jsonify({'status': 'ok'})


@app.route('/health', methods=['GET'])
def health():
    # Simple health check endpoint to verify server is running
    return health_response()


@app.route('/', methods=['GET'])
def root():
    # Azure health probes sometimes target the app root.
    return health_response()


# ── Transcribe ────────────────────────────────────────────────────────────────

@app.route('/transcribe', methods=['POST'])
def transcribe():
    # Accept both "audio" and common test key "file".
    audio_file = request.files.get('audio') or request.files.get('file')
    
    # Ensure an audio file is included in the request
    if audio_file is None:
        return jsonify({'error': 'No audio file provided.'}), 400

    # Validate file extension
    ext = os.path.splitext(audio_file.filename or '')[1].lower() or '.wav'
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'Unsupported audio format: {ext}'}), 400

    # Save uploaded file to temporary storage
    tmp_path = save_temp_file(audio_file)
    try:
        # Perform transcription using external module
        transcript = transcribe_audio(tmp_path)
    except Exception as e:
        return jsonify({'error': f'Transcription failed: {e}'}), 500
    finally:
        # Always clean up temp file after processing
        os.unlink(tmp_path)

    try:
        # Run content safety check on transcript
        check_content_safety(transcript)
    except ContentSafetyError as e:
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
    # Parse JSON request body safely
    data = request.get_json(silent=True)
    
    # Accept both "transcript" and common test key "text".
    if not data or ('transcript' not in data and 'text' not in data):
        return jsonify({'error': 'Missing transcript in request body.'}), 400

    # Clean and validate transcript content
    transcript = (data.get('transcript') or data.get('text') or '').strip()
    if not transcript:
        return jsonify({'error': 'Transcript is empty.'}), 400

    try:
        # Generate summary from transcript
        summary = summarize_text(transcript)
    except Exception as e:
        return jsonify({'error': f'Summarization failed: {e}'}), 500

    try:
        # Run content safety check on summary
        check_content_safety(summary)
    except ContentSafetyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        # Ignore safety service failures
        pass

    # Return summarized result
    return jsonify({'summary': summary})


# ── Process (combined) ────────────────────────────────────────────────────────

@app.route('/process', methods=['POST'])
def process():
    # Accept both "audio" and common test key "file".
    audio_file = request.files.get('audio') or request.files.get('file')

    # Ensure an audio file is included
    if audio_file is None:
        return jsonify({'error': 'No audio file provided.'}), 400

    # Validate file extension
    ext = os.path.splitext(audio_file.filename or '')[1].lower() or '.wav'
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'Unsupported audio format: {ext}'}), 400

    # Save file temporarily
    tmp_path = save_temp_file(audio_file)
    try:
        # Step 1: Transcribe audio
        transcript = transcribe_audio(tmp_path)
    except Exception as e:
        return jsonify({'error': f'Transcription failed: {e}'}), 500
    finally:
        # Clean up temp file
        os.unlink(tmp_path)

    try:
        # Safety check on transcript
        check_content_safety(transcript)
    except ContentSafetyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        pass

    try:
        # Step 2: Summarize transcript
        summary = summarize_text(transcript)
    except Exception as e:
        return jsonify({'error': f'Summarization failed: {e}'}), 500

    try:
        # Safety check on summary
        check_content_safety(summary)
    except ContentSafetyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        pass

    # Return both transcript and summary
    return jsonify({'transcript': transcript, 'summary': summary})


if __name__ == '__main__':
    # Run Flask app in debug mode (auto-reload + detailed errors)
    app.run(debug=True)
