// app.js - Voice + Text AI assistant frontend
// API_BASE is loaded from config.js

let sessionId     = "";
let mediaRecorder = null;
let audioChunks   = [];
let isRecording   = false;
let isBusy        = false;

const micButton          = document.getElementById("mic-button");
const micButtonLabel     = document.getElementById("mic-button-label");
const textInput          = document.getElementById("text-input");
const sendButton         = document.getElementById("send-button");
const conversationWindow = document.getElementById("conversation");
const statusDot          = document.getElementById("status-dot");
const statusText         = document.getElementById("status-text");
const audioPlayer        = document.getElementById("audio-player");
const audioElement       = document.getElementById("audio-element");
const clearBtn           = document.getElementById("clear-btn");
const toast              = document.getElementById("toast");
let toastTimer           = null;

// ── INIT ─────────────────────────────────────────────────────────
window.addEventListener("load", () => {
  sessionId = localStorage.getItem("bellavista_session") || generateId();
  localStorage.setItem("bellavista_session", sessionId);
  setStatus("ready", "Ready to assist you");

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    micButton.disabled = true;
    showToast("Microphone not supported in this browser. Use text input.");
  }
});

// ── UTILITIES ─────────────────────────────────────────────────────
function generateId() {
  // FIX: substr is deprecated — use substring instead
  return "sess_" + Math.random().toString(36).substring(2, 10);
}

function setStatus(type, text) {
  statusDot.className = "status-dot " + type;
  statusText.textContent = text;
}

function setBusy(busy) {
  isBusy = busy;
  sendButton.disabled = busy;
  textInput.disabled = busy;
  if (!isRecording) micButton.disabled = busy;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 4000);
}

function scrollToBottom() {
  conversationWindow.scrollTop = conversationWindow.scrollHeight;
}

// ── CONVERSATION UI ───────────────────────────────────────────────
function clearEmptyState() {
  const empty = conversationWindow.querySelector(".empty-state");
  if (empty) empty.remove();
}

function addMessage(role, text) {
  clearEmptyState();
  const messageDiv = document.createElement("div");
  messageDiv.className = "message " + role;

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "Aria - Bella Vista";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  messageDiv.appendChild(label);
  messageDiv.appendChild(bubble);
  conversationWindow.appendChild(messageDiv);
  scrollToBottom();
}

function showTypingIndicator() {
  clearEmptyState();
  const div = document.createElement("div");
  div.className = "message ai";
  div.id = "typing-indicator";

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = "Aria - Bella Vista";

  const bubble = document.createElement("div");
  bubble.className = "bubble typing-indicator";
  bubble.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';

  div.appendChild(label);
  div.appendChild(bubble);
  conversationWindow.appendChild(div);
  scrollToBottom();
}

function removeTypingIndicator() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

// ── MICROPHONE ────────────────────────────────────────────────────
micButton.addEventListener("click", async () => {
  if (isBusy) return;

  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunks = [];
      mediaRecorder = new MediaRecorder(stream, { mimeType: getBestMimeType() });

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        await processAudioRecording();
      };

      mediaRecorder.start();
      isRecording = true;
      micButton.classList.add("recording");
      micButtonLabel.textContent = "Stop Recording";
      setStatus("listening", "Listening...");

    } catch (err) {
      if (err.name === "NotAllowedError") {
        showToast("Microphone access denied. Please allow microphone and try again.");
      } else {
        showToast("Could not access microphone: " + err.message);
      }
    }

  } else {
    isRecording = false;
    micButton.classList.remove("recording");
    micButton.disabled = true;
    micButtonLabel.textContent = "Processing...";
    mediaRecorder.stop();
  }
});

function getBestMimeType() {
  const types = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  for (const t of types) {
    if (MediaRecorder.isTypeSupported(t)) return t;
  }
  return "";
}

async function processAudioRecording() {
  setBusy(true);
  setStatus("thinking", "Transcribing your voice...");

  try {
    const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
    const transcribedText = await transcribeAudio(audioBlob);

    if (!transcribedText || !transcribedText.trim()) {
      showToast("No speech detected. Please try again.");
      resetMicButton();
      setBusy(false);
      setStatus("ready", "Ready to assist you");
      return;
    }

    addMessage("user", transcribedText);
    await sendToAI(transcribedText);

  } catch (err) {
    console.error("Processing error:", err);
    showToast("Something went wrong. Please try again.");
    setStatus("ready", "Ready to assist you");
  }

  resetMicButton();
  setBusy(false);
}

function resetMicButton() {
  micButton.disabled = false;
  micButtonLabel.textContent = "Start Talking";
  micButton.classList.remove("recording");
}

// ── API CALLS ─────────────────────────────────────────────────────
async function transcribeAudio(audioBlob) {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");

  const res = await fetch(API_BASE + "/speech-to-text", {
    method: "POST",
    body: formData
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || "Transcription failed");
  }

  const data = await res.json();
  return data.text;
}

async function sendToAI(userText) {
  setStatus("thinking", "Thinking...");
  showTypingIndicator();

  try {
    const res = await fetch(API_BASE + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: userText, session_id: sessionId })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Chat failed");
    }

    const data = await res.json();

    if (data.session_id) {
      sessionId = data.session_id;
      localStorage.setItem("bellavista_session", sessionId);
    }

    removeTypingIndicator();
    addMessage("ai", data.reply);
    await speakText(data.reply);

  } catch (err) {
    removeTypingIndicator();
    showToast("Error: " + err.message);
    setStatus("ready", "Ready to assist you");
    throw err;
  }
}

async function speakText(text) {
  setStatus("speaking", "Playing response...");

  try {
    const res = await fetch(API_BASE + "/text-to-speech", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });

    if (!res.ok) {
      setStatus("ready", "Ready to assist you");
      return;
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);

    audioElement.src = url;
    audioPlayer.classList.add("visible");
    audioElement.play();

    audioElement.onended = () => {
      setStatus("ready", "Ready to assist you");
      URL.revokeObjectURL(url);
    };

  } catch (err) {
    console.warn("TTS error:", err);
    setStatus("ready", "Ready to assist you");
  }
}

// ── TEXT INPUT ────────────────────────────────────────────────────
sendButton.addEventListener("click", handleTextSend);

textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleTextSend();
  }
});

async function handleTextSend() {
  const text = textInput.value.trim();
  if (!text || isBusy) return;

  textInput.value = "";
  setBusy(true);
  addMessage("user", text);

  try {
    await sendToAI(text);
  } catch (err) {
    // error already shown in sendToAI
  }

  setBusy(false);
}

// ── CLEAR SESSION ─────────────────────────────────────────────────
clearBtn.addEventListener("click", async () => {
  if (isBusy) return;

  try {
    await fetch(API_BASE + "/session/" + sessionId, { method: "DELETE" });
  } catch (err) {
    console.warn("Could not clear backend session:", err);
  }

  sessionId = generateId();
  localStorage.setItem("bellavista_session", sessionId);

  conversationWindow.innerHTML = `
    <div class="empty-state">
      <span class="empty-icon">🍽</span>
      <p>How may I assist you today?</p>
      <p class="empty-hint">Speak or type your question</p>
    </div>
  `;

  audioPlayer.classList.remove("visible");
  setStatus("ready", "Ready to assist you");
});
