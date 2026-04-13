# LectureLens — Implementation Plan

AI-Powered Lecture Transcription & Summarization Tool
Cloud Computing for Software Development — SAIT 2026
Team: Brett Shalagan, Steven Brar, Kyle Chau, Heet Talati

---

## Phase 1 — Frontend (HTML/CSS/JS) ✅

**Files:**
- `frontend/index.html`
- `frontend/style.css`
- `frontend/app.js`

**Features:**

1. **Audio Recording UI**
   - Mic button (record/stop toggle) using `MediaRecorder` API
   - Recording timer display
   - Visual feedback (pulsing indicator + waveform while recording)

2. **File Upload UI**
   - Drag-and-drop zone + file picker (MP3, WAV, M4A)
   - Client-side validation: file type + 25 MB size limit
   - Selected file name display with clear button

3. **Submit & Processing State**
   - "Transcribe & Summarize" button (disabled until audio is ready)
   - Loading spinner with status message ("Transcribing…" → "Generating summary…")

4. **Results Display**
   - Two-panel layout: Transcript | Summary (stacks on mobile)
   - Summary parsed for `##` headings and `- ` bullet points
   - Copy-to-clipboard and download as `.txt` for each panel

5. **Error Handling**
   - Dismissable error banner for: mic denied, bad file type, file too large, API failures

---

## Phase 2 — Backend (Python/Flask)

**Files:**
- `backend/app.py` — Flask app + routes
- `backend/transcribe.py` — Azure Speech-to-Text logic
- `backend/summarize.py` — Azure OpenAI logic
- `backend/content_safety.py` — Azure Content Safety check (Heet)
- `backend/requirements.txt`
- `backend/.env` — API keys (gitignored)

**Routes:**

| Method | Route | Purpose |
|--------|-------|---------|
| `POST` | `/transcribe` | Accepts audio file, returns transcript |
| `POST` | `/summarize` | Accepts transcript text, returns summary |
| `POST` | `/process` | Combined endpoint (transcribe + summarize) |
| `GET`  | `/health` | Sanity check |

**Implementation order:**
1. Flask skeleton + CORS setup
2. File upload handling (save temp file, validate format)
3. Azure Speech-to-Text integration (`azure-cognitiveservices-speech` SDK)
4. Azure OpenAI integration (`openai` SDK pointed at Azure endpoint)
5. Azure Content Safety check (wrap around both outputs)
6. Wire all three into `/process`

---

## Phase 3 — Azure Cloud Setup

**Resources to provision (Azure Portal or CLI):**

1. **Resource Group** — `lecture-lens-rg`
2. **Azure Speech Service** — Free tier (F0), get key + region
3. **Azure OpenAI Service** — Deploy `gpt-4o-mini` or `gpt-35-turbo`
4. **Azure Content Safety** — Free tier, get key + endpoint
5. **Azure App Service** — B1 tier, Python 3.11 runtime (for deployment)

**Required `.env` variables:**

```
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=...
AZURE_OPENAI_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_DEPLOYMENT=...
AZURE_CONTENT_SAFETY_KEY=...
AZURE_CONTENT_SAFETY_ENDPOINT=...
```

---

## Phase 4 — Integration & Deployment

1. Test frontend ↔ backend locally (`flask run` + open `index.html`)
2. Add `Procfile` / `startup.sh` for App Service
3. Set environment variables in App Service configuration panel
4. Deploy backend via `az webapp deploy` or GitHub Actions
5. Point frontend `fetch()` calls to the deployed Azure App Service URL

---

## Division of Responsibilities

| Member | Responsibilities |
|--------|-----------------|
| Steven | Backend API, Azure integration, deployment |
| Brett  | Frontend UI, audio recording, transcript display |
| Heet   | Transcribing, Content Safety |
| Kyle   | AI summarization, testing, documentation |

---

## Success Criteria

- Transcription accuracy of 85%+ on clear English audio
- Summary generated within 15 seconds of transcript completion
- Runs reliably in Chrome and Firefox
- All team members contribute documented, tested code
