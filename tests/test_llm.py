import pytest
from backend.services.llm_service import LLMService

@pytest.mark.asyncio
async def test_llm_service_gemini_generation():
    service = LLMService()
    # Test open-ended dynamic generation
    response = await service.generate_response(
        user_text="What is the capital of India?", 
        history=[], 
        was_interrupted=False, 
        language="en-IN"
    )
    assert isinstance(response, str)
    assert len(response) > 0
    assert "new delhi" in response.lower() or "delhi" in response.lower()

@pytest.mark.asyncio
async def test_llm_service_fallback_on_invalid_key():
    service = LLMService()
    service.api_key = "invalid_key_123"
    response = await service.generate_response(
        user_text="mandi me bhav kya hai", 
        history=[], 
        was_interrupted=False, 
        language="hi-IN"
    )
    assert isinstance(response, str)
    assert "Indore Mandi" in response

def test_indic_language_detection():
    service = LLMService()
    assert service.detect_language("What is the capital of India?") == "en-IN"
    assert service.detect_language("Indore mandi me gehun ka bhav kya hai?") == "hi-IN"
    assert service.detect_language("Namaskaram, meeru evaru mariyu ela pani chestaru?") == "te-IN"
    assert service.detect_language("Vanakkam, neengal yaar?") == "ta-IN"
    assert service.detect_language("भारत की राजधानी क्या है?") == "hi-IN"
    assert service.detect_language("మీ పేరు ఏమిటి?") == "te-IN"
    assert service.detect_language("உங்கள் பெயர் என்ன?") == "ta-IN"
