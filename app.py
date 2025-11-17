#playback+quota limit app.py

import os
import base64
import uuid
from tempfile import NamedTemporaryFile

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import httpx
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set")
if not ORCHESTRATOR_URL:
    raise RuntimeError("ORCHESTRATOR_URL not set")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)


def transcribe_audio(path: str) -> str:
    with open(path, "rb") as f:
        res = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
        )
    text = getattr(res, "text", None)
    if text is None:
        text = str(res)
    return (text or "").strip()


def call_orchestrator(text: str, *, user_id: str, session_id: str, channel: str = "web_widget") -> dict:
    payload = {
        "channel": channel,
        "user_id": user_id,
        "session_id": session_id,
        "text": text,
    }
    resp = httpx.post(ORCHESTRATOR_URL, json=payload, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def elevenlabs_tts(text: str):
    """
    Returns (audio_base64, mime, tts_status)

    tts_status can be:
      - "ok"
      - "missing_api_key"
      - "quota_exceeded"
      - "auth_error"
      - "rate_limited"
      - "network_error"
      - "error"
    """
    if not ELEVENLABS_API_KEY:
        print("[TTS] ELEVENLABS_API_KEY missing")
        return None, None, "missing_api_key"

    if not text:
        return None, None, "error"

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL_ID,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        print("[TTS] ElevenLabs HTTP error:", status_code, e)

        if status_code == 402:
            return None, None, "quota_exceeded"
        elif status_code in (401, 403):
            return None, None, "auth_error"
        elif status_code == 429:
            return None, None, "rate_limited"
        else:
            return None, None, "error"
    except Exception as e:
        print("[TTS] ElevenLabs network error:", e)
        return None, None, "network_error"

    audio_bytes = resp.content
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    mime = resp.headers.get("Content-Type", "audio/mpeg")
    return audio_b64, mime, "ok"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/voice", methods=["POST"])
def api_voice():
    if "audio" not in request.files:
        return jsonify({"error": "no audio"}), 400

    file = request.files["audio"]
    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    with NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        file.save(tmp.name)
        path = tmp.name

    try:
        user_text = transcribe_audio(path)
        if not user_text:
            return jsonify({"error": "empty transcription"}), 200

        device_id = request.form.get("device_id")
        session_id = request.form.get("session_id")

        if not device_id:
            device_id = f"device-anon-{uuid.uuid4()}"
        if not session_id:
            session_id = f"sess-{uuid.uuid4()}"

        user_id = device_id

        orc = call_orchestrator(
            user_text,
            user_id=user_id,
            session_id=session_id,
            channel="web_widget",
        )

        reply_text = orc.get("reply_text") or orc.get("reply", {}).get("reply_text")
        if not reply_text:
            return jsonify({"error": "no reply_text", "raw": orc}), 200

        audio_b64, mime, tts_status = elevenlabs_tts(reply_text)

        return jsonify(
            {
                "user_text": user_text,
                "reply_text": reply_text,
                "audio_base64": audio_b64,
                "audio_mime": mime,
                "tts_status": tts_status,
                "tts_quota_exceeded": (tts_status == "quota_exceeded"),
            }
        )
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
