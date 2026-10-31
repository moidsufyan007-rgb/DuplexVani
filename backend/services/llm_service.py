import logging
from typing import List, Dict, Any

logger = logging.getLogger("DuplexVani.LLMService")

DUPLEX_SYSTEM_PROMPT = """You are DuplexVani, an ultra-fast conversational voice AI built with Gnani AI voice models.
Key Rules:
1. Keep responses very short (1-2 sentences max) for spoken voice.
2. Speak naturally in colloquial, friendly Hinglish.
3. If interrupted, acknowledge the user's interruption gracefully.
"""

class LLMService:
    """
    Conversational brain for DuplexVani.
    Generates fast, colloquial Hinglish conversational utterances.
    """

    async def generate_response(self, user_text: str, history: List[Dict[str, str]], was_interrupted: bool = False) -> str:
        user_lower = user_text.lower().strip()

        # 1. Graceful recovery if user just interrupted the bot
        if was_interrupted:
            return "Ji boliye, maine bolna band kar diya. Aap kya keh rahe the?"

        # 2. Interruption keywords
        if any(w in user_lower for w in ["ruko", "stop", "wait", "suno", "arrey", "arre"]):
            return "Ji bilkul, main ruk gaya. Kahiye, main sun raha hoon."

        # 3. Identity / Hackathon question
        if any(w in user_lower for w in ["kya ho", "who are you", "kaun ho", "duplex"]):
            return "Namaste! Main DuplexVani hoon — Gnani AI ke Prisma aur Timbre models par bana full-duplex voice agent. Aap mujhe bolte hue kabhi bhi interrupt kar sakte hain!"

        # 4. Regional Mandi Bhav demo scenario
        if any(w in user_lower for w in ["mandi", "kisan", "fasal", "bhav"]):
            return "Indore Mandi me aaj gehun 2450 rupay per quintal aur pyaz 28 rupay kilo chal raha hai. Kya aapko kisi aur fasal ka bhav dekhna hai?"

        # 5. Grassroots Kirana Khata demo scenario
        if any(w in user_lower for w in ["kirana", "doodh", "hisaab", "khata", "sugar"]):
            return "Ramesh bhai ke khate mein 2 packet doodh aur 1 packet bread ka 140 rupay udhaar note kar liya gaya hai."

        # Default conversational response
        return f"Main samajh gaya. Aapne kaha '{user_text}'. Isme main aapki poori sahayata kar sakta hoon, bataiye aage kya karna hai?"

llm_service = LLMService()
