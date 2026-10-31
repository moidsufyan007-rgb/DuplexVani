import pytest
from starlette.testclient import TestClient
from backend.main import app
from backend.core.state_machine import ConversationManager, VoiceState

def test_health_endpoint():
    """Verify backend health check returns status and model info."""
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["project"] == "DuplexVani"
    assert "Gnani Prisma" in data["models"]["stt"]
    assert "Gnani Timbre" in data["models"]["tts"]

def test_state_machine_transitions():
    """Verify state transitions and barge-in latency calculation."""
    manager = ConversationManager("test_session_001")
    assert manager.state == VoiceState.IDLE

    # Transition to LISTENING
    manager.set_state(VoiceState.LISTENING)
    assert manager.state == VoiceState.LISTENING

    # Transition to SPEAKING
    manager.start_speaking("playback_123")
    assert manager.state == VoiceState.SPEAKING
    assert manager.is_interrupted() is False

    # Simulate barge-in interruption
    interrupt_info = manager.trigger_interruption(client_timestamp=None)
    assert manager.state == VoiceState.INTERRUPTED
    assert manager.is_interrupted() is True
    assert manager.interruption_count == 1
    assert "barge_in_latency_ms" in interrupt_info

def test_websocket_full_duplex_and_interruption():
    """Verify end-to-end WebSocket stream and preemptive barge-in abort."""
    client = TestClient(app)
    with client.websocket_connect("/ws/duplex") as ws:
        # 1. Connection Handshake
        handshake = ws.receive_json()
        assert handshake["type"] == "HANDSHAKE"
        assert "session_id" in handshake

        # 2. User Utterance
        ws.send_json({
            "type": "USER_SPEECH_FINAL",
            "text": "Namaste, aap kaun hain?"
        })

        # Drain messages until assistant begins speaking
        received_types = []
        while "ASSISTANT_REPLY_START" not in received_types:
            msg = ws.receive_json()
            received_types.append(msg["type"])

        assert "TRANSCRIPTION_RESULT" in received_types
        assert "ASSISTANT_REPLY_START" in received_types

        # 3. User Barge-in Interruption (Interrupt while speaking)
        ws.send_json({
            "type": "USER_INTERRUPT",
            "timestamp": 1000.0
        })

        # Confirm the server preempts and responds with INTERRUPT_CONFIRMED
        found_interrupt_ack = False
        for _ in range(3):
            msg = ws.receive_json()
            if msg["type"] == "INTERRUPT_CONFIRMED":
                found_interrupt_ack = True
                assert msg["data"]["total_interruptions"] >= 1
                assert "barge_in_latency_ms" in msg["data"]
                break

        assert found_interrupt_ack, "Server did not confirm barge-in interruption event"
