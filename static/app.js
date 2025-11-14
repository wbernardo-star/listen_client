let mediaRecorder = null;
let chunks = [];

const recordBtn = document.getElementById("recordBtn");
const statusEl = document.getElementById("status");
const userTextEl = document.getElementById("userText");
const replyTextEl = document.getElementById("replyText");
const replyAudioEl = document.getElementById("replyAudio");

async function startRecording() {
  chunks = [];

  // Ask for mic
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);

  mediaRecorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) {
      chunks.push(e.data);
    }
  };

  mediaRecorder.onstop = async () => {
    // We are definitely stopped here, so reset the UI
    recordBtn.classList.remove("recording");
    recordBtn.textContent = "Tap to Talk";

    statusEl.textContent = "Uploading audio...";
    const blob = new Blob(chunks, { type: "audio/webm" });
    const formData = new FormData();
    formData.append("audio", blob, "recording.webm");

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
        statusEl.textContent = "Backend returned non-JSON error.";
        return;
      }

      if (!res.ok || data.error) {
        console.error("API error:", data);
        statusEl.textContent = "Error: " + (data.error || res.status);
        return;
      }

      userTextEl.textContent = data.user_text || "";
      replyTextEl.textContent = data.reply_text || "";

      if (data.audio_base64 && data.audio_mime) {
        const src = `data:${data.audio_mime};base64,${data.audio_base64}`;
        replyAudioEl.src = src;
        replyAudioEl.play();
      }

      statusEl.textContent = "Done.";
    } catch (err) {
      console.error("Fetch error:", err);
      statusEl.textContent = "Network/Fetch error. See console.";
    }
  };

  // Start recording & update UI
  mediaRecorder.start();
  recordBtn.classList.add("recording");
  recordBtn.textContent = "Tap to Stop";
  statusEl.textContent = "Recording...";
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    // we reset text in onstop, so no need to touch it here
  }
}

recordBtn.addEventListener("click", () => {
  if (!mediaRecorder || mediaRecorder.state === "inactive") {
    // Start a new recording
    startRecording().catch((err) => {
      console.error("Error starting recording:", err);
      statusEl.textContent = "Cannot access microphone.";
      recordBtn.classList.remove("recording");
      recordBtn.textContent = "Tap To Talk";
    });
  } else {
    // Stop the current recording
    stopRecording();
  }
});
