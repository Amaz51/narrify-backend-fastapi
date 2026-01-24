# Audio Processing Service

# Handles audio post-processing including pitch, speed, tone adjustments,
# normalization, and format conversion.

import uuid # unique id
from pathlib import Path 
from typing import Optional, Tuple

import librosa
import numpy as np
import soundfile as sf
from loguru import logger
from pydub import AudioSegment
from scipy import signal

from app.config import settings
from app.models.schemas import AudioFormat, TonePreset


class AudioService:
    
    # Audio Post-Processing Service
    # Applies various audio modifications and optimizations.

    def __init__(self):
        # Initialize audio service
        self.logger = logger.bind(name=__name__)
        self.output_dir = settings.OUTPUT_DIR
        self.sample_rate = settings.TTS_SAMPLE_RATE

    async def process_audio(
        self,
        input_path: Path,
        pitch: int = 0,
        speed: float = 1.0,
        tone: TonePreset = TonePreset.NORMAL,
        output_format: AudioFormat = AudioFormat.WAV,
        normalize: bool = True,
        trim_silence: bool = True,
    ) -> Path:

        # Complete audio processing pipeline
        # Returns Path to processed audio file

        try:
            self.logger.info(f"Processing audio: {input_path}")

            # Load audio
            audio, sr = librosa.load(str(input_path), sr=self.sample_rate)

            # Apply pitch shift
            if pitch != 0:
                audio = self._adjust_pitch(audio, sr, pitch)

            # Apply speed change
            if speed != 1.0:
                audio = self._adjust_speed(audio, sr, speed)

            # Apply tone preset
            if tone != TonePreset.NORMAL:
                audio = self._apply_tone(audio, sr, tone)

            # Normalize loudness
            if normalize:
                audio = self._normalize_audio(audio)

            # Trim silence
            if trim_silence:
                audio = self._trim_silence(audio, sr)

            # Generate output path
            audio_id = str(uuid.uuid4())[:12]
            output_filename = f"{audio_id}_processed.{output_format.value}"
            output_path = self.output_dir / output_filename

            # Save audio
            if output_format == AudioFormat.WAV:
                sf.write(str(output_path), audio, sr)
            elif output_format == AudioFormat.MP3:
                # Convert to MP3 using pydub
                temp_wav = self.output_dir / f"{audio_id}_temp.wav"
                sf.write(str(temp_wav), audio, sr)
                self._convert_to_mp3(temp_wav, output_path)
                temp_wav.unlink()  # Delete temp file

            self.logger.info(f"Audio processed: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Audio processing failed: {e}")
            raise Exception(f"Audio processing failed: {str(e)}")

    def _adjust_pitch(self, audio: np.ndarray, sr: int, semitones: int) -> np.ndarray:
        
        # Adjust audio pitch

        self.logger.debug(f"Adjusting pitch: {semitones:+d} semitones")

        try:
            audio_shifted = librosa.effects.pitch_shift(
                y=audio, sr=sr, n_steps=semitones
            )
            return audio_shifted

        except Exception as e:
            self.logger.warning(f"Pitch adjustment failed: {e}, returning original")
            return audio

    def _adjust_speed(self, audio: np.ndarray, sr: int, speed: float) -> np.ndarray:
        
        # Adjust audio speed

        self.logger.debug(f"Adjusting speed: {speed}x")

        try:
            audio_stretched = librosa.effects.time_stretch(y=audio, rate=speed)
            return audio_stretched

        except Exception as e:
            self.logger.warning(f"Speed adjustment failed: {e}, returning original")
            return audio

    def _apply_tone(
        self, audio: np.ndarray, sr: int, tone: TonePreset
    ) -> np.ndarray:
        
        # Apply tone preset
        # Returns Tone-adjusted audio
        
        self.logger.debug(f"Applying tone: {tone.value}")

        try:
            if tone == TonePreset.WARM:
                # Low-pass filter (softer, mellower)
                sos = signal.butter(10, 3000, "lp", fs=sr, output="sos")
                audio = signal.sosfilt(sos, audio)

            elif tone == TonePreset.BRIGHT:
                # High-pass filter (crisper, sharper)
                sos = signal.butter(10, 1000, "hp", fs=sr, output="sos")
                audio_high = signal.sosfilt(sos, audio)
                audio = audio + 0.3 * audio_high

            elif tone == TonePreset.DEEP:
                # Boost low frequencies
                sos = signal.butter(10, 500, "lp", fs=sr, output="sos")
                audio_low = signal.sosfilt(sos, audio)
                audio = audio + 0.3 * audio_low

            return audio

        except Exception as e:
            self.logger.warning(f"Tone adjustment failed: {e}, returning original")
            return audio

    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        
        # Normalize audio loudness
        
        self.logger.debug("Normalizing audio")

        try:
            # Peak normalization
            if np.max(np.abs(audio)) > 0:
                audio = audio / np.max(np.abs(audio))

            # Optionally apply compression (reduce dynamic range)
            audio = np.tanh(audio * 0.9)

            return audio

        except Exception as e:
            self.logger.warning(f"Normalization failed: {e}, returning original")
            return audio

    def _trim_silence(self, audio: np.ndarray, sr: int) -> np.ndarray:
        
        # Trim leading/trailing silence
        
        if not settings.TRIM_SILENCE:
            return audio

        self.logger.debug("Trimming silence")

        try:
            # Use librosa's trim function
            audio_trimmed, _ = librosa.effects.trim(
                y=audio,
                top_db=abs(settings.SILENCE_THRESHOLD),
                frame_length=2048,
                hop_length=512,
            )

            return audio_trimmed

        except Exception as e:
            self.logger.warning(f"Silence trimming failed: {e}, returning original")
            return audio

    def _convert_to_mp3(self, input_path: Path, output_path: Path):
        
        # Convert WAV to MP3
        self.logger.debug(f"Converting to MP3: {output_path}")

        try:
            audio = AudioSegment.from_wav(str(input_path))
            audio.export(
                str(output_path),
                format="mp3",
                bitrate=settings.AUDIO_BITRATE,
                parameters=["-q:a", "0"],  # Highest quality
            )

        except Exception as e:
            self.logger.error(f"MP3 conversion failed: {e}")
            raise

    async def merge_audio_files(
        self, audio_files: list[Path], output_path: Optional[Path] = None
    ) -> Path:
        
        # Merge multiple audio files into one
        
        try:
            self.logger.info(f"Merging {len(audio_files)} audio files")

            if not audio_files:
                raise ValueError("No audio files to merge")

            if len(audio_files) == 1:
                return audio_files[0]

            # Load all audio files
            audio_data = []
            for audio_file in audio_files:
                audio, sr = librosa.load(str(audio_file), sr=self.sample_rate)
                audio_data.append(audio)

            # Concatenate
            merged_audio = np.concatenate(audio_data)

            # Generate output path if not provided
            if output_path is None:
                audio_id = str(uuid.uuid4())[:12]
                output_path = self.output_dir / f"{audio_id}_merged.wav"

            # Save merged audio
            sf.write(str(output_path), merged_audio, self.sample_rate)

            self.logger.info(f"Audio files merged: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Audio merge failed: {e}")
            raise Exception(f"Audio merge failed: {str(e)}")

    def get_audio_info(self, audio_path: Path) -> dict:
        
        # Get audio file information

        try:
            audio, sr = librosa.load(str(audio_path), sr=None)

            duration = len(audio) / sr
            file_size = audio_path.stat().st_size

            # Calculate statistics
            rms = librosa.feature.rms(y=audio)[0]
            rms_mean = float(np.mean(rms))

            spectral_centroid = librosa.feature.spectral_centroid(y=audio, sr=sr)[0]
            sc_mean = float(np.mean(spectral_centroid))

            return {
                "duration": round(duration, 2),
                "sample_rate": sr,
                "channels": 1 if audio.ndim == 1 else audio.shape[0],
                "file_size": file_size,
                "rms_energy": round(rms_mean, 4),
                "spectral_centroid": round(sc_mean, 2),
            }

        except Exception as e:
            self.logger.error(f"Failed to get audio info: {e}")
            return {}

    def validate_audio(self, audio_path: Path) -> Tuple[bool, Optional[str]]:
        
        # Validate audio file

        try:
            if not audio_path.exists():
                return False, "Audio file does not exist"

            # Try to load audio
            audio, sr = librosa.load(str(audio_path), sr=None, duration=1.0)

            if len(audio) == 0:
                return False, "Audio file is empty"

            return True, None

        except Exception as e:
            return False, f"Invalid audio file: {str(e)}"

    def cleanup_temp_files(self) -> int:
        
        # Clean up temporary audio files
        # Delete temp files
        for temp_file in self.output_dir.glob("*_temp.*"):
            temp_file.unlink()
            deleted_count += 1
            self.logger.debug(f"Deleted temp file: {temp_file}")

        # Delete chunk files
        for chunk_file in self.output_dir.glob("chunk_*"):
            chunk_file.unlink()
            deleted_count += 1
            self.logger.debug(f"Deleted chunk file: {chunk_file}")

        if deleted_count > 0:
            self.logger.info(f"Cleaned up {deleted_count} temporary files")

        return deleted_count


# SINGLETON INSTANCE

audio_service = AudioService()

__all__ = ["AudioService", "audio_service"]
