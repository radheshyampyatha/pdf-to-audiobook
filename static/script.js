const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const uploadStep = document.getElementById('uploadStep');
const previewStep = document.getElementById('previewStep');
const convertingStep = document.getElementById('convertingStep');
const doneStep = document.getElementById('doneStep');
const removeFileBtn = document.getElementById('removeFile');
const convertBtn = document.getElementById('convertBtn');
const downloadBtn = document.getElementById('downloadBtn');
const startOverBtn = document.getElementById('startOver');
const langRow = document.getElementById('langRow');
const voiceGrid = document.getElementById('voiceGrid');
const statusBadge = document.getElementById('statusBadge');
const statusText = document.getElementById('statusText');

let currentFile = null;
let selectedLang = 'en';
let selectedVoice = 'luna';
let currentAudio = null;

// ─── Voice Data (15 English + 2 Nepali) ───
const VOICES = {
    en: [
        { key: 'luna',   name: 'Luna',   desc: 'Warm & Gentle' },
        { key: 'marcus', name: 'Marcus', desc: 'Deep & Calm' },
        { key: 'sophie', name: 'Sophie', desc: 'Sweet & Playful' },
        { key: 'oliver', name: 'Oliver', desc: 'Wise & Gentle' },
        { key: 'emma',   name: 'Emma',   desc: 'Elegant & Poised' },
        { key: 'nova',   name: 'Nova',   desc: 'Soft & Dreamy' },
        { key: 'atlas',  name: 'Atlas',  desc: 'Bold & Commanding' },
        { key: 'ivy',    name: 'Ivy',    desc: 'Bright & Cheerful' },
        { key: 'sage',   name: 'Sage',   desc: 'Smooth & Reassuring' },
        { key: 'ruby',   name: 'Ruby',   desc: 'Rich & Expressive' },
        { key: 'finn',   name: 'Finn',   desc: 'Husky & Mysterious' },
        { key: 'aria',   name: 'Aria',   desc: 'Clear & Professional' },
        { key: 'rex',    name: 'Rex',    desc: 'Gravelly & Rugged' },
        { key: 'dylan',  name: 'Dylan',  desc: 'Velvety & Soothing' },
        { key: 'frost',  name: 'Frost',  desc: 'Cool & British' },
    ],
    ne: [
        { key: 'hemkala', name: 'Hemkala', desc: 'Gentle & Soft' },
        { key: 'sagar',   name: 'Sagar',   desc: 'Calm & Steady' },
    ],
};

// ─── Check Status ───
fetch('/api/status').then(r => r.json()).then(data => {
    statusBadge.classList.add(data.online ? 'online' : 'offline');
    statusText.textContent = data.online ? 'Online HD' : 'Offline';
});

// ─── Language Buttons ───
langRow.querySelectorAll('.lang-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        langRow.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedLang = btn.dataset.lang;
        renderVoices();
    });
});

// ─── Voice Rendering ───
function renderVoices() {
    const voices = VOICES[selectedLang] || VOICES.en;
    selectedVoice = voices[0].key;

    voiceGrid.innerHTML = voices.map((v, i) => `
        <div class="voice-card${i === 0 ? ' active' : ''}" data-voice="${v.key}">
            <div class="voice-info">
                <span class="voice-name">${v.name}</span>
                <span class="voice-desc">${v.desc}</span>
            </div>
            <div class="voice-playing hidden">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect x="1" y="3" width="3" height="8" rx="1" fill="var(--amber)"/>
                    <rect x="5.5" y="1" width="3" height="12" rx="1" fill="var(--amber)"/>
                    <rect x="10" y="4" width="3" height="6" rx="1" fill="var(--amber)"/>
                </svg>
            </div>
        </div>
    `).join('');

    voiceGrid.querySelectorAll('.voice-card').forEach(card => {
        card.addEventListener('click', () => {
            voiceGrid.querySelectorAll('.voice-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            selectedVoice = card.dataset.voice;
            playVoicePreview(card.dataset.voice);
        });
    });
}

// ─── Voice Preview ───
function playVoicePreview(voiceKey) {
    stopCurrentAudio();
    const card = voiceGrid.querySelector(`[data-voice="${voiceKey}"]`);
    if (card) card.querySelector('.voice-playing').classList.remove('hidden');

    fetch('/api/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: selectedLang, voice: voiceKey })
    })
    .then(res => { if (!res.ok) throw new Error(); return res.blob(); })
    .then(blob => {
        const url = URL.createObjectURL(blob);
        currentAudio = new Audio(url);
        currentAudio.play().catch(() => {});
        currentAudio.onended = () => {
            if (card) card.querySelector('.voice-playing').classList.add('hidden');
            URL.revokeObjectURL(url);
        };
    })
    .catch(() => {
        if (card) card.querySelector('.voice-playing').classList.add('hidden');
    });
}

function stopVoicePreview(card) {
    if (currentAudio) { currentAudio.pause(); currentAudio.currentTime = 0; currentAudio = null; }
    if (card) card.querySelector('.voice-playing').classList.add('hidden');
}

function stopCurrentAudio() {
    if (currentAudio) { currentAudio.pause(); currentAudio.currentTime = 0; currentAudio = null; }
    voiceGrid.querySelectorAll('.voice-playing').forEach(el => el.classList.add('hidden'));
}

renderVoices();

// ─── Drag & Drop ───
dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
dropzone.addEventListener('drop', (e) => {
    e.preventDefault(); dropzone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file && file.name.toLowerCase().endsWith('.pdf')) handleFile(file);
});
fileInput.addEventListener('change', (e) => { if (e.target.files[0]) handleFile(e.target.files[0]); });

// ─── Handle File Upload ───
async function handleFile(file) {
    const formData = new FormData();
    formData.append('pdf', file);
    showStep('convertingStep');
    updateStatus('Reading your PDF...');

    try {
        const res = await fetch('/api/extract', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.error) { alert(data.error); showStep('uploadStep'); return; }

        currentFile = data;
        document.getElementById('fileName').textContent = data.original_name;
        document.getElementById('statPages').textContent = data.page_count;
        document.getElementById('statWords').textContent = formatNumber(data.word_count);
        document.getElementById('statDuration').textContent = `~${data.estimated_minutes} min`;
        showStep('previewStep');
    } catch (err) {
        alert('Failed to read PDF.'); showStep('uploadStep');
    }
}

function formatNumber(n) { return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : n.toString(); }

// ─── Convert ───
convertBtn.addEventListener('click', startConversion);

async function startConversion() {
    if (!currentFile) return;
    showStep('convertingStep');
    updateStatus('Preparing...');
    animateProgress(5, 1000);

    const filename = currentFile.filename;

    // Start conversion
    const convertPromise = fetch('/api/convert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            filename: filename,
            original_name: currentFile.original_name,
            language: selectedLang,
            voice: selectedVoice
        })
    });

    // Poll progress while converting
    let progressInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/progress/${filename}`);
            const prog = await res.json();
            if (prog.total > 0) {
                const pct = Math.round((prog.current / prog.total) * 95);
                animateProgress(pct, 800);
                const remaining = Math.ceil(prog.remaining);
                if (prog.status === 'converting') {
                    updateStatus(`Narrating chunk ${prog.current} of ${prog.total} — ~${formatTime(remaining)} remaining`);
                }
            }
        } catch (e) {}
    }, 1500);

    try {
        const res = await convertPromise;
        clearInterval(progressInterval);
        const data = await res.json();
        if (data.error) { alert(data.error); showStep('previewStep'); return; }

        animateProgress(100, 500);
        setTimeout(() => {
            document.getElementById('doneDuration').textContent = data.duration;
            document.getElementById('doneSize').textContent = data.file_size_mb + ' MB';
            document.getElementById('doneVoice').textContent = data.voice_used + ' · ' + data.mode;
            document.getElementById('savePath').textContent = data.save_path;
            downloadBtn.href = `/api/download/${encodeURIComponent(data.output_name)}`;
            downloadBtn.download = data.output_name;
            showStep('doneStep');
        }, 600);
    } catch (err) {
        clearInterval(progressInterval);
        alert('Conversion failed.'); showStep('previewStep');
    }
}

function formatTime(seconds) {
    if (seconds < 60) return `${seconds}s`;
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}m ${s}s`;
}

// ─── Progress ───
function animateProgress(target, duration) {
    const fill = document.getElementById('progressFill');
    const start = parseFloat(fill.style.width) || 0;
    const startTime = performance.now();
    function tick(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        fill.style.width = (start + (target - start) * (1 - Math.pow(1 - progress, 3))) + '%';
        if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

function updateStatus(text) { document.getElementById('convertingStatus').textContent = text; }

// ─── Navigation ───
removeFileBtn.addEventListener('click', cleanupAndReset);
startOverBtn.addEventListener('click', cleanupAndReset);

function cleanupAndReset() {
    if (currentFile) {
        fetch('/api/cleanup', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: currentFile.filename }) });
    }
    currentFile = null; fileInput.value = '';
    document.getElementById('progressFill').style.width = '0%';
    showStep('uploadStep');
}

function showStep(stepId) {
    [uploadStep, previewStep, convertingStep, doneStep].forEach(s => s.classList.add('hidden'));
    const el = document.getElementById(stepId);
    el.classList.remove('hidden');
    el.style.animation = 'none'; el.offsetHeight;
    el.style.animation = 'fadeUp 0.5s cubic-bezier(0.16, 1, 0.3, 1)';
}
