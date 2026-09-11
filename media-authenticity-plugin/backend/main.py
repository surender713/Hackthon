import os
import re
import json
import asyncio
import time
from typing import Any
from urllib.parse import urlparse
from pathlib import Path
from functools import lru_cache

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None
    
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
print(f"[DEBUG] GEMINI_API_KEY loaded: {bool(GEMINI_API_KEY)}")

app = FastAPI(title="Media Authenticity Plugin")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    text: str

REPUTABLE_DOMAINS = {
    "bbc.com",
    "bbc.co.uk",
    "indianexpress.com",
    "ndtv.com",
    "reuters.com",
    "thehindu.com",
}

def extract_claim(text: str) -> str:
    first_sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    return (first_sentence or text)[:100].strip()

def is_reputable_source(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in REPUTABLE_DOMAINS
    )

# Simple in-memory cache for API responses (max 100 entries)
_analysis_cache = {}
_CACHE_MAX_SIZE = 100

def get_cache_key(text: str) -> str:
    """Generate cache key from text hash"""
    return str(hash(text[:500]))

def get_cached_result(text: str) -> dict[str, Any] | None:
    """Retrieve cached analysis result"""
    cache_key = get_cache_key(text)
    return _analysis_cache.get(cache_key)

def cache_result(text: str, result: dict[str, Any]) -> None:
    """Cache analysis result"""
    if len(_analysis_cache) >= _CACHE_MAX_SIZE:
        # Remove oldest entry
        _analysis_cache.pop(next(iter(_analysis_cache)))
    _analysis_cache[get_cache_key(text)] = result

async def verify_claim_async(text: str) -> dict[str, Any]:
    query = extract_claim(text)
    sources: list[dict[str, str]] = []

    if DDGS is None:
        return {
            "claim_status": "Unverified / Search dependency is not installed",
            "sources": [],
        }

    async def search_with_retry():
        """Search with exponential backoff retry for rate limiting"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_event_loop()
                results = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: DDGS().text(query, max_results=3)),
                    timeout=5.0
                )
                return results
            except Exception as e:
                error_msg = str(e).lower()
                # Check for rate limiting
                if "ratelimit" in error_msg or "403" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # 2, 4 seconds
                        print(f"[DEBUG] Rate limited, retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                # Don't retry on other errors
                raise

    try:
        results = await search_with_retry()
        for result in results[:2]:  # Limit to 2 results
            title = str(result.get("title") or "").strip()
            url = str(result.get("href") or "").strip()
            if title and url:
                sources.append({"title": title, "url": url})
    except asyncio.TimeoutError:
        return {
            "claim_status": "Search timed out",
            "sources": [],
        }
    except Exception as e:
        print(f"[DEBUG] Search error: {e}")
        return {
            "claim_status": "Unverified / Search temporarily unavailable",
            "sources": [],
        }

    if any(is_reputable_source(source["url"]) for source in sources):
        claim_status = "Verified in mainstream media"
    elif sources:
        claim_status = "Related coverage found outside listed mainstream sources"
    else:
        claim_status = "Unverified / No matching news coverage"

    return {"claim_status": claim_status, "sources": sources}




@app.post("/analyze")
async def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    print("[DEBUG] /analyze endpoint called")
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text field cannot be empty.")

    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Gemini API key is not configured. Set GEMINI_API_KEY in backend/.env.",
        )

    # Check cache first
    cached = get_cached_result(text)
    if cached:
        print("[DEBUG] Returning cached result")
        return cached

    truncated = text[:2000]
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""Analyze if this text is AI-generated or human-written.
Return ONLY this JSON format:
{{"percentage": <0-100>, "label": "<number>% <AI-Generated|Human-Written>"}}

Text: {truncated}"""

    async def get_ai_score():
        """Get AI detection score from Gemini"""
        loop = asyncio.get_event_loop()
        try:
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model="gemini-3.6-flash",
                        contents=prompt,
                    )
                ),
                timeout=15.0
            )
            
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            return json.loads(response_text)
        except asyncio.TimeoutError:
            return {"percentage": 0, "label": "AI Detection Timeout"}
        except json.JSONDecodeError:
            return {"percentage": 0, "label": "Invalid API Response"}
        except Exception as exc:
            return {"percentage": 0, "label": f"AI Detection Error"}

    # Run AI detection and fact-check in parallel
    ai_score, verify_result = await asyncio.gather(
        get_ai_score(),
        verify_claim_async(text),
        return_exceptions=True
    )

    # Handle potential exceptions from gather
    if isinstance(ai_score, Exception):
        ai_score = {"percentage": 0, "label": "AI Detection Unavailable"}
    if isinstance(verify_result, Exception):
        verify_result = {"claim_status": "Verification unavailable", "sources": []}

    result = {"ai_score": ai_score, **verify_result}
    cache_result(text, result)
    
    return result

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/test-gemini")
def test_gemini() -> dict[str, str]:
    return {"message": "Using Gemini API", "key_present": bool(GEMINI_API_KEY)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)