# TODO / Known Limitations

## P2 — Planned improvements

- [ ] **Security headers** — `add_security_headers` hook exists but sets nothing.
      Add CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy.
- [ ] **Stop leaking server paths** — `/api/extract` returns `save_dir` and
      `/api/convert` returns `save_path` (full filesystem paths). Return only
      relative names; render client-side instead.
- [ ] **Periodic connectivity check** — online/offline mode is decided once at
      startup. Re-check lazily per conversion (or on a timer) with graceful
      fallback to offline TTS mid-session.
- [ ] **Production WSGI server** — ship a waitress/gunicorn entrypoint instead
      of the Flask dev server, plus an optional Dockerfile.
- [ ] **Rate-limit storage** — flask-limiter uses in-memory storage; switch to
      Redis storage when running multiple workers.
- [ ] **MP3 concatenation quality** — chunks are joined by raw byte append.
      Re-encode/stitch via ffmpeg or pydub to avoid boundary glitches.
- [ ] **Offline Nepali voices** — SAPI voice names (`Microsoft Heera/Ravi
      Desktop`) are not present on most Windows installs; detect available
      voices dynamically instead of a static map.
- [ ] **Tests** — add pytest coverage for text cleaning, chunking, and API
      endpoints (mock TTS backends).
- [ ] **PDF engine** — PyPDF2 is deprecated/unmaintained; migrate to `pypdf`.

## Future ideas

- EPUB/TXT/DOCX input support
- Per-chapter audiobook files + ID3 chapter metadata
- Adjustable speech rate/pitch controls in the UI
- Streaming playback while later chapters are still converting
