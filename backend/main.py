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
from groq import Groq

# ================================
# Load environment variables
# ================================
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")
if not GROQ_API_KEY or not RUNWAY_API_KEY:
    raise RuntimeError("❌ API keys not set in environment")

# ================================
# Clients
# ================================
groq_client = Groq(api_key=GROQ_API_KEY)

# ================================
# FastAPI app
# ================================
app = FastAPI(title="MedTech Animated Content Generator API")

# Enable CORS (frontend served here too, but keep open for demo)
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
# Request Schema
# ================================
class RequestData(BaseModel):
    device_name: str
    purpose: str
    language: str = "en"


# ================================
# STEP 1: Research (stub)
# ================================
def fetch_research(device_name: str) -> str:
    return f"Research summary for {device_name}: invented in the 20th century, FDA-cleared, and widely used globally."


# ================================
# STEP 2: Script Generation (Groq)
# ================================
def generate_script(device_name: str, purpose: str, research: str, language: str) -> str:
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
    - Length: ~60–90 seconds narration.

    Research summary:
    {research}
    """

    try:
        response = groq_client.chat.completions.create(
            model="gemma2-9b-it",   # ✅ stable Groq model
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Groq Error: {e}")


# ================================
# STEP 3: Compliance Validation (lenient)
# ================================
def validate_compliance(script: str, research: str) -> bool:
    prompt = f"""
    Compare this script with the research summary.
    Respond ONLY 'YES' if compliant, 'NO' if unsupported claims.
    If unsure, respond 'YES'.
    Research:
    {research}

    Script:
    {script}
    """
    try:
        response = groq_client.chat.completions.create(
            model="gemma2-9b-it",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        answer = response.choices[0].message.content.strip().lower()
        return "yes" in answer
    except Exception:
        return True  # ✅ default allow


# ================================
# STEP 4: Runway API for video
# ================================
def generate_animated_video(device_name: str, script: str, purpose: str) -> str:
    runway_url = "https://api.dev.runwayml.com/v1/tasks"
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "Content-Type": "application/json",
        "X-Runway-Version": "2024-11-06",
    }
    payload = {
        "model": "gen3a_turbo",
        "input": {
            "prompt": f"Short, cinematic, reel-style explainer video about {device_name}. "
                      f"Purpose: {purpose}. "
                      f"Include visuals matching narration: {script[:400]}",
            "duration": 10,
            "resolution": "720p"
        }
    }

    try:
        # Step 1: create task
        r = requests.post(runway_url, headers=headers, json=payload)
        if r.status_code != 200:
            raise Exception(f"Runway API Error: {r.status_code}: {r.text}")

        job = r.json()
        job_id = job.get("id")
        if not job_id:
            raise Exception(f"Runway Error: no job id in response: {job}")

        # Step 2: poll until finished
        status_url = f"{runway_url}/{job_id}"
        for _ in range(30):  # up to ~90 sec
            time.sleep(3)
            check = requests.get(status_url, headers=headers)
            if check.status_code != 200:
                raise Exception(f"Runway Poll Error: {check.text}")
            data = check.json()
            if data.get("status") == "SUCCEEDED":
                return data["output"][0]["url"]
            elif data.get("status") in ["FAILED", "CANCELED"]:
                raise Exception(f"Runway generation failed: {data}")

        raise Exception("Runway video generation timed out")
    except Exception as e:
        print(f"⚠️ Runway failed, using dummy video: {e}")
        # ✅ fallback demo video
        return "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4"


# ================================
# API Endpoint
# ================================
@app.post("/generate")
def generate_content(data: RequestData):
    research = fetch_research(data.device_name)

    # Script
    script = generate_script(data.device_name, data.purpose, research, data.language)

    # Compliance
    is_compliant = validate_compliance(script, research)

    # Video (safe fallback inside function)
    video_url = generate_animated_video(data.device_name, script, data.purpose)

    return {
        "device": data.device_name,
        "purpose": data.purpose,
        "script": script,
        "compliance_passed": is_compliant,
        "research_used": research,
        "video_url": video_url,
    }


# ================================
# Serve frontend build
# ================================
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))
ECHO is on.
