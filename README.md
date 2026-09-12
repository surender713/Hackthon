# Media Authenticity Plugin

Media Authenticity Plugin is a Chrome extension and FastAPI service for analyzing selected text and webpage images. It estimates AI-generation probability, verifies claims against live sources, detects recurring misinformation narratives, and checks images for signs of AI generation or digital manipulation. The extension keeps verification inside the page: select text or right-click an image, then request an analysis.

> This is an AI-detector prototype. Its result is probabilistic and should not be treated as proof of authorship.

## Why This Matters

In the era of sophisticated AI-generated content (ChatGPT, Claude, Gemini), the ability to quickly identify and verify information is critical. This plugin addresses a crucial gap:

- **Combats Misinformation**: Automatically flags potentially AI-generated text and cross-verifies claims against reputable sources
- **Saves Research Time**: Eliminates manual fact-checking by providing instant source verification alongside AI probability scores
- **Browser-Native**: Unlike standalone tools, this works seamlessly within your browser on any webpage
- **Privacy-Focused**: Analysis happens locally with your backend—no text is logged to external services (only API calls to Gemini/DuckDuckGo)
- **Comparative Advantage**: 
  - Faster than manual searches (parallel API + search execution)
  - More transparent than black-box AI detectors
  - Free tier compatible (uses free Gemini API)
  - Open source and extensible for organizations

## Features

- ✅ **AI Detection**: Analyzes selected text using Google Gemini API to estimate AI-generated vs human-written probability
- ✅ **Image Authenticity Detection**: Right-click any webpage image to analyze it for AI-generation or digital manipulation
- ✅ **Fact-Checking**: Verifies claims against live web sources using DuckDuckGo search
- ✅ **Source Verification**: Identifies reputable media sources (BBC, Reuters, AP, etc.)
- ✅ **Misinformation Pattern Detection**: Flags recurring narratives, propaganda framing, coordinated disinformation patterns, and conspiracy themes
- ✅ **Exportable Reports**: Download text verification records as JSON, HTML, or TXT files
- ✅ **Fast Response**: Parallel processing of AI detection and fact-checking (~3-4 seconds)
- ✅ **Smart Caching**: Caches results for identical text selections (instant retrieval)
- ✅ **Error Resilience**: Graceful fallbacks if one API is temporarily unavailable
- ✅ **In-page Display**: Beautiful status card showing results directly on the webpage

## Project Structure

```text
media-authenticity-plugin/
├── backend/
│   ├── main.py                    # FastAPI backend with async optimization
│   ├── requirements.txt           # Python dependencies
│   └── .env                       # API keys (GEMINI_API_KEY)
└── frontend/
    ├── manifest.json             # Extension configuration
    ├── background.js             # Service worker
    ├── content.js                # Content script
    └── styles.css                # Popup styling
```

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Chrome Extension (Frontend)                                  │
│ - User selects text or right-clicks an image                 │
│ - Context menu sends text or image URL to content script     │
│ - Images are converted to Base64 in the browser              │
└─────────┬───────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ FastAPI Backend (main.py)                                    │
│ - Caches results for identical text (instant retrieval)      │
│ - POST /analyze: text AI score + pattern detection + search  │
│ - POST /analyze-image: multimodal image forensics           │
└─────────┬───────────────────────────────────────────────────┘
          │
          ├─────────────────────────┬──────────────────────────┤
          ▼                         ▼                          ▼
  ┌──────────────┐         ┌──────────────┐       ┌──────────────────┐
  │ Google Gemini│         │ DuckDuckGo   │       │ Result Cache     │
  │ API          │         │ Text Search  │       │ (JSON in memory) │
   │ - Text score │         │ - 3 results  │       │ - Max 100 items  │
   │ - Patterns   │         │ - Top 2 used │       │ - LRU eviction   │
   │ - Image scan │         │             │       │                  │
  └──────────────┘         └──────────────┘       └──────────────────┘
          │                         │
          └─────────────────────────┘
                      │
                      ▼
        ┌────────────────────────────┐
        │ Return combined result JSON │
        │ - ai_score object           │
        │ - claim_status              │
        │ - sources array             │
        └────────────────────────────┘
                      │
                      ▼
        ┌────────────────────────────┐
        │ Extension displays card    │
      │ - AI detection %           │
      │ - Narrative alerts         │
      │ - Verification and sources │
      │ - JSON, HTML, TXT exports  │
        └────────────────────────────┘
```

### Async Optimization

The backend uses **asyncio.gather()** to run AI detection and fact-checking in parallel:

```python
ai_score, verify_result = await asyncio.gather(
    get_ai_score(),
    verify_claim_async(text),
    return_exceptions=True
)
```

**Why This Matters**:
- Sequential execution would take 15-20 seconds (sum of timeouts)
- Parallel execution achieves 3-4 seconds (max of timeouts + network latency)
- Both tasks run independently, so slowness in one doesn't block the other
- Graceful error handling: if Gemini times out, search result still returns

### Key Technical Details

1. **Thread Pool Executor**: Blocking I/O (Gemini API, DuckDuckGo) runs in a thread pool to avoid blocking the async event loop
2. **Timeouts**: 20s for text AI detection and 10s for search (prevents infinite hangs)
3. **Retry Logic**: Search retries up to 2x with exponential backoff for rate-limiting
4. **Caching**: In-memory cache prevents redundant AI calls for identical text
5. **Browser-side image encoding**: The content script fetches an image and sends Base64 data to avoid backend downloads from protected image URLs
6. **Image model fallback**: Image analysis defaults to `gemini-3.6-flash`; `GEMINI_IMAGE_MODEL` can override it

## Requirements

- **Python 3.10+** (for async/await support)
- **Google Chrome** (with developer mode enabled for unpacked extension)
- **Google Gemini API Key** (free tier available at [makersuite.google.com](https://makersuite.google.com))

## Backend Setup

### Windows PowerShell

```powershell
cd media-authenticity-plugin\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS or Linux

```bash
cd media-authenticity-plugin/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure Environment

Create `backend/.env` file in the `backend/` directory:

```env
GEMINI_API_KEY=your_google_gemini_api_key_here
GEMINI_IMAGE_MODEL=gemini-3.6-flash
```

#### Getting Your API Key

1. Visit [makersuite.google.com/app/apikey](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account (free account supported)
3. Click "Create API key"
4. Copy the generated key
5. Paste into `backend/.env`

#### Verify Configuration

```bash
cd backend
python -c "from dotenv import load_dotenv; import os; from pathlib import Path; load_dotenv(Path('.env')); print('✅ API Key loaded' if os.getenv('GEMINI_API_KEY') else '❌ API Key missing')"
```

Or test the backend endpoint:

```bash
python main.py
# In another terminal:
python -m pytest test_api.py  # if pytest is available
```

#### Security Best Practices

- ⚠️ **Never commit `.env`** - it's already in `.gitignore`
- ⚠️ **Never hardcode API keys** in `main.py`, `content.js`, or `manifest.json`
- ⚠️ **Keep backend private** - don't expose it to the public internet
- ✅ **Use environment variables** for all sensitive data
- ✅ **Rotate API keys** regularly if exposed

#### Configuration Options

Potential environment variables for customization:

```env
GEMINI_API_KEY=your_key                    # Required: Google Gemini API key
GEMINI_MODEL=gemini-3.6-flash              # Optional: Text model selection (currently configured in main.py)
GEMINI_IMAGE_MODEL=gemini-3.6-flash        # Optional: Image model selection
GEMINI_TIMEOUT=20                          # Optional: AI detection timeout in seconds (default: 20)
SEARCH_TIMEOUT=10                          # Optional: Search timeout in seconds (default: 10)
CACHE_MAX_SIZE=100                         # Optional: Max cached results (default: 100)
```

### Start the Backend

```bash
python main.py
```

Or with reload on code changes:

```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The API runs at `http://127.0.0.1:8000`

## Load the Extension

1. Open `chrome://extensions` in Chrome
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `media-authenticity-plugin/frontend` directory
5. Pin the extension for easy access

**Reload extension** after modifying any files (manifest.json, background.js, content.js).

## Use the Extension

1. ✅ Start the backend (running on port 8000)
2. ✅ Open any normal webpage
3. ✅ Select text or find an image
4. ✅ Right-click → **Verify with Authenticity Plugin**
5. ✅ View results in the popup card
6. ✅ For text reports, use **Export JSON**, **Export HTML**, or **Export TXT**

**Supported on**: Regular webpages (not Chrome system pages like chrome://, about://)

The backend truncates submitted text to 2,000 characters before analysis. Image data is fetched and Base64-encoded by the content script before it is sent to the backend.

## API

### `POST /analyze`

**Request:**
```json
{
  "text": "Text to analyze for AI detection and fact-checking"
}
```

**Response:**
```json
{
  "ai_score": {
    "percentage": 85,
    "label": "85% AI-Generated"
  },
   "pattern_data": {
      "pattern_detected": true,
      "narrative_summary": "Matches a recurring health misinformation narrative."
   },
  "claim_status": "Verified in mainstream media",
  "sources": [
    {
      "title": "Source article title",
      "url": "https://example.com/article"
    }
  ]
}
```

**Status Codes:**
- `200` ✅ Success
- `400` ❌ Empty text
- `500` ❌ Missing API key
- `502/504` ❌ API timeout or error (graceful fallback provided)

**Quick Test:**
```powershell
# Test the API
$body = @{text = "This is a test"} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/analyze -Method POST -ContentType "application/json" -Body $body

# Test image analysis with a Base64 image data URL
$imageBody = @{image_data = "data:image/jpeg;base64,/9j/..."} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/analyze-image -Method POST -ContentType "application/json" -Body $imageBody
```

### `POST /analyze-image`

Analyzes a Base64-encoded image with Gemini multimodal input. The frontend sends a data URL such as `data:image/png;base64,...`, although raw Base64 is also accepted.

**Request:**
```json
{
   "image_data": "data:image/jpeg;base64,/9j/..."
}
```

**Response:**
```json
{
   "percentage": 35,
   "label": "35% AI-Generated",
   "manipulation_details": "No clear manipulation indicators were found."
}
```

**Status Codes:**
- `200` ✅ Success
- `400` ❌ Empty image data
- `415` ❌ Unsupported image format
- `500` ❌ Missing API key
- `502` ❌ Gemini image-analysis failure

## Performance

| Operation | Time | Notes |
|-----------|------|-------|
| First request | 3-4 sec | Parallel Gemini API + DuckDuckGo search |
| Cached result | <100 ms | Same text retrieves instantly |
| Gemini timeout | 15 sec max | Returns fallback response |
| Search timeout | 5 sec max | Retries up to 2x with backoff |

## Troubleshooting

### 🔴 Backend won't start: "ModuleNotFoundError"

**Error**: `ModuleNotFoundError: No module named 'fastapi'` or similar

**Solution**:
```bash
cd backend
pip install -r requirements.txt
# or
pip install fastapi uvicorn google-genai ddgs requests python-dotenv
```

**Why**: Python dependencies not installed in virtual environment.

---

### 🔴 Backend won't start: "Gemini API key not configured"

**Error**: `HTTPException 500: Gemini API key is not configured`

**Solution**:
1. Create `backend/.env` file
2. Add: `GEMINI_API_KEY=your_actual_key_here`
3. Verify key from [makersuite.google.com/app/apikey](https://makersuite.google.com/app/apikey)
4. Restart backend: `python main.py`

**Why**: `.env` file missing or API key not set as environment variable.

---

### 🟠 "AI Detection Timeout" appears in popup

**Error**: Card shows "AI Detection Timeout" but extension is running

**Causes & Solutions**:

| Cause | Solution |
|-------|----------|
| Gemini API slow on first request | Wait 20 seconds, try again (cached results are instant) |
| API key invalid or expired | Get new key from [makersuite.google.com](https://makersuite.google.com/app/apikey), update `.env` |
| Network issues | Check internet connection, retry |
| Backend not running | Verify `python main.py` is still running on port 8000 |
| Port 8000 in use by another app | Change port: `python -m uvicorn main:app --port 8001` and update extension |

**Quick Debug**:
```bash
# Test backend health
curl http://127.0.0.1:8000/health
# Should return: {"status":"ok"}

# Test Gemini connectivity
curl http://127.0.0.1:8000/test-gemini
# Should return: {"message":"Using Gemini API", "key_present":true}
```

---

### 🟠 "Search timed out" in fact-check section

**Error**: Claim verification shows timeout, no sources found

**Causes & Solutions**:

| Cause | Solution |
|-------|----------|
| DuckDuckGo rate-limiting your IP | Wait 30 seconds, backend auto-retries with backoff |
| Network latency | Check internet speed, try again |
| Backend search timeout expired | Increase timeout: edit `verify_claim_async()` in `main.py` |

**Note**: Backend automatically retries up to 2x with exponential backoff before returning timeout.

---

### 🟠 Extension popup appears but shows "Server error"

**Error**: Card displays generic error message

**Diagnosis**:
1. Open Chrome DevTools: `F12` → `Console` tab
2. Look for error messages like:
   - `Failed to fetch http://127.0.0.1:8000/analyze`
   - `Invalid response from analysis server`

**Solutions**:
- Backend not running: `python main.py` in `backend/` directory
- CORS issues: Restart backend (CORS middleware already configured)
- Reload extension: `chrome://extensions` → find plugin → click refresh icon

---

### 🟠 Image card shows "Image analysis service is unavailable"

**Causes & Solutions**:

| Cause | Solution |
|-------|----------|
| Backend was not restarted after an image-analysis change | Stop and restart `python main.py` |
| Gemini image model is unavailable for the API key | Set `GEMINI_IMAGE_MODEL=gemini-3.6-flash` in `backend/.env` and restart |
| Image format is unsupported | Use JPEG, PNG, WebP, HEIC, or HEIF; SVG images are not supported |
| Image requires authentication or blocks browser fetches | Try a publicly accessible image or verify the page permits image requests |
| Extension content script is stale | Reload the extension from `chrome://extensions` |

The backend logs the specific Gemini model or image-processing error. The image endpoint tries the configured model first and then falls back to supported models.

---

### 🟠 Context menu item "Verify with Authenticity Plugin" doesn't appear

**Error**: Right-click menu missing, no context menu option visible

**Solutions**:

1. **Reload extension**:
   - Go to `chrome://extensions`
   - Find "Media Authenticity Plugin"
   - Click refresh/reload icon

2. **Check manifest.json**:
   - Verify `frontend/manifest.json` has correct permissions
   - Restart Chrome if permissions were blocked

3. **Supported pages only**:
   - Works on: normal webpages, Google.com, news sites
   - Does NOT work on: `chrome://` pages, `file://` URLs, extension pages
   - Test on a normal webpage first

4. **Enable context menu**:
   - Extension background.js must be running
   - Check: `chrome://extensions` → expand "Media Authenticity Plugin" → click "Background page" to debug

---

### 🟢 Performance is slow on first request

**Expected behavior**: First analysis takes 3-4 seconds

**Explanation**:
- Gemini API needs 1-2s network roundtrip
- DuckDuckGo search needs 1-2s network roundtrip
- Both run in parallel (not sequential)

**To improve**:
- Subsequent identical text is **instant** (cached results)
- Use shorter text snippets (faster API response)
- Ensure stable internet connection

---

### 🟢 Cache keeps returning old results

**Issue**: Same text always shows cached result, never updates

**Solution**: This is **intentional design**
- Identical text always produces identical analysis
- Cache is cleared on backend restart
- To force refresh: slightly modify text (add punctuation) and re-analyze

---

### 📋 Collecting Debug Information

If issues persist, collect this information:

1. **Backend logs**:
   ```bash
   cd backend && python main.py 2>&1 | tee debug.log
   # Run test, collect output
   ```

2. **Browser console**:
   - Open DevTools: `F12` → `Console`
   - Right-click → Verify → screenshot errors

3. **System info**:
   - Python version: `python --version`
   - Chrome version: `chrome://version`
   - OS: Windows/Mac/Linux

## Roadmap

- ✅ Image authenticity detection
- ✅ Misinformation pattern detection
- 🎯 Real-time confidence calibration
- 🎯 Offline mode support
- ✅ Export analysis reports (JSON, HTML, TXT)

## Dependencies

**Backend**
- `fastapi` - Web framework
- `uvicorn` - ASGI server  
- `google-genai` - Google Gemini API client
- `ddgs` - DuckDuckGo search (modern fork)
- `python-dotenv` - Environment variable management

**Frontend**
- Vanilla JavaScript (no build step required)
- Chrome Extension Manifest V3

## License

MIT License - see LICENSE file for details






