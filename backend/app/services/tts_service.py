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
    
    # Emotion → temperature mapping for expressive variance
    _EMOTION_TEMPERATURE = {
        "neutral":    0.65,
        "calm":       0.65,
        "sad":        0.68,
        "longing":    0.68,
        "tender":     0.70,
        "romantic":   0.72,
        "happy":      0.78,
        "excited":    0.82,
        "surprised":  0.82,
        "passionate": 0.84,
        "angry":      0.85,
        "breathless": 0.85,
        "fearful":    0.80,
        "disgust":    0.78,
    }

    def _get_emotion_temperature(self, emotion: str) -> float:
        """Return appropriate temperature for the given emotion label."""
        return self._EMOTION_TEMPERATURE.get(emotion.lower(), 0.75)

    # ---- Number-to-words helper (uses num2words if available) ----
    @staticmethod
    def _num_to_words(n: str) -> str:
        try:
            import num2words
            return num2words.num2words(int(n.replace(',', '')))
        except Exception:
            return n

    @staticmethod
    def _ordinal_to_words(n: str) -> str:
        try:
            import num2words
            return num2words.num2words(int(n), to='ordinal')
        except Exception:
            return n

    def _clean_text(self, text: str) -> str:
        """
        Clean and pre-process text for natural-sounding TTS output.

        Pipeline:
          1. Whitespace normalisation
          2. Abbreviation expansion (Mr/Dr/etc.)
          3. Currency → spoken form  ($12.50 → "twelve dollars fifty")
          4. Ordinal numbers  (3rd → "third")
          5. Cardinal numbers (1,234 → "one thousand two hundred thirty four")
          6. Acronym spacing  (FBI → "F B I")
          7. Punctuation → prosodic cues
          8. Strip XTTS-incompatible characters
        """
        import re

        # 1. Whitespace
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = re.sub(r'\s+', ' ', text).strip()

        # 2. Abbreviations
        abbrev = {
            r'\bMr\.': 'Mister', r'\bMrs\.': 'Missus', r'\bMs\.': 'Miss',
            r'\bDr\.': 'Doctor', r'\bProf\.': 'Professor',
            r'\bSt\.': 'Saint',  r'\bvs\.': 'versus',
            r'\betc\.': 'etcetera', r'\be\.g\.': 'for example',
            r'\bi\.e\.': 'that is', r'\bapprox\.': 'approximately',
        }
        for pat, repl in abbrev.items():
            text = re.sub(pat, repl, text, flags=re.IGNORECASE)

        # 3. Currency  ($12.50 / £100 / €45)
        def _currency(m):
            sym = m.group(1)
            amount = m.group(2).replace(',', '')
            name = {'$': 'dollars', '£': 'pounds', '€': 'euros'}.get(sym, sym)
            try:
                val = float(amount)
                major = int(val)
                minor = round((val - major) * 100)
                parts = [self._num_to_words(str(major)), name]
                if minor:
                    parts += [self._num_to_words(str(minor)),
                               'cents' if sym == '$' else 'pence' if sym == '£' else 'cents']
                return ' '.join(parts)
            except Exception:
                return m.group(0)
        text = re.sub(r'([\$£€])([\d,]+(?:\.\d{1,2})?)', _currency, text)

        # 4. Ordinal numbers  (1st, 2nd, 3rd, 4th …)
        def _ordinal(m):
            return self._ordinal_to_words(m.group(1))
        text = re.sub(r'\b(\d+)(?:st|nd|rd|th)\b', _ordinal, text)

        # 5. Cardinal numbers with commas or plain integers (up to 9 digits)
        def _cardinal(m):
            return self._num_to_words(m.group(0))
        text = re.sub(r'\b\d{1,3}(?:,\d{3})+\b', _cardinal, text)   # comma-separated
        text = re.sub(r'\b\d+\b', _cardinal, text)                    # plain digits

        # 6. ALL-CAPS acronyms (3+ letters) → spaced letters  (NASA → "N A S A")
        text = re.sub(
            r'\b([A-Z]{3,})\b',
            lambda m: ' '.join(list(m.group(1))),
            text
        )

        # 7. Punctuation → prosodic cues
        text = re.sub(r'\s*[—–]\s*', ', ', text)      # em/en-dash → pause
        text = re.sub(r'\.{2,}', '...', text)           # normalise ellipsis

        # 8. Strip characters XTTS can't handle — preserve Unicode letters/digits
        # \w in Python 3 already matches Unicode word chars (Urdu, Arabic, etc.)
        text = re.sub(r'[^\w\s\.,!?\-\'\"…]', '', text, flags=re.UNICODE)
        text = re.sub(r'\s+', ' ', text).strip()

        # Ensure terminal punctuation
        if text and text[-1] not in '.!?…':
            text += '.'

        return text
    

    async def generate_speech(
        self,
        text: str,
        voice: str = "voice7",
        speed: float = 1.0,
        language: str = "en",
        output_path: Optional[Path] = None,
        emotion: str = "neutral",
    ) -> Path:

        # Generate speech from text
        try:
            text = self._clean_text(text)
            temperature = self._get_emotion_temperature(emotion)

            self.logger.info(
                f"Generating speech ({len(text)} chars, voice: {voice}, "
                f"emotion: {emotion}, temp: {temperature:.2f})"
            )

            # Generate output path if not provided
            if output_path is None:
                audio_id = str(uuid.uuid4())[:12]
                output_path = self.output_dir / f"{audio_id}.wav"

            start_time = time.time()
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
                temperature,
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
        temperature: float = 0.75,
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
                temperature=temperature,   # Emotion-aware variance
                length_penalty=1.0,
                repetition_penalty=5.0,    # Prevent monotone repetition
                top_k=50,
                top_p=0.85,
            )

        except Exception as e:
            self.logger.error(f"Sync generation failed: {e}")
            raise

    def get_voice_conditioning_latents(self, voice_id: str):
        """
        Pre-compute XTTS conditioning latents for a voice.
        Returns (gpt_cond_latent, speaker_embedding) tuple, or None on failure.
        Call once per unique voice before the generation loop to avoid reloading
        the speaker WAV on every segment.
        """
        try:
            speaker_wav = self._get_voice_sample_path(voice_id)
            xtts_model = self.model.synthesizer.tts_model
            gpt_cond_latent, speaker_embedding = xtts_model.get_conditioning_latents(
                audio_path=[speaker_wav]
            )
            return gpt_cond_latent, speaker_embedding
        except Exception as e:
            self.logger.warning(f"Could not compute conditioning latents for {voice_id}: {e}")
            return None

    async def generate_speech_fast(
        self,
        text: str,
        gpt_cond_latent,
        speaker_embedding,
        speed: float = 1.0,
        language: str = "en",
        emotion: str = "neutral",
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Generate speech using pre-computed conditioning latents (fast path).
        Skips the speaker WAV loading + embedding step that runs in the standard path.
        """
        try:
            text = self._clean_text(text)
            temperature = self._get_emotion_temperature(emotion)

            if output_path is None:
                audio_id = str(uuid.uuid4())[:12]
                output_path = self.output_dir / f"{audio_id}.wav"

            start_time = time.time()
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._generate_audio_fast_sync,
                text,
                gpt_cond_latent,
                speaker_embedding,
                str(output_path),
                language,
                speed,
                temperature,
            )

            generation_time = time.time() - start_time
            self.logger.info(f"Fast speech generated in {generation_time:.2f}s: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Fast speech generation failed: {e}")
            raise Exception(f"TTS fast generation failed: {str(e)}")

    def _generate_audio_fast_sync(
        self,
        text: str,
        gpt_cond_latent,
        speaker_embedding,
        output_path: str,
        language: str,
        speed: float,
        temperature: float = 0.75,
    ):
        """Synchronous fast audio generation using pre-computed latents."""
        import soundfile as sf
        import numpy as np

        try:
            xtts_model = self.model.synthesizer.tts_model
            out = xtts_model.inference(
                text=text,
                language=language,
                gpt_cond_latent=gpt_cond_latent,
                speaker_embedding=speaker_embedding,
                speed=speed,
                temperature=temperature,
                length_penalty=1.0,
                repetition_penalty=5.0,
                top_k=50,
                top_p=0.85,
            )
            wav = np.array(out["wav"])
            sf.write(output_path, wav.astype("float32"), self.sample_rate)
        except Exception as e:
            self.logger.error(f"Fast sync generation failed: {e}")
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
