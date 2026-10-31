/**
 * DuplexVani — Client Audio Engine & Full-Duplex Interruption Handler
 * Supports Multilingual Indic Voice & Male Timbre (Devansh)
 */

class DuplexVaniClient {
  constructor() {
    this.ws = null;
    this.audioCtx = null;
    this.micStream = null;
    this.analyser = null;
    this.currentSource = null;
    this.isRecording = false;
    this.currentState = "IDLE";
    this.activePlaybackId = null;
    this.interruptionCount = 0;
    this.turnCount = 0;
    this.rtt = 0;
    this.speechRec = null;
    this.speechPermissionDenied = false;
    this.selectedLanguage = "hi-IN";
    
    // UI Elements
    this.stateBadge = document.getElementById("stateBadge");
    this.stateText = document.getElementById("stateText");
    this.latencyDisplay = document.getElementById("latencyDisplay");
    this.visualOrb = document.getElementById("visualOrb");
    this.subtitleText = document.getElementById("subtitleText");
    this.toggleMicBtn = document.getElementById("toggleMicBtn");
    this.toggleMicBtnText = document.getElementById("toggleMicBtnText");
    this.interruptBtn = document.getElementById("interruptBtn");
    this.connPill = document.getElementById("connPill");
    this.connStatusText = document.getElementById("connStatusText");
    this.sessionIdBadge = document.getElementById("sessionIdBadge");
    this.interruptCountEl = document.getElementById("interruptCount");
    this.turnCountEl = document.getElementById("turnCount");
    this.rttDisplay = document.getElementById("rttDisplay");
    this.feedMessages = document.getElementById("feedMessages");
    this.clearFeedBtn = document.getElementById("clearFeedBtn");
    this.langSelect = document.getElementById("langSelect");
    this.chipsRow = document.getElementById("chipsRow");
    this.canvas = document.getElementById("visualizerCanvas");
    this.canvasCtx = this.canvas.getContext("2d");

    this.initWebSocket();
    this.initEventListeners();
    this.startCanvasAnimation();
  }

  // --- WebSocket Connection ---
  initWebSocket() {
    const isFile = window.location.protocol === "file:";
    const host = (isFile || !window.location.host) ? "127.0.0.1:8000" : window.location.host;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${host}/ws/duplex`;

    this.connStatusText.innerText = "Connecting...";
    try {
      this.ws = new WebSocket(wsUrl);
    } catch (e) {
      console.warn("WebSocket init error:", e);
      setTimeout(() => this.initWebSocket(), 3000);
      return;
    }

    this.ws.onopen = () => {
      this.connPill.classList.add("connected");
      this.connStatusText.innerText = "Connected (Gnani Edge)";
      this.startPingLoop();
    };

    this.ws.onclose = () => {
      this.connPill.classList.remove("connected");
      this.connStatusText.innerText = "Disconnected. Reconnecting...";
      setTimeout(() => this.initWebSocket(), 2500);
    };

    this.ws.onerror = (err) => {
      console.warn("WebSocket Error:", err);
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        this.handleServerMessage(msg);
      } catch (err) {
        console.error("Error parsing WS message:", err);
      }
    };
  }

  startPingLoop() {
    if (this.pingInterval) clearInterval(this.pingInterval);
    this.pingInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({
          type: "PING",
          client_ts: performance.now()
        }));
      }
    }, 4000);
  }

  // --- Server Event Dispatcher ---
  handleServerMessage(msg) {
    switch (msg.type) {
      case "HANDSHAKE":
        this.sessionIdBadge.innerText = msg.session_id;
        this.setState("IDLE");
        this.addFeedItem("system", `Session initialized with Devansh (Male Voice).`);
        break;

      case "STATE_CHANGE":
        this.setState(msg.state);
        if (msg.metrics) {
          this.updateMetrics(msg.metrics);
        }
        break;

      case "INTERRUPT_CONFIRMED":
        const lat = msg.data.barge_in_latency_ms;
        this.latencyDisplay.innerText = `${lat} ms`;
        this.interruptionCount = msg.data.total_interruptions;
        this.interruptCountEl.innerText = this.interruptionCount;
        this.setState("INTERRUPTED");
        this.subtitleText.innerHTML = `⚠️ <em>Interrupted! Dropped audio in ${lat}ms.</em>`;
        setTimeout(() => {
          if (this.currentState === "INTERRUPTED") {
            this.setState("LISTENING");
          }
        }, 800);
        break;

      case "TRANSCRIPTION_RESULT":
        this.addFeedItem("user", msg.text);
        this.subtitleText.innerText = `You: "${msg.text}"`;
        break;

      case "ASSISTANT_REPLY_START":
        this.setState("SPEAKING");
        this.activePlaybackId = msg.playback_id;
        this.subtitleText.innerText = `Assistant (Devansh): "${msg.text}"`;
        this.addFeedItem("assistant", msg.text, msg.playback_id);
        this.interruptBtn.disabled = false;
        break;

      case "AUDIO_PAYLOAD":
        if (this.activePlaybackId === msg.playback_id && this.currentState === "SPEAKING") {
          this.playAudioBase64(msg.audio_base64, msg.playback_id);
        }
        break;

      case "PONG":
        const now = performance.now();
        this.rtt = Math.round(now - msg.client_ts);
        this.rttDisplay.innerText = `${this.rtt} ms`;
        break;
    }
  }

  setState(state) {
    this.currentState = state;
    this.stateText.innerText = state;
    
    this.stateBadge.className = "state-indicator";
    this.visualOrb.className = "orb-container";

    if (state === "LISTENING") {
      this.stateBadge.classList.add("listening");
      this.interruptBtn.disabled = true;
    } else if (state === "SPEAKING") {
      this.stateBadge.classList.add("speaking");
      this.visualOrb.classList.add("speaking");
      this.interruptBtn.disabled = false;
    } else if (state === "INTERRUPTED") {
      this.stateBadge.classList.add("interrupted");
      this.visualOrb.classList.add("interrupted");
      this.interruptBtn.disabled = true;
    } else {
      this.interruptBtn.disabled = true;
    }
  }

  // --- Instant Barge-In Engine ---
  triggerBargeIn() {
    const triggerTs = performance.now();

    if (this.currentSource) {
      try {
        this.currentSource.stop(0);
        this.currentSource.disconnect();
      } catch (e) {}
      this.currentSource = null;
    }

    if (this.activePlaybackId) {
      const activeEl = document.querySelector(`[data-playback="${this.activePlaybackId}"]`);
      if (activeEl) {
        activeEl.classList.add("cut-off");
        const p = activeEl.querySelector("p");
        if (p && !p.innerText.includes("[Cut off]")) {
          p.innerText += " 🛑 [Interrupted by user]";
        }
      }
    }

    this.activePlaybackId = null;

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: "USER_INTERRUPT",
        timestamp: triggerTs
      }));
    }
  }

  // --- Audio Playback Engine (48kHz WAV + Direct PCM) ---
  async playAudioBase64(base64Data, playbackId) {
    try {
      if (!this.audioCtx) {
        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (this.audioCtx.state === "suspended") {
        await this.audioCtx.resume();
      }

      const binaryString = window.atob(base64Data);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      let audioBuffer = null;

      try {
        audioBuffer = await this.audioCtx.decodeAudioData(bytes.buffer.slice(0));
      } catch (decodeErr) {
        const int16Array = new Int16Array(bytes.buffer);
        audioBuffer = this.audioCtx.createBuffer(1, int16Array.length, 48000);
        const channelData = audioBuffer.getChannelData(0);
        for (let i = 0; i < int16Array.length; i++) {
          channelData[i] = int16Array[i] / 32768.0;
        }
      }

      if (!audioBuffer) {
        this.setState("LISTENING");
        return;
      }

      if (this.currentSource) {
        try { this.currentSource.stop(0); } catch(e){}
      }

      const source = this.audioCtx.createBufferSource();
      source.buffer = audioBuffer;

      const gainNode = this.audioCtx.createGain();
      gainNode.gain.value = 1.0;

      if (this.analyser) {
        source.connect(this.analyser);
      }
      source.connect(gainNode);
      gainNode.connect(this.audioCtx.destination);

      source.onended = () => {
        if (this.activePlaybackId === playbackId) {
          this.currentSource = null;
          this.activePlaybackId = null;
          this.setState("LISTENING");
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: "PLAYBACK_FINISHED" }));
          }
        }
      };

      this.currentSource = source;
      source.start(0);

    } catch (err) {
      console.error("Audio playback error:", err);
      this.setState("LISTENING");
    }
  }

  // --- Speech & Mic Input ---
  async toggleMic() {
    if (this.isRecording) {
      this.stopMic();
    } else {
      await this.startMic();
    }
  }

  async startMic() {
    try {
      if (!this.audioCtx) {
        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (this.audioCtx.state === "suspended") {
        await this.audioCtx.resume();
      }

      if (!this.micStream) {
        this.micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }

      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 256;
      const micSource = this.audioCtx.createMediaStreamSource(this.micStream);
      micSource.connect(this.analyser);

      this.isRecording = true;
      this.toggleMicBtn.classList.add("recording");
      this.toggleMicBtnText.innerText = "Stop Session";
      this.setState("LISTENING");
      this.subtitleText.innerText = "Listening... Speak now!";

      this.startSpeechRecognition();

    } catch (err) {
      console.warn("Microphone not available, prompt mode active:", err);
      this.isRecording = true;
      this.toggleMicBtn.classList.add("recording");
      this.toggleMicBtnText.innerText = "Stop Session";
      this.setState("LISTENING");
      this.subtitleText.innerText = "Session active. Click any prompt chip below!";
    }
  }

  stopMic() {
    if (this.micStream) {
      this.micStream.getTracks().forEach(t => t.stop());
      this.micStream = null;
    }
    if (this.speechRec) {
      try { this.speechRec.stop(); } catch(e){}
    }
    this.isRecording = false;
    this.toggleMicBtn.classList.remove("recording");
    this.toggleMicBtnText.innerText = "Start Duplex Voice";
    this.setState("IDLE");
    this.subtitleText.innerText = "Session stopped. Click Start to resume.";
  }

  startSpeechRecognition() {
    if (this.speechPermissionDenied) return;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    if (this.speechRec) {
      try { this.speechRec.stop(); } catch(e){}
    }

    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = this.selectedLanguage;

    rec.onresult = (event) => {
      if (this.currentState === "SPEAKING") {
        this.triggerBargeIn();
      }

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          const spokenText = event.results[i][0].transcript.trim();
          if (spokenText) {
            this.sendFinalUtterance(spokenText);
          }
        }
      }
    };

    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        this.speechPermissionDenied = true;
      }
    };

    rec.onend = () => {
      if (this.isRecording && !this.speechPermissionDenied) {
        try { rec.start(); } catch(e){}
      }
    };

    try {
      rec.start();
      this.speechRec = rec;
    } catch(e){}
  }

  sendFinalUtterance(text) {
    if (this.audioCtx && this.audioCtx.state === "suspended") {
      this.audioCtx.resume();
    }

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: "USER_SPEECH_FINAL",
        text: text,
        language: this.selectedLanguage
      }));
      this.turnCount++;
      this.turnCountEl.innerText = this.turnCount;
    }
  }

  // --- Dynamic Language Prompts ---
  updateLanguagePrompts(lang) {
    this.selectedLanguage = lang;
    if (this.speechRec) {
      this.speechRec.lang = lang;
    }

    let prompts = [];
    if (lang === "te-IN") {
      prompts = [
        { label: '"Meeru evaru?"', text: "Namaskaram, meeru evaru mariyu ela pani chestaru?" },
        { label: '"Mandi Bhavam"', text: "Indore Mandi lo eeroju godhumalu mariyu ullipayala dharalu ela unnaayi?" },
        { label: '🛑 "Aagandi, nannu cheppanivvandi!"', text: "Arre aagandi, modata naaku cheppanivvandi!", barge: true }
      ];
    } else if (lang === "ta-IN") {
      prompts = [
        { label: '"Neengal yaar?"', text: "Vanakkam, neengal yaar matrum eppadi velai seigireergal?" },
        { label: '"Sandhai Nilavaram"', text: "Inraiya sandhai nilavaram eppadi ulladhu?" },
        { label: '🛑 "Nillungal, naan solgiren!"', text: "Arre nillungal, naan mudhalil pesugiren!", barge: true }
      ];
    } else if (lang === "en-IN") {
      prompts = [
        { label: '"Who are you?"', text: "Hello, who are you and how do you work?" },
        { label: '"Market Rates"', text: "What are the wheat and onion commodity prices today?" },
        { label: '🛑 "Wait, listen to me first!"', text: "Wait, hold on, listen to me first!", barge: true }
      ];
    } else {
      // Default Hindi / Hinglish
      prompts = [
        { label: '"Aap kaun hain?"', text: "Namaste, aap kaun hain aur aap kaise kaam karte hain?" },
        { label: '"Mandi Bhav Batao"', text: "Indore Mandi me aaj gehun aur pyaz ka kya bhav chal raha hai?" },
        { label: '"Kirana Khata Note Karo"', text: "Ramesh bhai ke hisaab mein do packet doodh note kar lo udhaar." },
        { label: '🛑 "Arre ruko, meri baat suno!"', text: "Arre ruko, pehle meri baat suno!", barge: true }
      ];
    }

    this.chipsRow.innerHTML = "";
    prompts.forEach(p => {
      const btn = document.createElement("button");
      btn.className = `chip ${p.barge ? "chip-barge" : ""}`;
      btn.setAttribute("data-text", p.text);
      btn.innerText = p.label;
      btn.addEventListener("click", () => {
        if (this.audioCtx && this.audioCtx.state === "suspended") {
          this.audioCtx.resume();
        }
        if (p.barge) {
          this.triggerBargeIn();
          setTimeout(() => this.sendFinalUtterance(p.text), 300);
        } else {
          this.sendFinalUtterance(p.text);
        }
      });
      this.chipsRow.appendChild(btn);
    });
  }

  // --- Waveform Canvas Animation ---
  startCanvasAnimation() {
    const bufferLength = 64;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      requestAnimationFrame(draw);

      const width = this.canvas.width;
      const height = this.canvas.height;
      this.canvasCtx.clearRect(0, 0, width, height);

      if (this.analyser) {
        this.analyser.getByteFrequencyData(dataArray);
      }

      this.canvasCtx.lineWidth = 2;
      const gradient = this.canvasCtx.createLinearGradient(0, 0, width, 0);
      gradient.addColorStop(0, "rgba(139, 92, 246, 0.2)");
      gradient.addColorStop(0.5, this.currentState === "SPEAKING" ? "rgba(16, 185, 129, 0.8)" : "rgba(6, 182, 212, 0.8)");
      gradient.addColorStop(1, "rgba(139, 92, 246, 0.2)");
      this.canvasCtx.strokeStyle = gradient;

      this.canvasCtx.beginPath();
      const sliceWidth = width / bufferLength;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * height) / 4 + height / 2;

        if (i === 0) this.canvasCtx.moveTo(x, y);
        else this.canvasCtx.lineTo(x, y);
        x += sliceWidth;
      }

      this.canvasCtx.stroke();
    };

    draw();
  }

  // --- UI Feed & Helpers ---
  addFeedItem(role, text, playbackId = null) {
    const item = document.createElement("div");
    item.className = `feed-item ${role}-item`;
    if (playbackId) {
      item.setAttribute("data-playback", playbackId);
    }
    item.innerHTML = `
      <span class="feed-role">${role.toUpperCase()}</span>
      <p>${text}</p>
    `;
    this.feedMessages.appendChild(item);
    this.feedMessages.scrollTop = this.feedMessages.scrollHeight;
  }

  updateMetrics(metrics) {
    if (metrics.turn_count !== undefined) this.turnCountEl.innerText = metrics.turn_count;
    if (metrics.interruption_count !== undefined) this.interruptCountEl.innerText = metrics.interruption_count;
  }

  // --- Event Listeners ---
  initEventListeners() {
    this.toggleMicBtn.addEventListener("click", () => this.toggleMic());
    
    this.interruptBtn.addEventListener("click", () => {
      if (this.currentState === "SPEAKING") {
        this.triggerBargeIn();
      }
    });

    window.addEventListener("keydown", (e) => {
      if (e.code === "Space" && e.target.tagName !== "INPUT" && this.currentState === "SPEAKING") {
        e.preventDefault();
        this.triggerBargeIn();
      }
    });

    this.langSelect.addEventListener("change", (e) => {
      this.updateLanguagePrompts(e.target.value);
    });

    // Initial prompts
    this.updateLanguagePrompts(this.selectedLanguage);

    this.clearFeedBtn.addEventListener("click", () => {
      this.feedMessages.innerHTML = "";
    });
  }
}

window.addEventListener("DOMContentLoaded", () => {
  window.duplexApp = new DuplexVaniClient();
});
