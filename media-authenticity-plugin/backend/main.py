import os
import re
import json
import base64
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
from google.genai import types

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None
    
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_IMAGE_MODELS = (
    os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.6-flash"),
    "gemini-1.5-flash",
    "gemini-2.5-flash",
    "gemini-3.6-flash",
)
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

class ImageAnalyzeRequest(BaseModel):
    image_data: str

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
                
                def do_search():
                    """Synchronous search wrapper"""
                    return DDGS().text(query, max_results=3)
                
                results = await asyncio.wait_for(
                    loop.run_in_executor(None, do_search),
                    timeout=10.0
                )
                print(f"[DEBUG] Search results found: {len(results) if results else 0}")
                return results
            except asyncio.TimeoutError:
                print(f"[DEBUG] Search attempt {attempt + 1} timed out")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                raise
            except Exception as e:
                error_msg = str(e).lower()
                print(f"[DEBUG] Search error on attempt {attempt + 1}: {e}")
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

    prompt = f"""Analyze the text below for two separate purposes:
1. Estimate the probability that the text was AI-generated rather than human-written.
2. Detect recurring misinformation narratives, coordinated disinformation patterns, or known conspiracy themes. Consider recognizable propaganda framing and recurring claims, but do not label a pattern solely because the claim is controversial.

Return ONLY valid JSON matching this exact schema. Do not include Markdown, code fences, or any additional text:
{{
    "percentage": 85,
    "label": "85% AI-Generated",
    "pattern_detected": true,
    "narrative_summary": "Matches known health/vaccine misinformation narratives regarding fake regulatory directives."
}}

Rules:
- percentage must be an integer from 0 to 100.
- label must state the percentage followed by either "AI-Generated" or "Human-Written".
- pattern_detected must be a boolean.
- narrative_summary must be a concise explanation when pattern_detected is true, otherwise an empty string.

Text: {truncated}"""

    async def get_ai_score():
        """Get AI detection score from Gemini"""
        loop = asyncio.get_event_loop()
        try:
            def make_api_call():
                """Synchronous API call wrapper"""
                return client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
            
            response = await asyncio.wait_for(
                loop.run_in_executor(None, make_api_call),
                timeout=20.0
            )
            
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            print(f"[DEBUG] AI Score response: {response_text}")
            parsed = json.loads(response_text)
            percentage = parsed.get("percentage", 0)
            try:
                percentage = max(0, min(100, int(percentage)))
            except (TypeError, ValueError):
                percentage = 0

            label = parsed.get("label")
            if not isinstance(label, str) or not label.strip():
                label = f"{percentage}% AI-Generated"

            return {
                "ai_score": {"percentage": percentage, "label": label},
                "pattern_data": {
                    "pattern_detected": parsed.get("pattern_detected") is True,
                    "narrative_summary": (
                        parsed.get("narrative_summary")
                        if isinstance(parsed.get("narrative_summary"), str)
                        else ""
                    ),
                },
            }
        except asyncio.TimeoutError:
            print("[DEBUG] AI detection timed out")
            return {
                "ai_score": {"percentage": 0, "label": "AI Detection Timeout"},
                "pattern_data": {"pattern_detected": False, "narrative_summary": ""},
            }
        except json.JSONDecodeError as e:
            print(f"[DEBUG] JSON decode error: {e}")
            return {
                "ai_score": {"percentage": 0, "label": "Invalid API Response"},
                "pattern_data": {"pattern_detected": False, "narrative_summary": ""},
            }
        except Exception as exc:
            print(f"[DEBUG] AI detection error: {exc}")
            return {
                "ai_score": {"percentage": 0, "label": "AI Detection Error"},
                "pattern_data": {"pattern_detected": False, "narrative_summary": ""},
            }

    # Run AI detection and fact-check in parallel
    ai_score, verify_result = await asyncio.gather(
        get_ai_score(),
        verify_claim_async(text),
        return_exceptions=True
    )

    # Handle potential exceptions from gather
    if isinstance(ai_score, Exception):
        ai_score = {
            "ai_score": {"percentage": 0, "label": "AI Detection Unavailable"},
            "pattern_data": {"pattern_detected": False, "narrative_summary": ""},
        }
    if isinstance(verify_result, Exception):
        verify_result = {"claim_status": "Verification unavailable", "sources": []}

    result = {
        "ai_score": ai_score.get("ai_score", {"percentage": 0, "label": "AI Detection Unavailable"}),
        "pattern_data": ai_score.get(
            "pattern_data",
            {"pattern_detected": False, "narrative_summary": ""},
        ),
        **verify_result,
    }
    cache_result(text, result)
    
    return result

@app.post("/analyze-image")
async def analyze_image(request: ImageAnalyzeRequest) -> dict[str, Any]:
    if not request.image_data:
        raise HTTPException(status_code=400, detail="image_data cannot be empty.")

    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Gemini API key is not configured. Set GEMINI_API_KEY in backend/.env.",
        )

    try:
        image_data = request.image_data
        mime_type = "image/jpeg"
        if image_data.startswith("data:"):
            header, image_data = image_data.split(",", 1)
            mime_type = header.split(";", 1)[0].removeprefix("data:") or mime_type

        image_bytes = base64.b64decode(image_data.strip(), validate=True)
        if not image_bytes:
            raise ValueError("Decoded image is empty.")

        supported_mime_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/heic",
            "image/heif",
        }
        if mime_type not in supported_mime_types:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported image format: {mime_type}.",
            )

        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = """Analyze this image for signs of AI generation (e.g., Midjourney, DALL-E) or digital manipulation. Look for unnatural textures, warped background elements, or anatomical inconsistencies. Reply ONLY with a JSON object in this exact format:
{
  "percentage": 92,
  "label": "92% AI-Generated",
  "manipulation_details": "Unnatural blending on the subject's hands and mismatched lighting shadows."
}"""
        response = None
        model_error = None
        for model_name in dict.fromkeys(GEMINI_IMAGE_MODELS):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        prompt,
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    ),
                )
                break
            except Exception as exc:
                model_error = exc
                print(f"[DEBUG] Image model {model_name} failed: {exc}")

        if response is None:
            raise model_error or RuntimeError("No image model response.")

        response_text = (response.text or "").strip()
        if not response_text:
            raise ValueError("Gemini returned an empty response.")
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        result = json.loads(response_text.strip())
        if not isinstance(result, dict):
            raise ValueError("Gemini returned a non-object response.")

        percentage = max(0, min(100, int(result.get("percentage", 0))))
        label = result.get("label")
        details = result.get("manipulation_details")
        if not isinstance(label, str) or not label.strip():
            label = f"{percentage}% AI-Generated"
        if not isinstance(details, str):
            details = ""

        return {
            "percentage": percentage,
            "label": label,
            "manipulation_details": details,
        }
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[DEBUG] Image analysis error: {exc}")
        raise HTTPException(
            status_code=502,
            detail="Image analysis service is unavailable.",
        ) from exc

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/test-gemini")
def test_gemini() -> dict[str, str]:
    return {"message": "Using Gemini API", "key_present": bool(GEMINI_API_KEY)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)