import os
import tempfile
import time
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
VEO_API_KEY = os.getenv("VEO_API_KEY")

# Optional: warn but don’t block if running locally
if not GEMINI_API_KEY or not VEO_API_KEY:
    print("⚠️  GEMINI_API_KEY or VEO_API_KEY not set — please supply via frontend or .env")

# ================================
# FastAPI app setup
# ================================
app = FastAPI(title="MedTech Animated Content Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve temp dir for videos
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
    veo_api_key: Optional[str] = None


# ================================
# STEP 1: Research (stub)
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
- Start directly with the device, not greetings.
- Use a storytelling/documentary tone.
- Cover:
  * Where and when it was invented
  * How it was invented
  * Surprising facts
  * Where it is used today
  * Technical explanation (how it works, how to use step by step)
  * Benefits and outcomes
  * Safety considerations
- Flow like a story, not like an essay.
- Language: {language}
Length: ~60–90 seconds narration.

Research summary:
{research}
"""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {gemini_key}",
    }
    body = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

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
    body = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

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
# STEP 4: Veo 3 Video Generation
# ================================
def generate_animated_video(device_name: str, script: str, purpose: str, veo_key: str) -> str:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID")
    location = "us-central1"
    model_id = "veo-3.0-generate-001"
    url = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model_id}:predictLongRunning"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {veo_key}",
    }

    prompt = (
        f"Short cinematic explainer video about {device_name}. Purpose: {purpose}. "
        f"Incorporate narration: {script[:400]}"
    )
    body = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "aspectRatio": "16:9",
            "resolution": "720p",
            "duration": "20s",
        },
    }

    # Kick off generation
    r = requests.post(url, headers=headers, json=body, timeout=60)
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Veo API init error: {r.status_code} {r.text}")

    resp = r.json()
    operation_name = resp.get("name")
    if not operation_name:
        raise HTTPException(status_code=500, detail=f"Veo API error: no operation name returned")

    # Poll for completion
    status_url = f"https://{location}-aiplatform.googleapis.com/v1/{operation_name}"
    for _ in range(60):
        time.sleep(5)
        r2 = requests.get(status_url, headers=headers)
        if r2.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Veo poll error: {r2.status_code} {r2.text}")
        data = r2.json()
        if data.get("done"):
            videos = data.get("response", {}).get("generatedVideos", [])
            if videos and "video" in videos[0]:
                return videos[0]["video"]
            raise HTTPException(status_code=500, detail=f"Veo completed but no video link found: {data}")
    raise HTTPException(status_code=500, detail="Veo video generation timed out")


# ================================
# API Endpoint
# ================================
@app.post("/generate")
def generate_content(data: RequestData):
    gemini_key = data.gemini_api_key or GEMINI_API_KEY
    veo_key = data.veo_api_key or VEO_API_KEY

    research = fetch_research(data.device_name)
    script = generate_script(data.device_name, data.purpose, research, data.language, gemini_key)
    compliance = validate_compliance(script, research, gemini_key)
    video_url = generate_animated_video(data.device_name, script, data.purpose, veo_key)

    return {
        "device": data.device_name,
        "purpose": data.purpose,
        "script": script,
        "compliance_passed": compliance,
        "research_used": research,
        "video_url": video_url,
    }


# ================================
# Serve frontend (if built)
# ================================
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))
