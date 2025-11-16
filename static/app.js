(() => {
  // ========================================================
  //  NEW: Generate or reuse persistent client_id 
  // ========================================================
  function getOrCreateClientId() {
    const key = "blink_client_id";
    try {
      let id = localStorage.getItem(key);
      if (!id) {
        id = "web-" + (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2));
        localStorage.setItem(key, id);
      }
      return id;
    } catch (e) {
      return "web-anon-" + Math.random().toString(36).slice(2);
    }
  }

  const CLIENT_ID = getOrCreateClientId();
  console.log("[Blink] client_id =", CLIENT_ID);

  // ========== existing UI code ==========
  const chat = document.getElementById('chat');
  const mic = document.getElementById('micButton');
  const label = document.getElementById('micLabel');
  const dot = document.getElementById('statusDot');
  const status = document.getElementById('statusText');

  let mediaStream = null;
  let recorder = null;
  let chunks = [];
  let recording = false;

  mic.onclick = async () => {
    if (!recording) {
      startRecording();
    } else {
      stopRecording();
    }
  };

  async function startRecording() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recorder = new MediaRecorder(mediaStream);

      recorder.ondataavailable = (e) => chunks.push(e.data);

      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: 'audio/wav' });
        chunks = [];
        await sendAudio(blob);
      };

      recorder.start();
      recording = true;
      label.textContent = "Stop Recording";
      dot.style.background = "red";
      status.textContent = "Listening...";
    } catch (e) {
      alert("Microphone error: " + e.message);
    }
  }

  function stopRecording() {
    if (recorder && recording) {
      recorder.stop();
      mediaStream.getTracks().forEach(t => t.stop());
    }
    recording = false;
    label.textContent = "Start Recording";
    dot.style.background = "green";
    status.textContent = "Processing...";
  }

  // ========================================================
  // NEW: Send audio + client_id to Flask backend
  // ========================================================
  async function sendAudio(blob) {
    const fd = new FormData();
    fd.append("audio", blob, "speech.wav");
    fd.append("client_id", CLIENT_ID);   // <---- IMPORTANT

    const resp = await fetch("/api/voice", { method: "POST", body: fd });
    const j = await resp.json();

    chat.value += "You: " + j.user_text + "\n";
    chat.value += "Blink: " + j.reply_text + "\n\n";

    // Play TTS audio
    if (j.audio_base64) {
      const audio = new Audio("data:" + j.audio_mime + ";base64," + j.audio_base64);
      audio.play();
    }

    if (j.session_done) {
      status.textContent = "Order Complete. Session ended.";
      dot.style.background = "gray";
    } else {
      status.textContent = "Ready";
      dot.style.background = "green";
    }
  }

})();
