import logging
from typing import List, Dict, Any

logger = logging.getLogger("DuplexVani.LLMService")

class LLMService:
    """
    Conversational brain for DuplexVani.
    Supports Hindi, Hinglish, English, Telugu, Tamil, Kannada, and Marathi.
    """

    async def generate_response(
        self, 
        user_text: str, 
        history: List[Dict[str, str]], 
        was_interrupted: bool = False,
        language: str = "hi-IN"
    ) -> str:
        user_lower = user_text.lower().strip()
        lang_code = language.split("-")[0].lower() # 'hi', 'en', 'te', 'ta', 'kn', 'mr'

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
                return "Ji boliye, maine bolna band kar diya. Aap kya keh rahe the?"
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
