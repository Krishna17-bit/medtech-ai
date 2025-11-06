import os
import tempfile
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional

# ================================
# Load environment variables
# ================================
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")

if not GEMINI_API_KEY:
    print("⚠️  GEMINI_API_KEY not set — please supply via .env or frontend.")

if not RUNWAY_API_KEY:
    print("⚠️  RUNWAY_API_KEY not set — video generation will fail.")

# ================================
# FastAPI app setup
# ================================
app = FastAPI(title="MedTech AI Content Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================================
# Serve temporary directory for assets
# ================================
temp_dir = tempfile.gettempdir()
app.mount("/videos", StaticFiles(directory=temp_dir), name="videos")

# ================================
# Request schema
# ================================
class RequestData(BaseModel):
    device_name: str
    purpose: str
    language: str = "en"
    gemini_api_key: Optional[str] = None
    runway_api_key: Optional[str] = None


# ================================
# STEP 1: Research (placeholder)
# ================================
def fetch_research(device_name: str) -> str:
    return (
        f"Research summary for {device_name}: invented in the 20th century, "
        f"FDA-cleared, and widely used globally."
    )


# ================================
# STEP 2: Gemini Script Generation
# ================================
def generate_script(device_name: str, purpose: str, research: str, language: str, gemini_key: str) -> str:
    prompt = f"""
Write a story-style narration for a {purpose}-focused explainer about the medical device: {device_name}.

Guidelines:
- Start directly with the device (no greetings)
- Storytelling/documentary tone
- Include:
  * When and where it was invented
  * How it was invented
  * Surprising facts
  * Where it is used today
  * How it works (technical explanation)
  * Benefits and outcomes
  * Safety considerations
Language: {language}
Length: about 60–90 seconds of narration.

Research summary:
{research}
"""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {gemini_key}",
    }
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        r = requests.post(url, headers=headers, json=body, timeout=60)
        if r.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Gemini API error: {r.status_code} {r.text}")
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini script generation failed: {str(e)}")


# ================================
# STEP 3: Compliance Validation
# ================================
def validate_compliance(script: str, research: str, gemini_key: str) -> bool:
    prompt = f"""
Compare this script with the research summary.
Respond ONLY with 'YES' if compliant, 'NO' if unsupported claims.
If unsure, respond 'YES'.

Research:
{research}

Script:
{script}
"""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {gemini_key}",
    }
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        r = requests.post(url, headers=headers, json=body, timeout=45)
        if r.status_code != 200:
            print(f"⚠️ Compliance check API error: {r.text}")
            return True
        data = r.json()
        result = data["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
        return "yes" in result
    except Exception as e:
        print(f"⚠️ Compliance validation failed: {e}")
        return True


# ================================
# STEP 4: RunwayML Video Generation
# ================================
def generate_video_with_runway(script: str, runway_key: str) -> Optional[str]:
    try:
        url = "https://api.runwayml.com/v1/gen2/video"
        headers = {
            "Authorization": f"Bearer {runway_key}",
            "Content-Type": "application/json",
        }
        body = {
            "prompt": script,
            "model": "gen2",
            "duration": 10,
            "ratio": "16:9"
        }

        r = requests.post(url, headers=headers, json=body, timeout=60)
        if r.status_code != 200:
            print(f"⚠️ Runway video error: {r.text}")
            return None

        data = r.json()
        return data.get("output_url")
    except Exception as e:
        print(f"⚠️ Runway video generation failed: {e}")
        return None


# ================================
# API Endpoint
# ================================
@app.post("/generate")
def generate_content(data: RequestData):
    gemini_key = data.gemini_api_key or GEMINI_API_KEY
    runway_key = data.runway_api_key or RUNWAY_API_KEY

    if not gemini_key:
        raise HTTPException(status_code=400, detail="Missing Gemini API key.")

    research = fetch_research(data.device_name)
    script = generate_script(data.device_name, data.purpose, research, data.language, gemini_key)
    compliance = validate_compliance(script, research, gemini_key)

    video_url = None
    if runway_key:
        video_url = generate_video_with_runway(script, runway_key)

    return {
        "device": data.device_name,
        "purpose": data.purpose,
        "script": script,
        "compliance_passed": compliance,
        "research_used": research,
        "video_url": video_url,
    }


# ================================
# Serve frontend (if exists)
# ================================
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))
