// Matrix Voice Assistant - unified app.js
// Uses: micButton, statusText, statusDot, chat (Matrix UI)
// Adapts the logic from listen_channel app.js
(() => {
  console.log("[MatrixVA] app.js loaded");

  // ---------- Persistent Client ID for multi-session ----------
  function getOrCreateClientId() {
    const key = "matrix_client_id";
    try {
      let id = localStorage.getItem(key);
      if (!id) {
        id =
          "web-" +
          (crypto.randomUUID
            ? crypto.randomUUID()
            : Math.random().toString(36).slice(2));
        localStorage.setItem(key, id);
      }
      return id;
    } catch (e) {
      return "web-anon-" + Math.random().toString(36).slice(2);
    }
  }

  const CLIENT_ID = getOrCreateClientId();
  console.log("[MatrixVA] CLIENT_ID:", CLIENT_ID);

  // ---------- DOM elements (Matrix HTML) ----------
  const micButton = document.getElementById("micButton");
  const micLabel = document.getElementById("micLabel");
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const chat = document.getElementById("chat");

  if (!micButton) {
    console.error("[MatrixVA] micButton not found in DOM");
    return;
  }

  // Recording state
  let mediaRecorder = null;
  let chunks = [];

  // ---------- UI helpers ----------
  function setStatus(text, dotClass) {
    statusText.textContent = text;
    statusDot.className = "va-dot " + dotClass;
  }

  function appendChat(role, text) {
    if (!text) return;
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
        micLabel.textContent = "Open Voice Link";
        setStatus("Uploading audio...", "va-dot-busy");

        const blob = new Blob(chunks, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");
        formData.append("client_id", CLIENT_ID);

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

          if (!res.ok || data.error) {
            console.error("API error:", data);
            setStatus("Error: " + (data.error || res.status), "va-dot-error");
            return;
          }

          appendChat("user", data.user_text || "");
          appendChat("bot", data.reply_text || "");

          if (data.audio_base64 && data.audio_mime) {
            const src = `data:${data.audio_mime};base64,${data.audio_base64}`;
            const audio = new Audio(src);
            audio.play();
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
      micLabel.textContent = "Stop";
      setStatus("Recording...", "va-dot-live");
    } catch (err) {
      console.error("Error starting recording:", err);
      setStatus("Cannot access microphone.", "va-dot-error");
      micButton.classList.remove("recording");
      micLabel.textContent = "Open Voice Link";
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
})();
