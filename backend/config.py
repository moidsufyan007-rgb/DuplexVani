import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env
load_dotenv(BASE_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "DuplexVani"
    GNANI_API_KEY: str = os.getenv("GNANI_API_KEY", "")
    
    # Official Gnani Vachana AI Voice Endpoints
    GNANI_PRISMA_STT_URL: str = os.getenv("GNANI_PRISMA_STT_URL", "https://api.vachana.ai/stt/v3")
    GNANI_TIMBRE_TTS_URL: str = os.getenv("GNANI_TIMBRE_TTS_URL", "https://api.vachana.ai/api/v1/tts/inference")
    
    # If False, calls live Gnani API
    USE_SIMULATED_GNANI: bool = os.getenv("USE_SIMULATED_GNANI", "false").lower() in ("true", "1", "yes")
    
    DEFAULT_LANGUAGE: str = "hi-IN"
    SAMPLE_RATE: int = 16000

settings = Settings()
