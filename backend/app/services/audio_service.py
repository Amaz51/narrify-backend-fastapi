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
       apply_eq: bool = True,
       apply_compression: bool = True,
       apply_deessing: bool = True,
       apply_noise_reduction: bool = True,
       apply_noise_gate: bool = True,
   ) -> Path:


       # Complete broadcast-grade audio processing pipeline
       # Returns Path to processed audio file


       try:
           self.logger.info(f"Processing audio: {input_path}")


           # Load audio
           audio, sr = librosa.load(str(input_path), sr=self.sample_rate)


           # 1. Trim leading/trailing silence first (cleaner signal for processing)
           if trim_silence:
               audio = self._trim_silence(audio, sr)


           # 2. Spectral noise reduction — removes broadband hiss from XTTS output
           if apply_noise_reduction:
               audio = self._noise_reduce(audio, sr)


           # 3. Noise gate — zeros out residual noise between speech segments
           if apply_noise_gate:
               audio = self._noise_gate(audio, sr)


           # 4. EQ chain: high-pass, presence, air
           if apply_eq:
               audio = self._apply_eq_chain(audio, sr)


           # 5. Apply pitch shift (optional user parameter)
           if pitch != 0:
               audio = self._adjust_pitch(audio, sr, pitch)


           # 6. Apply speed change (optional user parameter)
           if speed != 1.0:
               audio = self._adjust_speed(audio, sr, speed)


           # 7. Apply tone preset
           if tone != TonePreset.NORMAL:
               audio = self._apply_tone(audio, sr, tone)


           # 8. De-esser (before compression so sibilance doesn't pump the compressor)
           if apply_deessing:
               audio = self._deess(audio, sr)


           # 9. Soft compression – tighten dynamic range
           if apply_compression:
               audio = self._soft_compress(audio)


           # 10. Broadcast LUFS normalization (target -18 LUFS / Audible standard)
           if normalize:
               audio = self._normalize_audio(audio)


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
       """
       Broadcast-standard loudness normalization targeting -18 LUFS
       (Amazon Audible spec).  Falls back to peak normalization if pyloudnorm
       is not installed.
       """
       self.logger.debug("Normalizing audio (broadcast standard)")
       try:
           import pyloudnorm as pyln
           meter = pyln.Meter(self.sample_rate)
           loudness = meter.integrated_loudness(audio)
           # Avoid normalizing silence / near-silence
           if loudness < -70:
               return audio
           normalized = pyln.normalize.loudness(audio, loudness, -18.0)
           # Safety: hard-limit to prevent clipping after normalization
           normalized = np.clip(normalized, -0.98, 0.98)
           return normalized.astype(np.float32)
       except ImportError:
           # Fallback: peak normalization
           peak = np.max(np.abs(audio))
           if peak > 0:
               audio = audio / peak * 0.95
           return audio
       except Exception as e:
           self.logger.warning(f"Normalization failed: {e}, returning original")
           return audio


   def _apply_eq_chain(self, audio: np.ndarray, sr: int) -> np.ndarray:
       """
       Audiobook EQ chain:
         1. High-pass at 80 Hz  – removes low-frequency rumble
         2. Gentle presence boost 2–5 kHz +2 dB – clarity / intelligibility
         3. Air shelf 8 kHz +1.5 dB – brightness without harshness
       """
       try:
           from scipy import signal as _sig


           # 1. High-pass 80 Hz (3rd order Butterworth)
           sos_hp = _sig.butter(3, 80, btype='high', fs=sr, output='sos')
           audio = _sig.sosfilt(sos_hp, audio)


           # 2. Presence peak: +2 dB centred at 3 kHz, Q=1.0
           b_pres, a_pres = self._peaking_eq(sr, freq=3000, gain_db=2.0, Q=1.0)
           audio = _sig.lfilter(b_pres, a_pres, audio)


           # 3. Air shelf: +1.5 dB at 8 kHz (high-shelf)
           b_air, a_air = self._high_shelf_eq(sr, freq=8000, gain_db=1.5)
           audio = _sig.lfilter(b_air, a_air, audio)


           return audio.astype(np.float32)
       except Exception as e:
           self.logger.warning(f"EQ chain failed: {e}")
           return audio


   def _peaking_eq(self, sr: int, freq: float, gain_db: float, Q: float):
       """Biquad peaking EQ filter coefficients."""
       import math
       A = 10 ** (gain_db / 40.0)
       w0 = 2 * math.pi * freq / sr
       alpha = math.sin(w0) / (2 * Q)
       b0 =  1 + alpha * A
       b1 = -2 * math.cos(w0)
       b2 =  1 - alpha * A
       a0 =  1 + alpha / A
       a1 = -2 * math.cos(w0)
       a2 =  1 - alpha / A
       return [b0/a0, b1/a0, b2/a0], [1.0, a1/a0, a2/a0]


   def _high_shelf_eq(self, sr: int, freq: float, gain_db: float):
       """Biquad high-shelf EQ filter coefficients."""
       import math
       A = 10 ** (gain_db / 40.0)
       w0 = 2 * math.pi * freq / sr
       alpha = math.sin(w0) / 2 * math.sqrt((A + 1/A) * (1/0.707 - 1) + 2)
       cosw = math.cos(w0)
       b0 =       A * ((A+1) + (A-1)*cosw + 2*math.sqrt(A)*alpha)
       b1 = -2 * A * ((A-1) + (A+1)*cosw)
       b2 =       A * ((A+1) + (A-1)*cosw - 2*math.sqrt(A)*alpha)
       a0 =            (A+1) - (A-1)*cosw + 2*math.sqrt(A)*alpha
       a1 =   2 *     ((A-1) - (A+1)*cosw)
       a2 =            (A+1) - (A-1)*cosw - 2*math.sqrt(A)*alpha
       return [b0/a0, b1/a0, b2/a0], [1.0, a1/a0, a2/a0]


   def _soft_compress(self, audio: np.ndarray, threshold: float = 0.5,
                      ratio: float = 3.0, makeup_db: float = 1.5) -> np.ndarray:
       """
       Soft-knee compressor to tighten dynamic range.
       Threshold and makeup gain are applied in the linear domain.
       """
       try:
           makeup = 10 ** (makeup_db / 20.0)
           abs_audio = np.abs(audio)
           gain = np.where(
               abs_audio > threshold,
               threshold + (abs_audio - threshold) / ratio,
               abs_audio
           )
           # Avoid division by zero on silent frames
           scale = np.where(abs_audio > 1e-8, gain / (abs_audio + 1e-8), 1.0)
           return np.clip(audio * scale * makeup, -0.98, 0.98).astype(np.float32)
       except Exception as e:
           self.logger.warning(f"Compression failed: {e}")
           return audio


   def _deess(self, audio: np.ndarray, sr: int,
              threshold: float = 0.06, freq: float = 6500.0) -> np.ndarray:
       """
       Frequency-selective de-esser: attenuates sibilance in the 5–9 kHz band
       when energy exceeds threshold.
       """
       try:
           from scipy import signal as _sig
           # Isolate the sibilance band
           sos = _sig.butter(4, [5000, 9000], btype='bandpass', fs=sr, output='sos')
           sibilance = _sig.sosfilt(sos, audio)
           # Compute short-time energy envelope
           frame = int(sr * 0.005)   # 5 ms frames
           pad = frame - (len(sibilance) % frame or frame)
           padded = np.pad(sibilance, (0, pad))
           frames = padded.reshape(-1, frame)
           energy = np.sqrt(np.mean(frames ** 2, axis=1))
           # Build per-sample gain reduction
           gain_frames = np.where(energy > threshold, threshold / (energy + 1e-8), 1.0)
           gain = np.repeat(gain_frames, frame)[: len(audio)]
           return (audio * gain).astype(np.float32)
       except Exception as e:
           self.logger.warning(f"De-essing failed: {e}")
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


   def _noise_reduce(self, audio: np.ndarray, sr: int) -> np.ndarray:
       """
       Spectral noise reduction using noisereduce (stationary + non-stationary).
       Estimates noise profile from the quietest 10% of frames, then applies
       spectral gating to suppress broadband hiss introduced by XTTS synthesis.
       Falls back to scipy Wiener filter if noisereduce is unavailable.
       """
       try:
           import noisereduce as nr


           frame_len = 512
           n_frames = len(audio) // frame_len
           if n_frames < 2:
               return audio


           frames = audio[: n_frames * frame_len].reshape(n_frames, frame_len)
           rms_per_frame = np.sqrt(np.mean(frames ** 2, axis=1))


           # Use the quietest 10% of frames as the noise profile
           n_noise_frames = max(1, n_frames // 10)
           noise_indices = np.argsort(rms_per_frame)[:n_noise_frames]
           noise_profile = frames[noise_indices].flatten()


           reduced = nr.reduce_noise(
               y=audio,
               y_noise=noise_profile,
               sr=sr,
               stationary=False,
               prop_decrease=0.65,   # 65% — removes hiss without stripping consonant air (s/f/th)
               n_fft=1024,
               win_length=1024,
               hop_length=256,
               n_std_thresh_stationary=1.5,
           )
           return reduced.astype(np.float32)


       except ImportError:
           # Fallback: Wiener filter (scipy) — lighter but effective for stationary noise
           try:
               from scipy.signal import wiener
               return wiener(audio, mysize=29).astype(np.float32)
           except Exception:
               return audio
       except Exception as e:
           self.logger.warning(f"Noise reduction failed: {e}")
           return audio


   def _noise_gate(
       self,
       audio: np.ndarray,
       sr: int,
       threshold_db: float = -58.0,
       attack_ms: float = 10.0,
       release_ms: float = 80.0,
   ) -> np.ndarray:
       """
       Noise gate: attenuates audio segments below threshold_db toward silence.
       Prevents residual hiss between words while preserving natural breath sounds.


       Args:
           threshold_db: Gate opens above this level (default -58 dBFS — lenient
                         enough to keep breath sounds, strict enough to kill hiss).
           attack_ms:    How fast the gate opens (ms).
           release_ms:   How fast the gate closes — longer = more natural decay.
       """
       try:
           threshold_linear = 10 ** (threshold_db / 20.0)
           frame_len = max(1, int(sr * 0.010))  # 10 ms frames


           pad_len = (frame_len - len(audio) % frame_len) % frame_len
           padded = np.pad(audio, (0, pad_len))
           frames = padded.reshape(-1, frame_len)


           rms = np.sqrt(np.mean(frames ** 2, axis=1))
           gate = (rms > threshold_linear).astype(np.float32)


           # Smooth gate transitions (attack / release)
           attack_frames = max(1, int(attack_ms / 10))
           release_frames = max(1, int(release_ms / 10))
           smoothed = np.copy(gate)
           for i in range(1, len(smoothed)):
               diff = gate[i] - smoothed[i - 1]
               if diff > 0:
                   smoothed[i] = smoothed[i - 1] + diff / attack_frames
               else:
                   smoothed[i] = smoothed[i - 1] + diff / release_frames
           smoothed = np.clip(smoothed, 0.0, 1.0)


           # Expand from frame level back to sample level
           gain = np.repeat(smoothed, frame_len)[: len(audio)]
           return (audio * gain).astype(np.float32)


       except Exception as e:
           self.logger.warning(f"Noise gate failed: {e}")
           return audio


   def _convert_to_mp3(self, input_path: Path, output_path: Path):


       # Convert WAV to MP3 at 192 kbps (audiobook distribution standard)
       self.logger.debug(f"Converting to MP3 192kbps: {output_path}")


       try:
           audio = AudioSegment.from_wav(str(input_path))
           audio.export(
               str(output_path),
               format="mp3",
               bitrate="192k",       # Audible / Apple Books distribution quality
               parameters=["-q:a", "0"],  # Highest quality VBR pass
           )


       except Exception as e:
           self.logger.error(f"MP3 conversion failed: {e}")
           raise


   def _make_silence(self, duration_ms: int) -> np.ndarray:
       """Return a numpy array of silence for the given duration in milliseconds."""
       num_samples = int(self.sample_rate * duration_ms / 1000)
       return np.zeros(num_samples, dtype=np.float32)


   async def merge_audio_files(
       self,
       audio_files: list[Path],
       output_path: Optional[Path] = None,
       speaker_sequence: Optional[list] = None,
       inter_speaker_silence_ms: int = 420,
       intra_speaker_silence_ms: int = 180,
       crossfade_samples: int = 256,
   ) -> Path:
       """
       Merge audio files with natural silence gaps and micro-crossfades.


       Args:
           audio_files: Ordered list of per-segment WAV files.
           output_path: Where to write the final merged file.
           speaker_sequence: Optional list of speaker labels (same length as
               audio_files). When provided, a longer gap is inserted between
               consecutive segments from *different* speakers.
           inter_speaker_silence_ms: Gap (ms) between different speakers.
               Default 420 ms — long enough for the listener to register a
               speaker change, short enough to maintain narrative pace.
           intra_speaker_silence_ms: Gap (ms) between same-speaker segments.
               Default 180 ms — natural between-sentence breath space.
           crossfade_samples: Number of samples for micro-crossfade at each
               join to prevent audible clicks/pops (default 256 @ 24 kHz ≈ 10 ms).
       """
       try:
           self.logger.info(f"Merging {len(audio_files)} audio files")


           if not audio_files:
               raise ValueError("No audio files to merge")


           if len(audio_files) == 1:
               return audio_files[0]


           # Build concatenation with silence gaps.
           # NOTE: Do NOT peak-normalize individual segments here. Per-segment
           # normalization boosts every segment to peak 1.0, which destroys the
           # natural loudness variation between e.g. a whisper and an exclamation.
           # Relative loudness is preserved; a single LUFS normalization is applied
           # to the final merged file.
           pieces = []
           for idx, audio_file in enumerate(audio_files):
               audio, _ = librosa.load(str(audio_file), sr=self.sample_rate)


               # Micro-crossfade: apply a short fade-out at the end of each
               # segment and fade-in at the start of the next so that the
               # silence gap between them is perfectly click-free.
               fade = min(crossfade_samples, len(audio) // 4)
               if fade > 0:
                   fade_out = np.linspace(1.0, 0.0, fade, dtype=np.float32)
                   audio[-fade:] *= fade_out
                   fade_in = np.linspace(0.0, 1.0, fade, dtype=np.float32)
                   audio[:fade] *= fade_in


               pieces.append(audio)


               # Insert silence after every segment except the last
               if idx < len(audio_files) - 1:
                   if speaker_sequence and len(speaker_sequence) > idx + 1:
                       same_speaker = (speaker_sequence[idx] == speaker_sequence[idx + 1])
                       gap_ms = intra_speaker_silence_ms if same_speaker else inter_speaker_silence_ms
                   else:
                       gap_ms = intra_speaker_silence_ms
                   pieces.append(self._make_silence(gap_ms))


           merged_audio = np.concatenate(pieces)


           # Single LUFS normalization on the full merged file preserves
           # all relative loudness differences between segments.
           merged_audio = self._normalize_audio(merged_audio)
           merged_audio = np.clip(merged_audio, -0.97, 0.97).astype(np.float32)


           if output_path is None:
               audio_id = str(uuid.uuid4())[:12]
               output_path = self.output_dir / f"{audio_id}_merged.wav"


           sf.write(str(output_path), merged_audio, self.sample_rate, subtype='PCM_16')


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
       deleted_count = 0
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



