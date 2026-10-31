import os
import time
import json
import base64
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.core.state_machine import ConversationManager, VoiceState
from backend.gnani.client import gnani_client
from backend.services.llm_service import llm_service

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("DuplexVani.App")

app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "simulated_mode": gnani_client.simulated,
        "models": {
            "stt": "Gnani Prisma",
            "tts": "Gnani Timbre",
            "llm": "Conversational Hinglish Core"
        }
    }

async def process_speech_turn(
    websocket: WebSocket,
    manager: ConversationManager,
    user_text: str,
    audio_b64: str = None
):
    """
    Handles a full speech turn asynchronously.
    Can be cancelled instantly by asyncio if the user interrupts.
    """
    session_id = manager.session_id
    try:
        # 1. Transcribe audio if raw audio was sent
        if audio_b64 and not user_text:
            manager.set_state(VoiceState.PROCESSING)
            await websocket.send_json({"type": "STATE_CHANGE", "state": VoiceState.PROCESSING.value})
            audio_bytes = base64.b64decode(audio_b64)
            user_text = await gnani_client.transcribe_audio(audio_bytes, language=settings.DEFAULT_LANGUAGE)

        if not user_text.strip():
            manager.set_state(VoiceState.LISTENING)
            await websocket.send_json({"type": "STATE_CHANGE", "state": VoiceState.LISTENING.value})
            return

        manager.add_user_message(user_text)
        await websocket.send_json({
            "type": "TRANSCRIPTION_RESULT",
            "role": "user",
            "text": user_text
        })

        # 2. Generate response via LLM Brain
        manager.set_state(VoiceState.PROCESSING)
        await websocket.send_json({"type": "STATE_CHANGE", "state": VoiceState.PROCESSING.value})

        was_interrupted = manager.is_interrupted()
        reply_text = await llm_service.generate_response(user_text, manager.history, was_interrupted=was_interrupted)

        # 3. Notify client that assistant speech is beginning
        playback_id = f"play_{int(time.time()*1000)}"
        manager.start_speaking(playback_id)
        await websocket.send_json({
            "type": "ASSISTANT_REPLY_START",
            "playback_id": playback_id,
            "text": reply_text,
            "state": VoiceState.SPEAKING.value
        })

        # 4. Synthesize voice audio via Gnani Timbre
        audio_bytes = await gnani_client.synthesize_speech(reply_text, language=settings.DEFAULT_LANGUAGE)

        # 5. Deliver audio payload to client
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        await websocket.send_json({
            "type": "AUDIO_PAYLOAD",
            "playback_id": playback_id,
            "audio_base64": audio_base64,
            "format": "audio/wav"
        })
        manager.add_assistant_message(reply_text, was_cut_off=False)

    except asyncio.CancelledError:
        logger.info(f"[{session_id}] Speech turn task successfully aborted by barge-in interruption.")
        manager.add_assistant_message(user_text, was_cut_off=True)
        raise

@app.websocket("/ws/duplex")
async def duplex_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = f"sess_{int(time.time()*1000)}"
    manager = ConversationManager(session_id)
    active_turn_task: asyncio.Task = None
    logger.info(f"New full-duplex session connected: {session_id}")

    # Send initial connection handshake
    await websocket.send_json({
        "type": "HANDSHAKE",
        "session_id": session_id,
        "state": VoiceState.IDLE.value,
        "simulated": gnani_client.simulated,
        "message": "Connected to DuplexVani Real-Time Voice Gateway"
    })

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            msg_type = data.get("type", "")

            # 1. USER BARGE-IN / INTERRUPTION EVENT
            if msg_type == "USER_INTERRUPT":
                client_ts = data.get("timestamp")

                # Instantly abort any active generation or audio task
                if active_turn_task and not active_turn_task.done():
                    active_turn_task.cancel()
                    active_turn_task = None

                interrupt_meta = manager.trigger_interruption(client_ts)
                logger.info(f"[{session_id}] Barge-in interruption preempted stream! Latency: {interrupt_meta['barge_in_latency_ms']}ms")

                await websocket.send_json({
                    "type": "INTERRUPT_CONFIRMED",
                    "data": interrupt_meta
                })

            # 2. USER SPEECH FINISHED
            elif msg_type == "USER_SPEECH_FINAL":
                user_text = data.get("text", "")
                audio_b64 = data.get("audio_b64")

                # Cancel prior task if still running
                if active_turn_task and not active_turn_task.done():
                    active_turn_task.cancel()

                # Spawn new turn task concurrently
                active_turn_task = asyncio.create_task(
                    process_speech_turn(websocket, manager, user_text, audio_b64)
                )

            # 3. PLAYBACK FINISHED NOTIFICATION FROM CLIENT
            elif msg_type == "PLAYBACK_FINISHED":
                if manager.state == VoiceState.SPEAKING:
                    manager.stop_speaking()
                    await websocket.send_json({
                        "type": "STATE_CHANGE",
                        "state": VoiceState.LISTENING.value,
                        "metrics": manager.get_metrics()
                    })

            # 4. PING / LATENCY PROBE
            elif msg_type == "PING":
                await websocket.send_json({
                    "type": "PONG",
                    "client_ts": data.get("client_ts"),
                    "server_ts": time.time() * 1000
                })

    except WebSocketDisconnect:
        if active_turn_task and not active_turn_task.done():
            active_turn_task.cancel()
        logger.info(f"Session disconnected: {session_id}")
    except Exception as e:
        if active_turn_task and not active_turn_task.done():
            active_turn_task.cancel()
        logger.exception(f"Unexpected error in websocket session: {e}")

# Mount frontend directory for browser UI
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
