/**
 * DuplexVani - Timbre Studio UI Engine
 * High-fidelity clone with real-time waveform visualizer, dynamic telemetry,
 * and live full-duplex WebSocket voice call capabilities.
 */

(function () {
  'use strict';

  // --- State Variables ---
  let isCalling = false;
  let ws = null;
  let recognition = null;
  let audioContext = null;
  let analyser = null;
  let micStream = null;
  let animationFrameId = null;
  let isSpeaking = false;

  // DOM Elements
  const canvas = document.getElementById('timbreWaveformCanvas');
  const ctx = canvas ? canvas.getContext('2d') : null;
  const subtitleText = document.getElementById('liveSpeechText');
  const btnStartCall = document.getElementById('btnStartCall');
  const btnInterrupt = document.getElementById('btnInterrupt');
  const liveIndicator = document.getElementById('liveOutputStatus');
  const liveMeta = document.getElementById('liveOutputMeta');

  // Resize canvas for sharp retina rendering
  function resizeCanvas() {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    if (ctx) ctx.scale(dpr, dpr);
  }

  window.addEventListener('resize', resizeCanvas);
  setTimeout(resizeCanvas, 100);

  // --- Waveform Rendering Engine ---
  // Renders the exact symmetrical cyan equalizer bars from the screenshot
  let wavePhase = 0;
  const BAR_WIDTH = 3.5;
  const BAR_GAP = 3.5;
  const BAR_STEP = BAR_WIDTH + BAR_GAP;

  function drawWaveform() {
    if (!canvas || !ctx) return;
    const width = canvas.getBoundingClientRect().width;
    const height = canvas.getBoundingClientRect().height;
    const centerY = height / 2;

    ctx.clearRect(0, 0, width, height);

    const totalBars = Math.floor(width / BAR_STEP);
    wavePhase += 0.04;

    // Get microphone frequency data if call is live
    let freqData = null;
    if (analyser && isCalling) {
      freqData = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(freqData);
    }

    for (let i = 0; i < totalBars; i++) {
      const x = i * BAR_STEP + BAR_GAP;
      const normalizedPos = i / totalBars;

      let barHeight = 8; // baseline min height

      if (freqData && freqData.length > 0) {
        // Audio reactive
        const binIndex = Math.floor(normalizedPos * (freqData.length * 0.45));
        const val = freqData[binIndex] || 0;
        barHeight = Math.max(6, (val / 255) * (height * 0.88));
      } else {
        // Synthetic breathing multi-sine wave matching the screenshot visual
        const env1 = Math.sin(normalizedPos * Math.PI); // bell curve
        const wave1 = Math.sin(normalizedPos * 18 - wavePhase * 1.5);
        const wave2 = Math.cos(normalizedPos * 10 + wavePhase);
        const wave3 = Math.sin(normalizedPos * 28 - wavePhase * 2.2);

        const composite = (wave1 * 0.5 + wave2 * 0.3 + wave3 * 0.2) * env1;
        barHeight = Math.max(5, Math.abs(composite) * (height * 0.78) + 6);
      }

      // Symmetrical top and bottom around centerY
      const topY = centerY - barHeight / 2;
      const bottomY = centerY + barHeight / 2;

      // Create glowing cyan-teal gradient
      const gradient = ctx.createLinearGradient(0, topY, 0, bottomY);
      gradient.addColorStop(0, '#06b6d4');
      gradient.addColorStop(0.5, '#22d3ee');
      gradient.addColorStop(1, '#14b8a6');

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.roundRect(x, topY, BAR_WIDTH, barHeight, 2);
      ctx.fill();
    }

    animationFrameId = requestAnimationFrame(drawWaveform);
  }

  // Start waveform animation loop
  drawWaveform();

  // --- Dynamic Typewriter Subtitle ---
  const defaultQuote = "...and I can move that appointment to Thursday at ten — does that work for you";
  let charIdx = 0;
  let isDeleting = false;

  function typeWriterCycle() {
    if (isCalling) return; // During a live call, real speech replaces synthetic cycle
    if (!subtitleText) return;

    if (!isDeleting && charIdx <= defaultQuote.length) {
      subtitleText.textContent = defaultQuote.substring(0, charIdx);
      charIdx++;
      setTimeout(typeWriterCycle, 45);
    } else if (!isDeleting && charIdx > defaultQuote.length) {
      setTimeout(() => {
        isDeleting = true;
        typeWriterCycle();
      }, 5000);
    } else if (isDeleting && charIdx > 0) {
      subtitleText.textContent = defaultQuote.substring(0, charIdx);
      charIdx--;
      setTimeout(typeWriterCycle, 20);
    } else {
      isDeleting = false;
      setTimeout(typeWriterCycle, 1000);
    }
  }

  setTimeout(typeWriterCycle, 800);

  // --- Interactive Live Full-Duplex Connection ---
  async function startLiveSession() {
    try {
      // Initialize Audio Context & Microphone Analyser
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const source = audioContext.createMediaStreamSource(micStream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 128;
      source.connect(analyser);

      // Establish WebSocket to DuplexVani backend
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/ws/call`;
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        isCalling = true;
        updateCallUI(true);
        if (subtitleText) subtitleText.textContent = "Live Duplex Connected. Speak into microphone in English or Hindi...";
        if (liveIndicator) liveIndicator.innerHTML = '<span class="live-dot"></span> 1 CONCURRENT SESSION (LIVE)';
        initSpeechRecognition();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleServerMessage(data);
        } catch (err) {
          console.error("WS Parse error", err);
        }
      };

      ws.onerror = (err) => {
        console.error("WS Error:", err);
      };

      ws.onclose = () => {
        endLiveSession();
      };
    } catch (err) {
      console.warn("Microphone or WebSocket error, running in simulated telemetry mode:", err);
      alert("Microphone permission required for live voice test. Falling back to simulation mode.");
    }
  }

  function handleServerMessage(data) {
    if (data.type === "STATE_CHANGE") {
      if (data.state === "SPEAKING") {
        isSpeaking = true;
        if (btnInterrupt) btnInterrupt.style.display = "inline-flex";
      } else {
        isSpeaking = false;
      }
    } else if (data.type === "TRANSCRIPT_CHUNK" || data.type === "TRANSCRIPT_FINAL") {
      const text = data.text || "";
      if (subtitleText && text) {
        subtitleText.textContent = (data.role === "assistant" ? "DuplexVani: " : "You: ") + text;
      }
    } else if (data.type === "METRICS_UPDATE" && data.metrics) {
      if (liveMeta) {
        liveMeta.textContent = `sess_${(data.metrics.session_id || "8f2a41c9").slice(0, 8)} · ATLAS · 24 kHz · TTFA ${Math.round(data.metrics.ttfa_ms || 141)} ms`;
      }
    }
  }

  function endLiveSession() {
    isCalling = false;
    isSpeaking = false;
    if (recognition) {
      try { recognition.stop(); } catch (e) {}
      recognition = null;
    }
    if (micStream) {
      micStream.getTracks().forEach(t => t.stop());
      micStream = null;
    }
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.close();
    }
    ws = null;
    analyser = null;
    updateCallUI(false);
    if (subtitleText) subtitleText.textContent = defaultQuote;
    if (liveIndicator) liveIndicator.innerHTML = '<span class="live-dot"></span> 340 CONCURRENT SESSIONS';
  }

  function updateCallUI(active) {
    if (!btnStartCall) return;
    if (active) {
      btnStartCall.innerHTML = `
        <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
        End Live Call
      `;
      btnStartCall.style.backgroundColor = "#ef4444";
      if (btnInterrupt) btnInterrupt.style.display = "inline-flex";
    } else {
      btnStartCall.innerHTML = `
        <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2H3v2a9 9 0 0 0 8 8.94V23h2v-2.06A9 9 0 0 0 21 12v-2h-2z"/></svg>
        Start Live Duplex Call
      `;
      btnStartCall.style.backgroundColor = "#10b981";
      if (btnInterrupt) btnInterrupt.style.display = "none";
    }
  }

  function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-IN';

    recognition.onresult = (e) => {
      let interim = '';
      let final = '';
      for (let i = e.resultIndex; i < e.results.length; ++i) {
        if (e.results[i].isFinal) {
          final += e.results[i][0].transcript;
        } else {
          interim += e.results[i][0].transcript;
        }
      }
      const activeText = final || interim;
      if (activeText && subtitleText) {
        subtitleText.textContent = `You: ${activeText}`;
      }
      if (final && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "USER_SPEECH_FINAL",
          text: final.trim(),
          language: "en-IN"
        }));
      }
    };

    recognition.onend = () => {
      if (isCalling && recognition) {
        try { recognition.start(); } catch (err) {}
      }
    };

    try {
      recognition.start();
    } catch (e) {
      console.warn("SpeechRec error:", e);
    }
  }

  // Barge-In Interruption trigger
  function triggerInterruption() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "INTERRUPT" }));
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      if (subtitleText) subtitleText.textContent = "[Barge-In: Assistant interrupted]";
    }
  }

  // --- Keyboard Shortcuts ---
  window.addEventListener('keydown', (e) => {
    if (e.code === 'Space' && isCalling) {
      e.preventDefault();
      triggerInterruption();
    }
  });

  // --- Button Event Listeners ---
  if (btnStartCall) {
    btnStartCall.addEventListener('click', () => {
      if (isCalling) {
        endLiveSession();
      } else {
        startLiveSession();
      }
    });
  }

  if (btnInterrupt) {
    btnInterrupt.addEventListener('click', triggerInterruption);
  }

  // Sidebar item tab switching
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
      if (item.classList.contains('active')) return;
      document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
      item.classList.add('active');
    });
  });

  console.log("DuplexVani Timbre Studio UI Initialized successfully.");
})();
