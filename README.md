# PDF to Audiobook

Turn any PDF into an MP3 audiobook in your browser. Upload, pick a narrator,
listen to a preview, and download the finished audiobook — everything runs
locally on your machine.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/flask-3.1-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

## Features

- **Drag & drop** PDF upload with a 4-step wizard UI (upload → voice → convert → download)
- **17 neural narrators** — 15 English voices + 2 Nepali voices, each with click-to-preview
- **Dual TTS engines**
  - *Online*: Microsoft Edge neural voices (HD quality) via `edge-tts`
  - *Offline*: automatic fallback to local Windows SAPI voices via `pyttsx3`
- **Smart text cleaning** — strips page numbers, headers/footers, URLs, emails,
  and copyright boilerplate before narration
- **Live progress** — chunk-by-chunk progress with time-remaining estimates
- **Accurate duration** — real MP3 length read from audio metadata (`mutagen`)
- **Resilient synthesis** — failed TTS chunks retry automatically (3× with backoff)
- **Rate limiting** and upload size caps built in

## Quick Start

### Prerequisites

- Python 3.10 or newer
- Internet connection for HD neural voices (optional — works offline with lower-quality local voices)

### Install & Run

```bash
git clone https://github.com/<your-username>/pdf-to-audiobook.git
cd pdf-to-audiobook

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

## Usage

1. **Upload** — drag a PDF onto the dropzone (max 50 MB)
2. **Choose a narrator** — click any voice card to hear a preview
3. **Convert** — watch live progress while your audiobook is synthesized
4. **Download** — grab the finished MP3; it's also saved to the `output/` folder

## Configuration

All settings are environment variables — sensible defaults, nothing required:

| Variable     | Default     | Description                                    |
|--------------|-------------|------------------------------------------------|
| `APP_DEBUG`  | `0`         | `1` enables Flask debug mode (dev only!)       |
| `APP_HOST`   | `127.0.0.1` | Bind address. Use `0.0.0.0` for LAN access    |
| `APP_PORT`   | `5000`      | Server port                                    |
| `APP_SECRET` | random      | Flask secret key                               |

Example — share on your local network:

```bash
APP_HOST=0.0.0.0 APP_PORT=8080 python app.py
```

## Voices

| Personality | Voice ID | Style |
|---|---|---|
| Luna | en-US-AvaNeural | Warm & Gentle |
| Marcus | en-US-AndrewNeural | Deep & Calm |
| Sophie | en-US-JennyNeural | Sweet & Playful |
| Oliver | en-US-BrianNeural | Wise & Gentle |
| Emma | en-GB-SoniaNeural | Elegant & Poised |
| Nova | en-US-AvaMultilingualNeural | Soft & Dreamy |
| Atlas | en-US-AndrewMultilingualNeural | Bold & Commanding |
| Ivy | en-US-EmmaNeural | Bright & Cheerful |
| Sage | en-US-ChristopherNeural | Smooth & Reassuring |
| Ruby | en-US-MichelleNeural | Rich & Expressive |
| Finn | en-US-EricNeural | Husky & Mysterious |
| Aria | en-US-AriaNeural | Clear & Professional |
| Rex | en-US-RogerNeural | Gravelly & Rugged |
| Dylan | en-US-GuyNeural | Velvety & Soothing |
| Frost | en-GB-ThomasNeural | Cool & British |
| Hemkala | ne-NP-HemkalaNeural | Nepali · Gentle & Soft |
| Sagar | ne-NP-SagarNeural | Nepali · Calm & Steady |

Offline mode maps these personalities to whatever Microsoft SAPI voices are
installed locally (usually David/Zira on Windows).

## How It Works

```
PDF ──▶ PyPDF2 text extraction ──▶ text cleaning ──▶ sentence-aware chunking
     ──▶ concurrent TTS per chunk ──▶ retry on failure ──▶ MP3 concatenation
     ──▶ single downloadable audiobook
```

Text is split into ≤4500-character chunks at sentence boundaries so long books
synthesize reliably, then chunk files are merged into one MP3.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Could not extract text from PDF" | The PDF is likely scanned images — OCR is not supported yet |
| Badge shows "Offline" | No internet detected; local SAPI voices will be used (quality varies) |
| Conversion fails mid-way | Check console logs — individual chunks retry 3× before giving up |
| Port already in use | Set `APP_PORT` to another value |

## Privacy

Your PDFs never leave your machine except for the text sent to Microsoft's
Edge TTS service when online mode is active. Uploaded files are auto-deleted;
generated audio lives only in your local `output/` folder.

## License

[MIT](LICENSE) © radheshyam
