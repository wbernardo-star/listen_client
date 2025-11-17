// ============================================================
// Matrix Voice Assistant - app.js
// - Per-device ID (localStorage)
// - Per-tab Session ID
// - Flow guard during food_order
// - Clears chat after order done/cancel
// - Shows toast: "Order complete. Starting fresh." / "Order cancelled. Starting fresh."
// - Hidden audio playback (no visible player)
// ============================================================

(() => {
  console.log("[MatrixVA] app.js loaded");

  // -------------------- DEVICE ID --------------------
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

  // -------------------- SESSION ID --------------------
  const SESSION_ID =
    "sess-" +
    (crypto.randomUUID
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2));
  console.log("[MatrixVA] SESSION_ID:", SESSION_ID);

  // Insert labels
  const deviceEl = document.getElementById("deviceIdLabel");
  const sessionEl = document.getElementById("sessionIdLabel");
  const flowWarningEl = document.getElementById("flowWarning");

  if (deviceEl) deviceEl.textContent = DEVICE_ID;
  if (sessionEl) sessionEl.textContent = SESSION_ID;

  const micButton = document.getElementById("micButton");
  const micLabel = document.getElementById("micLabel");
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const chat = document.getElementById("chat");

  if (!micButton || !micLabel || !statusDot || !statusText || !chat) {
    console.error("[MatrixVA] Missing essential DOM elements");
    return;
  }

  let mediaRecorder = null;
  let chunks = [];
  let inOrderFlow = false;

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

  function clearChat() {
    chat.innerHTML = "";
  }

  // ---------- Toast helper ----------
  function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "va-toast";
    toast.textContent = message;
    document.body.appendChild(toast);

    // Trigger show
    requestAnimationFrame(() => {
      toast.classList.add("show");
    });

    // Hide after 2.5s, remove after 3s
    setTimeout(() => {
      toast.classList.remove("show");
    }, 2500);

    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 3000);
  }

  // ---------- Flow guard logic ----------
  function updateFlowGuard(debug, replyText) {
    const flow = debug && debug.flow;
    const step = debug && debug.step;

    const nowInFlow = flow === "food_order" && step != null;
    const wasInFlow = inOrderFlow;
    inOrderFlow = nowInFlow;

    // Toggle banner + beforeunload
    if (inOrderFlow) {
      if (flowWarningEl) flowWarningEl.style.display = "block";
      window.onbeforeunload = function (e) {
        const message =
          "Your food order is in progress. If you close or refresh, you will lose this order.";
        e = e || window.event;
        if (e) e.returnValue = message;
        return message;
      };
    } else {
      if (flowWarningEl) flowWarningEl.style.display = "none";
      window.onbeforeunload = null;
    }

    // Detect order completion/cancellation and clear chat + toast
    if (wasInFlow && !inOrderFlow && replyText) {
      const lower = replyText.toLowerCase();
      if (lower.includes("your food order has been placed")) {
        clearChat();
        showToast("Order complete. Starting fresh.");
      } else if (
        lower.includes("i've canceled the order") ||
        lower.includes("i have canceled the order") ||
        lower.includes("i've cancelled the order") || // just in case spelling variant
        lower.includes("order has been canceled") ||
        lower.includes("order has been cancelled")
      ) {
        clearChat();
        showToast("Order cancelled. Starting fresh.");
      }
    }
  }

  // ---------- Recording logic ----------
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
        micButton.classList.remove("recording");
        micLabel.textContent = "Open Voice Link";
        setStatus("Uploading...", "va-dot-busy");

        const blob = new Blob(chunks, { type: "audio/webm" });
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");
        formData.append("device_id", DEVICE_ID);
        formData.append("session_id", SESSION_ID);

        try {
          const res = await fetch("/api/voice", {
            method: "POST",
            body: formData,
          });

          const data = await res.json();
          console.log("[MatrixVA] /api/voice response:", data);

          appendChat("user", data.user_text);
          appendChat("bot", data.reply_text);

          // Update flow guard + detect end-of-flow
          updateFlowGuard(data.debug, data.reply_text);

          // Hidden audio playback (no visible player)
          if (data.audio_base64 && data.audio_mime) {
            const src = `data:${data.audio_mime};base64,${data.audio_base64}`;
            const audio = new Audio(src);
            audio
              .play()
              .then(() => console.log("[TTS] Playback OK"))
              .catch((err) =>
                console.error("[TTS] Playback failed:", err)
              );
          } else {
            console.warn("[TTS] No audio returned.");
          }

          setStatus("Ready", "va-dot-idle");
        } catch (err) {
          console.error("Fetch error:", err);
          setStatus("Network error", "va-dot-error");
        }
      };

      mediaRecorder.start();
      micButton.classList.add("recording");
      micLabel.textContent = "Stop";
      setStatus("Recording...", "va-dot-live");
    } catch (err) {
      console.error("Recording error:", err);
      setStatus("Mic blocked", "va-dot-error");
      micButton.classList.remove("recording");
      micLabel.textContent = "Open Voice Link";
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
  }

  micButton.addEventListener("click", () => {
    if (!mediaRecorder || mediaRecorder.state === "inactive") {
      startRecording();
    } else {
      stopRecording();
    }
  });

  setStatus("Ready", "va-dot-idle");
})();
