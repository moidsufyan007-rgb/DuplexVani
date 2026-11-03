import pytest
from backend.services.llm_service import LLMService
from backend.core.state_machine import ConversationManager, VoiceState

def test_mandi_transaction_initial_booking():
    service = LLMService()
    txn, reply = service.parse_transaction(
        "Indore Mandi me 5 quintal gehun book karo",
        was_interrupted=False,
        active_txn=None,
        language="hi-IN"
    )
    assert txn is not None
    assert txn["domain"] == "MANDI_TRADE"
    assert "Indore APMC Mandi" in txn["counterparty"]
    assert "Wheat" in txn["item"]
    assert "5 Quintal" in txn["quantity"]
    assert "12,250" in txn["total_amount"]
    assert txn["status"] == "CONFIRMED"
    assert "12,250" in reply

def test_mandi_transaction_voice_bargein_override():
    service = LLMService()
    # Initial order
    t1, _ = service.parse_transaction(
        "Indore Mandi me 5 quintal gehun book karo",
        was_interrupted=False,
        active_txn=None,
        language="hi-IN"
    )
    assert t1 is not None

    # Simulate barge-in interruption override
    t2, reply2 = service.parse_transaction(
        "Wait, gehun nahi, 10 quintal sarson karo!",
        was_interrupted=True,
        active_txn=t1,
        language="hi-IN"
    )
    assert t2 is not None
    assert t2["domain"] == "MANDI_TRADE"
    assert "Mustard" in t2["item"]
    assert "10 Quintal" in t2["quantity"]
    assert "54,000" in t2["total_amount"]
    assert t2["status"] == "OVERRIDDEN_AND_CONFIRMED"
    assert "BARGE-IN" in t2["status_badge"]
    assert "54,000" in reply2
    assert len(t2["audit_trail"]) >= 3

def test_kirana_ledger_and_override():
    service = LLMService()
    k1, _ = service.parse_transaction(
        "Ramesh bhai ke khate mein 500 rupay udhaar likho",
        was_interrupted=False,
        active_txn=None,
        language="hi-IN"
    )
    assert k1 is not None
    assert k1["domain"] == "KIRANA_LEDGER"
    assert "Ramesh" in k1["counterparty"]
    assert "500" in k1["total_amount"]

    # Interruption override to 1200
    k2, reply_k2 = service.parse_transaction(
        "Ruko, 500 nahi, 1200 rupay likho!",
        was_interrupted=True,
        active_txn=k1,
        language="hi-IN"
    )
    assert k2 is not None
    assert "1,200" in k2["total_amount"]
    assert k2["status"] == "OVERRIDDEN_AND_CONFIRMED"
    assert "1,200" in reply_k2

def test_transaction_state_machine_integration():
    manager = ConversationManager("sess_test_txn")
    service = LLMService()

    # Step 1: Initial trade
    t1, _ = service.parse_transaction("Indore Mandi me 5 quintal gehun book karo")
    manager.update_transaction(t1)
    assert manager.active_transaction["total_amount"] == "Rs. 12,250"

    # Step 2: User interrupts while assistant is speaking
    manager.start_speaking("play_test")
    interrupt_meta = manager.trigger_interruption(None)
    assert interrupt_meta["state"] == VoiceState.INTERRUPTED.value
    assert manager.active_transaction["status"] == "PREEMPTED_BY_BARGE_IN"

    # Step 3: User provides overridden trade
    t2, _ = service.parse_transaction(
        "Wait, gehun nahi, 10 quintal sarson karo!",
        was_interrupted=True,
        active_txn=manager.active_transaction
    )
    manager.update_transaction(t2)
    assert manager.active_transaction["status"] == "OVERRIDDEN_AND_CONFIRMED"
    assert manager.active_transaction["total_amount"] == "Rs. 54,000"
