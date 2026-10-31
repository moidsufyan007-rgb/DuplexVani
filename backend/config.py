import os
from pathlib import Path
from dotenv import load_dotenv

# Path definitions
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
load_dotenv(BASE_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "DuplexVani"
    GNANI_API_KEY: str = os.getenv("GNANI_API_KEY", "")
    GNANI_PRISMA_STT_URL: str = os.getenv("GNANI_PRISMA_STT_URL", "https://api.gnani.ai/v1/prisma/transcribe")
    GNANI_TIMBRE_TTS_URL: str = os.getenv("GNANI_TIMBRE_TTS_URL", "https://api.gnani.ai/v1/timbre/synthesize")
    
    # Toggle for local testing without consuming credits
    USE_SIMULATED_GNANI: bool = os.getenv("USE_SIMULATED_GNANI", "true").lower() in ("true", "1", "yes")
    
    DEFAULT_LANGUAGE: str = "hi"
    SAMPLE_RATE: int = 16000

settings = Settings()
