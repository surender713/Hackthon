# Media Authenticity Plugin

Media Authenticity Plugin is a Chrome extension and FastAPI service for analyzing selected text to detect AI-generated content and verify claims against live sources. The extension keeps verification inside the page: select text, right-click, and request an analysis.

> This is an AI-detector prototype. Its result is probabilistic and should not be treated as proof of authorship.

## Features

- ✅ **AI Detection**: Analyzes selected text using Google Gemini API to estimate AI-generated vs human-written probability
- ✅ **Fact-Checking**: Verifies claims against live web sources using DuckDuckGo search
- ✅ **Source Verification**: Identifies reputable media sources (BBC, Reuters, AP, etc.)
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

1. User selects text and right-clicks → **"Verify with Media Authenticity"**
2. Extension sends text to `POST /analyze` on local backend
3. Backend **concurrently**:
   - Sends to Google Gemini API for AI detection
   - Searches DuckDuckGo for related sources
4. Extension displays results in an in-page status card

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

Create `backend/.env`:

```env
GEMINI_API_KEY=your_google_gemini_api_key_here
```

Get your API key:
1. Visit [makersuite.google.com](https://makersuite.google.com/app/apikey)
2. Create an API key
3. Copy it to `.env` file

**Important**: Do not commit `.env` or expose the key in the browser extension.

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
3. ✅ Select text
4. ✅ Right-click → **Verify with Media Authenticity**
5. ✅ View results in the popup card

**Supported on**: Regular webpages (not Chrome system pages like chrome://, about://)

The backend truncates submitted text to 2,000 characters before analysis.

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
```

## Performance

| Operation | Time | Notes |
|-----------|------|-------|
| First request | 3-4 sec | Parallel Gemini API + DuckDuckGo search |
| Cached result | <100 ms | Same text retrieves instantly |
| Gemini timeout | 15 sec max | Returns fallback response |
| Search timeout | 5 sec max | Retries up to 2x with backoff |

## Troubleshooting

### Backend won't start: "Gemini API key not configured"
- Ensure `backend/.env` has `GEMINI_API_KEY=your_key`
- Verify API key is valid at [makersuite.google.com](https://makersuite.google.com/app/apikey)
- Restart backend after adding key

### Extension popup appears but shows "Unavailable"
- Check browser console (F12 → Console)
- Verify backend is running: `http://127.0.0.1:8000/docs` should show Swagger UI
- Reload extension from `chrome://extensions`

### Search verification shows "Temporarily unavailable"
- DuckDuckGo may be rate-limiting requests
- Backend automatically retries with exponential backoff
- Try again in a few seconds

### Context menu item doesn't appear
- Reload extension from `chrome://extensions`
- Test on a normal webpage (not chrome://, file://, or extension pages)
- Right-click and select text to trigger the menu

### Timeout errors
- Gemini API is slow on first request (up to 15 seconds)
- Subsequent requests are faster
- Check internet connection

## Roadmap

- 🎯 Image authenticity detection
- 🎯 Misinformation pattern detection
- 🎯 Real-time confidence calibration
- 🎯 Offline mode support
- 🎯 Export analysis reports

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






