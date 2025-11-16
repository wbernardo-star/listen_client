#listen_client-main/app.py


import os
from tempfile import NamedTemporaryFile
from flask import Flask, render_template, request, jsonify
import httpx
import uuid
from dotenv import load_dotenv

load_dotenv()

ORCHESTRATOR_URL = os.getenv("MCP_ORCH_URL")

from tts import tts
from stt import transcribe

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/voice", methods=["POST"])
def api_voice():
    if "audio" not in request.files:
        return jsonify({"error": "no_audio"}), 400

    f = request.files["audio"]

    with NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        f.save(tmp.name)
        audio_path = tmp.name

    try:
        # --- STT ---
        text = transcribe(audio_path)
        if not text:
            return jsonify({"error": "empty_transcript"}), 200

        # ===========================================================
        # NEW: Get client_id from widget; create session_id
        # ===========================================================
        client_id = request.form.get("client_id")
        if not client_id:
            client_id = f"web-anon-{uuid.uuid4()}"

        session_id = client_id
        user_id = client_id

        # ===========================================================
        # Call MCP Orchestrator using client session IDs
        # ===========================================================
        payload = {
            "channel": "web_widget",
            "user_id": user_id,
            "session_id": session_id,
            "text": text
        }

        r = httpx.post(ORCHESTRATOR_URL, json=payload, timeout=40.0)
        r.raise_for_status()

        orchestrator = r.json()
        reply_text = orchestrator.get("reply_text", "")
        
        # Does orchestrator say the flow is complete?
        session_done = orchestrator.get("session_done", False)
        if orchestrator.get("debug", {}).get("session_done"):
            session_done = True

        # --- ElevenLabs TTS ---
        audio_b64, mime = tts(reply_text)

        return jsonify({
            "user_text": text,
            "reply_text": reply_text,
            "audio_base64": audio_b64,
            "audio_mime": mime,
            "session_done": session_done,
        })

    finally:
        try:
            os.remove(audio_path)
        except:
            pass


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
