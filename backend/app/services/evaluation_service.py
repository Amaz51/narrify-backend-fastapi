"""
Voice Evaluation Service
Computes objective quality metrics on generated audio:
  - WER  (Word Error Rate)       via openai-whisper + jiwer
  - UTMOS (Naturalness/MOS)      via utmos22, falls back to energy proxy
  - SECS  (Speaker Similarity)   via resemblyzer
  - SER   (Emotion Accuracy)     via transformers wav2vec2 pipeline
  - SNR   (Audio Quality)        via soundfile + numpy
"""

import os
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from loguru import logger


class EvaluationService:
    def __init__(self):
        self._whisper_model = None
        self._ser_pipeline = None
        self._voice_encoder = None

    # ── Lazy model loaders ────────────────────────────────────────────────────

    def _load_whisper(self):
        if self._whisper_model is None:
            try:
                import whisper
                self._whisper_model = whisper.load_model("base")
                logger.info("Whisper model loaded (base)")
            except ImportError:
                logger.warning("openai-whisper not installed — WER will be unavailable")
            except Exception as e:
                logger.error(f"Whisper load failed: {e}")
        return self._whisper_model

    def _load_ser(self):
        if self._ser_pipeline is None:
            try:
                from transformers import pipeline
                self._ser_pipeline = pipeline(
                    "audio-classification",
                    model="ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
                )
                logger.info("SER pipeline loaded")
            except Exception as e:
                logger.warning(f"SER pipeline failed to load: {e}")
        return self._ser_pipeline

    def _load_voice_encoder(self):
        if self._voice_encoder is None:
            try:
                from resemblyzer import VoiceEncoder
                self._voice_encoder = VoiceEncoder()
                logger.info("Voice encoder (resemblyzer) loaded")
            except ImportError:
                logger.warning("resemblyzer not installed — SECS will be unavailable")
            except Exception as e:
                logger.error(f"Voice encoder load failed: {e}")
        return self._voice_encoder

    # ── Individual metrics ────────────────────────────────────────────────────

    def compute_wer(self, audio_path: str, original_text: str) -> dict:
        """Word Error Rate and Character Error Rate using Whisper + jiwer."""
        try:
            model = self._load_whisper()
            if model is None:
                return {"wer": None, "cer": None, "error": "openai-whisper not installed"}

            result = model.transcribe(audio_path)
            transcribed = result["text"].strip()

            try:
                import jiwer
                wer = jiwer.wer(original_text, transcribed)
                cer = jiwer.cer(original_text, transcribed)
            except ImportError:
                # Rough WER without jiwer: compare word sets
                ref_words = original_text.lower().split()
                hyp_words = transcribed.lower().split()
                errors = sum(1 for r, h in zip(ref_words, hyp_words) if r != h)
                errors += abs(len(ref_words) - len(hyp_words))
                wer = errors / max(len(ref_words), 1)
                cer = None

            return {
                "wer": round(float(wer), 4),
                "cer": round(float(cer), 4) if cer is not None else None,
                "transcribed_text": transcribed[:500],   # cap length
            }
        except Exception as e:
            logger.error(f"WER computation failed: {e}")
            return {"wer": None, "cer": None, "error": str(e)}

    def compute_snr(self, audio_path: str) -> dict:
        """Signal-to-Noise Ratio estimate (dB). Higher is better (> 20 dB is good)."""
        try:
            data, sr = sf.read(audio_path)
            if data.ndim > 1:
                data = data.mean(axis=1)

            rms_total = np.sqrt(np.mean(data ** 2))
            if rms_total < 1e-10:
                return {"snr_db": 0.0}

            # Estimate noise as the quietest 10% of frames
            frame_size = max(1, sr // 100)   # 10 ms frames
            frames = [data[i: i + frame_size] for i in range(0, len(data) - frame_size, frame_size)]
            frame_rms = [np.sqrt(np.mean(f ** 2)) for f in frames if len(f) == frame_size]
            frame_rms.sort()
            noise_rms = np.mean(frame_rms[: max(1, len(frame_rms) // 10)])

            if noise_rms < 1e-10:
                snr_db = 60.0
            else:
                snr_db = 20 * np.log10(rms_total / noise_rms)

            return {"snr_db": round(float(snr_db), 2)}
        except Exception as e:
            logger.error(f"SNR computation failed: {e}")
            return {"snr_db": None, "error": str(e)}

    def compute_utmos(self, audio_path: str) -> dict:
        """
        Predicted MOS score (1–5 scale, higher is better).
        Uses utmos22 package if installed; falls back to a clipping-based energy proxy.
        """
        try:
            import torch
            import torchaudio

            try:
                import utmos
                predictor = utmos.Score(device="cpu")
                wav, sr = torchaudio.load(audio_path)
                score = predictor.calculate_one_sample(wav, sr)
                return {"utmos": round(float(score), 4), "method": "utmos22"}
            except ImportError:
                pass   # fall through to proxy

            # Proxy: penalise clipping and very low energy
            data, sr = sf.read(audio_path)
            if data.ndim > 1:
                data = data.mean(axis=1)

            clip_ratio = float(np.mean(np.abs(data) > 0.97))
            rms = float(np.sqrt(np.mean(data ** 2)))
            silence_ratio = float(np.mean(np.abs(data) < 0.001))

            proxy = 4.5 - clip_ratio * 10 - silence_ratio * 2
            proxy = float(np.clip(proxy, 1.0, 5.0))

            return {
                "utmos": round(proxy, 2),
                "method": "energy_proxy",
                "note": "Install utmos22 for accurate MOS prediction",
            }
        except Exception as e:
            logger.error(f"UTMOS computation failed: {e}")
            return {"utmos": None, "error": str(e)}

    def compute_ser(self, audio_path: str, intended_emotion: Optional[str] = None) -> dict:
        """Speech Emotion Recognition using wav2vec2 classifier."""
        try:
            pipe = self._load_ser()
            if pipe is None:
                return {"detected_emotion": None, "error": "SER model not available"}

            results = pipe(audio_path)
            top = results[0]
            detected = top["label"].lower()
            confidence = round(float(top["score"]), 4)

            emotion_match = None
            if intended_emotion:
                emotion_match = detected == intended_emotion.lower().strip()

            return {
                "detected_emotion": detected,
                "confidence": confidence,
                "emotion_match": emotion_match,
                "all_emotions": {r["label"].lower(): round(float(r["score"]), 4) for r in results},
            }
        except Exception as e:
            logger.error(f"SER computation failed: {e}")
            return {"detected_emotion": None, "error": str(e)}

    def compute_secs(self, generated_path: str, reference_path: str) -> dict:
        """Speaker Encoder Cosine Similarity (−1 to 1, higher = more similar speaker)."""
        try:
            encoder = self._load_voice_encoder()
            if encoder is None:
                return {"secs": None, "error": "resemblyzer not installed"}

            from resemblyzer import preprocess_wav

            wav_gen = preprocess_wav(generated_path)
            wav_ref = preprocess_wav(reference_path)
            embed_gen = encoder.embed_utterance(wav_gen)
            embed_ref = encoder.embed_utterance(wav_ref)
            similarity = float(np.dot(embed_gen, embed_ref))

            return {"secs": round(similarity, 4)}
        except Exception as e:
            logger.error(f"SECS computation failed: {e}")
            return {"secs": None, "error": str(e)}

    # ── Composite score ───────────────────────────────────────────────────────

    def _overall_score(self, metrics: dict) -> Optional[float]:
        """
        Weighted composite 0–100. Weights:
          WER 30 % | UTMOS 25 % | SECS 25 % | Emotion match 10 % | SNR 10 %
        """
        score = 0.0
        weight_total = 0.0

        wer = (metrics.get("intelligibility") or {}).get("wer")
        if wer is not None:
            score += (1 - min(float(wer), 1.0)) * 100 * 0.30
            weight_total += 0.30

        utmos = (metrics.get("naturalness") or {}).get("utmos")
        if utmos is not None:
            score += ((float(utmos) - 1) / 4) * 100 * 0.25
            weight_total += 0.25

        secs = (metrics.get("speaker_similarity") or {}).get("secs")
        if secs is not None:
            score += ((float(secs) + 1) / 2) * 100 * 0.25
            weight_total += 0.25

        match = (metrics.get("emotion") or {}).get("emotion_match")
        if match is not None:
            score += (100.0 if match else 0.0) * 0.10
            weight_total += 0.10

        snr = (metrics.get("audio_quality") or {}).get("snr_db")
        if snr is not None:
            score += min(float(snr) / 40.0, 1.0) * 100 * 0.10
            weight_total += 0.10

        if weight_total == 0:
            return None
        return round(score / weight_total, 1)

    # ── Main entry point ──────────────────────────────────────────────────────

    def evaluate(
        self,
        audio_path: str,
        original_text: Optional[str] = None,
        reference_audio_path: Optional[str] = None,
        intended_emotion: Optional[str] = None,
    ) -> dict:
        """Run all metrics and return a unified result dict."""
        logger.info(f"Running evaluation on: {audio_path}")
        metrics: dict = {}

        # Intelligibility
        if original_text and original_text.strip():
            metrics["intelligibility"] = self.compute_wer(audio_path, original_text)
        else:
            metrics["intelligibility"] = {"wer": None, "cer": None, "note": "No reference text provided"}

        # Naturalness
        metrics["naturalness"] = self.compute_utmos(audio_path)

        # Audio quality
        metrics["audio_quality"] = self.compute_snr(audio_path)

        # Emotion
        metrics["emotion"] = self.compute_ser(audio_path, intended_emotion)

        # Speaker similarity (only when reference is available)
        if reference_audio_path:
            metrics["speaker_similarity"] = self.compute_secs(audio_path, reference_audio_path)
        else:
            metrics["speaker_similarity"] = {"secs": None, "note": "No reference audio provided"}

        metrics["overall_score"] = self._overall_score(metrics)
        logger.info(f"Evaluation complete. Overall score: {metrics['overall_score']}")
        return metrics


# Singleton
evaluation_service = EvaluationService()
