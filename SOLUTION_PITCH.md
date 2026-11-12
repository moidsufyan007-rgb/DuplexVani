# DuplexVani — 1-Page Solution Pitch
### Great Indian AI Internship Challenge 2026 | Gnani AI
**Submitted by:** Mohd Abdul Moid Sufiyan | MJCET, Hyderabad

---

## 🔴 The Problem

India's 7,000+ APMC mandis and 12 million kirana stores run on **voice — not apps**. A mandi trader negotiating wheat prices at 6 AM has no time to type. A kirana owner tracking credit in a noisy bazaar can't use a form. Existing voice bots break the moment a user talks over them — they wait, they miss words, they restart. For Bharat's real-world commerce, **half-duplex voice AI is not enough**.

---

## ✅ The Solution — DuplexVani

**DuplexVani** is a **full-duplex agentic voice desk** where the AI listens and speaks *at the same time* — just like a real human conversation partner.

| Capability | How It Works |
|---|---|
| **Sub-16ms Barge-In Preemption** | Web Audio API energy-based VAD detects user interruption in a single 16ms frame and cancels AI speech via `asyncio.Task.cancel()` — no lag, no overlap |
| **APMC Mandi Trade State Machine** | Deterministic 7-state engine: `IDLE → COMMODITY → QUANTITY → PRICE → CONFIRMED → EXECUTED`. LLM extracts intent; state machine enforces correctness — AI cannot corrupt a trade |
| **Gnani AI Voice Stack** | Gnani Prisma v3.0 STT + Timbre v3.0 TTS — optimized for 8kHz GSM telephony and Hindi/Hinglish/Telugu code-switching out of the box |
| **Zero-Click Indic Code-Switching** | Phonetic normalization handles *"do sau kilo sarso"*, *"teen hazaar rate do"* — no language selection needed |
| **Kirana Voice Ledger** | Farmers and shop owners can book trades, check rates, and manage credit entirely by voice — zero literacy barrier |

---

## 🏗️ Architecture (3-Layer)

```
[User Voice] → Gnani Prisma STT → Gemini Flash LLM (intent) → Trade State Machine
                                                                      ↓
[User Hears] ← Gnani Timbre TTS ← Response Generator ← State Transition Output
                    ↑
         Sub-16ms VAD Barge-In interrupts this pipeline at any point
```

**Stack:** FastAPI · WebSocket (full-duplex) · Gnani Vachana API · Gemini Flash · Web Audio API · Python asyncio

---

## 📊 Why It Wins

- **10/10 automated tests passing** — trade flows, barge-in, STT fallback, state rollback
- **57-second full-conversation demo** — APMC wheat trade from greeting to execution with live interruption
- **8kHz GSM telephony simulation** — built for real mandi phone conditions, not lab Wi-Fi
- **Render-deployable** — `render.yaml` included for 1-click public hosting

---

## 🎬 Links

| Resource | URL |
|---|---|
| **GitHub Repo** | https://github.com/moidsufyan007-rgb/DuplexVani |
| **Demo Video (57s)** | https://github.com/moidsufyan007-rgb/DuplexVani/releases/tag/v1.0.0 |
| **Watch Demo Direct** | https://github.com/moidsufyan007-rgb/DuplexVani/releases/download/v1.0.0/DuplexVani_Full_Conversation_Demo.mp4 |

---

*Built in under 10 days · Solo participant · Powered by Gnani AI + Google Gemini*
