import os
import uuid
import base64
import tempfile
import subprocess
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


# =============================================
# Load environment variables
# =============================================
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")
EDEN_API_KEY = os.getenv("EDEN_API_KEY")  # NEW — EdenAI TTS
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "/usr/bin/ffmpeg")

if not GEMINI_API_KEY:
    print("⚠️ Missing GEMINI_API_KEY")
if not RUNWAY_API_KEY:
    print("⚠️ Missing RUNWAY_API_KEY")
if not EDEN_API_KEY:
    print("⚠️ Missing EDEN_API_KEY (Required for TTS)")


# =============================================
# FastAPI Setup
# =============================================
app = FastAPI(title="MedTech AI Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

temp_dir = tempfile.gettempdir()
app.mount("/videos", StaticFiles(directory=temp_dir), name="videos")


# =============================================
# Input Model
# =============================================
class RequestData(BaseModel):
    device_name: str
    purpose: str
    language: str = "en"


# =============================================
# STEP 1 — Fetch Research
# =============================================
def fetch_research(device_name: str):
    return f"Research summary for {device_name}: widely used and medically approved."


# =============================================
# STEP 2 — Gemini Script Generation
# =============================================
def generate_script(device, purpose, research, language, key):
    prompt = f"""
Write a documentary-style narration for a {purpose}-focused explainer about the medical device {device}.
Include:
- Origin
- When/where invented
- How it works
- Surprising facts
- Safety
Length ~ 70 seconds.
Language: {language}
Research:
{research}
"""

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    r = requests.post(url, json=body, headers=headers)
    if r.status_code != 200:
        raise HTTPException(500, f"Gemini Error: {r.text}")

    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


# =============================================
# STEP 3 — Compliance Check
# =============================================
def validate_compliance(script, research, key):
    prompt = f"""
Compare script with research.
Respond ONLY YES or NO.
If unsure → YES.

Research:
{research}
Script:
{script}
"""

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    r = requests.post(url, json=body, headers=headers)
    try:
        result = r.json()["candidates"][0]["content"]["parts"][0]["text"].lower()
        return "yes" in result
    except:
        return True


# =============================================
# STEP 4 — Runway GEN-2 Silent Video
# =============================================
def generate_gen2_video(prompt, key):
    url = "https://api.runwayml.com/v1/generate"

    payload = {
        "model": "gen2",
        "prompt": prompt,
        "num_frames": 200,
        "fps": 20,
        "resolution": "1080p"
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    r = requests.post(url, json=payload, headers=headers)
    if r.status_code != 200:
        raise HTTPException(500, f"Runway Error: {r.text}")

    return r.json()["output"][0]["video"]


# =============================================
# STEP 5 — EdenAI TTS (MP3)
# =============================================
def generate_audio(script, eden_key):
    url = "https://api.edenai.run/v2/audio/text_to_speech"

    payload = {
        "providers": "google",  # or "amazon", "microsoft", "ibm"
        "language": "en-US",
        "voice": "en-US-Neural2-D",
        "text": script,
        "audio_format": "mp3"
    }

    headers = {
        "Authorization": f"Bearer {eden_key}"
    }

    r = requests.post(url, json=payload, headers=headers)
    if r.status_code != 200:
        raise HTTPException(500, f"EdenAI TTS Error: {r.text}")

    # Eden AI returns Base64 audio
    audio_b64 = r.json()["google"]["audio"]
    audio_bytes = base64.b64decode(audio_b64)

    audio_path = os.path.join(temp_dir, f"audio_{uuid.uuid4().hex}.mp3")
    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    return audio_path


# =============================================
# STEP 6 — Subtitle File (SRT)
# =============================================
def create_srt(script):
    lines = script.split(". ")
    srt = ""
    current_time = 0

    for i, line in enumerate(lines):
        start = f"00:00:{current_time:02d},000"
        end = f"00:00:{current_time + 2:02d},000"
        current_time += 2
        srt += f"{i+1}\n{start} --> {end}\n{line}\n\n"

    path = os.path.join(temp_dir, f"sub_{uuid.uuid4().hex}.srt")
    with open(path, "w") as f:
        f.write(srt)
    return path


# =============================================
# STEP 7 — Merge Audio + Subtitles + Video
# =============================================
def ffmpeg_merge(video_url, audio_path, srt_path):
    raw_video_path = os.path.join(temp_dir, f"vid_{uuid.uuid4().hex}.mp4")
    with open(raw_video_path, "wb") as f:
        f.write(requests.get(video_url).content)

    final_path = os.path.join(temp_dir, f"final_{uuid.uuid4().hex}.mp4")

    cmd = [
        FFMPEG_PATH,
        "-i", raw_video_path,
        "-i", audio_path,
        "-vf", f"subtitles='{srt_path}'",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        final_path
    ]

    subprocess.run(cmd, check=True)
    return final_path


# =============================================
# API Route
# =============================================
@app.post("/generate")
def generate(data: RequestData):

    research = fetch_research(data.device_name)

    script = generate_script(
        data.device_name,
        data.purpose,
        research,
        data.language,
        GEMINI_API_KEY
    )

    compliance = validate_compliance(script, research, GEMINI_API_KEY)

    video_url = generate_gen2_video(script, RUNWAY_API_KEY)
    audio_path = generate_audio(script, EDEN_API_KEY)
    srt_path = create_srt(script)

    final_video = ffmpeg_merge(video_url, audio_path, srt_path)

    hostname = os.getenv("RENDER_EXTERNAL_HOSTNAME")
    public_url = (
        f"https://{hostname}/videos/{os.path.basename(final_video)}"
        if hostname
        else f"/videos/{os.path.basename(final_video)}"
    )

    return {
        "script": script,
        "compliance_passed": compliance,
        "video_url": public_url
    }

# =============================================
# Serve Frontend (Vite build)
# =============================================
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend/dist"))

print("Frontend path resolved to:", frontend_path)

if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    print("❌ FRONTEND DIST NOT FOUND AT:", frontend_path)


