# Voice Listening Client

This application is a Flask‑based voice interface that enables fully
interactive voice conversations using:

-   Speech‑to‑Text (STT)
-   Orchestrator (MCP adapter) processing
-   Text‑to‑Speech (TTS)
-   A browser‑based floating widget or embeddable iframe

It supports ElevenLabs for STT and TTS, with OpenAI Whisper and OpenAI
TTS as fallback providers.

------------------------------------------------------------------------

## Features

### Speech‑to‑Text (STT)

-   Primary: ElevenLabs Scribe STT
-   Fallback: OpenAI Whisper (`whisper-1`)

### Orchestrator Integration

-   Uses Canonical Request Envelope v1.1
-   Sends `context`, `session`, `request`, and `observability` blocks
-   Adds required headers:
    -   `X-API-Key`
    -   `Content-Type: application/json`

### Text‑to‑Speech (TTS)

-   Primary: ElevenLabs TTS
-   Fallback: OpenAI TTS (`gpt-4o-mini-tts`)

### Web Integration

-   Returns JSON containing:
    -   `user_text`
    -   `reply_text`
    -   `audio_base64`
    -   `audio_mime`
    -   `tts_provider`
    -   `stt_provider`
-   Browser widget plays the synthesized audio automatically

------------------------------------------------------------------------

## Project Structure

    app.py
    templates/
        index.html
    static/
        app.js
        embed.js
    .env

------------------------------------------------------------------------

## Environment Variables (.env)

    OPENAI_API_KEY=
    ORCHESTRATOR_URL=https://your-orchestrator-url/canonical/voice
    ORCHESTRATOR_API_KEY=

    ELEVENLABS_API_KEY=
    ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
    ELEVENLABS_TTS_MODEL_ID=eleven_multilingual_v2
    ELEVENLABS_STT_MODEL_ID=scribe_v1

    ORCHESTRATOR_CLIENT_APP=voice-widget
    ORCHESTRATOR_TENANT=default-tenant
    ORCHESTRATOR_LOCALE=en-US

------------------------------------------------------------------------

## Running the App

    python app.py

Open in browser:

    http://localhost:5000

------------------------------------------------------------------------

## Voice Pipeline

### 1. Browser sends audio (`webm`)

### 2. STT (ElevenLabs → Whisper)

### 3. Canonical Orchestrator request

### 4. TTS (ElevenLabs → OpenAI)

### 5. Audio returned to the browser and played

------------------------------------------------------------------------

## `/api/voice` Response Example

``` json
{
  "user_text": "Hello there",
  "reply_text": "Hi! How can I help?",
  "audio_base64": "<base64>",
  "audio_mime": "audio/mpeg",
  "tts_provider": "elevenlabs",
  "stt_provider": "openai_whisper",
  "user_id": "user-123",
  "session_id": "sess-abc"
}
```

------------------------------------------------------------------------

# Embedding the Listening Client in Any Web App

The listening interface can be embedded on top of any website using a
single script include.

This script injects:

-   A floating launcher button (bottom‑right)
-   An iframe overlay that loads the full voice UI

------------------------------------------------------------------------

## 1. Hosted URLs

Assume your deployment:

    https://your-voice-app.example.com

Important URLs:

-   UI: `https://your-voice-app.example.com/`
-   Embed script: `https://your-voice-app.example.com/static/embed.js`

------------------------------------------------------------------------

## 2. Recommended Embed Snippet

Place this inside the `<body>` of any site:

``` html
<script
  src="https://your-voice-app.example.com/static/embed.js"
  data-assistant-url="https://your-voice-app.example.com/"
  async
></script>
```

This will:

-   Render a floating button labeled "Blink"
-   On click, display your full voice assistant inside a
    microphone‑enabled iframe

The iframe is automatically configured with:

    allow="microphone *"

------------------------------------------------------------------------

## 3. Direct iframe Embed (Alternative)

You may embed the assistant directly:

``` html
<iframe
  src="https://your-voice-app.example.com/"
  style="
    position: fixed;
    right: 24px;
    bottom: 80px;
    width: 400px;
    height: 640px;
    border-radius: 16px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    z-index: 9999;
  "
  allow="microphone *"
></iframe>
```

In this mode you control:

-   Opening/closing UI
-   Position
-   Button behavior

------------------------------------------------------------------------

## 4. Requirements

-   Must run on HTTPS for mic access
-   Cross-domain embedding requires proper CORS settings
-   Never expose API keys in client-side HTML/JS

------------------------------------------------------------------------

## Frontend Example Snippet (Using `/api/voice`)

``` javascript
async function sendAudio(blob) {
  const form = new FormData();
  form.append("audio", blob);

  const r = await fetch("/api/voice", {
    method: "POST",
    body: form
  });

  const data = await r.json();
  const audio = new Audio("data:" + data.audio_mime + ";base64," + data.audio_base64);
  audio.play();
}
```

------------------------------------------------------------------------

## Deployment Notes

    gunicorn -w 4 app:app

HTTPS is required for microphone functionality.

------------------------------------------------------------------------
