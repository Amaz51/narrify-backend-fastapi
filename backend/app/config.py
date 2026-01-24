#Configuration Module

#Handles all configuration and environment variables for the application.
#Uses pydantic-settings for type-safe configuration management.


import os
from pathlib import Path
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    
    # Application Settings

    # All configuration loaded from environment variables or .env file.
    # Type-safe with automatic validation.
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # APPLICATION SETTINGS

    APP_NAME: str = "Narrify Phase 1"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development, production, testing
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

    # API SETTINGS

    API_V1_PREFIX: str = "/api"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True

    # CORS Settings
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    ALLOWED_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    ALLOWED_HEADERS: List[str] = ["*"]

    # DIRECTORIES

    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOAD_DIR: Path = DATA_DIR / "uploads"
    OUTPUT_DIR: Path = DATA_DIR / "outputs"
    VOICE_DIR: Path = DATA_DIR / "voices"
    CACHE_DIR: Path = DATA_DIR / "cache"
    MODEL_CACHE_DIR: Path = BASE_DIR / "models"

    # FILE UPLOAD SETTINGS

    MAX_UPLOAD_SIZE: int = 52428800  # 50MB in bytes
    ALLOWED_EXTENSIONS: List[str] = [".pdf"]
    UPLOAD_TIMEOUT: int = 300  # 5 minutes

    # TTS MODEL SETTINGS
    
    TTS_MODEL_NAME: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    TTS_CHUNK_SIZE: int = 200  # words per chunk
    TTS_SAMPLE_RATE: int = 22050
    USE_GPU: bool = True  # Auto-detect: True for MPS/CUDA, False for CPU
    TTS_LANGUAGE: str = "en"

    # Voice settings
    DEFAULT_SPEED: float = 1.0
    DEFAULT_PITCH: int = 0
    DEFAULT_TONE: str = "normal"
    MIN_SPEED: float = 0.5
    MAX_SPEED: float = 2.0
    MIN_PITCH: int = -12
    MAX_PITCH: int = 12
    AVAILABLE_TONES: List[str] = ["normal", "warm", "bright", "deep"]

    # PDF PROCESSING SETTING    
    # Chapter detection patterns
    CHAPTER_PATTERNS: List[str] = [
        r"^Chapter\s+\d+",
        r"^CHAPTER\s+\d+",
        r"^\d+\.\s+[A-Z]",
        r"^Part\s+\d+",
    ]

    # Text cleaning
    MIN_CHAPTER_LENGTH: int = 100  # minimum characters
    MAX_CHAPTER_LENGTH: int = 50000  # maximum characters
    
    # AUDIO PROCESSING SETTINGS

    AUDIO_FORMAT: str = "wav"  # wav, mp3
    AUDIO_BITRATE: str = "192k"  # for MP3
    NORMALIZE_AUDIO: bool = True
    TRIM_SILENCE: bool = True
    SILENCE_THRESHOLD: int = -50  # dB
    
    # TEXT NORMALIZATION SETTINGS

    NORMALIZE_NUMBERS: bool = True
    NORMALIZE_DATES: bool = True
    NORMALIZE_CURRENCY: bool = True
    NORMALIZE_ABBREVIATIONS: bool = True

    # Common abbreviations mapping
    ABBREVIATIONS: dict = {
        "Dr.": "Doctor",
        "Mr.": "Mister",
        "Mrs.": "Misses",
        "Ms.": "Miss",
        "St.": "Street",
        "Ave.": "Avenue",
        "Blvd.": "Boulevard",
        "etc.": "etcetera",
        "e.g.": "for example",
        "i.e.": "that is",
    }

    # PERFORMANCE SETTINGS

    MAX_WORKERS: int = 4  # for concurrent processing
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 3600  # 1 hour in seconds
    
    # LOGGING SETTINGS    

    LOG_DIR: Path = BASE_DIR / "logs"
    LOG_ROTATION: str = "100 MB"
    LOG_RETENTION: str = "30 days"
    LOG_FORMAT: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # SECURITY SETTINGS
    

    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # DEMO VOICES    

    DEMO_VOICES: List[dict] = [
        {
            "id": "voice1",
            "name": "Sarah - Female (US)",
            "language": "en",
            "gender": "female",
            "sample_file": "voice1_sample.wav",
            "description": "Clear, professional female voice",
        },
        {
            "id": "voice2",
            "name": "Maryam - Female (UK)",
            "language": "en",
            "gender": "female",
            "sample_file": "voice2_sample.wav",
            "description": "Deep, authoritative female voice",
        },
        {
            "id": "voice3",
            "name": "James - male (AU)",
            "language": "en",
            "gender": "male",
            "sample_file": "voice3_sample.wav",
            "description": "Warm, friendly, deep male voice",
        },
        {
            "id": "voice4",
            "name": "Abdullah - Male (pakistan)",
            "language": "en",
            "gender": "male",
            "sample_file": "voice4_sample.wav",
            "description": "noise male voice",
        },
        {
            "id": "voice5",
            "name": "Olivia - Female (CA)",
            "language": "en",
            "gender": "female",
            "sample_file": "voice7_sample.wav",
            "description": "Calm, soothing female voice",
        },
        {
            "id": "voice6",
            "name": "Men - male (CA)",
            "language": "en",
            "gender": "male",
            "sample_file": "voice6_sample.wav",
            "description": "Calm, soothing male voice",
        },
        {
            "id": "voice10",
            "name": "Shahzaib - male (CA)",
            "language": "en",
            "gender": "male",
            "sample_file": "voice10_sample.wav",
            "description": "Calm, soothing male voice",
        },
    ]

    
    # VALIDATORS
    
    @field_validator("UPLOAD_DIR", "OUTPUT_DIR", "VOICE_DIR", "CACHE_DIR", "LOG_DIR")
    @classmethod
    def create_directories(cls, v: Path) -> Path:
        # Ensure directories exist
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("USE_GPU")
    @classmethod
    def validate_gpu(cls, v: bool) -> bool:
        # Auto-detect GPU availability
        if v:
            try:
                import torch

                # Check for CUDA (NVIDIA)
                if torch.cuda.is_available():
                    return True
                # Check for MPS (Apple Silicon)
                if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    return True
            except ImportError:
                pass
        return False

    @field_validator("MAX_UPLOAD_SIZE")
    @classmethod
    def validate_upload_size(cls, v: int) -> int:
        # Ensure reasonable upload size
        if v < 1024 or v > 1073741824:  # 1KB to 1GB
            raise ValueError("MAX_UPLOAD_SIZE must be between 1KB and 1GB")
        return v

    
    # HELPER METHODS
    

    def is_development(self) -> bool:
        # Check if running in development mode
        return self.ENVIRONMENT.lower() == "development"

    def is_production(self) -> bool:
        # Check if running in production mode
        return self.ENVIRONMENT.lower() == "production"

    def get_cors_origins(self) -> List[str]:
        # Get CORS allowed origins
        if self.is_development():
            return self.ALLOWED_ORIGINS + ["*"]
        return self.ALLOWED_ORIGINS

    def get_device(self) -> str:
        # Get computing device (cuda/mps/cpu)
        if not self.USE_GPU:
            return "cpu"

        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass

        return "cpu"

    def format_file_size(self, size_bytes: int) -> str:
        # Format bytes to human-readable size
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"


# GLOBAL SETTINGS INSTANCE

settings = Settings()

# Create necessary directories on import
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
settings.VOICE_DIR.mkdir(parents=True, exist_ok=True)
settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
settings.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# EXPORT

__all__ = ["settings", "Settings"]
