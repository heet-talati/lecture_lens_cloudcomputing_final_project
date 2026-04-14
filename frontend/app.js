'use strict';

// ============================================================
// LectureLens — Frontend Logic
// ============================================================

// ----- Config -----
// When the backend is running locally, point to it here.
// Change to your deployed Azure App Service URL before production.
const API_BASE = 'http://127.0.0.1:5000';

// ----- State -----
const state = {
  activeTab: 'upload',   // 'upload' | 'record'
  uploadedFile: null,    // File object from picker or drop
  recordedBlob: null,    // Blob from MediaRecorder
  recordingDuration: 0,  // seconds
  mediaRecorder: null,
  timerInterval: null,
  elapsedSeconds: 0,
};

// ----- DOM References -----
const $ = id => document.getElementById(id);

const tabUpload      = $('tab-upload');
const tabRecord      = $('tab-record');
const panelUpload    = $('panel-upload');
const panelRecord    = $('panel-record');

const dropZone       = $('dropZone');
const browseBtn      = $('browseBtn');
const fileInput      = $('fileInput');
const fileSelected   = $('fileSelected');
const fileNameEl     = $('fileName');
const clearFileBtn   = $('clearFileBtn');

const recordBtn      = $('recordBtn');
const recordLabel    = $('recordLabel');
const timerEl        = $('timer');
const waveform       = $('waveform');
const recordingReady = $('recordingReady');
const recordDuration = $('recordDuration');
const clearRecordBtn = $('clearRecordBtn');

const errorBanner    = $('errorBanner');
const errorMessage   = $('errorMessage');
const dismissError   = $('dismissError');

const processBtn     = $('processBtn');
const loadingCard    = $('loadingCard');
const loadingMessage = $('loadingMessage');

const resultsSection = $('resultsSection');
const transcriptText = $('transcriptText');
const summaryText    = $('summaryText');
const resetBtn       = $('resetBtn');

// ============================================================
// Tabs
// ============================================================
function switchTab(tab) {
  state.activeTab = tab;

  tabUpload.classList.toggle('active', tab === 'upload');
  tabRecord.classList.toggle('active', tab === 'record');

  panelUpload.classList.toggle('hidden', tab !== 'upload');
  panelRecord.classList.toggle('hidden', tab !== 'record');

  hideError();
  updateProcessBtn();
}

tabUpload.addEventListener('click', () => switchTab('upload'));
tabRecord.addEventListener('click', () => switchTab('record'));

// ============================================================
// File Upload
// ============================================================
const ALLOWED_TYPES = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp4', 'audio/m4a', 'audio/x-m4a'];
const MAX_SIZE_MB   = 25;

function isValidAudio(file) {
  const okType = ALLOWED_TYPES.includes(file.type) || file.name.match(/\.(mp3|wav|m4a)$/i);
  const okSize = file.size <= MAX_SIZE_MB * 1024 * 1024;
  return { okType, okSize };
}

function setUploadedFile(file) {
  const { okType, okSize } = isValidAudio(file);

  if (!okType) {
    showError('Unsupported file type. Please upload an MP3, WAV, or M4A file.');
    return;
  }
  if (!okSize) {
    showError(`File is too large. Maximum size is ${MAX_SIZE_MB} MB.`);
    return;
  }

  hideError();
  state.uploadedFile = file;
  fileNameEl.textContent = file.name;
  fileSelected.classList.remove('hidden');
  updateProcessBtn();
}

function clearUpload() {
  state.uploadedFile = null;
  fileInput.value = '';
  fileSelected.classList.add('hidden');
  updateProcessBtn();
}

// Browse button
browseBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  fileInput.click();
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setUploadedFile(fileInput.files[0]);
});

clearFileBtn.addEventListener('click', clearUpload);

// Click on drop zone (but not on the browse button)
dropZone.addEventListener('click', () => fileInput.click());

// Keyboard accessibility
dropZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    fileInput.click();
  }
});

// Drag & drop
dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));

dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) setUploadedFile(file);
});

// ============================================================
// Audio Recording
// ============================================================
async function startRecording() {
  hideError();

  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      showError('Microphone access was denied. Please allow microphone permission and try again.');
    } else {
      showError('Could not access microphone. Make sure your device has a working mic.');
    }
    return;
  }

  const chunks = [];
  const options = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? { mimeType: 'audio/webm;codecs=opus' }
    : {};

  state.mediaRecorder = new MediaRecorder(stream, options);

  state.mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };

  state.mediaRecorder.onstop = () => {
    stream.getTracks().forEach(t => t.stop());
    const mimeType = state.mediaRecorder.mimeType || 'audio/webm';
    state.recordedBlob = new Blob(chunks, { type: mimeType });
    state.recordingDuration = state.elapsedSeconds;

    recordingReady.classList.remove('hidden');
    recordDuration.textContent = formatTime(state.elapsedSeconds);
    updateProcessBtn();
  };

  state.mediaRecorder.start(250); // collect data every 250ms

  // UI updates
  recordBtn.classList.add('recording');
  recordLabel.textContent = 'Recording… click to stop';
  timerEl.classList.remove('hidden');
  waveform.classList.add('active');

  state.elapsedSeconds = 0;
  timerEl.textContent = '00:00';
  state.timerInterval = setInterval(() => {
    state.elapsedSeconds++;
    timerEl.textContent = formatTime(state.elapsedSeconds);
  }, 1000);
}

function stopRecording() {
  if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
    state.mediaRecorder.stop();
  }
  clearInterval(state.timerInterval);

  recordBtn.classList.remove('recording');
  recordLabel.textContent = 'Click to start recording';
  timerEl.classList.add('hidden');
  waveform.classList.remove('active');
}

recordBtn.addEventListener('click', () => {
  if (state.mediaRecorder && state.mediaRecorder.state === 'recording') {
    stopRecording();
  } else {
    startRecording();
  }
});

clearRecordBtn.addEventListener('click', () => {
  state.recordedBlob = null;
  state.recordingDuration = 0;
  recordingReady.classList.add('hidden');
  updateProcessBtn();
});

function formatTime(totalSeconds) {
  const m = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
  const s = String(totalSeconds % 60).padStart(2, '0');
  return `${m}:${s}`;
}

// ============================================================
// Process Button State
// ============================================================
function updateProcessBtn() {
  const hasUpload = state.activeTab === 'upload' && state.uploadedFile !== null;
  const hasRecord = state.activeTab === 'record' && state.recordedBlob !== null;
  processBtn.disabled = !(hasUpload || hasRecord);
}

// ============================================================
// Error Handling
// ============================================================
function showError(msg) {
  errorMessage.textContent = msg;
  errorBanner.classList.remove('hidden');
}

function hideError() {
  errorBanner.classList.add('hidden');
}

dismissError.addEventListener('click', hideError);

// ============================================================
// Process (Transcribe + Summarize)
// ============================================================
processBtn.addEventListener('click', processAudio);

async function processAudio() {
  hideError();

  const file = state.activeTab === 'upload'
    ? state.uploadedFile
    : await blobToFile(state.recordedBlob);

  if (!file) return;

  // Show loading state
  const inputSection = document.querySelector('.input-section');
  inputSection.classList.add('hidden');
  loadingCard.classList.remove('hidden');
  resultsSection.classList.add('hidden');

  try {
    loadingMessage.textContent = 'Transcribing audio…';
    const transcript = await transcribeAudio(file);

    loadingMessage.textContent = 'Generating summary…';
    const summary = await summarizeTranscript(transcript);

    showResults(transcript, summary);
  } catch (err) {
    loadingCard.classList.add('hidden');
    inputSection.classList.remove('hidden');
    showError(err.message || 'Something went wrong. Please try again.');
  }
}

async function blobToFile(blob) {
  if (!blob.type.includes('webm') && !blob.type.includes('ogg')) {
    return new File([blob], 'recording.wav', { type: blob.type });
  }
  // Decode compressed audio → PCM WAV using the Web Audio API (no ffmpeg needed)
  const arrayBuffer = await blob.arrayBuffer();
  const audioCtx = new AudioContext();
  const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
  audioCtx.close();
  const wavBlob = _encodeWav(audioBuffer);
  return new File([wavBlob], 'recording.wav', { type: 'audio/wav' });
}

function _encodeWav(audioBuffer) {
  const numChannels = audioBuffer.numberOfChannels;
  const sampleRate  = audioBuffer.sampleRate;
  const numFrames   = audioBuffer.length;
  const blockAlign  = numChannels * 2; // 16-bit
  const dataSize    = numFrames * blockAlign;
  const buf         = new ArrayBuffer(44 + dataSize);
  const view        = new DataView(buf);

  const writeStr = (off, str) => { for (let i = 0; i < str.length; i++) view.setUint8(off + i, str.charCodeAt(i)); };

  writeStr(0,  'RIFF');
  view.setUint32( 4, 36 + dataSize, true);
  writeStr(8,  'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);                          // PCM
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true);    // byte rate
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true);                         // bits per sample
  writeStr(36, 'data');
  view.setUint32(40, dataSize, true);

  let offset = 44;
  for (let i = 0; i < numFrames; i++) {
    for (let ch = 0; ch < numChannels; ch++) {
      const s = Math.max(-1, Math.min(1, audioBuffer.getChannelData(ch)[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      offset += 2;
    }
  }
  return new Blob([buf], { type: 'audio/wav' });
}

// ============================================================
// API Calls
// ============================================================

async function transcribeAudio(file) {
  const formData = new FormData();
  formData.append('audio', file);

  const res = await fetch(`${API_BASE}/transcribe`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Transcription failed (HTTP ${res.status}).`);
  }

  const data = await res.json();
  return data.transcript;
}

async function summarizeTranscript(transcript) {
  const res = await fetch(`${API_BASE}/summarize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ transcript }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Summarization failed (HTTP ${res.status}).`);
  }

  const data = await res.json();
  return data.summary;
}

// ============================================================
// Results Display
// ============================================================
function showResults(transcript, summary) {
  loadingCard.classList.add('hidden');

  transcriptText.textContent = transcript;
  renderSummary(summary);

  resultsSection.classList.remove('hidden');
}

// Render summary: detect simple markdown-style headings (## or **bold**)
// so the output looks structured even as plain text.
function renderSummary(text) {
  summaryText.innerHTML = '';

  const lines = text.split('\n');
  let html = '';

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) { html += '<br>'; continue; }

    // ## Heading
    if (trimmed.startsWith('## ')) {
      html += `<div class="summary-heading">${escapeHtml(trimmed.slice(3))}</div>`;
    }
    // **bold heading** (standalone line)
    else if (/^\*\*(.+)\*\*$/.test(trimmed)) {
      html += `<div class="summary-heading">${escapeHtml(trimmed.replace(/\*\*/g, ''))}</div>`;
    }
    // Bullet list
    else if (trimmed.startsWith('- ') || trimmed.startsWith('• ')) {
      html += `<li>${escapeHtml(trimmed.slice(2))}</li>`;
    }
    else {
      html += `<p>${escapeHtml(trimmed)}</p>`;
    }
  }

  summaryText.innerHTML = html;
}

function escapeHtml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ============================================================
// Copy & Download
// ============================================================
document.querySelectorAll('[data-copy]').forEach(btn => {
  btn.addEventListener('click', () => {
    const which = btn.dataset.copy;
    const text  = which === 'transcript'
      ? transcriptText.textContent
      : summaryText.innerText;

    navigator.clipboard.writeText(text).then(() => {
      const original = btn.innerHTML;
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.innerHTML = original;
        btn.classList.remove('copied');
      }, 2000);
    }).catch(() => showError('Could not copy to clipboard.'));
  });
});

document.querySelectorAll('[data-download]').forEach(btn => {
  btn.addEventListener('click', () => {
    const which    = btn.dataset.download;
    const text     = which === 'transcript'
      ? transcriptText.textContent
      : summaryText.innerText;
    const filename = which === 'transcript' ? 'transcript.txt' : 'summary.txt';

    const blob = new Blob([text], { type: 'text/plain' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  });
});

// ============================================================
// Reset
// ============================================================
resetBtn.addEventListener('click', () => {
  // Clear state
  state.uploadedFile   = null;
  state.recordedBlob   = null;
  state.recordingDuration = 0;

  // Reset file UI
  fileInput.value = '';
  fileSelected.classList.add('hidden');
  recordingReady.classList.add('hidden');

  // Reset results
  transcriptText.textContent = '';
  summaryText.innerHTML = '';

  // Show input section
  resultsSection.classList.add('hidden');
  loadingCard.classList.add('hidden');
  document.querySelector('.input-section').classList.remove('hidden');

  hideError();
  switchTab('upload');
  updateProcessBtn();
});
