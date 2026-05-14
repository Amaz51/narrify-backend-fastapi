#Configuration Module

#Handles all configuration and environment variables for the application.
#Uses pydantic-settings for type-safe configuration management.


import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import field_validator, Field
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

    APP_NAME: str = "AI Multilingual Audiobook System"
    APP_VERSION: str = "2.0.0"
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
    TTS_SAMPLE_RATE: int = 24000
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
    # Chapter detection patterns — matched against stripped lines.
    # Ordered from most specific to least specific.
    CHAPTER_PATTERNS: List[str] = [
        # "Chapter 1" / "CHAPTER 1" / "Chapter 1:" / "CHAPTER ONE"
        r"^(?:Chapter|CHAPTER)\s+(?:\d+|[A-Z][a-z]+)(?:\s*[:\-—].*)?$",
        # "Part 1" / "PART ONE"
        r"^(?:Part|PART)\s+(?:\d+|[A-Z][a-z]+)(?:\s*[:\-—].*)?$",
        # Numbered heading: "1. Title" or "1 Title" (no dot)
        r"^\d+(?:\.)?\s+[A-Z][A-Za-z\s]{2,}$",
        # Standalone structural labels (PROLOGUE, EPILOGUE, etc.)
        r"^(?:PROLOGUE|EPILOGUE|INTRODUCTION|PREFACE|FOREWORD|AFTERWORD|"
        r"ACKNOWLEDGEMENTS?|APPENDIX|INTERLUDE|CODA)(?:\s*[:\-—].*)?$",
        # Title-case labels (Prologue, Epilogue, …)
        r"^(?:Prologue|Epilogue|Introduction|Preface|Foreword|Afterword|"
        r"Acknowledgements?|Appendix|Interlude|Coda)(?:\s*[:\-—].*)?$",
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
    MAX_CONCURRENT_TASKS: int = 5
    BATCH_SIZE: int = 10  # Segments per batch
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 3600  # 1 hour in seconds
    
    # ==================== REDIS/CACHE Settings ====================
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        # env="REDIS_URL"
    )
    REDIS_CACHE_TTL: int = 3600  # 1 hour
    
    # ==================== Celery Settings ====================
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/1",
        # validation_alias="CELERY_BROKER_URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/2",
        # validation_alias="CELERY_RESULT_BACKEND"
    )
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 3600  # 1 hour max
    
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
    

    SECRET_KEY: str = Field(
        default="your-secret-key-here-change-in-production", 
        # validation_alias="SECRET_KEY"
        )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # DEMO VOICES    

    DEMO_VOICES: List[dict] = [
        {
            "id": "voice2",
            "name": "Maryam",
            "language": "en",
            "gender": "female",
            "mood": "Authoritative",
            "type": "Natural",
            "featured": True,
            "sample_file": "voice2_sample.wav",
            "description": "Deep, authoritative female voice ideal for non-fiction",
        },
        {
            "id": "voice3",
            "name": "James",
            "language": "en",
            "gender": "male",
            "mood": "Warm & Friendly",
            "type": "Neural",
            "featured": True,
            "sample_file": "voice3_sample.wav",
            "description": "Warm, friendly, deep male voice great for storytelling",
        },
        {
            "id": "voice6",
            "name": "Michael",
            "language": "en",
            "gender": "male",
            "mood": "Deep & Calm",
            "type": "Neural",
            "featured": False,
            "sample_file": "voice6_sample.wav",
            "description": "Deep, calm male voice with measured pacing",
        },
        {
            "id": "voice7",
            "name": "Shahzaib",
            "language": "en",
            "gender": "male",
            "mood": "Storyteller",
            "type": "Natural",
            "featured": False,
            "sample_file": "voice7_sample.wav",
            "description": "Engaging storyteller voice with natural rhythm",
        },
        {
            "id": "ivy",
            "name": "Ivy",
            "language": "en",
            "gender": "female",
            "mood": "Sophisticated",
            "type": "Studio",
            "featured": True,
            "sample_file": "Ivy - sophisticated english.mp3",
            "description": "Sophisticated, refined female voice with elegant delivery",
        },
        {
            "id": "dallin",
            "name": "Dallin",
            "language": "en",
            "gender": "male",
            "mood": "Inspiring",
            "type": "Natural",
            "featured": False,
            "sample_file": "dallin - english male inspiring.mp3",
            "description": "Uplifting, inspiring male voice with motivational energy",
        },
        {
            "id": "lauran",
            "name": "Lauran",
            "language": "en",
            "gender": "female",
            "mood": "Friendly",
            "type": "Neural",
            "featured": True,
            "sample_file": "lauran - friendly english.mp3",
            "description": "Warm, approachable female voice with a conversational tone",
        },
        {
            "id": "sara",
            "name": "Sara",
            "language": "en",
            "gender": "female",
            "mood": "Expressive",
            "type": "Natural",
            "featured": False,
            "sample_file": "sara-indian accent.mp3",
            "description": "Expressive female voice with a distinct South Asian accent",
        },
        {
            "id": "victoria",
            "name": "Victoria",
            "language": "en",
            "gender": "female",
            "mood": "Elegant",
            "type": "Studio",
            "featured": False,
            "sample_file": "victoria-english.mp3",
            "description": "Polished, elegant female voice with precise enunciation",
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

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Ensure secret key is strong enough in production"""
        if len(v) < 16:
            raise ValueError("SECRET_KEY should be at least 16 characters for security")
        return v
    
    @field_validator("UPLOAD_DIR", "OUTPUT_DIR", "EMBEDDINGS_DIR", "CACHE_DIR", "LOG_DIR")
    @classmethod
    def create_all_directories(cls, v: Path) -> Path:
        """Ensure all required directories exist"""
        v.mkdir(parents=True, exist_ok=True)
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
        # NOTE: Do NOT add "*" here — combining "*" with allow_credentials=True
        # is invalid per the CORS spec and browsers will reject all responses.
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
    
    def get_language_code(self, language: str) -> str:
        """Get NLLB language code from human-readable name"""
        lang_lower = language.lower()
        if lang_lower in self.SUPPORTED_LANGUAGES:
            return self.SUPPORTED_LANGUAGES[lang_lower]
        raise ValueError(f"Unsupported language: {language}")
    
    def get_voice_embedding_path(self, voice_id: str) -> Path:
        """Get path to voice embedding file"""
        return self.EMBEDDINGS_DIR / f"{voice_id}.pt"
    
    EMOTION_MODEL: str = "j-hartmann/emotion-english-distilroberta-base"
    
    # NLP Model
    SPACY_MODEL: str = "en_core_web_sm"
    
    # Multi-Speaker Detection
    ENABLE_SPEAKER_DETECTION: bool = True
    ENABLE_EMOTION_DETECTION: bool = True
    NLLB_MODEL: str = "facebook/nllb-200-distilled-600M"
    NLLB_DEVICE: str = Field(
        default="cpu", 
        # validation_alias="NLLB_DEVICE"
        )
    
    # Supported language codes (NLLB format)
    SUPPORTED_LANGUAGES: Dict[str, str] = {
        "english": "eng_Latn",
        "german": "deu_Latn",
        "urdu": "urd_Arab",
        "hindi": "hin_Deva",
        "spanish": "spa_Latn",
        "french": "fra_Latn",
        "arabic": "arb_Arab",
        "chinese": "zho_Hans",
        "japanese": "jpn_Jpan",
        "korean": "kor_Hang",
    }
    
    # Speaker Gender Mapping (extend as needed)
    DEFAULT_CHARACTER_GENDERS: Dict[str, str] = {
        # From examples
        "harry": "male",
        "hermione": "female",
        "ron": "male",
        "narrator": "neutral",
        # Add more as needed
    }
    
    # ==================== File Storage Settings ====================
    EMBEDDINGS_DIR: Path = BASE_DIR / "data" / "embeddings"
    
    # Voice profiles (stored in embeddings directory)
    DEFAULT_VOICES: Dict[str, dict] = {
        "narrator": {
            "id": "narrator_default",
            "gender": "neutral",
            "embedding_file": "narrator_neutral.pt"
        },
        "male": {
            "id": "male_default",
            "gender": "male",
            "embedding_file": "male_voice.pt"
        },
        "female": {
            "id": "female_default",
            "gender": "female",
            "embedding_file": "female_voice.pt"
        }
    }
    
    # ==================== TTS Settings (XTTS v2) ====================
    TTS_MODEL: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    TTS_DEVICE: str = Field(default="cpu", validation_alias="TTS_DEVICE")

# GLOBAL SETTINGS INSTANCE

settings = Settings()

# Create necessary directories on import
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
settings.VOICE_DIR.mkdir(parents=True, exist_ok=True)
settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
settings.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
settings.EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

# EXPORT

__all__ = ["settings", "Settings"]
