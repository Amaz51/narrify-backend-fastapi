"""
Main Processing Pipeline - FIXED VERSION
Orchestrates all NLP and TTS services to create multi-speaker emotion-aware audiobooks

FIXES:
- Uses cached PDF data instead of looking for files on disk
- Compatible with existing upload flow
"""

from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
import time

from app.services.pdf_service import pdf_service
from app.services.text_service import text_service
from app.services.nlp.dialogue_service import dialogue_service
from app.services.nlp.speaker_service import speaker_service
from app.services.nlp.emotion_engine import emotion_service
from app.services.tts_service import tts_service
from app.services.audio_service import audio_service
from app.models.schemas import Chapter


class AudiobookProcessor:
    """
    Main Pipeline Orchestrator
    
    Implements complete workflow from PDF Section 2:
    1. PDF Text Extraction (from cache)
    2. Sentence Segmentation (spaCy)
    3. Dialogue Detection (Rule-based)
    4. Speaker Identification
    5. Emotion Analysis (GoEmotions)
    6. Speaker + Emotion Tagged Segments (JSON)
    7. TTS Generation (XTTS v2)
    8. Audio Stitching
    """
    
    def __init__(self):
        self.logger = logger.bind(name=__name__)
    
    async def process_pdf_to_segments(
        self, 
        pdf_path: Path,
        detect_emotions: bool = True
    ) -> Dict:
        """
        Process PDF into speaker-tagged, emotion-labeled segments
        
        This creates the MANDATORY intermediate representation from PDF Section 3.7
        
        Args:
            pdf_path: Path to PDF file
            detect_emotions: Whether to detect emotions
            
        Returns:
            Dict with file_id, chapters, and segments
        """
        start_time = time.time()
        self.logger.info(f"Processing PDF: {pdf_path}")
        
        # Reset speaker registry for new book
        speaker_service.reset_registry()
        
        # Step 1: Extract text from PDF
        self.logger.info("Step 1/6: Extracting text from PDF...")
        pdf_doc = await pdf_service.process_pdf(pdf_path)
        
        # Step 2: Detect chapters
        self.logger.info("Step 2/6: Detecting chapters...")
        chapters = pdf_service.detect_chapters(pdf_doc.text_content)
        
        # Step 3-6: Process each chapter
        all_segments = []
        chapter_segments = []
        
        for chapter in chapters:
            self.logger.info(f"Processing Chapter {chapter.id}: {chapter.title}")
            
            segments = await self._process_chapter_text(
                chapter.content,
                detect_emotions=detect_emotions
            )
            
            chapter_segments.append({
                "chapter_id": chapter.id,
                "chapter_title": chapter.title,
                "segments": segments,
                "segment_count": len(segments)
            })
            
            all_segments.extend(segments)
        
        processing_time = time.time() - start_time
        
        result = {
            "file_id": pdf_doc.file_id,
            "filename": pdf_doc.filename,
            "total_chapters": len(chapters),
            "total_segments": len(all_segments),
            "chapters": chapter_segments,
            "speakers_detected": list(speaker_service.get_all_speakers().keys()),
            "processing_time": round(processing_time, 2)
        }
        
        self.logger.info(
            f"✅ PDF processed: {len(chapters)} chapters, "
            f"{len(all_segments)} segments in {processing_time:.1f}s"
        )
        
        return result
    
    async def process_pdf_from_cache(
        self,
        pdf_doc,
        chapters: List,
        detect_emotions: bool = True
    ) -> Dict:
        """
        НОВЫЙ МЕТОД: Process PDF from cached data (no file path needed)
        
        This is used by routes.py when PDF is already in cache
        
        Args:
            pdf_doc: Cached PDFDocument object
            chapters: List of Chapter objects
            detect_emotions: Whether to detect emotions
            
        Returns:
            Dict with file_id, chapters, and segments
        """
        start_time = time.time()
        self.logger.info(f"Processing cached PDF: {pdf_doc.filename}")
        
        # Reset speaker registry for new book
        speaker_service.reset_registry()
        
        # Process each chapter
        all_segments = []
        chapter_segments = []
        
        for chapter in chapters:
            self.logger.info(f"Processing Chapter {chapter.id}: {chapter.title}")
            
            segments = await self._process_chapter_text(
                chapter.content,
                detect_emotions=detect_emotions
            )
            
            chapter_segments.append({
                "chapter_id": chapter.id,
                "chapter_title": chapter.title,
                "segments": segments,
                "segment_count": len(segments)
            })
            
            all_segments.extend(segments)
        
        processing_time = time.time() - start_time
        
        result = {
            "file_id": pdf_doc.file_id,
            "filename": pdf_doc.filename,
            "total_chapters": len(chapters),
            "total_segments": len(all_segments),
            "chapters": chapter_segments,
            "speakers_detected": list(speaker_service.get_all_speakers().keys()),
            "processing_time": round(processing_time, 2)
        }
        
        self.logger.info(
            f"✅ PDF processed: {len(chapters)} chapters, "
            f"{len(all_segments)} segments in {processing_time:.1f}s"
        )
        
        return result
    
    async def _process_chapter_text(
        self,
        chapter_text: str,
        detect_emotions: bool = True
    ) -> List[Dict]:
        """
        Process chapter text into tagged segments
    
        Implements PDF requirements:
        - Sentence segmentation (spaCy)
        - Dialogue detection (quotation marks)
        - Speaker identification (reporting verbs)
        - Emotion detection (GoEmotions)
    
        Returns:
        List of segment dicts with mandatory format
        """
        # Step 3: Normalize text
        self.logger.debug("Step 3/6: Normalizing text...")
        normalized_text = text_service.normalize(chapter_text)

        # Step 4: Segment into sentences
        self.logger.debug("Step 4/6: Segmenting sentences...")
        sentences = self._segment_sentences(normalized_text)
    
        # Step 5-6: Process each sentence (dialogue + speaker detection first)
        segments = []
        previous_speaker = None

        for sentence in sentences:
            if not sentence.strip():
                continue

            # Dialogue detection & speaker identification
            processed = dialogue_service.process_sentence(sentence, previous_speaker)

            text = processed['text'].strip()
            if not text or len(text) < 3:
                self.logger.debug(f"⚠️ Skipping short/empty segment: '{text}'")
                continue

            # Gender inference
            gender = speaker_service.infer_gender(processed['speaker'])

            segments.append({
                "speaker": processed['speaker'],
                "gender": gender,
                "text": text,
                "emotion": "neutral",          # placeholder — batch filled below
                "segment_type": processed['segment_type']
            })

            if processed['segment_type'] == 'dialogue':
                previous_speaker = processed['speaker']

        # Batch emotion detection — single BERT call for all segments
        if detect_emotions and segments:
            texts = [seg['text'] for seg in segments]
            emotions = emotion_service.batch_detect_emotions(texts)
            for seg, emo in zip(segments, emotions):
                seg['emotion'] = emo

        self.logger.debug(f"Created {len(segments)} segments (filtered empty)")
        return segments

    # async def _process_chapter_text(
    #     self,
    #     chapter_text: str,
    #     detect_emotions: bool = True
    # ) -> List[Dict]:
    #     """
    #     Process chapter text into tagged segments
        
    #     Implements PDF requirements:
    #     - Sentence segmentation (spaCy)
    #     - Dialogue detection (quotation marks)
    #     - Speaker identification (reporting verbs)
    #     - Emotion detection (GoEmotions)
        
    #     Returns:
    #         List of segment dicts with mandatory format
    #     """
    #     # Step 3: Normalize text
    #     self.logger.debug("Step 3/6: Normalizing text...")
    #     normalized_text = text_service.normalize(chapter_text)
        
    #     # Step 4: Segment into sentences
    #     self.logger.debug("Step 4/6: Segmenting sentences...")
    #     sentences = self._segment_sentences(normalized_text)
        
    #     # Step 5-6: Process each sentence
    #     segments = []
    #     previous_speaker = None
        
    #     for sentence in sentences:
    #         if not sentence.strip():
    #             continue
            
    #         # Dialogue detection & speaker identification
    #         processed = dialogue_service.process_sentence(sentence, previous_speaker)
            
    #         # Gender inference
    #         gender = speaker_service.infer_gender(processed['speaker'])
            
    #         # Emotion detection
    #         if detect_emotions:
    #             emotion = emotion_service.detect_emotion(processed['text'])
    #         else:
    #             emotion = "neutral"
            
    #         # Create segment in MANDATORY format (PDF Section 3.7)
    #         segment = {
    #             "speaker": processed['speaker'],
    #             "gender": gender,
    #             "text": processed['text'],
    #             "emotion": emotion,
    #             "segment_type": processed['segment_type']
    #         }
            
    #         segments.append(segment)
            
    #         # Update previous speaker for context
    #         if processed['segment_type'] == 'dialogue':
    #             previous_speaker = processed['speaker']
        
    #     self.logger.debug(f"Created {len(segments)} segments")
    #     return segments
    
    def _segment_sentences(self, text: str) -> List[str]:
        """
        Simple sentence segmentation
        
        TODO: Replace with spaCy for better accuracy
        """
        
        import re
        
        # Split on sentence endings
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Clean and filter
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    async def generate_audiobook(
        self,
        segments: List[Dict],
        voice_assignments: Optional[Dict[str, str]] = None,
        speed: float = 1.0,
        output_path: Optional[Path] = None,
        emotion_intensity: float = 1.5  # ← Sweet spot
    ) -> Path:
        """Generate with NATURAL emotion prosody"""
        
        start_time = time.time()
        self.logger.info(f"🎭 Generating with emotion intensity: {emotion_intensity}x")
        
        # Clamp base speed
        speed = max(0.9, min(1.1, speed))
        
        if voice_assignments is None:
            voice_assignments = self._create_default_voice_assignments(segments)
        
        audio_files = []
        
        for i, segment in enumerate(segments, 1):
            voice_id = voice_assignments.get(
                segment['speaker'],
                self._get_default_voice_for_gender(segment['gender'])
            )
            
            # ========== CRITICAL: Enable emotion prosody ==========
            emotion = segment.get('emotion', 'neutral')
            
            # Get prosody with intensity
            prosody = emotion_service.get_prosody_settings(
                emotion, 
                intensity=emotion_intensity
            )
            
            # Apply emotion to speed (WIDER RANGE for more expressiveness)
            adjusted_speed = speed * prosody['speed']
            adjusted_speed = max(0.75, min(1.35, adjusted_speed))  # ±35% swing

            # Add natural pause markers that XTTS interprets prosodically
            text = segment['text']
            if emotion in ['tender', 'romantic', 'longing', 'sad']:
                text = text.replace('. ', '... ')
                text = text.replace(', ', ', ')
            elif emotion in ['passionate', 'excited', 'breathless']:
                text = text.replace('...', '.')

            self.logger.info(
                f"Segment {i}/{len(segments)}: {segment['speaker']} "
                f"[{emotion}] speed={adjusted_speed:.2f}"
            )

            try:
                audio_path = await tts_service.generate_speech(
                    text=text,
                    voice=voice_id,
                    speed=adjusted_speed,
                    language="en",
                    emotion=emotion,        # emotion-aware temperature
                )
                audio_files.append(audio_path)
            except Exception as e:
                self.logger.warning(f"Skipping segment {i}: {e}")
                continue
        
        if not audio_files:
            raise Exception("No audio generated")

        # Collect speaker labels for the segments that actually produced audio
        generated_speakers = []
        file_idx = 0
        for segment in segments:
            if file_idx >= len(audio_files):
                break
            generated_speakers.append(segment['speaker'])
            file_idx += 1

        final_audio = await audio_service.merge_audio_files(
            audio_files,
            output_path=output_path,
            speaker_sequence=generated_speakers,
        )
        
        generation_time = time.time() - start_time
        self.logger.info(
            f"✅ Generated: {len(audio_files)}/{len(segments)} segments "
            f"in {generation_time:.1f}s"
        )
        
        return final_audio
    
    def _create_default_voice_assignments(
        self,
        segments: List[Dict]
    ) -> Dict[str, str]:
        """
        Create default voice assignments based on speaker gender
        """
        assignments = {}
        
        # Get unique speakers
        speakers = {seg['speaker']: seg['gender'] for seg in segments}
        
        for speaker, gender in speakers.items():
            assignments[speaker] = self._get_default_voice_for_gender(gender)
        
        return assignments
    
    def _get_default_voice_for_gender(self, gender: str) -> str:
        """
        Get default voice ID based on gender
        """
        from app.config import settings
        
        # Map gender to available voices
        for voice in settings.DEMO_VOICES:
            if voice['gender'] == gender:
                return voice['id']
        
        # Fallback to first voice
        return settings.DEMO_VOICES[0]['id'] if settings.DEMO_VOICES else "voice7"


# Global instance
audiobook_processor = AudiobookProcessor()

__all__ = ["AudiobookProcessor", "audiobook_processor"]