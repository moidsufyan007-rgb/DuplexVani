import logging
import re
from typing import List, Dict, Any
import httpx
from backend.config import settings

logger = logging.getLogger("DuplexVani.LLMService")

class LLMService:
    """
    Dynamic Conversational Brain for DuplexVani.
    Uses Google Gemini Flash when GEMINI_API_KEY is configured,
    with an instant zero-latency rule-based fallback for reliability.
    """

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY.strip()
        self.model = "gemini-3.5-flash"
        self.gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    async def generate_response(
        self, 
        user_text: str, 
        history: List[Dict[str, str]] = None, 
        was_interrupted: bool = False,
        language: str = "hi-IN"
    ) -> str:
        history = history or []
        
        # Try dynamic Gemini LLM first if API key is provided
        if self.api_key:
            try:
                response = await self._call_gemini(user_text, history, was_interrupted, language)
                if response:
                    return response
            except Exception as e:
                logger.warning(f"Gemini API call failed or timed out: {e}. Falling back to local brain.")

        # Fallback to local rule-based engine
        return self._rule_based_fallback(user_text, was_interrupted, language)

    async def _call_gemini(
        self, 
        user_text: str, 
        history: List[Dict[str, str]], 
        was_interrupted: bool, 
        language: str
    ) -> str:
        lang_code = language.split("-")[0].lower()
        lang_names = {
            "hi": "Hindi or natural conversational Hinglish",
            "en": "clear Indian English",
            "te": "Telugu (natural conversational Telugu)",
            "ta": "Tamil (natural conversational Tamil)",
            "kn": "Kannada",
            "mr": "Marathi"
        }
        target_lang = lang_names.get(lang_code, "Hindi or conversational Hinglish")

        system_instruction = (
            f"You are DuplexVani, an Indian real-time conversational voice assistant powered by Gnani AI. "
            f"You are speaking out loud to the user via Gnani Timbre speech synthesis.\n"
            f"CRITICAL RULES:\n"
            f"1. Respond strictly in {target_lang}.\n"
            f"2. Keep responses brief (1-2 spoken sentences maximum, under 25 words).\n"
            f"3. Strictly DO NOT use markdown, bolding, asterisks, bullet points, numbered lists, or emojis. "
            f"The output must be pure plain text suitable for direct speech synthesis.\n"
            f"4. NEVER start answers with repetitive filler phrases like 'Ji boliye' or 'G. Bolie' or 'Haan boliye'. "
            f"Answer the user's intent directly, naturally, and conversationally.\n"
        )
        if was_interrupted:
            system_instruction += (
                "5. NOTE: The user just interrupted you while you were speaking! "
                "Briefly acknowledge with 'Sure' or 'Got it' and directly address their statement.\n"
            )

        # Build contents from recent conversation turns
        contents = []
        recent_history = history[-6:] if len(history) > 6 else history
        for msg in recent_history:
            role = "user" if msg.get("role") == "user" else "model"
            text = msg.get("text", "")
            if text:
                contents.append({"role": role, "parts": [{"text": text}]})

        # Append current user prompt
        contents.append({"role": "user", "parts": [{"text": user_text}]})

        payload = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "generationConfig": {
                "thinkingConfig": {"thinkingBudget": 0},
                "temperature": 0.7,
                "maxOutputTokens": 120
            }
        }

        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(
                f"{self.gemini_url}?key={self.api_key}",
                json=payload
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                # Sanitize any accidental formatting/markdown for TTS
                clean = re.sub(r"[\*#_`~<>]", "", raw_text).strip()
                clean = " ".join(clean.split())
                if clean:
                    logger.info(f"Gemini LLM generated response ({language}): {clean}")
                    return clean
            else:
                logger.warning(f"Gemini returned status {resp.status_code}: {resp.text}")
                return ""

    def _rule_based_fallback(self, user_text: str, was_interrupted: bool, language: str) -> str:
        user_lower = user_text.lower().strip()
        lang_code = language.split("-")[0].lower()

        # --- TELUGU ---
        if lang_code == "te":
            if was_interrupted:
                return "Cheppandi, nenu maatladadam aapesanu. Meeru em chebutunnaru?"
            if any(w in user_lower for w in ["aagu", "stop", "wait", "ruko"]):
                return "Sare, nenu aagipoyanu. Cheppandi."
            if any(w in user_lower for w in ["evaru", "who", "kaun", "duplex"]):
                return "Namaskaram! Nenu DuplexVani — Gnani AI models tho tayaraina full-duplex voice assistant. Meeru nannu eppudaina interrupt cheyavachhu!"
            return f"Nenu artham chesukonnanu. Meeru '{user_text}' annaru. Nenu meeku ela sahayapadagalanu?"

        # --- TAMIL ---
        elif lang_code == "ta":
            if was_interrupted:
                return "Sollunga, naan pesuvadhu niruthivitten. Neengal enna sonneergal?"
            if any(w in user_lower for w in ["nillu", "stop", "wait"]):
                return "Sari, naan niruthi vitten. Sollunga."
            if any(w in user_lower for w in ["yaar", "who", "duplex"]):
                return "Vanakkam! Naan DuplexVani — Gnani AI Prisma matrum Timbre modelsil uruvaakkappatta full-duplex voice assistant!"
            return f"Naan purindhu konden. Neengal '{user_text}' sonneergal. Naan ungalukku eppadi uthavalaam?"

        # --- ENGLISH (Indian English) ---
        elif lang_code == "en":
            if was_interrupted:
                return "Go ahead, I stopped speaking for you! What were you saying?"
            if any(w in user_lower for w in ["stop", "wait", "hold on", "listen"]):
                return "Sure, I have paused. Please continue."
            if any(w in user_lower for w in ["who are you", "what is this", "duplex"]):
                return "Hello! I am DuplexVani — a real-time full-duplex voice agent powered by Gnani AI's Prisma and Timbre models. You can interrupt me anytime!"
            return f"Got it. You said '{user_text}'. How can I assist you further?"

        # --- HINDI & HINGLISH (Default) ---
        else:
            if was_interrupted:
                return "Haan, main sun raha hoon. Kahiye?"
            if any(w in user_lower for w in ["ruko", "stop", "wait", "suno", "arrey", "arre"]):
                return "Ji bilkul, main ruk gaya. Kahiye, main sun raha hoon."
            if any(w in user_lower for w in ["kya ho", "who are you", "kaun ho", "duplex"]):
                return "Namaste! Main DuplexVani hoon — Gnani AI ke Prisma aur Timbre models par bana full-duplex voice agent. Aap mujhe bolte hue kabhi bhi interrupt kar sakte hain!"
            if any(w in user_lower for w in ["mandi", "kisan", "fasal", "bhav"]):
                return "Indore Mandi me aaj gehun 2450 rupay per quintal aur pyaz 28 rupay kilo chal raha hai. Kya aapko kisi aur fasal ka bhav dekhna hai?"
            if any(w in user_lower for w in ["kirana", "doodh", "hisaab", "khata", "sugar"]):
                return "Ramesh bhai ke khate mein 2 packet doodh aur 1 packet bread ka 140 rupay udhaar note kar liya gaya hai."
            return f"Main samajh gaya. Aapne kaha '{user_text}'. Isme main aapki poori sahayata kar sakta hoon, bataiye aage kya karna hai?"

llm_service = LLMService()
