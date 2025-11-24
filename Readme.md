# Voice AI Web App

A voice-enabled web application that performs:

1.  Speech-to-Text (STT)
2.  LLM Orchestration via an MCP-compatible canonical endpoint
3.  Text-to-Speech (TTS)
4.  Browser-side audio conversation loop

Supports ElevenLabs (primary STT/TTS) with OpenAI fallback, and
persistent user identity via cookies.

## Features

### Speech-to-Text (STT)

-   Primary: ElevenLabs Scribe STT (`model_id: scribe_v1`)
-   Fallback: OpenAI Whisper (`model: whisper-1`)

### Orchestrator Integration

-   Sends a canonical request envelope to your orchestrator
    (`/canonical/voice` or `/canonical/message`)
-   Includes context, session, and request blocks
-   Authenticated using `X-API-Key`
-   Uses `request.type = "text"`

### Text-to-Speech (TTS)

-   Primary: ElevenLabs TTS (`eleven_multilingual_v2`)
-   Fallback: OpenAI TTS (`gpt-4o-mini-tts`)

### Persistent User Identity

-   Generates a `voice_user_id` cookie automatically
-   Ensures multi-turn, session-aware conversations

### Frontend

-   Records audio using WebRTC
-   Sends audio to backend and plays TTS responses

## Project Structure

    app.py              
    templates/
      index.html        
    static/
      scripts.js        
    README.md           
    .env.example        

## Requirements

-   Python 3.9+
-   Valid API keys for OpenAI, ElevenLabs, and the orchestrator

Install dependencies:

    pip install -r requirements.txt

## Environment Variables (.env)

    OPENAI_API_KEY=your_openai_key
    ORCHESTRATOR_URL=https://your-orchestrator-url/canonical/voice
    ORCHESTRATOR_API_KEY=adapter-super-secret-key-1

    ELEVENLABS_API_KEY=your_elevenlabs_key
    ELEVENLABS_VOICE_ID=EXAVITQu4vr4xnSDxMaL
    ELEVENLABS_TTS_MODEL_ID=eleven_multilingual_v2
    ELEVENLABS_STT_MODEL_ID=scribe_v1

    ORCHESTRATOR_LOCALE=en-US
    ORCHESTRATOR_TENANT=default-tenant
    ORCHESTRATOR_CLIENT_APP=voice-widget

## Running the App

    python app.py

Open in browser:

    http://localhost:5000

## Voice Pipeline

1.  User speaks into microphone
2.  STT:
    -   Try ElevenLabs STT
    -   Fallback to OpenAI Whisper
3.  Orchestrator receives canonical request envelope
4.  TTS:
    -   Try ElevenLabs TTS
    -   Fallback to OpenAI TTS
5.  Browser receives base64 audio and plays it

## API Response Example

    {
      "user_text": "Hello there",
      "reply_text": "Hi, how can I assist you today?",
      "audio_base64": "<base64_audio>",
      "audio_mime": "audio/mpeg",
      "tts_provider": "elevenlabs",
      "stt_provider": "openai_whisper",
      "user_id": "user-1ab2cd3",
      "session_id": "sess-xyz123"
    }

## Debugging

Check `stt_provider` to know which engine processed speech. Check
`tts_provider` to know which engine generated audio. Inspect
`raw_orchestrator_response` if the reply text does not appear.
