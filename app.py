import os
import re
import uuid
import math
import asyncio
import socket
import logging
import time
from flask import Flask, render_template, request, jsonify, send_file, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from PyPDF2 import PdfReader
import pyttsx3
import edge_tts

try:
    from mutagen.mp3 import MP3
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

# ─── Config ───────────────────────────────────────────────────────────────────
DEBUG = os.environ.get('APP_DEBUG', '0') == '1'
HOST = os.environ.get('APP_HOST', '127.0.0.1')
PORT = int(os.environ.get('APP_PORT', 5000))
SECRET_KEY = os.environ.get('APP_SECRET', uuid.uuid4().hex)

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['OUTPUT_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

CHAR_LIMIT = 4500

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('pdf2mp3')

# ─── Rate Limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(get_remote_address, app=app, default_limits=["30/minute"])
CONVERSION_PROGRESS = {}
MAX_PROGRESS_ENTRIES = 50


# ─── Helpers ──────────────────────────────────────────────────────────────────
def check_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False


ONLINE = check_internet()


def safe_filename(filename):
    """Prevent path traversal attacks."""
    basename = os.path.basename(filename)
    basename = re.sub(r'[^\w\-.]', '_', basename)
    return basename[:100]


def cleanup_progress():
    """Prevent memory leak from progress dict."""
    if len(CONVERSION_PROGRESS) > MAX_PROGRESS_ENTRIES:
        oldest_keys = sorted(CONVERSION_PROGRESS, key=lambda k: CONVERSION_PROGRESS[k].get('timestamp', 0))[:MAX_PROGRESS_ENTRIES // 2]
        for k in oldest_keys:
            CONVERSION_PROGRESS.pop(k, None)


def cleanup_old_files(directory, max_age_hours=1):
    """Delete files older than max_age_hours."""
    now = time.time()
    cutoff = now - (max_age_hours * 3600)
    try:
        for f in os.listdir(directory):
            fp = os.path.join(directory, f)
            if os.path.isfile(fp) and os.path.getmtime(fp) < cutoff:
                os.remove(fp)
                log.info(f"Cleaned up old file: {f}")
    except Exception as e:
        log.warning(f"Cleanup error: {e}")


# ─── Security Headers ─────────────────────────────────────────────────────────
@app.after_request
def add_security_headers(response):
    return response


# ─── Voice Definitions ────────────────────────────────────────────────────────
VOICE_MAP = {
    'en': [
        {'key': 'luna',   'id': 'en-US-AvaNeural',            'label': 'Luna',   'desc': 'Warm & Gentle'},
        {'key': 'marcus', 'id': 'en-US-AndrewNeural',          'label': 'Marcus', 'desc': 'Deep & Calm'},
        {'key': 'sophie', 'id': 'en-US-JennyNeural',           'label': 'Sophie', 'desc': 'Sweet & Playful'},
        {'key': 'oliver', 'id': 'en-US-BrianNeural',           'label': 'Oliver', 'desc': 'Wise & Gentle'},
        {'key': 'emma',   'id': 'en-GB-SoniaNeural',           'label': 'Emma',   'desc': 'Elegant & Poised'},
        {'key': 'nova',    'id': 'en-US-AvaMultilingualNeural', 'label': 'Nova',    'desc': 'Soft & Dreamy'},
        {'key': 'atlas',   'id': 'en-US-AndrewMultilingualNeural','label': 'Atlas',  'desc': 'Bold & Commanding'},
        {'key': 'ivy',     'id': 'en-US-EmmaNeural',            'label': 'Ivy',     'desc': 'Bright & Cheerful'},
        {'key': 'sage',    'id': 'en-US-ChristopherNeural',     'label': 'Sage',    'desc': 'Smooth & Reassuring'},
        {'key': 'ruby',    'id': 'en-US-MichelleNeural',        'label': 'Ruby',    'desc': 'Rich & Expressive'},
        {'key': 'finn',    'id': 'en-US-EricNeural',            'label': 'Finn',    'desc': 'Husky & Mysterious'},
        {'key': 'aria',    'id': 'en-US-AriaNeural',            'label': 'Aria',    'desc': 'Clear & Professional'},
        {'key': 'rex',     'id': 'en-US-RogerNeural',           'label': 'Rex',     'desc': 'Gravelly & Rugged'},
        {'key': 'dylan',   'id': 'en-US-GuyNeural',             'label': 'Dylan',   'desc': 'Velvety & Soothing'},
        {'key': 'frost',   'id': 'en-GB-ThomasNeural',          'label': 'Frost',   'desc': 'Cool & British'},
    ],
    'ne': [
        {'key': 'hemkala', 'id': 'ne-NP-HemkalaNeural', 'label': 'Hemkala', 'desc': 'Gentle & Soft'},
        {'key': 'sagar',   'id': 'ne-NP-SagarNeural',   'label': 'Sagar',   'desc': 'Calm & Steady'},
    ],
}

OFFLINE_VOICE_MAP = {
    'en': {
        'luna':    'Microsoft Zira Desktop',
        'marcus':  'Microsoft David Desktop',
        'sophie':  'Microsoft Zira Desktop',
        'oliver':  'Microsoft David Desktop',
        'emma':    'Microsoft Zira Desktop',
        'nova':    'Microsoft Zira Desktop',
        'atlas':   'Microsoft David Desktop',
        'ivy':     'Microsoft Zira Desktop',
        'sage':    'Microsoft David Desktop',
        'ruby':    'Microsoft Zira Desktop',
        'finn':    'Microsoft David Desktop',
        'aria':    'Microsoft Zira Desktop',
        'rex':     'Microsoft David Desktop',
        'dylan':   'Microsoft David Desktop',
        'frost':   'Microsoft Zira Desktop',
    },
    'ne': {
        'hemkala': 'Microsoft Heera Desktop',
        'sagar':   'Microsoft Ravi Desktop',
    },
}


# ─── Text Processing ──────────────────────────────────────────────────────────
def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return pages


def deep_clean(text):
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r'^\d{1,4}\s*$', stripped):
            continue
        if re.match(r'^(page|pg?\.?)\s*\d+', stripped, re.IGNORECASE):
            continue
        if re.match(r'^\d+\s*/\s*\d+$', stripped):
            continue
        if re.match(r'^(copyright|©|\(c\))\s', stripped, re.IGNORECASE):
            continue
        if re.match(r'^all\s+rights?\s+reserved', stripped, re.IGNORECASE):
            continue
        if re.match(r'^(www\.|http|\.com|\.org|\.net|\.edu)', stripped, re.IGNORECASE):
            continue
        if re.match(r'^\S+@\S+\.\S+', stripped):
            continue
        if re.match(r'^(draft|confidential|sample|preview|unlicensed)', stripped, re.IGNORECASE):
            continue
        if re.match(r'^printed\s+on', stripped, re.IGNORECASE):
            continue
        if re.match(r'^(table\s+of\s+contents|contents|index|appendix|chapter)\s*$', stripped, re.IGNORECASE):
            continue
        if re.match(r'^[\.\s]+$', stripped):
            continue
        if len(stripped) <= 2 and not stripped.isalpha():
            continue
        cleaned.append(stripped)
    return ' '.join(cleaned)


def clean_text(text):
    text = deep_clean(text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x00-\x7F\u0900-\u097F\u0A00-\u0A7F\u0980-\u09FF\u2000-\u206F]+', ' ', text)
    text = re.sub(r'\s+([,.!?;:])', r'\1', text)
    return text.strip()


def storyteller_transform(text):
    """Normalize punctuation and whitespace for smoother narration."""
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def split_text(text, max_chars=CHAR_LIMIT):
    chunks = []
    sentences = re.split(r'(?<=[.!?])\s+', text)
    current_chunk = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(current_chunk) + len(sentence) + 5 <= max_chars:
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            if len(sentence) > max_chars:
                words = sentence.split()
                current_chunk = ""
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= max_chars:
                        current_chunk += (" " if current_chunk else "") + word
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = word
            else:
                current_chunk = sentence
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def generate_offline(text, voice_key, lang, output_path):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    sapi_name = OFFLINE_VOICE_MAP.get(lang, OFFLINE_VOICE_MAP['en']).get(voice_key, 'Microsoft Zira Desktop')
    for v in voices:
        if sapi_name.lower() in v.name.lower():
            engine.setProperty('voice', v.id)
            break
    engine.setProperty('rate', 150)
    engine.setProperty('volume', 1.0)
    engine.save_to_file(text, output_path)
    engine.runAndWait()


async def tts_chunks(chunks, voice_id, output_paths, progress_key):
    """Run TTS chunks concurrently in a single event loop, updating
    CONVERSION_PROGRESS as each chunk completes."""
    total = len(chunks)
    done = 0
    start_time = time.time()
    tasks = [asyncio.ensure_future(_generate_chunk(chunk, voice_id, outpath))
             for chunk, outpath in zip(chunks, output_paths)]
    for fut in asyncio.as_completed(tasks):
        await fut  # raises if a chunk failed after all retries
        done += 1
        elapsed = time.time() - start_time
        avg_time = elapsed / done
        remaining = avg_time * (total - done)
        cleanup_progress()
        CONVERSION_PROGRESS[progress_key] = {
            'current': done, 'total': total,
            'elapsed': round(elapsed, 1), 'remaining': round(remaining, 1),
            'status': 'converting', 'timestamp': time.time()
        }


async def _generate_chunk(text, voice_id, output_path, max_retries=3):
    """Synthesize one chunk with retry + exponential backoff."""
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            communicate = edge_tts.Communicate(text, voice_id, rate="+0%")
            await communicate.save(output_path)
            return
        except Exception as e:
            last_err = e
            log.warning(f"TTS chunk attempt {attempt}/{max_retries} failed: {e}")
            await asyncio.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"TTS chunk failed after {max_retries} attempts: {last_err}")


def get_audio_duration(path, file_size):
    """Read real audio duration via mutagen; fall back to a bitrate estimate."""
    if HAS_MUTAGEN:
        try:
            return MP3(path).info.length
        except Exception as e:
            log.warning(f"mutagen duration read failed, estimating: {e}")
    bitrate = 48000 if ONLINE else 128000
    return (file_size * 8) / bitrate


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
@limiter.exempt
def api_status():
    return jsonify({'online': ONLINE, 'mode': 'Online (Edge TTS HD)' if ONLINE else 'Offline (Local TTS)'})


@app.route('/api/voices')
@limiter.exempt
def voices():
    return jsonify({
        'voices': {lang: vlist for lang, vlist in VOICE_MAP.items()},
        'online': ONLINE
    })


@app.route('/api/preview', methods=['POST'])
@limiter.limit("10/minute")
def preview_voice():
    data = request.get_json()
    lang = data.get('language', 'en')
    voice_key = data.get('voice', 'luna')

    preview_text = "Hi, would you like me to read this for you?"
    preview_id = uuid.uuid4().hex[:12]
    preview_path = os.path.join(app.config['OUTPUT_FOLDER'], f"_preview_{preview_id}.mp3")

    try:
        if ONLINE:
            voice_list = VOICE_MAP.get(lang, VOICE_MAP['en'])
            voice_info = next((v for v in voice_list if v['key'] == voice_key), voice_list[0])
            communicate = edge_tts.Communicate(preview_text, voice_info['id'], rate="+10%")
            asyncio.run(communicate.save(preview_path))
        else:
            generate_offline(preview_text, voice_key, lang, preview_path)

        with open(preview_path, 'rb') as f:
            audio_data = f.read()
        if os.path.exists(preview_path):
            os.remove(preview_path)

        return Response(audio_data, mimetype='audio/mpeg', headers={'Content-Disposition': 'inline; filename=preview.mp3'})
    except Exception as e:
        log.error(f"Preview error: {e}")
        if os.path.exists(preview_path):
            os.remove(preview_path)
        return jsonify({'error': str(e)}), 500


@app.route('/api/extract', methods=['POST'])
@limiter.limit("10/minute")
def extract():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['pdf']
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Please upload a valid PDF file'}), 400

    filename = f"{uuid.uuid4().hex}.pdf"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        pages = extract_text_from_pdf(filepath)
        if not pages:
            return jsonify({'error': 'Could not extract text from PDF'}), 400
        full_text = clean_text(' '.join(pages))
        word_count = len(full_text.split())
        estimated_minutes = math.ceil(word_count / 120)

        log.info(f"Extracted {word_count} words from {len(pages)} pages")
        return jsonify({
            'filename': filename,
            'original_name': file.filename,
            'text_preview': full_text[:500] + ('...' if len(full_text) > 500 else ''),
            'word_count': word_count,
            'page_count': len(pages),
            'estimated_minutes': estimated_minutes,
            'save_dir': app.config['OUTPUT_FOLDER']
        })
    except Exception as e:
        log.error(f"Extract error: {e}")
        return jsonify({'error': f'Error reading PDF: {str(e)}'}), 500


@app.route('/api/convert', methods=['POST'])
@limiter.limit("3/minute")
def convert():
    data = request.get_json()
    if not data or 'filename' not in data:
        return jsonify({'error': 'No filename provided'}), 400

    filename = safe_filename(data['filename'])
    language = data.get('language', 'en')
    voice_key = data.get('voice', 'luna')

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'PDF file not found'}), 404

    chunk_paths = []
    try:
        pages = extract_text_from_pdf(filepath)
        full_text = clean_text(' '.join(pages))
        full_text = storyteller_transform(full_text)
        chunks = split_text(full_text)
        total_chunks = len(chunks)

        if ONLINE:
            voice_list = VOICE_MAP.get(language, VOICE_MAP['en'])
            voice_info = next((v for v in voice_list if v['key'] == voice_key), voice_list[0])
        else:
            voice_info = {'label': voice_key.title()}

        start_time = time.time()
        log.info(f"Converting {filename}: {total_chunks} chunks, voice={voice_info['label']}")

        if ONLINE:
            chunk_paths = [os.path.join(app.config['OUTPUT_FOLDER'], f"{filename}_{i}.mp3") for i in range(total_chunks)]
            asyncio.run(tts_chunks(chunks, voice_info['id'], chunk_paths, filename))
        else:
            chunk_paths = []
            for i, chunk in enumerate(chunks):
                chunk_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{filename}_{i}.mp3")
                generate_offline(chunk, voice_key, language, chunk_path)
                chunk_paths.append(chunk_path)

                elapsed = time.time() - start_time
                done = i + 1
                avg_time = elapsed / done
                remaining = avg_time * (total_chunks - done)
                cleanup_progress()
                CONVERSION_PROGRESS[filename] = {
                    'current': done, 'total': total_chunks,
                    'elapsed': round(elapsed, 1), 'remaining': round(remaining, 1),
                    'status': 'converting', 'timestamp': time.time()
                }

        if not chunk_paths:
            return jsonify({'error': 'No audio generated'}), 500

        safe_name = safe_filename(os.path.splitext(data.get('original_name', 'audiobook'))[0])
        output_name = f"{safe_name}_audiobook.mp3"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_name)

        with open(output_path, 'wb') as outf:
            for cp in chunk_paths:
                with open(cp, 'rb') as inf:
                    outf.write(inf.read())

        for cp in chunk_paths:
            if os.path.exists(cp):
                os.remove(cp)

        total_elapsed = time.time() - start_time
        CONVERSION_PROGRESS[filename] = {
            'current': total_chunks, 'total': total_chunks,
            'elapsed': round(total_elapsed, 1), 'remaining': 0,
            'status': 'done', 'timestamp': time.time()
        }

        file_size = os.path.getsize(output_path)
        duration_seconds = get_audio_duration(output_path, file_size)
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = int(duration_seconds % 60)
        duration_str = f"{hours}h {minutes}m {seconds}s" if hours > 0 else f"{minutes}m {seconds}s"

        log.info(f"Done: {output_name} ({file_size/1024/1024:.1f}MB, {duration_str}) in {total_elapsed:.1f}s")
        return jsonify({
            'success': True,
            'output_name': output_name,
            'duration': duration_str,
            'duration_seconds': duration_seconds,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'voice_used': voice_info['label'],
            'mode': 'Online (Edge TTS HD)' if ONLINE else 'Offline (Local TTS)',
            'save_path': output_path
        })
    except Exception as e:
        log.error(f"Convert error: {e}")
        for cp in chunk_paths:
            if os.path.exists(cp):
                os.remove(cp)
        return jsonify({'error': f'Conversion error: {str(e)}'}), 500


@app.route('/api/progress/<filename>')
@limiter.exempt
def conversion_progress(filename):
    safe = safe_filename(filename)
    prog = CONVERSION_PROGRESS.get(safe, {
        'current': 0, 'total': 0, 'elapsed': 0, 'remaining': 0, 'status': 'starting'
    })
    return jsonify(prog)


@app.route('/api/download/<filename>')
@limiter.exempt
def download(filename):
    safe = safe_filename(filename)
    filepath = os.path.join(app.config['OUTPUT_FOLDER'], safe)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    return send_file(filepath, as_attachment=True, download_name=safe)


@app.route('/api/cleanup', methods=['POST'])
@limiter.limit("5/minute")
def cleanup():
    data = request.get_json()
    filename = data.get('filename')
    if filename:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename(filename))
        if os.path.exists(filepath):
            os.remove(filepath)
    return jsonify({'success': True})


# ─── Startup Cleanup ──────────────────────────────────────────────────────────
with app.app_context():
    cleanup_old_files(app.config['UPLOAD_FOLDER'], max_age_hours=2)
    cleanup_old_files(app.config['OUTPUT_FOLDER'], max_age_hours=2)


if __name__ == '__main__':
    log.info(f"Mode: {'ONLINE (Edge TTS HD)' if ONLINE else 'OFFLINE (Local TTS)'}")
    log.info(f"Local:   http://127.0.0.1:{PORT}")
    app.run(debug=DEBUG, host=HOST, port=PORT)
