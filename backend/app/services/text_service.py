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
  
   # Emotion → temperature mapping.
   # Higher temperature = more expressive, more variable delivery.
   # Noise is handled by post-processing, not by capping temperature.
  
   _EMOTION_TEMPERATURE = {
       "neutral": 0.65,
       "calm": 0.64,
       "serious": 0.65,


       "sad": 0.67,
       "longing": 0.68,
       "heartbroken": 0.69,
       "crying": 0.68,


       "tender": 0.68,
       "loving": 0.69,
       "romantic": 0.70,


       "happy": 0.70,
       "joyful": 0.71,
       "excited": 0.72,
       "surprised": 0.71,


       "passionate": 0.72,
       "breathless": 0.72,
       "nervous": 0.70,
       "anxious": 0.71,
       "fearful": 0.70,


       "angry": 0.73,
       "disgust": 0.70,
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


       # 8. Strip characters XTTS can't handle
       text = re.sub(r'[^\w\s\.,!?\-\'\"…]', '', text)
       text = re.sub(r'\s+', ' ', text).strip()


       # Ensure terminal punctuation
       if text and text[-1] not in '.!?…':
           text += '.'


       return text
  


   def _inject_prosody(self, text: str, emotion: str = "neutral") -> str:
       """
       Add punctuation-based prosodic cues that guide XTTS toward natural,
       emotionally-coloured delivery.


       XTTS v2 treats punctuation as prosody instructions:
         ','   → micro-pause, continues breath
         '...' → beat pause, slight pitch drop
         '—'   → mid-phrase tension break
         '!'   → rising energy at phrase end
         '?'   → rising intonation
         CAPS  → lexical stress on that word


       Rules are kept surgical — we reshape rhythm, not meaning.
       """
       import re


       # 1. Break run-on sentences: insert a comma before coordinating conjunctions
       #    when the preceding clause is ≥ 12 words (long enough to need a breath).
       def _add_breath(m):
           before, conj, after = m.group(1), m.group(2), m.group(3)
           if len(before.split()) >= 12 and not before.rstrip().endswith(','):
               return f"{before.rstrip()}, {conj} {after.lstrip()}"
           return m.group(0)


       text = re.sub(
           r'([^,;:.!?\n]{55,}?)\s+(and|but|yet|so|for|although|though|because|while)\s+([A-Za-z])',
           _add_breath,
           text,
           flags=re.IGNORECASE,
       )


       # 2. Narrative beat: "and suddenly / but then / yet somehow" after a comma
       #    → replace comma with '...' for dramatic pause before the turn.
       if emotion not in ('excited', 'angry', 'breathless'):
           text = re.sub(
               r',\s+(and\s+(?:suddenly|then|yet)|but\s+(?:then|suddenly|somehow)|yet\s+somehow)\s+',
               r'... \1 ',
               text,
               flags=re.IGNORECASE,
           )


       # 3. Melancholy emotions: short complete sentences trail off with '...'
       #    "She was gone." (≤7 words) → "She was gone..."
       if emotion in ('sad', 'longing', 'tender', 'romantic'):
           def _trail(m):
               s = m.group(0).strip()
               words = s.split()
               if 3 <= len(words) <= 8 and s.endswith('.'):
                   return s[:-1] + '...'
               return s
           text = re.sub(r'\b[A-Z][^.!?\n]{8,35}\.', _trail, text)


       # 4. High-energy emotions: clipped em-dash rhythm on comma lists
       #    "He ran, he fell, he screamed" → "He ran — he fell — he screamed"
       if emotion in ('angry', 'breathless', 'fearful', 'excited'):
           # Replace up to 3 consecutive commas with em-dashes for staccato delivery
           count = [0]
           def _clip(m):
               if count[0] < 3:
                   count[0] += 1
                   return ' — '
               return m.group(0)
           text = re.sub(r',\s+', _clip, text)


       # 5. Ensure no runaway ellipsis or doubled dashes from transforms
       text = re.sub(r'\.{4,}', '...', text)
       text = re.sub(r'—\s*—+', '—', text)
       text = re.sub(r'\s{2,}', ' ', text).strip()


       return text


   def get_voice_conditioning_latents(self, voice_id: str):
       """
       Pre-compute XTTS speaker conditioning latents for a voice.
       Results are cached in-memory so the WAV is loaded only once per session.
       Falls back gracefully — callers should handle None return.
       """
       if not hasattr(self, '_latent_cache'):
           self._latent_cache: Dict = {}
       if voice_id in self._latent_cache:
           return self._latent_cache[voice_id]
       try:
           wav_path = self._get_voice_sample_path(voice_id)
           xtts = self.model.synthesizer.tts_model  # type: ignore[attr-defined]
           gpt_cond_latent, speaker_embedding = xtts.get_conditioning_latents(
               audio_path=[wav_path]
           )
           self._latent_cache[voice_id] = (gpt_cond_latent, speaker_embedding)
           self.logger.info(f"Cached conditioning latents for voice: {voice_id}")
           return gpt_cond_latent, speaker_embedding
       except Exception as e:
           self.logger.warning(f"Could not pre-compute latents for {voice_id}: {e}")
           return None


   async def generate_speech_fast(
       self,
       text: str,
       gpt_cond_latent,
       speaker_embedding,
       speed: float = 1.0,
       language: str = "en",
       output_path: Optional[Path] = None,
       emotion: str = "neutral",
   ) -> Path:
       """
       Generate speech using pre-computed XTTS conditioning latents.
       ~30-50% faster than generate_speech because embedding extraction
       (the most expensive per-segment step) is skipped.
       """
       try:
           text = self._clean_text(text)
           text = self._inject_prosody(text, emotion)
           temperature = self._get_emotion_temperature(emotion)


           if output_path is None:
               audio_id = str(uuid.uuid4())[:12]
               output_path = self.output_dir / f"{audio_id}.wav"


           start_time = time.time()
           loop = asyncio.get_event_loop()
           await loop.run_in_executor(
               None,
               self._generate_audio_sync_fast,
               text,
               gpt_cond_latent,
               speaker_embedding,
               str(output_path),
               language,
               speed,
               temperature,
           )
           self.logger.info(f"Speech (fast) generated in {time.time()-start_time:.2f}s: {output_path}")
           return output_path
       except Exception as e:
           self.logger.error(f"Fast speech generation failed: {e}")
           raise Exception(f"TTS generation failed: {str(e)}")


   def _generate_audio_sync_fast(
       self,
       text: str,
       gpt_cond_latent,
       speaker_embedding,
       output_path: str,
       language: str,
       speed: float,
       temperature: float,
   ):
       """Synchronous XTTS inference using pre-computed latents."""
       import soundfile as sf
       import numpy as np


       xtts = self.model.synthesizer.tts_model  # type: ignore[attr-defined]
       outputs = xtts.inference(
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
       wav = np.array(outputs["wav"])
       sf.write(output_path, wav, self.sample_rate)


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
           text = self._inject_prosody(text, emotion)
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
               temperature=temperature,   # Emotion-aware expressiveness
               length_penalty=1.0,
               repetition_penalty=5.0,    # Prevent monotone repetition
               top_k=50,                  # Wide enough for natural prosody variation
               top_p=0.85,                # Nucleus sampling for natural delivery
           )


       except Exception as e:
           self.logger.error(f"Sync generation failed: {e}")
           raise


   def _preprocess_speaker_wav(self, wav_path: str) -> str:
       """
       Clean the reference speaker WAV before passing it to XTTS cloning.
       A noise-free, well-trimmed reference dramatically improves clone quality.


       Returns the path to a preprocessed (cached) copy, or the original path
       on failure.
       """
       try:
           import hashlib, librosa, soundfile as sf, numpy as np


           src = Path(wav_path)
           # Cache key: filename + mtime so we re-process only when file changes
           mtime = str(src.stat().st_mtime)
           cache_key = hashlib.md5(f"{wav_path}{mtime}".encode()).hexdigest()[:12]
           cached = self.output_dir / f"_ref_{cache_key}.wav"


           if cached.exists():
               return str(cached)


           audio, sr = librosa.load(wav_path, sr=24000, mono=True)


           # 1. Trim silence
           audio, _ = librosa.effects.trim(audio, top_db=35, frame_length=2048, hop_length=512)


           # 2. Noise reduction on the reference sample
           try:
               import noisereduce as nr
               frame_len = 512
               n_frames = len(audio) // frame_len
               if n_frames >= 2:
                   frames = audio[: n_frames * frame_len].reshape(n_frames, frame_len)
                   rms = np.sqrt(np.mean(frames ** 2, axis=1))
                   n_noise = max(1, n_frames // 10)
                   noise_profile = frames[np.argsort(rms)[:n_noise]].flatten()
                   audio = nr.reduce_noise(
                       y=audio, y_noise=noise_profile, sr=sr,
                       stationary=False, prop_decrease=0.60,  # light — preserve voice character
                       n_fft=1024, hop_length=256,
                   ).astype(np.float32)
           except Exception:
               pass


           # 3. Normalise to -1 dBFS so XTTS has consistent input level
           peak = np.max(np.abs(audio))
           if peak > 1e-6:
               audio = audio / peak * 0.89


           sf.write(str(cached), audio, sr, subtype='PCM_16')
           self.logger.debug(f"Preprocessed speaker WAV cached: {cached}")
           return str(cached)


       except Exception as e:
           self.logger.warning(f"Speaker WAV preprocessing failed: {e}, using original")
           return wav_path


   def _get_voice_sample_path(self, voice_id: str) -> str:


       # Get path to voice sample file
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


       # Preprocess the speaker reference for cleaner cloning
       return self._preprocess_speaker_wav(str(sample_path))


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


           # Generate audio (generate_chapter is the simple single-voice path;
           # the multi-speaker path in processor.py passes emotion per segment)
           audio_path = await self.generate_speech(
               text=chunk,
               voice=voice,
               speed=speed,
               output_path=output_path,
               emotion="neutral",
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
                   "mood": voice_config.get("mood", "Natural"),
                   "type": voice_config.get("type", "Neural"),
                   "featured": voice_config.get("featured", False),
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



