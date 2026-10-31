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
    """

    def __init__(self):
        self.api_key = settings.GNANI_API_KEY
        self.prisma_url = settings.GNANI_PRISMA_STT_URL
        self.timbre_url = settings.GNANI_TIMBRE_TTS_URL
        self.simulated = settings.USE_SIMULATED_GNANI or not bool(self.api_key)
        self.default_male_voice = "Devansh" # Supported male voices: Devansh, Avinash, Shubham, Prakash, Yash

    async def transcribe_audio(self, audio_bytes: bytes, language: str = "hi-IN") -> str:
        """
        Sends audio to Gnani Prisma STT for transcription in the target language.
        """
        if not self.simulated and self.api_key:
            try:
                headers = {"X-API-Key-ID": self.api_key}
                files = {"audio_file": ("speech.wav", audio_bytes, "audio/wav")}
                data = {
                    "model": "prisma-v3.0",
                    "language_code": language
                }

                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(self.prisma_url, headers=headers, files=files, data=data)
                    if resp.status_code == 200:
                        res_json = resp.json()
                        return res_json.get("transcript", res_json.get("text", ""))
                    else:
                        logger.warning(f"Prisma returned status {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Live Prisma STT call failed: {e}")

        return "Namaste! Main DuplexVani hoon. Aap mujhe bolte hue kabhi bhi interrupt kar sakte hain!"

    async def synthesize_speech(self, text: str, language: str = "hi-IN", voice: Optional[str] = None) -> bytes:
        """
        Calls Gnani Timbre TTS using crisp male voice ('Devansh') at native 48,000 Hz.
        Supports regional Indic languages (Hindi, Telugu, Tamil, Kannada, Marathi, English, etc.)
        """
        sample_rate = 48000
        chosen_voice = voice or self.default_male_voice

        if not self.simulated and self.api_key:
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
                    "speed": 1.15  # Snappy, natural male cadence
                }
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(self.timbre_url, headers=headers, json=payload)
                    if resp.status_code == 200:
                        raw_pcm = resp.content
                        wav_buf = io.BytesIO()
                        with wave.open(wav_buf, 'wb') as wav:
                            wav.setnchannels(1)        # Mono
                            wav.setsampwidth(2)        # 16-bit linear PCM
                            wav.setframerate(sample_rate)
                            wav.writeframes(raw_pcm)
                        return wav_buf.getvalue()
                    else:
                        logger.warning(f"Gnani Timbre returned status {resp.status_code}: {resp.text}")
            except Exception as e:
                logger.error(f"Live Timbre TTS call failed: {e}")

        # Local fallback
        return self._generate_local_audio(text)

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
