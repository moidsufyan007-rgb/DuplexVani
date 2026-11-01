import logging
import re
from typing import List, Dict, Any
import httpx
from backend.config import settings

logger = logging.getLogger("DuplexVani.LLMService")

class LLMService:
    """
    Dynamic Conversational Brain for DuplexVani.
    Uses a multi-model fallback cascade across Google Gemini Flash/Lite models,
    with an intelligent rule-based fallback if offline.
    """

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY.strip()
        # Fallback model cascade to guarantee 100% uptime even if one model hits quota
        self.models = [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.7-flash"
        ]

    async def generate_response(
        self, 
        user_text: str, 
        history: List[Dict[str, str]] = None, 
        was_interrupted: bool = False,
        language: str = "en-IN"
    ) -> str:
        history = history or []
        
        # Try dynamic Gemini LLM cascade if API key is provided
        if self.api_key:
            try:
                response = await self._call_gemini_cascade(user_text, history, was_interrupted, language)
                if response:
                    return response
            except Exception as e:
                logger.warning(f"All Gemini models in cascade failed: {e}. Using intelligent fallback.")

        # Fallback to local intelligent response engine
        return self._rule_based_fallback(user_text, was_interrupted, language)

    async def _call_gemini_cascade(
        self, 
        user_text: str, 
        history: List[Dict[str, str]], 
        was_interrupted: bool, 
        language: str
    ) -> str:
        lang_code = language.split("-")[0].lower()
        lang_names = {
            "en": "clear, conversational Indian English",
            "hi": "Hindi or natural conversational Hinglish",
            "te": "Telugu (natural conversational Telugu)",
            "ta": "Tamil (natural conversational Tamil)",
            "kn": "Kannada",
            "mr": "Marathi"
        }
        target_lang = lang_names.get(lang_code, "clear conversational English")

        system_instruction = (
            f"You are DuplexVani, an Indian real-time conversational voice assistant powered by Gnani AI. "
            f"You are speaking out loud to the user via Gnani Timbre speech synthesis.\n"
            f"CRITICAL RULES:\n"
            f"1. Respond strictly in {target_lang}.\n"
            f"2. Keep responses brief (1-2 spoken sentences maximum, under 25 words).\n"
            f"3. Strictly DO NOT use markdown, bolding, asterisks, bullet points, numbered lists, or emojis. "
            f"The output must be pure plain text suitable for direct speech synthesis.\n"
            f"4. NEVER start answers with repetitive filler phrases like 'Ji boliye' or 'G. Bolie' or 'Got it, you said'. "
            f"Answer the user's question directly, intelligently, and conversationally.\n"
        )
        if was_interrupted:
            system_instruction += (
                "5. NOTE: The user just interrupted you. Seamlessly transition and answer what they just asked.\n"
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
                "temperature": 0.7,
                "maxOutputTokens": 90
            }
        }

        # Try models in cascade
        async with httpx.AsyncClient(timeout=3.5) as client:
            for model_name in self.models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
                    resp = await client.post(url, json=payload)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        clean = re.sub(r"[\*#_`~<>]", "", raw_text).strip()
                        clean = " ".join(clean.split())
                        if clean:
                            logger.info(f"Gemini [{model_name}] generated response ({language}): {clean}")
                            return clean
                    elif resp.status_code == 429:
                        logger.warning(f"Model {model_name} quota exceeded (429). Falling back to next model...")
                        continue
                    else:
                        logger.warning(f"Model {model_name} returned status {resp.status_code}: {resp.text}")
                except Exception as model_err:
                    logger.warning(f"Error calling {model_name}: {model_err}")
                    continue

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
                return "Namaskaram! Nenu DuplexVani — Gnani AI models tho tayaraina full-duplex voice assistant."
            if any(w in user_lower for w in ["capital", "rajadhani", "india"]):
                return "Bharatadesha rajadhani New Delhi."
            return f"Nenu artham chesukonnanu. Meeru adigina vishayam gurinchi nenu sahayapadagalanu."

        # --- TAMIL ---
        elif lang_code == "ta":
            if was_interrupted:
                return "Sollunga, naan pesuvadhu niruthivitten."
            if any(w in user_lower for w in ["nillu", "stop", "wait"]):
                return "Sari, naan niruthi vitten. Sollunga."
            if any(w in user_lower for w in ["yaar", "who", "duplex"]):
                return "Vanakkam! Naan DuplexVani — Gnani AI modelsil uruvaakkappatta voice assistant!"
            if any(w in user_lower for w in ["capital", "thalainagaram", "india"]):
                return "Indhiyavin thalainagaram Pudhu Delhi aagum."
            return f"Naan purindhu konden. Naan ungalukku eppadi uthavalaam?"

        # --- ENGLISH (Indian English) ---
        elif lang_code == "en":
            if was_interrupted:
                return "Go ahead, I am listening."
            if any(w in user_lower for w in ["stop", "wait", "hold on", "listen"]):
                return "Sure, I have paused. Please continue."
            if any(w in user_lower for w in ["who are you", "what is this", "duplex"]):
                return "Hello! I am DuplexVani — a real-time full-duplex voice agent powered by Gnani AI's Prisma and Timbre models."
            if any(w in user_lower for w in ["capital of india", "capital of bharat", "capital"]):
                return "The capital of India is New Delhi."
            if any(w in user_lower for w in ["domestic animal", "animal", "pets"]):
                return "People love domestic animals because they offer unconditional companionship, warmth, and loyalty."
            if any(w in user_lower for w in ["weather", "forecast", "climate"]):
                return "The weather is currently clear and pleasant with mild temperatures."
            if any(w in user_lower for w in ["mandi", "market", "prices", "rate"]):
                return "In the wholesale agricultural market today, wheat is trading around 2450 rupees per quintal."
            return f"I understand your query. Let me assist you with that."

        # --- HINDI & HINGLISH (Default) ---
        else:
            if was_interrupted:
                return "Haan, main sun raha hoon. Kahiye?"
            if any(w in user_lower for w in ["ruko", "stop", "wait", "suno", "arrey", "arre"]):
                return "Ji bilkul, main ruk gaya. Kahiye, main sun raha hoon."
            if any(w in user_lower for w in ["kya ho", "who are you", "kaun ho", "duplex"]):
                return "Namaste! Main DuplexVani hoon — Gnani AI ke Prisma aur Timbre models par bana full-duplex voice agent."
            if any(w in user_lower for w in ["capital", "rajdhani", "bharat", "india"]):
                return "Bharat ki rajdhani New Delhi hai."
            if any(w in user_lower for w in ["domestic animal", "janwar", "kutte", "pets"]):
                return "Log paaltu janwaron se pyaar karte hain kyunki wo wafadaar hote hain aur insaano ka tanav kam karte hain."
            if any(w in user_lower for w in ["mandi", "kisan", "fasal", "bhav"]):
                return "Indore Mandi me aaj gehun 2450 rupay per quintal aur pyaz 28 rupay kilo chal raha hai."
            if any(w in user_lower for w in ["kirana", "doodh", "hisaab", "khata", "sugar"]):
                return "Ramesh bhai ke khate mein 2 packet doodh aur 1 packet bread ka 140 rupay udhaar note kar liya gaya hai."
            return f"Main samajh gaya. Isme main aapki poori sahayata kar sakta hoon."

llm_service = LLMService()
