# TTS Service
# Handles text-to-speech generation using Coqui XTTS v2.
# Supports zero-shot voice cloning and customization.

import asyncio
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import torch
#import _load_model
from loguru import logger
from TTS.api import TTS

from app.config import settings
from app.models.schemas import TonePreset


class TTSService:
    
    # Text-to-Speech Service
    # Uses Coqui XTTS v2 for high-quality speech synthesis.
    
    def __init__(self):
        # Initialize TTS service
        self.logger = logger.bind(name=__name__)
        self.model: Optional[TTS] = None
        self.device = settings.get_device()
        self.model_name = settings.TTS_MODEL_NAME
        self.sample_rate = settings.TTS_SAMPLE_RATE
        self.voice_dir = settings.VOICE_DIR
        self.output_dir = settings.OUTPUT_DIR

        # Load model on initialization
        self._load_model()

    def _load_model(self):
        """
        Load TTS model

        Raises:
            Exception: If model loading fails
        """
        try:
            self.logger.info(f"Loading TTS model: {self.model_name}")
            self.logger.info(f"Device: {self.device}")

            # Set environment variable for model cache
            import os

            os.environ["TTS_HOME"] = str(settings.MODEL_CACHE_DIR)
            os.environ["COQUI_TOS_AGREED"] = "1"

            # Load model
            self.model = TTS(
                model_name=self.model_name,
                progress_bar=False,
                gpu=False,
            )

            # Move to appropriate device
            if self.device == "cuda":
                self.model.to("cuda")
            elif self.device == "mps":
                # MPS support
                pass
                #self.model.to("mps")

            self.logger.info("TTS model loaded successfully")

        except Exception as e:
            self.logger.error(f"Failed to load TTS model: {e}")
            raise Exception(f"TTS model loading failed: {str(e)}")

    def is_model_loaded(self) -> bool:
        """Check if model is loaded"""
        return self.model is not None

    async def generate_speech(
        self,
        text: str,
        voice: str = "voice1",
        speed: float = 1.0,
        language: str = "en",
        output_path: Optional[Path] = None,
    ) -> Path:
        
        # Generate speech from text
        try:
            start_time = time.time()
            self.logger.info(f"Generating speech ({len(text)} chars, voice: {voice})")

            # Generate output path if not provided
            if output_path is None:
                audio_id = str(uuid.uuid4())[:12]
                output_path = self.output_dir / f"{audio_id}.wav"

            # Get voice sample path
            voice_sample_path = self._get_voice_sample_path(voice)

            # Run generation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._generate_audio_sync,
                text,
                voice_sample_path,
                str(output_path),
                language,
                speed,
            )

            generation_time = time.time() - start_time
            self.logger.info(
                f"Speech generated in {generation_time:.2f}s: {output_path}"
            )

            return output_path

        except Exception as e:
            self.logger.error(f"Speech generation failed: {e}")
            raise Exception(f"TTS generation failed: {str(e)}")

    def _generate_audio_sync(
        self,
        text: str,
        speaker_wav: str,
        output_path: str,
        language: str,
        speed: float,
    ):
        
        # Synchronous audio generation
        try:
            # Generate audio with zero-shot voice cloning
            self.model.tts_to_file(
                text=text,
                file_path=output_path,
                speaker_wav=speaker_wav,
                language=language,
                speed=speed,
            )

        except Exception as e:
            self.logger.error(f"Sync generation failed: {e}")
            raise

    def _get_voice_sample_path(self, voice_id: str) -> str:
        
        #Get path to voice sample file
        # Map voice ID to sample file
        voice_mapping = {voice["id"]: voice["sample_file"] for voice in settings.DEMO_VOICES}

        sample_filename = voice_mapping.get(voice_id)
        if not sample_filename:
            raise FileNotFoundError(f"Voice not found: {voice_id}")

        sample_path = self.voice_dir / sample_filename

        if not sample_path.exists():
            # Create default voice sample if not exists
            self.logger.warning(f"Voice sample not found: {sample_path}")
            self.logger.warning("Using default voice")
            # Return path to any available sample or raise error
            available_samples = list(self.voice_dir.glob("*.wav"))
            if available_samples:
                return str(available_samples[0])
            raise FileNotFoundError(f"No voice samples available")

        return str(sample_path)

    async def generate_chapter(
        self,
        chapter_text: str,
        voice: str,
        speed: float,
        chunk_size: int = 200,
    ) -> List[Path]:
        
        # Generate audio for entire chapter (with chunking)
        # For long chapters, splits into manageable chunks to avoid memory issues and improve processing time
        
        from app.services.text_service import text_service

        # Split into chunks
        chunks = text_service.chunk_text(chapter_text, max_words=chunk_size)

        self.logger.info(f"Generating {len(chunks)} audio chunks")

        audio_files = []

        for i, chunk in enumerate(chunks, 1):
            self.logger.info(f"Processing chunk {i}/{len(chunks)}")

            # Generate unique filename
            chunk_id = str(uuid.uuid4())[:12]
            output_path = self.output_dir / f"chunk_{chunk_id}.wav"

            # Generate audio
            audio_path = await self.generate_speech(
                text=chunk,
                voice=voice,
                speed=speed,
                output_path=output_path,
            )

            audio_files.append(audio_path)

        return audio_files

    def get_available_voices(self) -> List[Dict]:
        
        # Get list of available voices
        # List of voice information dicts
        
        voices = []

        for voice_config in settings.DEMO_VOICES:
            sample_path = self.voice_dir / voice_config["sample_file"]

            voices.append(
                {
                    "id": voice_config["id"],
                    "name": voice_config["name"],
                    "language": voice_config["language"],
                    "gender": voice_config["gender"],
                    "description": voice_config["description"],
                    "sample_available": sample_path.exists(),
                    "sample_url": f"/api/voices/{voice_config['id']}/sample"
                    if sample_path.exists()
                    else None,
                }
            )

        return voices

    async def create_voice_sample(self, voice_id: str, sample_text: str) -> Path:
        
        # Create sample audio for a voice
        
        sample_path = self.voice_dir / f"{voice_id}_sample.wav"

        await self.generate_speech(
            text=sample_text,
            voice=voice_id,
            output_path=sample_path,
        )

        return sample_path

    def estimate_generation_time(self, word_count: int) -> float:
        
        # Estimate generation time based on word count
        if self.device == "cpu":
            seconds_per_word = 0.5
        else:
            seconds_per_word = 0.1

        estimated_time = word_count * seconds_per_word
        return round(estimated_time, 2)

    def validate_parameters(
        self, speed: float, pitch: int, tone: str
    ) -> Tuple[bool, Optional[str]]:
        
        # Validate TTS parameters
        
        if not (settings.MIN_SPEED <= speed <= settings.MAX_SPEED):
            return (
                False,
                f"Speed must be between {settings.MIN_SPEED} and {settings.MAX_SPEED}",
            )

        if not (settings.MIN_PITCH <= pitch <= settings.MAX_PITCH):
            return (
                False,
                f"Pitch must be between {settings.MIN_PITCH} and {settings.MAX_PITCH}",
            )

        if tone not in settings.AVAILABLE_TONES:
            return False, f"Tone must be one of: {', '.join(settings.AVAILABLE_TONES)}"

        return True, None

    def cleanup_old_outputs(self, hours: int = 24) -> int:
        
        # Clean up old generated audio files
        # hours: Delete files older than this many hours
        import time

        deleted_count = 0
        cutoff_time = time.time() - (hours * 60 * 60)

        for audio_file in self.output_dir.glob("*.wav"):
            if audio_file.stat().st_mtime < cutoff_time:
                audio_file.unlink()
                deleted_count += 1
                self.logger.debug(f"Deleted old audio: {audio_file}")

        if deleted_count > 0:
            self.logger.info(f"Cleaned up {deleted_count} old audio files")

        return deleted_count

    def get_model_info(self) -> Dict:
        
        # Get information about loaded model
        # Dictionary with model information
        
        return {
            "model_name": self.model_name,
            "device": self.device,
            "sample_rate": self.sample_rate,
            "loaded": self.is_model_loaded(),
            "gpu_available": torch.cuda.is_available(),
            "mps_available": hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available(),
        }


# SINGLETON INSTANCE

tts_service = TTSService()

__all__ = ["TTSService", "tts_service"]
