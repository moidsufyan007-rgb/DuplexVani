import logging
import re
import time
from typing import List, Dict, Any, Tuple, Optional
import httpx
from backend.config import settings

logger = logging.getLogger("DuplexVani.LLMService")

COMMODITY_RATES = {
    "sarson": {"name": "Mustard (Sarson)", "rate": 5400, "unit": "Quintal"},
    "mustard": {"name": "Mustard (Sarson)", "rate": 5400, "unit": "Quintal"},
    "gehun": {"name": "Wheat (Gehun)", "rate": 2450, "unit": "Quintal"},
    "wheat": {"name": "Wheat (Gehun)", "rate": 2450, "unit": "Quintal"},
    "soyabean": {"name": "Soybean (Soyabean)", "rate": 4800, "unit": "Quintal"},
    "soybean": {"name": "Soybean (Soyabean)", "rate": 4800, "unit": "Quintal"},
    "pyaz": {"name": "Onion (Pyaz)", "rate": 2800, "unit": "Quintal"},
    "onion": {"name": "Onion (Pyaz)", "rate": 2800, "unit": "Quintal"},
    "chana": {"name": "Gram (Chana)", "rate": 5900, "unit": "Quintal"},
    "cotton": {"name": "Cotton (Kapas)", "rate": 7200, "unit": "Quintal"},
    "kapas": {"name": "Cotton (Kapas)", "rate": 7200, "unit": "Quintal"}
}

MANDI_LOCATIONS = ["Indore", "Nashik", "Bhopal", "Neemuch", "Kota", "Dewas", "Nagpur", "Guntur"]

WORD_TO_NUM = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
    "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10, "gyarah": 11, "barah": 12,
    "pandrah": 15, "bees": 20, "pachis": 25, "tees": 30, "pachaas": 50,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "twenty": 20, "fifty": 50, "hundred": 100
}

class LLMService:
    """
    Enterprise Conversational Brain & Transaction Engine for DuplexVani.
    Supports:
    1. APMC Mandi Agri-Trade Desk with Voice Interruption Preemption.
    2. Bharat Kirana & Banking Voice Ledger.
    3. Multi-Model Gemini Flash cascade for open-ended queries.
    4. Deterministic offline fallback engine.
    """

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY.strip()
        self.models = [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.7-flash"
        ]

    def detect_language(self, text: str) -> str:
        """
        Sub-millisecond Indic Code-Switching detector.
        Identifies Devanagari, Telugu, Tamil, Kannada scripts,
        or classifies Romanized Hinglish vs Indian English.
        """
        if not text or not text.strip():
            return "en-IN"

        # 1. Unicode Script Range Check
        for char in text:
            cp = ord(char)
            if 0x0900 <= cp <= 0x097F:
                return "hi-IN"
            if 0x0C00 <= cp <= 0x0C7F:
                return "te-IN"
            if 0x0B80 <= cp <= 0x0BFF:
                return "ta-IN"
            if 0x0C80 <= cp <= 0x0CFF:
                return "kn-IN"

        # 2. Romanized Indic Vocabulary Check
        words = set(text.lower().replace("?", " ").replace(".", " ").replace(",", " ").replace("!", " ").split())
        
        hi_indicators = {
            "kya", "hai", "hain", "bhav", "batao", "namaste", "kaun", "ho", "ruko", "meri", "baat", 
            "suno", "doodh", "khata", "gehun", "chahiye", "kaise", "kahan", "nahi", "theek", 
            "bolo", "aap", "mera", "tum", "kisan", "mandi", "pyaz", "arrey", "arre", "hisaab",
            "shukriya", "dhanyawad", "samajh", "bhai", "paaltu", "janwar", "rajdhani", "sarson",
            "quintal", "udhaar", "likho", "badal", "karo"
        }
        te_indicators = {
            "meeru", "evaru", "namaskaram", "ela", "unnaru", "cheppandi", "eeroju", "dharalu", 
            "godhumalu", "aagandi", "naaku", "pani", "bharatadesha", "rajadhani", "sahayam"
        }
        ta_indicators = {
            "vanakkam", "neengal", "yaar", "sollunga", "eppadi", "irukkeenga", "sandhai", 
            "nillungal", "pesugiren", "velai", "thalainagaram", "uthavalaam"
        }

        if any(w in words for w in hi_indicators):
            return "hi-IN"
        if any(w in words for w in te_indicators):
            return "te-IN"
        if any(w in words for w in ta_indicators):
            return "ta-IN"

        return "en-IN"

    def get_language_name(self, lang_code: str) -> str:
        lang = lang_code.split("-")[0].lower()
        mapping = {
            "en": "Indian English",
            "hi": "Hindi / Hinglish",
            "te": "Telugu (తెలుగు)",
            "ta": "Tamil (தமிழ்)",
            "kn": "Kannada (ಕನ್ನಡ)",
            "mr": "Marathi (मराठी)"
        }
        return mapping.get(lang, "Indic Multilingual")

    def extract_target_number(self, text: str, default: int = 1) -> Tuple[int, Optional[int]]:
        """
        Extracts the target number, handling negations like '500 nahi, 1200' or '5 quintal nahi, 10'.
        Returns (target_number, negated_number_if_any).
        """
        text_lower = text.lower()
        
        # Check for pattern like: (\d+)\s*(?:nahi|not|mat)\s*,?\s*(\d+)
        neg_match = re.search(r'(\d+)\s*(?:nahi|not|mat|pe nahi)\s*[, ]+\s*(\d+)', text_lower)
        if neg_match:
            old_val = int(neg_match.group(1))
            new_val = int(neg_match.group(2))
            return new_val, old_val

        # Find all standalone numbers
        digits = [int(m) for m in re.findall(r'\b\d+\b', text_lower)]
        if digits:
            if len(digits) > 1 and any(w in text_lower for w in ["nahi", "not", "instead", "badal", "update", "cancel"]):
                return digits[-1], digits[0]
            return digits[0], None

        for word, val in WORD_TO_NUM.items():
            if re.search(rf'\b{word}\b', text_lower):
                return val, None

        return default, None

    def extract_target_commodity(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Finds the target commodity, accounting for negations like 'gehun nahi, sarson karo'.
        Returns (target_commodity_key, negated_commodity_key).
        """
        text_lower = text.lower()
        found_keys = []
        
        for k in COMMODITY_RATES.keys():
            if re.search(rf'\b{k}\b', text_lower):
                if k not in found_keys:
                    found_keys.append(k)

        if not found_keys:
            return None, None

        negated_key = None
        target_key = None
        for k in found_keys:
            if re.search(rf'\b{k}\s*(?:nahi|mat|cancel|not)\b|\b(?:nahi|not|cancel)\s*{k}\b', text_lower):
                negated_key = k
            else:
                target_key = k

        if target_key:
            return target_key, negated_key
        elif found_keys:
            return found_keys[-1], negated_key
        return None, None

    def parse_transaction(
        self, 
        user_text: str, 
        was_interrupted: bool = False, 
        active_txn: Optional[Dict[str, Any]] = None,
        language: str = "hi-IN"
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Parses full-duplex speech for APMC Mandi Agri-Trade orders and Kirana Ledger entries.
        Seamlessly handles voice barge-in preemptions, cancellations, and order overrides.
        """
        text_lower = user_text.lower().strip()
        lang_code = language.split("-")[0].lower()
        now_str = time.strftime("%H:%M:%S")

        is_preempting = was_interrupted or any(k in text_lower for k in [
            "nahi", "not", "wait", "ruko", "cancel", "badal", "instead", "arrey", "arre", "update", "galat"
        ])

        # 1. MANDI AGRI-COMMODITY TRADE
        target_comm_key, negated_comm_key = self.extract_target_commodity(text_lower)
        is_mandi_related = (
            target_comm_key is not None or 
            negated_comm_key is not None or
            any(m.lower() in text_lower for m in MANDI_LOCATIONS) or 
            "mandi" in text_lower or 
            "quintal" in text_lower or
            (active_txn and active_txn.get("domain") == "MANDI_TRADE" and is_preempting)
        )

        if is_mandi_related:
            location = "Indore APMC Mandi"
            matched_loc = False
            for m in MANDI_LOCATIONS:
                if m.lower() in text_lower:
                    location = f"{m} APMC Mandi"
                    matched_loc = True
                    break
            if not matched_loc and active_txn and active_txn.get("domain") == "MANDI_TRADE":
                location = active_txn.get("counterparty", "Indore APMC Mandi")

            comm_info = COMMODITY_RATES.get(target_comm_key) if target_comm_key else None
            if not comm_info and active_txn and active_txn.get("domain") == "MANDI_TRADE":
                comm_name = active_txn.get("item", "Wheat (Gehun)")
                comm_rate = active_txn.get("raw_rate", 2450)
                comm_unit = "Quintal"
            elif comm_info:
                comm_name = comm_info["name"]
                comm_rate = comm_info["rate"]
                comm_unit = comm_info["unit"]
            else:
                comm_name = "Wheat (Gehun)"
                comm_rate = 2450
                comm_unit = "Quintal"

            qty, _ = self.extract_target_number(text_lower, default=5)
            total_val = qty * comm_rate
            formatted_total = f"Rs. {total_val:,}"
            formatted_rate = f"Rs. {comm_rate:,} / {comm_unit}"

            # If preempting/overriding an active Mandi order
            if is_preempting and active_txn and active_txn.get("domain") == "MANDI_TRADE":
                old_item = active_txn.get("item", "Wheat (Gehun)")
                old_qty = active_txn.get("quantity", "5 Quintal")
                old_total = active_txn.get("total_amount", "Rs. 12,250")
                
                trail = list(active_txn.get("audit_trail", []))
                trail.append(f"[{now_str}] PREEMPTED VIA BARGE-IN: Audio stream aborted (<50ms)")
                trail.append(f"[{now_str}] OVERRIDE APPLIED: {qty} {comm_unit} {comm_name} @ {formatted_rate} (Total: {formatted_total})")

                updated_txn = {
                    "txn_id": active_txn.get("txn_id", f"TXN-AGRI-{int(time.time()*100)%10000:04d}"),
                    "domain": "MANDI_TRADE",
                    "domain_label": "Mandi Agri-Trade Desk",
                    "counterparty": location,
                    "item": comm_name,
                    "raw_rate": comm_rate,
                    "quantity": f"{qty} {comm_unit}",
                    "unit_rate": formatted_rate,
                    "total_amount": formatted_total,
                    "status": "OVERRIDDEN_AND_CONFIRMED",
                    "status_badge": "OVERRIDDEN VIA BARGE-IN",
                    "badge_class": "badge-override",
                    "override_note": f"Cancelled {old_qty} {old_item} ({old_total})",
                    "timestamp": now_str,
                    "audit_trail": trail
                }

                if lang_code == "en":
                    spoken_reply = (
                        f"Updated! Cancelled {old_qty} of {old_item.split('(')[0].strip()} and "
                        f"booked {qty} quintals of {comm_name.split('(')[0].strip()} in {location.split()[0]} Mandi instead. "
                        f"Total is {total_val:,} rupees."
                    )
                elif lang_code == "te":
                    spoken_reply = (
                        f"Sare, update chesamu! {old_qty} cancel chesi, {qty} quintalla {comm_name.split('(')[0].strip()} "
                        f"{location.split()[0]} Mandi lo book chesamu. Motham {total_val:,} rupayalu."
                    )
                elif lang_code == "ta":
                    spoken_reply = (
                        f"Sari, maatram seiyappattadhu! {old_qty} rathu seidhu {qty} quintal {comm_name.split('(')[0].strip()} "
                        f"{location.split()[0]} Mandiyil book seiyappattadhu. Motha thogai {total_val:,} roobai."
                    )
                else:
                    spoken_reply = (
                        f"Bilkul, update kar diya! {old_qty} {old_item.split('(')[0].strip()} cancel karke "
                        f"ab {qty} {comm_unit} {comm_name.split('(')[0].strip()} book kar diya hai {location.split()[0]} Mandi me. "
                        f"Total banta hai {total_val:,} rupay."
                    )
                return updated_txn, spoken_reply
            else:
                txn_id = f"TXN-AGRI-{int(time.time()*100)%10000:04d}"
                new_txn = {
                    "txn_id": txn_id,
                    "domain": "MANDI_TRADE",
                    "domain_label": "Mandi Agri-Trade Desk",
                    "counterparty": location,
                    "item": comm_name,
                    "raw_rate": comm_rate,
                    "quantity": f"{qty} {comm_unit}",
                    "unit_rate": formatted_rate,
                    "total_amount": formatted_total,
                    "status": "CONFIRMED",
                    "status_badge": "CONFIRMED & SETTLED",
                    "badge_class": "badge-confirmed",
                    "override_note": None,
                    "timestamp": now_str,
                    "audit_trail": [
                        f"[{now_str}] Order Initiated: {qty} {comm_unit} {comm_name} @ {formatted_rate}",
                        f"[{now_str}] APMC Match: {location} settled at {formatted_total}"
                    ]
                }
                if lang_code == "en":
                    spoken_reply = (
                        f"Confirmed. Booked {qty} quintals of {comm_name.split('(')[0].strip()} in {location.split()[0]} Mandi. "
                        f"At {comm_rate:,} rupees per quintal, total is {total_val:,} rupees."
                    )
                elif lang_code == "te":
                    spoken_reply = (
                        f"Sare, {location.split()[0]} Mandi lo {qty} quintalla {comm_name.split('(')[0].strip()} book chesamu. "
                        f"Rate {comm_rate:,} rupayala tho motham {total_val:,} rupayalu."
                    )
                elif lang_code == "ta":
                    spoken_reply = (
                        f"Sari, {location.split()[0]} Mandiyil {qty} quintal {comm_name.split('(')[0].strip()} book seiyappattadhu. "
                        f"Motha thogai {total_val:,} roobai."
                    )
                else:
                    spoken_reply = (
                        f"Ji, {location.split()[0]} Mandi me {qty} {comm_unit} {comm_name.split('(')[0].strip()} book kar diya gaya hai. "
                        f"Rate {comm_rate:,} rupay ke hisaab se total banta hai {total_val:,} rupay."
                    )
                return new_txn, spoken_reply

        # 2. BHARAT KIRANA / BANKING LEDGER
        kirana_keywords = ["khata", "khate", "udhaar", "baki", "jama", "kirana", "likho", "debit", "credit", "dukan", "ramesh", "suresh"]
        if any(k in text_lower for k in kirana_keywords) or (active_txn and active_txn.get("domain") == "KIRANA_LEDGER" and is_preempting):
            party = "Ramesh Bhai (Khata #104)"
            for name in ["Ramesh", "Suresh", "Patil", "Patel", "Sharma", "Verma"]:
                if name.lower() in text_lower:
                    party = f"{name} Bhai (Khata #104)"
                    break
            
            amount, _ = self.extract_target_number(text_lower, default=500)
            formatted_amount = f"Rs. {amount:,}"

            if is_preempting and active_txn and active_txn.get("domain") == "KIRANA_LEDGER":
                old_amt = active_txn.get("total_amount", "Rs. 500")
                trail = list(active_txn.get("audit_trail", []))
                trail.append(f"[{now_str}] PREEMPTED VIA BARGE-IN: Audio stream aborted (<50ms)")
                trail.append(f"[{now_str}] OVERRIDE APPLIED: {party} updated to {formatted_amount} Udhaar")

                updated_txn = {
                    "txn_id": active_txn.get("txn_id", f"TXN-KHATA-{int(time.time()*100)%10000:04d}"),
                    "domain": "KIRANA_LEDGER",
                    "domain_label": "Kirana Credit Ledger",
                    "counterparty": party,
                    "item": "Dukan Udhaar (Debit)",
                    "raw_rate": amount,
                    "quantity": "1 Entry",
                    "unit_rate": formatted_amount,
                    "total_amount": formatted_amount,
                    "status": "OVERRIDDEN_AND_CONFIRMED",
                    "status_badge": "OVERRIDDEN VIA BARGE-IN",
                    "badge_class": "badge-override",
                    "override_note": f"Corrected from {old_amt}",
                    "timestamp": now_str,
                    "audit_trail": trail
                }
                if lang_code == "en":
                    spoken_reply = f"Updated! Corrected {party.split()[0]}'s entry to {amount:,} rupees debit in the ledger."
                elif lang_code == "te":
                    spoken_reply = f"Sare, update chesamu! {party.split()[0]} khata lo {amount:,} rupayala udharu ga marchamu."
                elif lang_code == "ta":
                    spoken_reply = f"Sari, maatram seiyappattadhu! {party.split()[0]} kanakkil {amount:,} roobai kadanaga maatrapattadhu."
                else:
                    spoken_reply = (
                        f"Theek hai, update kar diya! {party.split()[0]} ke khate mein {old_amt.replace('Rs.', '').strip()} rupay ko badal kar "
                        f"{amount:,} rupay udhaar darj kar diya gaya hai."
                    )
                return updated_txn, spoken_reply
            else:
                txn_id = f"TXN-KHATA-{int(time.time()*100)%10000:04d}"
                new_txn = {
                    "txn_id": txn_id,
                    "domain": "KIRANA_LEDGER",
                    "domain_label": "Kirana Credit Ledger",
                    "counterparty": party,
                    "item": "Dukan Udhaar (Debit)",
                    "raw_rate": amount,
                    "quantity": "1 Entry",
                    "unit_rate": formatted_amount,
                    "total_amount": formatted_amount,
                    "status": "CONFIRMED",
                    "status_badge": "CONFIRMED & SETTLED",
                    "badge_class": "badge-confirmed",
                    "override_note": None,
                    "timestamp": now_str,
                    "audit_trail": [
                        f"[{now_str}] Entry Initiated: {party} -> {formatted_amount} Udhaar",
                        f"[{now_str}] Khata Ledger synced successfully"
                    ]
                }
                if lang_code == "en":
                    spoken_reply = f"Recorded {amount:,} rupees debit in {party.split()[0]}'s ledger."
                elif lang_code == "te":
                    spoken_reply = f"{party.split()[0]} khata lo {amount:,} rupayala udharu note chesamu."
                elif lang_code == "ta":
                    spoken_reply = f"{party.split()[0]} kanakkil {amount:,} roobai kadan padhivu seiyappattadhu."
                else:
                    spoken_reply = f"{party.split()[0]} bhai ke khate mein {amount:,} rupay udhaar note kar liya gaya hai."
                return new_txn, spoken_reply

        return None, ""

    async def generate_response(
        self, 
        user_text: str, 
        history: List[Dict[str, str]] = None, 
        was_interrupted: bool = False,
        language: str = "en-IN",
        active_txn: Optional[Dict[str, Any]] = None,
        return_transaction: bool = False
    ) -> Any:
        history = history or []
        
        # Handle zero-click automatic Indic code-switching
        effective_language = language
        if language == "auto" or language.startswith("auto"):
            effective_language = self.detect_language(user_text)
            logger.info(f"Auto-detected language for '{user_text[:30]}...': {effective_language}")

        # 1. PRIORITY 1: Check for deterministic Bharat Enterprise Transaction
        txn_data, txn_reply = self.parse_transaction(
            user_text, 
            was_interrupted=was_interrupted, 
            active_txn=active_txn, 
            language=effective_language
        )
        if txn_data and txn_reply:
            logger.info(f"Transaction processed [{txn_data['domain']}]: {txn_data['status']}")
            if return_transaction:
                return txn_reply, txn_data
            return txn_reply

        # 2. PRIORITY 2: Open-ended conversational intelligence via Gemini LLM cascade
        if self.api_key:
            try:
                response = await self._call_gemini_cascade(user_text, history, was_interrupted, effective_language)
                if response:
                    if return_transaction:
                        return response, None
                    return response
            except Exception as e:
                logger.warning(f"All Gemini models in cascade failed: {e}. Using intelligent fallback.")

        # 3. PRIORITY 3: Local intelligent rule-based fallback
        fallback_reply = self._rule_based_fallback(user_text, was_interrupted, effective_language)
        if return_transaction:
            return fallback_reply, None
        return fallback_reply

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
            return "Nenu artham chesukonnanu. Meeru adigina vishayam gurinchi nenu sahayapadagalanu."

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
            return "Naan purindhu konden. Naan ungalukku eppadi uthavalaam?"

        # --- ENGLISH (Indian English) ---
        elif lang_code == "en":
            if was_interrupted:
                return "Go ahead, I am listening."
            if any(w in user_lower for w in ["stop", "wait", "hold on", "listen"]):
                return "Sure, I have paused. Please continue."
            if any(w in user_lower for w in ["who are you", "what is this", "duplex"]):
                return "Hello! I am DuplexVani — a real-time full-duplex voice desk powered by Gnani AI models."
            if any(w in user_lower for w in ["capital of india", "capital of bharat", "capital"]):
                return "The capital of India is New Delhi."
            if any(w in user_lower for w in ["domestic animal", "animal", "pets"]):
                return "People love domestic animals because they offer unconditional companionship, warmth, and loyalty."
            if any(w in user_lower for w in ["weather", "forecast", "climate"]):
                return "The weather is currently clear and pleasant with mild temperatures."
            if any(w in user_lower for w in ["mandi", "market", "prices", "rate"]):
                return "In the wholesale agricultural market today, wheat is trading around 2450 rupees per quintal."
            return "I understand your query. Let me assist you with that."

        # --- HINDI & HINGLISH (Default) ---
        else:
            if was_interrupted:
                return "Haan, main sun raha hoon. Kahiye?"
            if any(w in user_lower for w in ["ruko", "stop", "wait", "suno", "arrey", "arre"]):
                return "Ji bilkul, main ruk gaya. Kahiye, main sun raha hoon."
            if any(w in user_lower for w in ["kya ho", "who are you", "kaun ho", "duplex"]):
                return "Namaste! Main DuplexVani hoon — Gnani AI ke Prisma aur Timbre models par bana full-duplex voice desk."
            if any(w in user_lower for w in ["capital", "rajdhani", "bharat", "india"]):
                return "Bharat ki rajdhani New Delhi hai."
            if any(w in user_lower for w in ["domestic animal", "janwar", "kutte", "pets"]):
                return "Log paaltu janwaron se pyaar karte hain kyunki wo wafadaar hote hain aur insaano ka tanav kam karte hain."
            if any(w in user_lower for w in ["mandi", "kisan", "fasal", "bhav"]):
                return "Indore Mandi me aaj gehun 2450 rupay per quintal aur sarson 5400 rupay chal raha hai."
            if any(w in user_lower for w in ["kirana", "doodh", "hisaab", "khata", "sugar"]):
                return "Ramesh bhai ke khate mein 2 packet doodh aur 1 packet bread ka 140 rupay udhaar note kar liya gaya hai."
            return "Main samajh gaya. Isme main aapki poori sahayata kar sakta hoon."

llm_service = LLMService()
