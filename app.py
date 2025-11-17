#Revert app.py

import os
import uuid
from tempfile import NamedTemporaryFile

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import httpx

# Load .env (Railway will override with environment variables)
load_dotenv()

app = Flask(__name__)

# MCP Orchestrator endpoint
ORCHESTRATOR_URL = (
    os.getenv("MCP_ORCH_URL") 
    or os.getenv("ORCHESTRATOR_URL")
)

# Import STT + TTS modules (your existing helper scripts)
from stt import transcribe
from tts import tts


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/voice", methods=["POST"])
def api_voice():
    """
    Voice API:
      1. Receives microphone recording (WebM)
      2. Transcribes speech → text (STT)
      3. Sends text to MCP Orchestrator
      4. Receives reply text from MCP
      5. Converts reply to audio (TTS)
      6. Sends JSON back to frontend

    Frontend sends:
      - audio: WebM file
      - device_id: persistent identity (per device)
      - session_id: unique per browser tab / page load
    """

    # -------------------------------------------------------
    # 1. Validate audio
    # -------------------------------------------------------
    if "audio" not in request.files:
        return jsonify({"error": "no_audio"}), 400

    audio_file = request.files["audio"]

    # Save temp file
    with NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        audio_file.save(tmp.name)
        audio_path = tmp.name

    try:
        # -------------------------------------------------------
        # 2. Speech-to-Text (STT)
        # -------------------------------------------------------
        user_text = transcribe(audio_path) or ""
        if not user_text.strip():
            return jsonify({"error": "empty_transcript"}), 200

        # -------------------------------------------------------
        # 3. Handle multi-session IDs
        # -------------------------------------------------------
        device_id = request.form.get("device_id")
        session_id = request.form.get("session_id")

        if not device_id:
            device_id = f"device-anon-{uuid.uuid4()}"

        if not session_id:
            session_id = f"sess-{uuid.uuid4()}"

        # Device identity = “user”
        user_id = device_id  

        # -------------------------------------------------------
        # 4. Call MCP Orchestrator
        # -------------------------------------------------------
        if not ORCHESTRATOR_URL:
            return jsonify({
                "error": "missing_orchestrator_url",
                "details": "Set MCP_ORCH_URL or ORCHESTRATOR_URL in environment variables."
            }), 500

        payload = {
            "channel": "web_widget",
            "user_id": user_id,
            "session_id": session_id,
            "text": user_text,
        }

        try:
            orch_response = httpx.post(ORCHESTRATOR_URL, json=payload, timeout=60.0)
            orch_response.raise_for_status()
            orch_data = orch_response.json()
        except Exception as e:
            return jsonify({"error": "orchestrator_error", "details": str(e)}), 500

        reply_text = orch_data.get("reply_text") or orch_data.get("decision") or ""

        # For auto-reset on completion
        session_done = bool(
            orch_data.get("session_done") or 
            orch_data.get("debug", {}).get("session_done")
        )

        # -------------------------------------------------------
        # 5. Convert reply text → audio (TTS)
        # -------------------------------------------------------
        audio_b64, audio_mime = tts(reply_text)

        # -------------------------------------------------------
        # 6. Return response to the Listen Client UI
        # -------------------------------------------------------
        return jsonify({
            "user_text": user_text,
            "reply_text": reply_text,
            "audio_base64": audio_b64,
            "audio_mime": audio_mime,
            "session_done": session_done,
        })

    finally:
        # Cleanup temp file
        try:
            os.remove(audio_path)
        except Exception:
            pass


if __name__ == "__main__":
    # Local testing only — Railway uses gunicorn via Procfile
    app.run(host="0.0.0.0", port=8000, debug=True)
