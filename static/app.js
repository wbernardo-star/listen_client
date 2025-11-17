// ============================================================
// Matrix Voice Assistant - app.js
// - Per-device ID  (persistent in localStorage)
// - Per-page/tab SESSION_ID
// - Shows both IDs on page
// - Uses visible <audio id="replyAudio"> player for TTS
// ============================================================

(() => {
  console.log("[MatrixVA] app.js loaded");

  // -------------------- DEVICE ID (per device) --------------------
  function getOrCreateDeviceId() {
    const key = "matrix_device_id";
    try {
      let id = localStorage.getItem(key);
      if (!id) {
        id =
          "device-" +
          (crypto.randomUUID
            ? crypto.randomUUID()
            : Math.random().toString(36).slice(2));
        localStorage.setItem(key, id);
      }
      return id;
    } catch (e) {
      return "device-anon-" + Math.random().toString(36).slice(2);
    }
  }
  const DEVICE_ID = getOrCreateDeviceId();
  console.log("[MatrixVA] DEVICE_ID:", DEVICE_ID);

  // -------------------- SESSION ID (per page/tab) --------------------
  const SESSION_ID =
    "sess-" +
    (crypto.randomUUID
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2));
  console.log("[MatrixVA] SESSION_ID:", SESSION_ID);

  // -------------------- Inject IDs into webpage labels --------------------
  const deviceLabelEl = document.getElementById("deviceIdLabel");
  const sessionLabelEl = document.getElementById("sessionIdLabel");
  if (deviceLabelEl) deviceLabelEl.textContent = DEVICE_ID;
  if (sessionLabelEl) sessionLabelEl.textContent = SESSION_ID;

  // ---------- DOM elements (Matrix HTML) ----------
  const micButton = document.getElementById("micButton");
  const micLabel = document.getElementById("micLabel");
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const chat = document.getElementById("chat");
  const replyAudioEl = document.getElementById("replyAudio");

  if (!micButton) {
    console.error("[MatrixVA] micButton not found in DOM");
    return;
  }

  // Recording state
  let mediaRecorder = null;
  let chunks = [];

  // ---------- UI helpers ----------
  function setStatus(text, dotClass) {
    if (statusText) statusText.textContent = text;
    if (statusDot) statusDot.className = "va-dot " + dotClass;
  }

  function appendChat(role, text) {
    if (!chat || !text) return;
    const div = document.createElement("div");
    div.className = "va-msg va-" + role;
    div.textContent = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  // ---------- Start recording ----------
  async function startRecording() {
    chunks = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunks.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Reset UI state at stop
        micButton.classList.remove("recording");
        if (micLabel) micLabel.textContent = "Open Voice Link";
        setStatus("Uploading audio...", "va-dot-busy");

        const blob = new Blob(chunks, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");

        // 🔑 Send both device_id and session_id
        formData.append("device_id", DEVICE_ID);
        formData.append("session_id", SESSION_ID);

        try {
          const res = await fetch("/api/voice", {
            method: "POST",
            body: formData,
          });

          let data;
          try {
            data = await res.json();
          } catch (e) {
            console.error("Failed to parse JSON:", e);
            setStatus("Backend returned non-JSON error.", "va-dot-error");
            return;
          }

          console.log("[MatrixVA] /api/voice response:", data);

          if (data.user_text) appendChat("user", data.user_text);
          if (data.reply_text) appendChat("bot", data.reply_text);

          if (data.audio_base64 && data.audio_mime) {
            const src = `data:${data.audio_mime};base64,${data.audio_base64}`;
            console.log("[TTS] audio_base64 length:", data.audio_base64.length);
            console.log("[TTS] audio_mime:", data.audio_mime);

            if (replyAudioEl) {
              replyAudioEl.src = src;
              replyAudioEl.load();
              replyAudioEl
                .play()
                .then(() => {
                  console.log("[TTS] Playback started via <audio> element");
                })
                .catch((err) => {
                  console.error("[TTS] Playback failed:", err);
                });
            } else {
              // Fallback: use temporary Audio object if element missing
              const audio = new Audio(src);
              audio
                .play()
                .then(() => console.log("[TTS] Playback started via new Audio()"))
                .catch((err) =>
                  console.error("[TTS] Playback failed via new Audio():", err)
                );
            }
          } else {
            console.warn("[TTS] No audio_base64/audio_mime in response");
          }

          if (data.session_done) {
            setStatus("Order complete — session reset.", "va-dot-idle");
          } else {
            setStatus("Ready", "va-dot-idle");
          }
        } catch (err) {
          console.error("Fetch error:", err);
          setStatus("Network/Fetch error. See console.", "va-dot-error");
        }
      };

      // Start recording & update UI
      mediaRecorder.start();
      micButton.classList.add("recording");
      if (micLabel) micLabel.textContent = "Stop";
      setStatus("Recording...", "va-dot-live");
    } catch (err) {
      console.error("Error starting recording:", err);
      setStatus("Cannot access microphone.", "va-dot-error");
      micButton.classList.remove("recording");
      if (micLabel) micLabel.textContent = "Open Voice Link";
    }
  }

  // ---------- Stop recording ----------
  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
      // UI reset happens in onstop
    }
  }

  // ---------- Button wiring ----------
  micButton.addEventListener("click", () => {
    console.log("[MatrixVA] micButton clicked");
    if (!mediaRecorder || mediaRecorder.state === "inactive") {
      startRecording();
    } else {
      stopRecording();
    }
  });

  // Initial status
  setStatus("Ready", "va-dot-idle");
})();
