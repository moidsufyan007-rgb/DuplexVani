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
