import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, '.env'), override=True)

from transcribe import transcribe_audio
from summarize import summarize_text
from content_safety import check_content_safety, ContentSafetyError

app = Flask(__name__)
CORS(app)

ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.webm', '.ogg'}
MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB


def save_temp_file(file_storage):
    """Save an uploaded FileStorage to a named temp file; return its path."""
    ext = os.path.splitext(file_storage.filename)[1].lower() or '.wav'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    file_storage.save(tmp.name)
    tmp.close()
    return tmp.name


# ── Health ────────────────────────────────────────────────────────────────────

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


# ── Transcribe ────────────────────────────────────────────────────────────────

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided.'}), 400

    audio_file = request.files['audio']

    ext = os.path.splitext(audio_file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'Unsupported audio format: {ext}'}), 400

    tmp_path = save_temp_file(audio_file)
    try:
        transcript = transcribe_audio(tmp_path)
    except Exception as e:
        return jsonify({'error': f'Transcription failed: {e}'}), 500
    finally:
        os.unlink(tmp_path)

    try:
        check_content_safety(transcript)
    except ContentSafetyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        pass  # Content Safety is best-effort; don't block on service errors

    return jsonify({'transcript': transcript})


# ── Summarize ─────────────────────────────────────────────────────────────────

@app.route('/summarize', methods=['POST'])
def summarize():
    data = request.get_json(silent=True)
    if not data or 'transcript' not in data:
        return jsonify({'error': 'Missing transcript in request body.'}), 400

    transcript = data['transcript'].strip()
    if not transcript:
        return jsonify({'error': 'Transcript is empty.'}), 400

    try:
        summary = summarize_text(transcript)
    except Exception as e:
        return jsonify({'error': f'Summarization failed: {e}'}), 500

    try:
        check_content_safety(summary)
    except ContentSafetyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        pass

    return jsonify({'summary': summary})


# ── Process (combined) ────────────────────────────────────────────────────────

@app.route('/process', methods=['POST'])
def process():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided.'}), 400

    audio_file = request.files['audio']

    ext = os.path.splitext(audio_file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f'Unsupported audio format: {ext}'}), 400

    tmp_path = save_temp_file(audio_file)
    try:
        transcript = transcribe_audio(tmp_path)
    except Exception as e:
        return jsonify({'error': f'Transcription failed: {e}'}), 500
    finally:
        os.unlink(tmp_path)

    try:
        check_content_safety(transcript)
    except ContentSafetyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        pass

    try:
        summary = summarize_text(transcript)
    except Exception as e:
        return jsonify({'error': f'Summarization failed: {e}'}), 500

    try:
        check_content_safety(summary)
    except ContentSafetyError as e:
        return jsonify({'error': str(e)}), 400
    except Exception:
        pass

    return jsonify({'transcript': transcript, 'summary': summary})


if __name__ == '__main__':
    app.run(debug=True)
