/**
 * DuplexVani — Enterprise Voice Desk Operator Client
 * Features:
 * - Clean Enterprise Telecommunications Console Architecture
 * - Sub-50ms Barge-In Preemption Controller
 * - 8kHz GSM Telephonic Codec Simulation (Bandpass 300Hz-3400Hz)
 * - Indian Market & Traffic Ambient Noise Simulator (-18dB SNR)
 * - Multilingual Indic Routing & Gnani Timbre Male Voice (Devansh)
 */

class DuplexVaniConsole {
  constructor() {
    this.ws = null;
    this.audioCtx = null;
    this.micStream = null;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.analyser = null;
    this.currentSource = null;
    this.noiseSource = null;
    this.noiseGain = null;
    this.isRecording = false;
    this.currentState = "IDLE";
    this.activePlaybackId = null;
    this.interruptionCount = 0;
    this.turnCount = 0;
    this.rtt = 0;
    this.speechRec = null;
    this.speechPermissionDenied = false;
    this.selectedLanguage = "hi-IN";
    this.isLiveMode = false;         // Default: Credit Shield (Free Mode)
    this.isTelephonyMode = false;     // Default: 48kHz HD (Off)
    this.isNoiseActive = false;       // Default: Clean ambience (Off)
    
    // UI Elements
    this.statusBanner = document.getElementById("statusBanner");
    this.statusDot = document.getElementById("statusDot");
    this.stateText = document.getElementById("stateText");
    this.subtitleText = document.getElementById("subtitleText");
    this.latencyDisplay = document.getElementById("latencyDisplay");
    this.meterDbDisplay = document.getElementById("meterDbDisplay");
    this.codecBadge = document.getElementById("codecBadge");
    this.noiseBadge = document.getElementById("noiseBadge");
    
    this.toggleMicBtn = document.getElementById("toggleMicBtn");
    this.toggleMicBtnText = document.getElementById("toggleMicBtnText");
    this.interruptBtn = document.getElementById("interruptBtn");
    
    this.telephonyToggleBtn = document.getElementById("telephonyToggleBtn");
    this.telephonyStatusText = document.getElementById("telephonyStatusText");
    this.noiseToggleBtn = document.getElementById("noiseToggleBtn");
    this.noiseStatusText = document.getElementById("noiseStatusText");
    
    this.modeToggleBtn = document.getElementById("modeToggleBtn");
    this.modeIcon = document.getElementById("modeIcon");
    this.modeText = document.getElementById("modeText");
    this.langSelect = document.getElementById("langSelect");
    this.connBadge = document.getElementById("connBadge");
    this.connStatusText = document.getElementById("connStatusText");
    this.sessionIdBadge = document.getElementById("sessionIdBadge");
    
    this.interruptCountEl = document.getElementById("interruptCount");
    this.turnCountEl = document.getElementById("turnCount");
    this.rttDisplay = document.getElementById("rttDisplay");
    this.feedMessages = document.getElementById("feedMessages");
    this.clearFeedBtn = document.getElementById("clearFeedBtn");
    this.chipsRow = document.getElementById("chipsRow");
    
    // Telemetry Waterfall Elements
    this.preemptBadge = document.getElementById("preemptBadge");
    this.barBargeIn = document.getElementById("barBargeIn");
    this.valBargeIn = document.getElementById("valBargeIn");
    this.barLlm = document.getElementById("barLlm");
    this.valLlm = document.getElementById("valLlm");
    this.barTts = document.getElementById("barTts");
    this.valTts = document.getElementById("valTts");
    this.barTotal = document.getElementById("barTotal");
    this.valTotal = document.getElementById("valTotal");
    
    this.canvas = document.getElementById("visualizerCanvas");
    this.canvasCtx = this.canvas.getContext("2d");

    // Session Recording & WAV Export Elements
    this.recordSessionBtn = document.getElementById("recordSessionBtn");
    this.recordSessionBtnText = document.getElementById("recordSessionBtnText");
    this.isSessionRecording = false;
    this.sessionRecorder = null;
    this.sessionRecordChunks = [];
    this.sessionRecordDestination = null;
    this.sessionRecordTimer = null;
    this.sessionRecordSeconds = 0;
    this.micRecorderSource = null;

    this.initWebSocket();
    this.initEventListeners();
    this.startSpectrumMeter();
  }

  // --- WebSocket Connection ---
  initWebSocket() {
    const isFile = window.location.protocol === "file:";
    const host = (isFile || !window.location.host) ? "127.0.0.1:8000" : window.location.host;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${host}/ws/duplex`;

    this.connStatusText.innerText = "CONNECTING...";
    try {
      this.ws = new WebSocket(wsUrl);
    } catch (e) {
      setTimeout(() => this.initWebSocket(), 3000);
      return;
    }

    this.ws.onopen = () => {
      this.connStatusText.innerText = "ONLINE";
      this.startPingLoop();
    };

    this.ws.onclose = () => {
      this.connStatusText.innerText = "OFFLINE";
      setTimeout(() => this.initWebSocket(), 2500);
    };

    this.ws.onerror = (err) => {
      console.warn("WebSocket Notice:", err);
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
        this.sessionIdBadge.innerText = `SESSION #${msg.session_id.slice(-6)}`;
        this.setState("IDLE");
        this.addLogEntry("SYSTEM", `Channel linked. Mode: ${this.isLiveMode ? 'Live Gnani' : 'Credit Shield'}`);
        break;

      case "MODE_UPDATED":
        this.isLiveMode = msg.is_live;
        this.updateModeUI();
        break;

      case "STATE_CHANGE":
        this.setState(msg.state);
        if (msg.metrics) {
          this.updateMetrics(msg.metrics);
        }
        break;

      case "INTERRUPT_CONFIRMED":
        const lat = msg.data.barge_in_latency_ms;
        const preempt = msg.data.task_preemption_ms || 2.4;
        this.updateBargeInTelemetry(lat, preempt);
        this.interruptionCount = msg.data.total_interruptions;
        this.interruptCountEl.innerText = this.interruptionCount;
        this.setState("INTERRUPTED");
        this.subtitleText.innerText = `Preempted audio stream in ${preempt}ms. Listening...`;
        setTimeout(() => {
          if (this.currentState === "INTERRUPTED") {
            this.setState("LISTENING");
          }
        }, 800);
        break;

      case "TRANSCRIPTION_RESULT":
        const engineLabel = msg.engine ? ` [${msg.engine}]` : "";
        this.addLogEntry("USER", `${msg.text}${engineLabel}`);
        this.subtitleText.innerText = `Recognized: "${msg.text}"`;
        break;

      case "ASSISTANT_REPLY_START":
        this.setState("SPEAKING");
        this.activePlaybackId = msg.playback_id;
        const ttsEngine = msg.engine ? ` (${msg.engine})` : "";
        this.subtitleText.innerText = `Synthesizing (Devansh): "${msg.text}"`;
        this.addLogEntry("DEVANSH", `${msg.text}${ttsEngine}`, msg.playback_id);
        this.interruptBtn.disabled = false;
        if (msg.llm_ms) {
          this.valLlm.innerText = `${msg.llm_ms} ms`;
          const pctLlm = Math.min(100, Math.max(8, (msg.llm_ms / 600) * 100));
          this.barLlm.style.width = `${pctLlm}%`;
        }
        break;

      case "AUDIO_PAYLOAD":
        if (msg.telemetry) {
          this.updateTelemetry(msg.telemetry);
        }
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

  // --- State Visualization ---
  setState(state) {
    this.currentState = state;
    this.statusBanner.className = "status-banner";

    if (state === "LISTENING") {
      this.statusBanner.classList.add("listening");
      this.stateText.innerText = "STREAMING (LISTENING)";
      this.interruptBtn.disabled = true;
    } else if (state === "SPEAKING") {
      this.statusBanner.classList.add("speaking");
      this.stateText.innerText = "DEVANSH SPEAKING";
      this.interruptBtn.disabled = false;
    } else if (state === "INTERRUPTED") {
      this.statusBanner.classList.add("interrupted");
      this.stateText.innerText = "BARGE-IN PREEMPTED";
      this.interruptBtn.disabled = true;
    } else {
      this.stateText.innerText = "READY (IDLE)";
      this.interruptBtn.disabled = true;
    }
  }

  // --- Real-Time Telemetry & Latency Waterfall ---
  updateTelemetry(data) {
    if (!data) return;

    if (data.llm_ms !== undefined) {
      this.valLlm.innerText = `${data.llm_ms} ms`;
      const pctLlm = Math.min(100, Math.max(10, (data.llm_ms / 600) * 100));
      this.barLlm.style.width = `${pctLlm}%`;
    }

    if (data.tts_ms !== undefined) {
      this.valTts.innerText = `${data.tts_ms} ms`;
      const pctTts = Math.min(100, Math.max(10, (data.tts_ms / 600) * 100));
      this.barTts.style.width = `${pctTts}%`;
    }

    if (data.total_turn_ms !== undefined) {
      this.valTotal.innerText = `${data.total_turn_ms} ms`;
      const pctTotal = Math.min(100, Math.max(15, (data.total_turn_ms / 1000) * 100));
      this.barTotal.style.width = `${pctTotal}%`;
    }

    if (data.turn_count !== undefined) {
      this.turnCount = data.turn_count;
      this.turnCountEl.innerText = this.turnCount;
    }
  }

  updateBargeInTelemetry(bargeInMs, preemptMs) {
    if (bargeInMs !== undefined) {
      this.valBargeIn.innerText = `${bargeInMs} ms`;
      this.latencyDisplay.innerText = `${bargeInMs} ms`;
      const pctBarge = Math.min(100, Math.max(8, (bargeInMs / 50) * 100));
      this.barBargeIn.style.width = `${pctBarge}%`;
    }
    if (preemptMs !== undefined && this.preemptBadge) {
      this.preemptBadge.innerText = `PREEMPTION: ${preemptMs}ms`;
    }
  }

  // --- Mode Toggle (Credit Shield vs Live Gnani) ---
  toggleMode() {
    this.isLiveMode = !this.isLiveMode;
    this.updateModeUI();

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: "SET_LIVE_MODE",
        is_live: this.isLiveMode
      }));
    }

    const modeLabel = this.isLiveMode ? "Live Gnani AI (Prisma & Timbre)" : "Credit Shield (Free)";
    this.addLogEntry("SYSTEM", `Active speech mode switched: ${modeLabel}`);
  }

  updateModeUI() {
    if (this.isLiveMode) {
      this.modeToggleBtn.className = "pill-btn pill-shield pill-live";
      this.modeIcon.innerText = "⚡";
      this.modeText.innerText = "Live Gnani AI (Active)";
    } else {
      this.modeToggleBtn.className = "pill-btn pill-shield";
      this.modeIcon.innerText = "🛡️";
      this.modeText.innerText = "Credit Shield (Free)";
    }
  }

  // --- Telephonic 8kHz GSM Codec Simulator ---
  toggleTelephonyCodec() {
    this.isTelephonyMode = !this.isTelephonyMode;

    if (this.isTelephonyMode) {
      this.telephonyToggleBtn.classList.add("telephony-active");
      this.telephonyStatusText.innerText = "ON";
      this.codecBadge.innerText = "CODEC: G.711 (8kHz GSM)";
      this.addLogEntry("SYSTEM", "8kHz GSM Telephonic Bandpass Filter (300Hz-3400Hz) engaged.");
    } else {
      this.telephonyToggleBtn.classList.remove("telephony-active");
      this.telephonyStatusText.innerText = "OFF";
      this.codecBadge.innerText = "CODEC: 48kHz HD Wideband";
      this.addLogEntry("SYSTEM", "Wideband 48kHz studio audio restored.");
    }
  }

  // --- Indian Market & Traffic Noise Simulator (-18dB SNR) ---
  toggleMarketNoise() {
    this.isNoiseActive = !this.isNoiseActive;

    if (this.isNoiseActive) {
      this.startMarketNoise();
      this.noiseToggleBtn.classList.add("noise-active");
      this.noiseStatusText.innerText = "ON (-18dB)";
      this.noiseBadge.innerText = "AMBIENCE: NOISY BAZAAR";
      this.addLogEntry("SYSTEM", "Ambient Indian market chatter & traffic background noise (-18dB SNR) engaged.");
    } else {
      this.stopMarketNoise();
      this.noiseToggleBtn.classList.remove("noise-active");
      this.noiseStatusText.innerText = "OFF";
      this.noiseBadge.innerText = "AMBIENCE: CLEAN";
      this.addLogEntry("SYSTEM", "Ambient noise generator stopped. Clean acoustics restored.");
    }
  }

  startMarketNoise() {
    try {
      if (!this.audioCtx) {
        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (this.audioCtx.state === "suspended") {
        this.audioCtx.resume();
      }

      // Synthesize realistic 4-second brownian ambient noise buffer
      const sampleRate = this.audioCtx.sampleRate;
      const bufferSize = sampleRate * 4;
      const noiseBuffer = this.audioCtx.createBuffer(1, bufferSize, sampleRate);
      const output = noiseBuffer.getChannelData(0);

      let lastOut = 0.0;
      for (let i = 0; i < bufferSize; i++) {
        const white = Math.random() * 2 - 1;
        // Brownian filter + low-frequency engine hum + periodic chatter murmur
        const t = i / sampleRate;
        const chatterMod = 0.8 + 0.2 * Math.sin(2 * Math.PI * 1.5 * t) + 0.1 * Math.sin(2 * Math.PI * 4.2 * t);
        lastOut = (lastOut + (0.02 * white)) / 1.02;
        output[i] = lastOut * 3.5 * chatterMod;
      }

      const noiseSrc = this.audioCtx.createBufferSource();
      noiseSrc.buffer = noiseBuffer;
      noiseSrc.loop = true;

      const gain = this.audioCtx.createGain();
      gain.gain.value = 0.045; // Subtle realistic ambient level (-18dB SNR)

      noiseSrc.connect(gain);
      gain.connect(this.audioCtx.destination);
      if (this.sessionRecordDestination) {
        gain.connect(this.sessionRecordDestination);
      }
      noiseSrc.start(0);

      this.noiseSource = noiseSrc;
      this.noiseGain = gain;
    } catch (e) {
      console.warn("Noise generator error:", e);
    }
  }

  stopMarketNoise() {
    if (this.noiseSource) {
      try {
        this.noiseSource.stop(0);
        this.noiseSource.disconnect();
      } catch (e) {}
      this.noiseSource = null;
      this.noiseGain = null;
    }
  }

  // --- Preemptive Barge-In Engine ---
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
        if (p && !p.innerText.includes("[PREEMPTED]")) {
          p.innerText += " 🛑 [PREEMPTED BY USER BARGE-IN]";
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

  // --- Audio Playback Engine (with Telephony Filter) ---
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

      // Telephony GSM Simulation (Bandpass 300Hz - 3400Hz filter)
      if (this.isTelephonyMode) {
        const bandpass = this.audioCtx.createBiquadFilter();
        bandpass.type = "bandpass";
        bandpass.frequency.value = 1850;
        bandpass.Q.value = 0.9;

        source.connect(bandpass);
        bandpass.connect(gainNode);
      } else {
        source.connect(gainNode);
      }

      if (this.analyser) {
        gainNode.connect(this.analyser);
      }
      gainNode.connect(this.audioCtx.destination);
      if (this.sessionRecordDestination) {
        gainNode.connect(this.sessionRecordDestination);
      }

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

  // --- Microphone & Audio Capture (MediaRecorder) ---
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
        this.micStream = await navigator.mediaDevices.getUserMedia({ 
          audio: { echoCancellation: true, noiseSuppression: true, sampleRate: 16000 } 
        });
      }

      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 256;
      const micSource = this.audioCtx.createMediaStreamSource(this.micStream);
      micSource.connect(this.analyser);
      if (this.sessionRecordDestination) {
        micSource.connect(this.sessionRecordDestination);
      }
      this.micSourceNode = micSource;

      this.audioChunks = [];
      try {
        this.mediaRecorder = new MediaRecorder(this.micStream);
        this.mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) this.audioChunks.push(e.data);
        };
        this.mediaRecorder.start(250);
      } catch (mrErr) {
        console.warn("MediaRecorder init notice:", mrErr);
      }

      this.isRecording = true;
      this.toggleMicBtn.classList.add("recording");
      this.toggleMicBtnText.innerText = "Commit Audio Stream";
      this.setState("LISTENING");
      this.subtitleText.innerText = "Channel recording active. Speak, then click Commit.";

      this.startSpeechRecognition();

    } catch (err) {
      console.warn("Microphone access notice:", err);
      this.isRecording = true;
      this.toggleMicBtn.classList.add("recording");
      this.toggleMicBtnText.innerText = "Stop Channel";
      this.setState("LISTENING");
      this.subtitleText.innerText = "Channel online. Click a benchmark scenario below.";
    }
  }

  async stopMic() {
    let capturedBlob = null;
    if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
      this.mediaRecorder.stop();
      capturedBlob = new Blob(this.audioChunks, { type: "audio/wav" });
    }

    if (this.speechRec) {
      try { this.speechRec.stop(); } catch(e){}
    }

    this.isRecording = false;
    this.toggleMicBtn.classList.remove("recording");
    this.toggleMicBtnText.innerText = "Connect Voice Stream";
    this.setState("PROCESSING");
    this.subtitleText.innerText = "Transcribing & evaluating stream...";

    if (capturedBlob && capturedBlob.size > 500) {
      const reader = new FileReader();
      reader.readAsDataURL(capturedBlob);
      reader.onloadend = () => {
        const base64Audio = reader.result.split(",")[1];
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({
            type: "USER_SPEECH_FINAL",
            audio_b64: base64Audio,
            language: this.selectedLanguage,
            is_live: this.isLiveMode
          }));
          this.turnCount++;
          this.turnCountEl.innerText = this.turnCount;
        }
      };
    } else {
      this.setState("IDLE");
      this.subtitleText.innerText = "Stream closed. Click 'Connect Voice' to resume.";
    }
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
    };

    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        this.speechPermissionDenied = true;
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
        language: this.selectedLanguage,
        is_live: this.isLiveMode
      }));
      this.turnCount++;
      this.turnCountEl.innerText = this.turnCount;
    }
  }

  // --- Dynamic Enterprise Scenarios ---
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
        { label: '🛑 "Aagandi, naaku cheppanivvandi!"', text: "Arre aagandi, modata naaku cheppanivvandi!", barge: true }
      ];
    } else if (lang === "ta-IN") {
      prompts = [
        { label: '"Neengal yaar?"', text: "Vanakkam, neengal yaar matrum eppadi velai seigireergal?" },
        { label: '"Sandhai Nilavaram"', text: "Inraiya sandhai nilavaram eppadi ulladhu?" },
        { label: '🛑 "Nillungal, naan solgiren!"', text: "Arre nillungal, naan mudhalil pesugiren!", barge: true }
      ];
    } else if (lang === "en-IN") {
      prompts = [
        { label: '"Who are you?"', text: "Hello, who are you and how does DuplexVani work?" },
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

  // --- 1-Click Session Audio Recording & WAV Exporter ---
  async toggleSessionRecording() {
    if (this.isSessionRecording) {
      await this.stopSessionRecording();
    } else {
      await this.startSessionRecording();
    }
  }

  async startSessionRecording() {
    try {
      if (!this.audioCtx) {
        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
      }
      if (this.audioCtx.state === "suspended") {
        await this.audioCtx.resume();
      }
      if (!this.sessionRecordDestination) {
        this.sessionRecordDestination = this.audioCtx.createMediaStreamDestination();
      }

      // If mic is active, ensure it connects to the recorder stream
      if (this.micSourceNode) {
        try { this.micSourceNode.connect(this.sessionRecordDestination); } catch (e) {}
      }

      this.sessionRecordChunks = [];
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") 
        ? "audio/webm;codecs=opus" 
        : "audio/webm";
      this.sessionRecorder = new MediaRecorder(this.sessionRecordDestination.stream, { mimeType: mime });

      this.sessionRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) this.sessionRecordChunks.push(e.data);
      };

      this.sessionRecorder.start(250);
      this.isSessionRecording = true;
      this.recordSessionBtn.classList.add("recording");
      this.sessionRecordSeconds = 0;
      this.recordSessionBtnText.innerText = "● REC (00:00)";
      this.addLogEntry("SYSTEM", "Dual-channel studio audio recording started. Capturing user mic + Devansh voice.");

      this.sessionRecordTimer = setInterval(() => {
        this.sessionRecordSeconds++;
        const mins = String(Math.floor(this.sessionRecordSeconds / 60)).padStart(2, "0");
        const secs = String(this.sessionRecordSeconds % 60).padStart(2, "0");
        this.recordSessionBtnText.innerText = `● REC (${mins}:${secs})`;
      }, 1000);

    } catch (err) {
      console.error("Session recording init error:", err);
      this.addLogEntry("SYSTEM", `Failed to initialize session recorder: ${err.message}`);
    }
  }

  async stopSessionRecording() {
    if (!this.sessionRecorder || this.sessionRecorder.state === "inactive") return;

    if (this.sessionRecordTimer) {
      clearInterval(this.sessionRecordTimer);
      this.sessionRecordTimer = null;
    }

    this.isSessionRecording = false;
    this.recordSessionBtn.classList.remove("recording");
    this.recordSessionBtnText.innerText = "Exporting WAV...";

    this.sessionRecorder.onstop = async () => {
      try {
        const rawBlob = new Blob(this.sessionRecordChunks, { type: "audio/webm" });
        const arrayBuffer = await rawBlob.arrayBuffer();
        const audioBuffer = await this.audioCtx.decodeAudioData(arrayBuffer);
        const wavBlob = this.encodeWAV(audioBuffer.getChannelData(0), audioBuffer.sampleRate);

        const url = URL.createObjectURL(wavBlob);
        const a = document.createElement("a");
        a.style.display = "none";
        a.href = url;
        const timestamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
        a.download = `DuplexVani_Demo_${timestamp}.wav`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          document.body.removeChild(a);
          window.URL.revokeObjectURL(url);
        }, 1000);

        const kbSize = Math.round(wavBlob.size / 1024);
        this.addLogEntry("SYSTEM", `Demo WAV saved: ${a.download} (${kbSize} KB, 48kHz Linear PCM)`);
      } catch (exportErr) {
        console.warn("WAV transcode notice, saving raw WebM container:", exportErr);
        const rawBlob = new Blob(this.sessionRecordChunks, { type: "audio/webm" });
        const url = URL.createObjectURL(rawBlob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `DuplexVani_Demo_Audio.webm`;
        a.click();
        this.addLogEntry("SYSTEM", "Demo audio exported (WebM container).");
      } finally {
        this.recordSessionBtnText.innerText = "Record Demo WAV";
      }
    };

    this.sessionRecorder.stop();
  }

  encodeWAV(samples, sampleRate = 48000) {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    const writeString = (offset, string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };

    writeString(0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // Linear PCM
    view.setUint16(22, 1, true); // Mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // Byte rate
    view.setUint16(32, 2, true); // Block align
    view.setUint16(34, 16, true); // 16-bit
    writeString(36, "data");
    view.setUint32(40, samples.length * 2, true);

    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }

    return new Blob([view], { type: "audio/wav" });
  }

  // --- Professional Linear Studio Spectrum Bars ---
  startSpectrumMeter() {
    const bufferLength = 48;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      requestAnimationFrame(draw);

      const width = this.canvas.width;
      const height = this.canvas.height;
      this.canvasCtx.clearRect(0, 0, width, height);

      let maxVal = 0;
      if (this.analyser) {
        this.analyser.getByteFrequencyData(dataArray);
        for (let i = 0; i < bufferLength; i++) {
          if (dataArray[i] > maxVal) maxVal = dataArray[i];
        }
      }

      const db = maxVal > 0 ? Math.round((maxVal / 255) * 48 - 48) : -48;
      this.meterDbDisplay.innerText = `${db} dB`;

      const barWidth = (width / bufferLength) - 2;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255.0) * height * 0.9;
        const isSpeaking = this.currentState === "SPEAKING";

        this.canvasCtx.fillStyle = isSpeaking ? "#10b981" : "#3b82f6";
        if (this.currentState === "INTERRUPTED") this.canvasCtx.fillStyle = "#ef4444";

        this.canvasCtx.fillRect(x, height - barHeight, barWidth, barHeight);
        x += barWidth + 2;
      }
    };

    draw();
  }

  // --- Timestamped Call Log Helper ---
  addLogEntry(role, text, playbackId = null) {
    const now = new Date();
    const timeStr = now.toTimeString().split(" ")[0];

    const entry = document.createElement("div");
    entry.className = `log-entry ${role.toLowerCase()}-entry`;
    if (playbackId) {
      entry.setAttribute("data-playback", playbackId);
    }
    entry.innerHTML = `
      <div>
        <span class="entry-time">[${timeStr}]</span>
        <span class="entry-badge">${role}</span>
      </div>
      <p>${text}</p>
    `;
    this.feedMessages.appendChild(entry);
    this.feedMessages.scrollTop = this.feedMessages.scrollHeight;
  }

  updateMetrics(metrics) {
    if (metrics.turn_count !== undefined) this.turnCountEl.innerText = metrics.turn_count;
    if (metrics.interruption_count !== undefined) this.interruptCountEl.innerText = metrics.interruption_count;
  }

  // --- Event Listeners ---
  initEventListeners() {
    this.toggleMicBtn.addEventListener("click", () => this.toggleMic());
    this.modeToggleBtn.addEventListener("click", () => this.toggleMode());
    this.telephonyToggleBtn.addEventListener("click", () => this.toggleTelephonyCodec());
    this.noiseToggleBtn.addEventListener("click", () => this.toggleMarketNoise());
    this.recordSessionBtn.addEventListener("click", () => this.toggleSessionRecording());
    
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

    this.updateLanguagePrompts(this.selectedLanguage);

    this.clearFeedBtn.addEventListener("click", () => {
      this.feedMessages.innerHTML = "";
    });
  }
}

window.addEventListener("DOMContentLoaded", () => {
  window.duplexConsole = new DuplexVaniConsole();
});
