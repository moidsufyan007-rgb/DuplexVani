import io
import wave
import httpx
import logging
from typing import Optional
from backend.config import settings

logger = logging.getLogger("DuplexVani.GnaniClient")

class GnaniVoiceClient:
    """
    Official Client for Gnani AI / Vachana Voice Models:
    - Prisma v3.0 STT: Low-latency Indic & Hinglish speech transcription
    - Timbre v3.0 TTS: Natural Indic voice synthesis (Devansh, Avinash, etc.)
    Supports dynamic per-session switching between Live and Credit Shield (Free) mode.
    """

    def __init__(self):
        self.api_key = settings.GNANI_API_KEY
        self.prisma_url = settings.GNANI_PRISMA_STT_URL
        self.timbre_url = settings.GNANI_TIMBRE_TTS_URL
        self.default_male_voice = "Devansh"

    async def transcribe_audio(self, audio_bytes: bytes, language: str = "hi-IN", is_live: bool = False) -> str:
        """
        Transcribes speech audio into text.
        If is_live=True and API key exists, calls live Gnani Prisma STT.
        If is_live=False, returns simulated transcription with 0 credit consumption.
        """
        if is_live and self.api_key:
            try:
                headers = {"X-API-Key-ID": self.api_key}
                files = {"audio_file": ("speech.wav", audio_bytes, "audio/wav")}
                data = {
                    "model": "prisma-v3.0",
                    "language_code": language
                }

                logger.info(f"Calling Live Gnani Prisma STT (Lang: {language}, Audio size: {len(audio_bytes)} bytes)")
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(self.prisma_url, headers=headers, files=files, data=data)
                    if resp.status_code == 200:
                        res_json = resp.json()
                        transcript = res_json.get("transcript", res_json.get("text", "")).strip()
                        if transcript:
                            return transcript
                    else:
                        logger.warning(f"Prisma returned status {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Live Prisma STT call failed: {e}")

        # Credit Shield / Simulated Mode (Free)
        return self._simulate_transcription(language)

    async def synthesize_speech(
        self, 
        text: str, 
        language: str = "hi-IN", 
        voice: Optional[str] = None,
        is_live: bool = False
    ) -> bytes:
        """
        Synthesizes text into natural voice audio.
        If is_live=True, calls Gnani Timbre TTS (48kHz Devansh).
        If is_live=False, uses local speech generator with 0 credit consumption.
        """
        sample_rate = 48000
        chosen_voice = voice or self.default_male_voice

        if is_live and self.api_key:
            try:
                headers = {
                    "X-API-Key-ID": self.api_key,
                    "Content-Type": "application/json"
                }
                payload = {
                    "text": text,
                    "model": "timbre-v3.0",
                    "voice": chosen_voice,
                    "language": language,
                    "sample_rate": sample_rate,
                    "speed": 1.15
                }
                logger.info(f"Calling Live Gnani Timbre TTS (Voice: {chosen_voice}, Lang: {language})")
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(self.timbre_url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        raw_pcm = resp.content
                        wav_buf = io.BytesIO()
                        with wave.open(wav_buf, 'wb') as wav:
                            wav.setnchannels(1)
                            wav.setsampwidth(2)
                            wav.setframerate(sample_rate)
                            wav.writeframes(raw_pcm)
                        return wav_buf.getvalue()
                    else:
                        logger.warning(f"Gnani Timbre returned status {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Live Timbre TTS call failed: {e}")

        # Credit Shield fallback
        return self._generate_local_audio(text)

    def _simulate_transcription(self, language: str) -> str:
        lang_code = language.split("-")[0].lower()
        if lang_code == "te":
            return "Namaskaram! DuplexVani gurinchi naaku vivarinchandi."
        elif lang_code == "ta":
            return "Vanakkam! DuplexVani patri enakku sollungal."
        elif lang_code == "en":
            return "Hello! Tell me about DuplexVani and how it works."
        else:
            return "Namaste! Mujhe DuplexVani ke bare mein bataiye aur aap kaise kaam karte hain?"

    def _generate_local_audio(self, text: str) -> bytes:
        try:
            import pyttsx3
            import os
            engine = pyttsx3.init()
            engine.setProperty('rate', 165)
            temp_file = "temp_local_voice.wav"
            engine.save_to_file(text, temp_file)
            engine.runAndWait()

            with open(temp_file, "rb") as f:
                data = f.read()

            try:
                os.remove(temp_file)
            except Exception:
                pass
            return data
        except Exception:
            return self._generate_fallback_carrier(len(text))

    def _generate_fallback_carrier(self, char_count: int) -> bytes:
        import math
        import struct

        sample_rate = 16000
        duration = min(3.5, max(1.0, char_count * 0.05))
        num_samples = int(sample_rate * duration)

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)

            frames = bytearray()
            for i in range(num_samples):
                t = i / sample_rate
                sample = 0.3 * math.sin(2 * math.pi * 180 * t) + 0.15 * math.sin(2 * math.pi * 360 * t)
                envelope = math.sin(math.pi * (i / num_samples))
                val = int(sample * envelope * 32767)
                frames.extend(struct.pack('<h', val))
            wav.writeframes(frames)

        return buf.getvalue()

gnani_client = GnaniVoiceClient()
