#listenclient fix app.py

import os
import base64
import uuid
from datetime import datetime, timezone
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
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL")  # e.g. https://.../canonical/voice
ORCHESTRATOR_API_KEY = os.getenv("ORCHESTRATOR_API_KEY")  # adapter-super-secret-key-1

# Optional context metadata
ORCHESTRATOR_LOCALE = os.getenv("ORCHESTRATOR_LOCALE", "en-US")
ORCHESTRATOR_TENANT = os.getenv("ORCHESTRATOR_TENANT", "default-tenant")
ORCHESTRATOR_CLIENT_APP = os.getenv("ORCHESTRATOR_CLIENT_APP", "voice-widget")

# ElevenLabs
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
ELEVENLABS_TTS_MODEL_ID = os.getenv("ELEVENLABS_TTS_MODEL_ID", "eleven_multilingual_v2")
ELEVENLABS_STT_MODEL_ID = os.getenv("ELEVENLABS_STT_MODEL_ID", "scribe_v1")  # STT

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set")
if not ORCHESTRATOR_URL:
    raise RuntimeError("ORCHESTRATOR_URL not set")
if not ORCHESTRATOR_API_KEY:
    raise RuntimeError("ORCHESTRATOR_API_KEY not set (should be your adapter-super-secret-key-1)")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)


# =========================================================
#  STT (Speech-to-Text)
#   1) Try ElevenLabs Scribe STT
#   2) Fallback to OpenAI Whisper
# =========================================================

def elevenlabs_stt(path: str):
    """
    Primary STT with ElevenLabs Scribe.
    Returns (text, provider_name) or (None, None) on error.
    """
    if not ELEVENLABS_API_KEY:
        print("[STT] ELEVENLABS_API_KEY missing, skipping ElevenLabs STT.")
        return None, None

    url = "https://api.elevenlabs.io/v1/speech-to-text/convert"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
    }
    # According to ElevenLabs docs, you send the file + model_id.  [oai_citation:0‡ElevenLabs](https://elevenlabs.io/docs/api-reference/speech-to-text/convert?utm_source=chatgpt.com)
    files = {
        "file": open(path, "rb"),
    }
    data = {
        "model_id": ELEVENLABS_STT_MODEL_ID,
    }

    try:
        resp = httpx.post(url, headers=headers, files=files, data=data, timeout=60.0)
        resp.raise_for_status()
        j = resp.json()
        # Typical STT response includes a "text" field.  [oai_citation:1‡ElevenLabs](https://elevenlabs.io/docs/capabilities/speech-to-text?utm_source=chatgpt.com)
        text = j.get("text") or j.get("transcription", {}).get("text")
        if not text:
            print("[STT] ElevenLabs STT returned no text field:", j)
            return None, None
        print("[STT] ElevenLabs STT succeeded.")
        return text.strip(), "elevenlabs"
    except Exception as e:
        print("[STT] ElevenLabs STT error, will fallback to OpenAI Whisper:", e)
        return None, None
    finally:
        try:
            files["file"].close()
        except Exception:
            pass


def openai_whisper_stt(path: str):
    """
    Fallback STT with OpenAI Whisper.
    Returns (text, provider_name) or (None, None) on error.
    """
    try:
        with open(path, "rb") as f:
            res = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )
        text = getattr(res, "text", None)
        if text is None:
            text = str(res)
        text = (text or "").strip()
        if not text:
            print("[STT] OpenAI Whisper returned empty text.")
            return None, None
        print("[STT] OpenAI Whisper succeeded.")
        return text, "openai_whisper"
    except Exception as e:
        print("[STT] OpenAI Whisper error:", e)
        return None, None


def transcribe_audio(path: str):
    """
    High-level STT wrapper:
    1) Try ElevenLabs STT
    2) Fallback to OpenAI Whisper
    """
    text, provider = elevenlabs_stt(path)
    if text:
        return text, provider or "elevenlabs"

    text, provider = openai_whisper_stt(path)
    if text:
        return text, provider or "openai_whisper"

    return "", None


# =========================================================
#  Orchestrator Call (/canonical/voice-style)
# =========================================================

def call_orchestrator(
    text: str,
    *,
    user_id: str,
    session_id: str,
    channel: str = "web_widget",
) -> dict:
    """
    Call the /canonical/voice endpoint with the shape it expects:
    {
      "context": { ... },
      "session": { ... },
      "request": {
        "type": "text",
        "text": "<user text>"
      }
    }
    """

    payload = {
        "context": {
            "channel": channel,
            "user_id": user_id,
            "locale": ORCHESTRATOR_LOCALE,
            "tenant": ORCHESTRATOR_TENANT,
            "client_app": ORCHESTRATOR_CLIENT_APP,
        },
        "session": {
            "session_id": session_id,
            "user_id": user_id,
        },
        "request": {
            "type": "text",   # supported types: text, audio (we use text)
            "text": text,
            "metadata": {
                "raw_transcript": text,
            },
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

    try:
        data = resp.json()
    except ValueError:
        data = {
            "error": "orchestrator_non_json_response",
            "status_code": resp.status_code,
            "body": resp.text,
        }

    print("=== Orchestrator response OK ===")
    print(data)
    return data


# =========================================================
#  TTS (Text-to-Speech)
#   1) ElevenLabs TTS
#   2) Fallback to OpenAI TTS
# =========================================================

def elevenlabs_tts(text: str):
    """
    Primary TTS: ElevenLabs.
    Returns (audio_base64, mime, provider) or (None, None, None) on error.
    """
    if not ELEVENLABS_API_KEY:
        print("[TTS] ELEVENLABS_API_KEY missing, skipping ElevenLabs TTS.")
        return None, None, None

    if not text:
        return None, None, None

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_TTS_MODEL_ID,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        resp.raise_for_status()
    except Exception as e:
        print("[TTS] ElevenLabs TTS error, will fallback to OpenAI TTS:", e)
        return None, None, None

    audio_bytes = resp.content
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    mime = resp.headers.get("Content-Type", "audio/mpeg")
    print("[TTS] ElevenLabs TTS succeeded.")
    return audio_b64, mime, "elevenlabs"


def openai_tts_fallback(text: str):
    """
    Fallback TTS using OpenAI's TTS models.
    Returns (audio_base64, mime, provider) or (None, None, None) on error.
    """
    if not text:
        return None, None, None

    try:
        audio = openai_client.audio.speech.create(
            model="gpt-4o-mini-tts",   # or "tts-1" / another available TTS model
            voice="alloy",
            input=text,
        )

        audio_bytes = audio.read()
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        mime = "audio/mpeg"
        print("[TTS] OpenAI TTS fallback succeeded.")
        return audio_b64, mime, "openai"
    except Exception as e:
        print("[TTS] OpenAI TTS fallback error:", e)
        return None, None, None


# =========================================================
#  Routes
# =========================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/voice", methods=["POST"])
def api_voice():
    # Persistent user_id via cookie
    user_id = request.cookies.get("voice_user_id")
    if not user_id:
        user_id = f"user-{uuid.uuid4()}"

    # Session can be passed from frontend or generated server-side
    session_id = request.form.get("session_id")
    if not session_id:
        session_id = f"sess-{uuid.uuid4()}"

    # Early error: no audio
    if "audio" not in request.files:
        resp = jsonify({"error": "no audio"})
        resp.set_cookie("voice_user_id", user_id, max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax")
        return resp, 400

    file = request.files["audio"]
    if file.filename == "":
        resp = jsonify({"error": "empty filename"})
        resp.set_cookie("voice_user_id", user_id, max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax")
        return resp, 400

    # Save temp audio file
    with NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        file.save(tmp.name)
        path = tmp.name

    try:
        # 1) STT
        user_text, stt_provider = transcribe_audio(path)
        if not user_text:
            resp = jsonify({"error": "empty transcription", "stt_provider": stt_provider})
            resp.set_cookie("voice_user_id", user_id, max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax")
            return resp, 200

        # 2) Orchestrator
        orc = call_orchestrator(
            user_text,
            user_id=user_id,
            session_id=session_id,
            channel="web_widget",
        )

        # Only treat as a hard error if our wrapper signaled it
        if isinstance(orc, dict) and orc.get("error") == "orchestrator_http_error":
            resp = jsonify(
                {
                    "error": "orchestrator_call_failed",
                    "details": orc,
                    "stt_provider": stt_provider,
                }
            )
            resp.set_cookie("voice_user_id", user_id, max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax")
            return resp, 502

        # 3) Extract reply_text from orchestrator response
        reply_text = None
        if isinstance(orc, dict):
            # Common shapes
            reply_text = (
                (orc.get("reply") or {}).get("reply_text")
                or orc.get("reply_text")
                or (orc.get("response") or {}).get("text")
                or orc.get("text")
            )

        if not reply_text:
            # Fallback: at least speak *something* so UI isn't silent
            reply_text = "I received your message, but I could not understand the response from the orchestrator."
            print("[Orchestrator] No clear reply_text field in response, using fallback.")

        # 4) TTS
        audio_b64, mime, tts_provider = elevenlabs_tts(reply_text)
        if not audio_b64:
            audio_b64, mime, tts_provider = openai_tts_fallback(reply_text)
        if not audio_b64:
            tts_provider = None

        resp = jsonify(
            {
                "user_text": user_text,
                "reply_text": reply_text,
                "audio_base64": audio_b64,
                "audio_mime": mime,
                "tts_provider": tts_provider,
                "stt_provider": stt_provider,
                "user_id": user_id,
                "session_id": session_id,
                "raw_orchestrator_response": orc,
            }
        )
        resp.set_cookie("voice_user_id", user_id, max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax")
        return resp

    finally:
        try:
            os.remove(path)
        except Exception:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
