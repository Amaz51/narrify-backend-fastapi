"""
Audio Stitching Service
Advanced audio merging with crossfades and normalization

Implements PDF Section 3.10:
- Merge audio segments using pydub
- Apply crossfades for seamless transitions
- Normalize output
"""

from pathlib import Path
from typing import List, Optional
import numpy as np
from pydub import AudioSegment
from pydub.effects import normalize
from loguru import logger

from app.config import settings


class AudioStitchingService:
    """
    Professional audio stitching service
    
    Features:
    - Seamless crossfades between segments
    - Loudness normalization
    - Silence trimming
    - Format conversion
    """
    
    def __init__(self):
        self.logger = logger.bind(name=__name__)
        self.output_dir = settings.OUTPUT_DIR
    
    async def stitch_audio_segments(
        self,
        audio_files: List[Path],
        output_path: Optional[Path] = None,
        crossfade_ms: int = 100,
        normalize_audio: bool = True,
        add_silence_between: int = 500,  # ms between segments
    ) -> Path:
        """
        Stitch multiple audio files into one
        
        Args:
            audio_files: List of audio file paths
            output_path: Output file path
            crossfade_ms: Crossfade duration in milliseconds
            normalize_audio: Whether to normalize final audio
            add_silence_between: Silence duration between segments (ms)
            
        Returns:
            Path to stitched audio file
        """
        if not audio_files:
            raise ValueError("No audio files to stitch")
        
        if len(audio_files) == 1:
            self.logger.info("Single file, no stitching needed")
            return audio_files[0]
        
        self.logger.info(f"Stitching {len(audio_files)} audio segments")
        
        try:
            # Load all audio segments
            segments = []
            for i, audio_file in enumerate(audio_files, 1):
                self.logger.debug(f"Loading segment {i}/{len(audio_files)}")
                segment = AudioSegment.from_wav(str(audio_file))
                segments.append(segment)
            
            # Start with first segment
            combined = segments[0]
            
            # Add remaining segments with crossfade
            for i, segment in enumerate(segments[1:], 2):
                self.logger.debug(f"Merging segment {i}/{len(segments)}")
                
                # Add silence between segments
                if add_silence_between > 0:
                    silence = AudioSegment.silent(duration=add_silence_between)
                    combined = combined + silence
                
                # Crossfade into next segment
                if crossfade_ms > 0 and len(combined) > crossfade_ms:
                    combined = combined.append(segment, crossfade=crossfade_ms)
                else:
                    combined = combined + segment
            
            # Normalize loudness
            if normalize_audio:
                self.logger.debug("Normalizing audio")
                combined = normalize(combined)
            
            # Generate output path if not provided
            if output_path is None:
                import uuid
                audio_id = str(uuid.uuid4())[:12]
                output_path = self.output_dir / f"{audio_id}_stitched.wav"
            
            # Export
            self.logger.info(f"Exporting to: {output_path}")
            combined.export(
                str(output_path),
                format="wav",
                parameters=["-ar", str(settings.TTS_SAMPLE_RATE)]
            )
            
            # Get duration
            duration = len(combined) / 1000.0  # Convert to seconds
            
            self.logger.info(
                f"✅ Audio stitched: {len(audio_files)} segments → "
                f"{duration:.1f}s @ {output_path}"
            )
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"Audio stitching failed: {e}")
            raise Exception(f"Audio stitching failed: {str(e)}")
    
    async def add_background_music(
        self,
        speech_path: Path,
        music_path: Path,
        output_path: Optional[Path] = None,
        music_volume: float = 0.2,  # 20% of speech volume
    ) -> Path:
        """
        Add background music to speech audio
        
        Args:
            speech_path: Path to speech audio
            music_path: Path to background music
            output_path: Output path
            music_volume: Music volume relative to speech (0.0-1.0)
            
        Returns:
            Path to mixed audio
        """
        try:
            self.logger.info("Adding background music")
            
            # Load audio files
            speech = AudioSegment.from_wav(str(speech_path))
            music = AudioSegment.from_file(str(music_path))
            
            # Loop music if shorter than speech
            if len(music) < len(speech):
                repeats = (len(speech) // len(music)) + 1
                music = music * repeats
            
            # Trim music to speech length
            music = music[:len(speech)]
            
            # Reduce music volume
            music = music - (20 * (1 - music_volume))  # Reduce by dB
            
            # Mix speech and music
            mixed = speech.overlay(music)
            
            # Generate output path
            if output_path is None:
                import uuid
                audio_id = str(uuid.uuid4())[:12]
                output_path = self.output_dir / f"{audio_id}_with_music.wav"
            
            # Export
            mixed.export(str(output_path), format="wav")
            
            self.logger.info(f"✅ Music added: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Failed to add background music: {e}")
            raise
    
    async def convert_format(
        self,
        input_path: Path,
        output_format: str = "mp3",
        bitrate: str = "192k"
    ) -> Path:
        """
        Convert audio to different format
        
        Args:
            input_path: Input audio file
            output_format: Target format (mp3, wav, ogg, etc.)
            bitrate: Bitrate for compressed formats
            
        Returns:
            Path to converted file
        """
        try:
            self.logger.info(f"Converting to {output_format}")
            
            # Load audio
            audio = AudioSegment.from_file(str(input_path))
            
            # Generate output path
            output_path = input_path.with_suffix(f".{output_format}")
            
            # Export with format-specific settings
            export_params = {}
            if output_format == "mp3":
                export_params = {
                    "format": "mp3",
                    "bitrate": bitrate,
                    "parameters": ["-q:a", "0"]  # Highest quality
                }
            elif output_format == "ogg":
                export_params = {
                    "format": "ogg",
                    "codec": "libvorbis",
                    "parameters": ["-q:a", "6"]
                }
            else:
                export_params = {"format": output_format}
            
            audio.export(str(output_path), **export_params)
            
            self.logger.info(f"✅ Converted to {output_format}: {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Format conversion failed: {e}")
            raise
    
    def get_audio_duration(self, audio_path: Path) -> float:
        """
        Get audio duration in seconds
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Duration in seconds
        """
        try:
            audio = AudioSegment.from_file(str(audio_path))
            duration = len(audio) / 1000.0  # Convert ms to seconds
            return duration
        except Exception as e:
            self.logger.error(f"Failed to get audio duration: {e}")
            return 0.0
    
    async def apply_fade_effects(
        self,
        audio_path: Path,
        fade_in_ms: int = 1000,
        fade_out_ms: int = 1000,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Apply fade in/out effects
        
        Args:
            audio_path: Input audio
            fade_in_ms: Fade in duration (ms)
            fade_out_ms: Fade out duration (ms)
            output_path: Output path
            
        Returns:
            Path to processed audio
        """
        try:
            audio = AudioSegment.from_file(str(audio_path))
            
            # Apply fades
            if fade_in_ms > 0:
                audio = audio.fade_in(fade_in_ms)
            
            if fade_out_ms > 0:
                audio = audio.fade_out(fade_out_ms)
            
            # Generate output path
            if output_path is None:
                output_path = audio_path.with_name(
                    f"{audio_path.stem}_faded{audio_path.suffix}"
                )
            
            audio.export(str(output_path), format="wav")
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"Failed to apply fade effects: {e}")
            raise


# Global instance
audio_stitching_service = AudioStitchingService()

__all__ = ["AudioStitchingService", "audio_stitching_service"]