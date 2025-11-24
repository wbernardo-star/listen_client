#listenclient fix app.py

import os
import base64
import uuid
from tempfile import NamedTemporaryFile

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import httpx
from openai import OpenAI

load_dotenv()

# ---------------------------------------------------------
#  Environment variables
# ---------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL")
ORCHESTRATOR_API_KEY = os.getenv("ORCHESTRATOR_API_KEY")  # should match your PowerShell $apiKey

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set")
if not ORCHESTRATOR_URL:
    raise RuntimeError("ORCHESTRATOR_URL not set")
if not ORCHESTRATOR_API_KEY:
    raise RuntimeError("ORCHESTRATOR_API_KEY not set (should be your adapter-super-secret-key-1)")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)


# ---------------------------------------------------------
#  Whisper STT
# ---------------------------------------------------------
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


# ---------------------------------------------------------
#  MCP Orchestrator call (multi-session aware)
# ---------------------------------------------------------
def call_orchestrator(
    text: str,
    *,
    user_id: str,
    session_id: str,
    channel: str = "web_widget",
) -> dict:
    # Shape payload the way /canonical/voice expects:
    # { "context": {...}, "session": {...}, "request": {...} }
    payload = {
        "context": {
            "channel": channel,
            "user_id": user_id,
        },
        "session": {
            "session_id": session_id,
            "user_id": user_id,  # required according to error: body.session.user_id
        },
        "request": {
            "type": "input_text",
            "input_text": text,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-Key": ORCHESTRATOR_API_KEY,
    }

    resp = httpx.post(
        ORCHESTRATOR_URL,
        json=payload,
        headers=headers,
        timeout=30.0,
    )

    # If the orchestrator returns an error, don't raise — surface details instead
    if resp.status_code >= 400:
        print("=== Orchestrator HTTP error ===")
        print("Status :", resp.status_code)
        print("URL    :", ORCHESTRATOR_URL)
        print("Headers:", headers)
        print("Body   :", resp.text)
        print("Payload:", payload)

        return {
            "error": "orchestrator_http_error",
            "status_code": resp.status_code,
            "body": resp.text,
        }

    # If success, return JSON payload
    try:
        return resp.json()
    except ValueError:
        # Not JSON, return raw body
        return {
            "error": "orchestrator_non_json_response",
            "status_code": resp.status_code,
            "body": resp.text,
        }


# ---------------------------------------------------------
#  Primary TTS: ElevenLabs
# ---------------------------------------------------------
def elevenlabs_tts(text: str):
    """
    Primary TTS provider.
    Returns (audio_base64, mime) or (None, None) on error.
    """
    if not ELEVENLABS_API_KEY:
        print("[TTS] ELEVENLABS_API_KEY missing, skipping ElevenLabs.")
        return None, None

    if not text:
        return None, None

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
    except Exception as e:
        print("[TTS] ElevenLabs error, will fallback to OpenAI TTS:", e)
        return None, None

    audio_bytes = resp.content
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    mime = resp.headers.get("Content-Type", "audio/mpeg")
    return audio_b64, mime


# ---------------------------------------------------------
#  Fallback TTS: OpenAI audio.speech
# ---------------------------------------------------------
def openai_tts_fallback(text: str):
    """
    Fallback TTS using OpenAI's TTS models.
    Returns (audio_base64, mime) or (None, None) on error.
    """
    if not text:
        return None, None

    try:
        audio = openai_client.audio.speech.create(
            model="gpt-4o-mini-tts",   # or "tts-1" / another available TTS model
            voice="alloy",             # default OpenAI voice
            input=text,
        )

        audio_bytes = audio.read()
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        mime = "audio/mpeg"
        print("[TTS] OpenAI TTS fallback succeeded.")
        return audio_b64, mime

    except Exception as e:
        print("[TTS] OpenAI TTS fallback error:", e)
        return None, None


# ---------------------------------------------------------
#  Routes
# ---------------------------------------------------------
@app.route("/")
def index():
    # Just render the page; user_id cookie will be created on first /api/voice call
    return render_template("index.html")


@app.route("/api/voice", methods=["POST"])
def api_voice():
    # --- Persistent user_id via cookie ---
    user_id = request.cookies.get("voice_user_id")
    if not user_id:
        user_id = f"user-{uuid.uuid4()}"  # e.g. user-7c0c8c3a-bd38-4a9c-b9b4-1d28d2e3c4ff

    # Optional: session_id can still come from frontend or be generated per request
    session_id = request.form.get("session_id")
    if not session_id:
        session_id = f"sess-{uuid.uuid4()}"

    # Early error: no audio
    if "audio" not in request.files:
        resp = jsonify({"error": "no audio"})
        resp.set_cookie(
            "voice_user_id",
            user_id,
            max_age=60 * 60 * 24 * 365,  # 1 year
            httponly=True,
            samesite="Lax",
        )
        return resp, 400

    file = request.files["audio"]
    if file.filename == "":
        resp = jsonify({"error": "empty filename"})
        resp.set_cookie(
            "voice_user_id",
            user_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="Lax",
        )
        return resp, 400

    # Save temp audio file
    with NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        file.save(tmp.name)
        path = tmp.name

    try:
        # 1) STT (Whisper)
        user_text = transcribe_audio(path)
        if not user_text:
            resp = jsonify({"error": "empty transcription"})
            resp.set_cookie(
                "voice_user_id",
                user_id,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                samesite="Lax",
            )
            return resp, 200

        # 2) Call MCP Orchestrator
        orc = call_orchestrator(
            user_text,
            user_id=user_id,
            session_id=session_id,
            channel="web_widget",
        )

        # If orchestrator returned an error, surface it to the client
        if isinstance(orc, dict) and orc.get("error"):
            resp = jsonify(
                {
                    "error": "orchestrator_call_failed",
                    "details": orc,
                }
            )
            resp.set_cookie(
                "voice_user_id",
                user_id,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                samesite="Lax",
            )
            return resp, 502

        reply_text = orc.get("reply_text") or orc.get("reply", {}).get("reply_text")
        if not reply_text:
            resp = jsonify({"error": "no reply_text", "raw": orc})
            resp.set_cookie(
                "voice_user_id",
                user_id,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                samesite="Lax",
            )
            return resp, 200

        # 3) TTS: try ElevenLabs first
        audio_b64, mime = elevenlabs_tts(reply_text)

        # 4) If ElevenLabs fails → fallback to OpenAI TTS
        tts_provider = "elevenlabs"
        if not audio_b64:
            audio_b64, mime = openai_tts_fallback(reply_text)
            tts_provider = "openai" if audio_b64 else "none"

        resp = jsonify(
            {
                "user_text": user_text,
                "reply_text": reply_text,
                "audio_base64": audio_b64,
                "audio_mime": mime,
                "tts_provider": tts_provider,
                "user_id": user_id,
                "session_id": session_id,
            }
        )
        resp.set_cookie(
            "voice_user_id",
            user_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="Lax",
        )
        return resp

    finally:
        try:
            os.remove(path)
        except Exception:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
