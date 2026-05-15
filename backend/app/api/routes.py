"""
API Routes - Enhanced with Multi-Speaker Emotion-Aware Features
Backward compatible with Phase 1 (all original endpoints preserved)
"""

import asyncio
import json
import threading
import uuid as _uuid
from pathlib import Path
from typing import Dict, List, Optional
import torch
import time

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
    Query,
)
from fastapi.responses import FileResponse, StreamingResponse
from loguru import logger
from app.limiter import limiter

from app.config import settings
from app.models.schemas import (
    # Phase 1 Schemas (Original)
    AudioGenerationRequest,
    AudioGenerationResponse,
    ChapterInfo,
    ChaptersResponse,
    ErrorResponse,
    FileUploadResponse,
    HealthResponse,
    VoiceInfo,
    VoicesResponse,
    # Phase 2 Schemas (NEW)
    ProcessingRequestV2,
    ProcessingResponseV2,
    MultiSpeakerGenerationRequest,
    MultiSpeakerGenerationResponse,
    SpeakerSegment,
    EmotionStatistics,
    SpeakerStatistics,
    # Evaluation
    EvaluationResponse,
)

# Phase 1 Services (Original)
from app.services.audio_service import audio_service
from app.services.pdf_service import pdf_service
from app.services.tts_service import tts_service
from app.services.evaluation_service import evaluation_service

# Phase 2 Services (NEW)
try:
    from app.services.processor import audiobook_processor
    from app.services.nlp.dialogue_service import dialogue_service
    from app.services.nlp.speaker_service import speaker_service
    from app.services.nlp.emotion_engine import emotion_service
    PHASE_2_ENABLED = True
except ImportError:
    logger.warning("Phase 2 services not available - multi-speaker features disabled")
    PHASE_2_ENABLED = False

# Create router
router = APIRouter()

# Cache for processed PDFs (file_id -> PDFDocument)
pdf_cache = {}

# Cache for chapters (file_id -> List[Chapter])
chapter_cache = {}

# Cache for processed segments (file_id -> processed data)
segment_cache = {}

# ── Async task store ────────────────────────────────────────────────────────
# Redis-backed so task state survives FastAPI --reload restarts.
# Falls back to in-memory dict when Redis is unavailable.

class _TaskProxy(dict):
    """dict subclass that writes every __setitem__ back to the parent store."""
    def __init__(self, store: "_RedisTaskStore", task_id: str, data: dict):
        super().__init__(data)
        object.__setattr__(self, '_store', store)
        object.__setattr__(self, '_task_id', task_id)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        try:
            object.__getattribute__(self, '_store')._write(
                object.__getattribute__(self, '_task_id'), dict(self)
            )
        except Exception:
            pass


class _RedisTaskStore:
    _TTL = 86400  # 24 h

    def __init__(self):
        self._local: Dict[str, dict] = {}
        self._redis = None
        try:
            import redis as _redis_lib
            self._redis = _redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
            self._redis.ping()
            logger.info("RedisTaskStore: connected to Redis")
        except Exception as exc:
            logger.warning(f"RedisTaskStore: Redis unavailable, using in-memory fallback ({exc})")

    def _key(self, task_id: str) -> str:
        return f"narrify:task:{task_id}"

    def _write(self, task_id: str, data: dict) -> None:
        self._local[task_id] = data
        if self._redis:
            try:
                self._redis.setex(self._key(task_id), self._TTL, json.dumps(data))
            except Exception:
                pass

    def _read_raw(self, task_id: str):
        if task_id in self._local:
            return self._local[task_id]
        if self._redis:
            try:
                raw = self._redis.get(self._key(task_id))
                if raw:
                    data = json.loads(raw)
                    self._local[task_id] = data
                    return data
            except Exception:
                pass
        return None

    def __setitem__(self, task_id: str, value: dict) -> None:
        self._write(task_id, value)

    def __getitem__(self, task_id: str) -> _TaskProxy:
        data = self._read_raw(task_id)
        if data is None:
            raise KeyError(task_id)
        return _TaskProxy(self, task_id, data)

    def get(self, task_id: str, default=None):
        data = self._read_raw(task_id)
        if data is None:
            return default
        return _TaskProxy(self, task_id, data)


task_store = _RedisTaskStore()


# ==================== PHASE 1 ENDPOINTS (ORIGINAL) ====================

# HEALTH CHECK

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check API health and model status",
)
async def health_check():
    """Health status check"""
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        model_loaded=tts_service.is_model_loaded(),
        device=settings.get_device(),
    )


# PDF UPLOAD & PROCESSING

@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload PDF",
    description="Upload PDF file for processing",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file"},
        413: {"model": ErrorResponse, "description": "File too large"},
    },
)
@limiter.limit("20/minute")
async def upload_pdf(request: Request, file: UploadFile = File(..., description="PDF file to upload")):
    """
    Upload and process PDF file
    Returns: Upload confirmation with file ID and metadata
    """
    try:
        logger.info(f"Received upload: {file.filename}")

        if not file.filename.endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed",
            )

        # Read file content
        content = await file.read()

        # Check file size
        if len(content) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {settings.format_file_size(settings.MAX_UPLOAD_SIZE)}",
            )

        # Save file
        file_path = await pdf_service.save_upload(content, file.filename)

        # Validate PDF
        is_valid, error_msg = pdf_service.validate_pdf(file_path)
        if not is_valid:
            file_path.unlink()  # Delete invalid file
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg
            )

        # Process PDF
        pdf_doc = await pdf_service.process_pdf(file_path)

        # Detect chapters
        chapters = pdf_service.detect_chapters(pdf_doc.text_content)

        # Clear stale cache entries before storing new ones (ensures re-uploads always get fresh data)
        pdf_cache.clear()
        chapter_cache.clear()
        segment_cache.clear()

        # Cache results
        pdf_cache[pdf_doc.file_id] = pdf_doc
        chapter_cache[pdf_doc.file_id] = chapters

        logger.info(
            f"PDF processed: {pdf_doc.file_id} ({len(chapters)} chapters)"
        )

        return FileUploadResponse(
            file_id=pdf_doc.file_id,
            filename=pdf_doc.filename,
            file_size=file_path.stat().st_size,
            pages=pdf_doc.pages,
            chapters=len(chapters),
            metadata=pdf_doc.metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload processing failed: {str(e)}",
        )


# CHAPTER RETRIEVAL

@router.get(
    "/chapters/{file_id}",
    response_model=ChaptersResponse,
    summary="Get Chapters",
    description="Get all chapters from uploaded PDF",
    responses={404: {"model": ErrorResponse, "description": "File not found"}},
)
async def get_chapters(file_id: str):
    """Get chapters for uploaded file"""
    try:
        # Check cache
        if file_id not in chapter_cache:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {file_id}",
            )

        chapters = chapter_cache[file_id]

        # Convert to response format
        chapter_infos = []
        for chapter in chapters:
            estimated_duration = pdf_service.estimate_duration(chapter.word_count)

            chapter_infos.append(
                ChapterInfo(
                    id=chapter.id,
                    title=chapter.title,
                    content=chapter.content[:500] + "..."
                    if len(chapter.content) > 500
                    else chapter.content,  # Truncate for response
                    word_count=chapter.word_count,
                    estimated_duration=estimated_duration,
                    start_page=chapter.start_page,
                )
            )

        total_words = sum(ch.word_count for ch in chapters)

        return ChaptersResponse(
            file_id=file_id,
            chapters=chapter_infos,
            total_chapters=len(chapters),
            total_words=total_words,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get chapters: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve chapters: {str(e)}",
        )


# VOICE MANAGEMENT

@router.get(
    "/voices",
    summary="Get Voices",
    description="Get list of available voices",
)
async def get_voices():
    """Returns list of all voice options including custom clones"""
    try:
        voices_data = tts_service.get_available_voices()

        # Build voice list from demo voices
        result = []
        for v in voices_data:
            result.append({
                "voice_id": v["id"],
                "voice_name": v["name"],
                "id": v["id"],
                "name": v["name"],
                "language": v["language"],
                "gender": v["gender"],
                "type": v.get("type", "Neural"),
                "mood": v.get("mood", "Natural"),
                "featured": v.get("featured", False),
                "description": v.get("description", ""),
                "sample_url": f"/api/voices/{v['id']}/sample",
                "is_custom": False,
            })

        # Append custom cloned voices
        try:
            import torch as _torch
            embeddings_dir = settings.EMBEDDINGS_DIR
            if embeddings_dir.exists():
                for pt_file in sorted(embeddings_dir.glob("custom_*.pt")):
                    voice_id = pt_file.stem
                    voice_name = f"Custom Voice ({voice_id[:8]})"
                    gender = "neutral"
                    try:
                        meta = _torch.load(str(pt_file), map_location="cpu", weights_only=False)
                        if isinstance(meta, dict) and "voice_name" in meta:
                            voice_name = meta["voice_name"]
                            gender = meta.get("gender", "neutral")
                    except Exception:
                        pass
                    result.append({
                        "voice_id": voice_id,
                        "voice_name": voice_name,
                        "id": voice_id,
                        "name": voice_name,
                        "language": "en",
                        "gender": gender,
                        "type": "Cloned",
                        "mood": "Custom Clone",
                        "featured": False,
                        "description": "Your custom cloned voice",
                        "sample_url": f"/api/voices/{voice_id}/sample",
                        "is_custom": True,
                    })
        except Exception as e:
            logger.warning(f"Could not load custom voices: {e}")

        return {"voices": result, "total": len(result), "total_voices": len(result)}

    except Exception as e:
        logger.error(f"Failed to get voices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve voices: {str(e)}",
        )


@router.get(
    "/voices/{voice_id}/sample",
    summary="Get Voice Sample",
    description="Get audio sample for a voice",
    responses={404: {"description": "Voice sample not found"}},
)
async def get_voice_sample(voice_id: str):
    """Get voice sample audio — works for both default voices and custom clones"""
    try:
        # 1. Check demo / default voices first
        voice_config = next(
            (v for v in settings.DEMO_VOICES if v["id"] == voice_id), None
        )
        if voice_config:
            sample_path = settings.VOICE_DIR / voice_config["sample_file"]
            if sample_path.exists():
                ext = sample_path.suffix.lower()
                media_type = "audio/mpeg" if ext == ".mp3" else "audio/wav"
                return FileResponse(
                    path=sample_path,
                    media_type=media_type,
                    filename=f"{voice_id}_sample{ext}",
                )

        # 2. Check custom cloned voices (embeddings dir has custom_<id>.wav)
        cloned_wav = settings.EMBEDDINGS_DIR / f"{voice_id}.wav"
        if cloned_wav.exists():
            return FileResponse(
                path=cloned_wav,
                media_type="audio/wav",
                filename=f"{voice_id}_sample.wav",
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sample found for voice: {voice_id}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get voice sample: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve sample: {str(e)}",
        )


# AUDIO GENERATION (ORIGINAL - SINGLE SPEAKER)

@router.post(
    "/generate",
    response_model=AudioGenerationResponse,
    summary="Generate Audio (Single Speaker)",
    description="Generate audiobook for a chapter with single voice [PHASE 1]",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid parameters"},
        404: {"model": ErrorResponse, "description": "File or chapter not found"},
    },
)
async def generate_audio(request: AudioGenerationRequest):
    """
    Generate audiobook audio for a chapter (ORIGINAL ENDPOINT)
    Returns: Generated audio information
    """
    try:
        logger.info(
            f"Generating audio: {request.file_id}, ch{request.chapter}, voice:{request.voice}"
        )

        start_time = time.time()

        # Validate file exists
        if request.file_id not in chapter_cache:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.file_id}",
            )

        chapters = chapter_cache[request.file_id]

        # Get specific chapter
        chapter = pdf_service.get_chapter_by_id(chapters, request.chapter)
        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chapter not found: {request.chapter}",
            )

        # Validate parameters
        is_valid, error_msg = tts_service.validate_parameters(
            request.speed, request.pitch, request.tone
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg
            )

        normalized_text = chapter.content

        # Generate speech (with chunking for long chapters)
        if chapter.word_count > settings.TTS_CHUNK_SIZE:
            # Generate in chunks and merge
            audio_chunks = await tts_service.generate_chapter(
                normalized_text,
                voice=request.voice,
                speed=request.speed,
                chunk_size=settings.TTS_CHUNK_SIZE,
            )

            # Merge chunks
            tts_output = await audio_service.merge_audio_files(audio_chunks)

            # Cleanup chunk files
            for chunk in audio_chunks:
                if chunk.exists():
                    chunk.unlink()
        else:
            # Generate single audio
            tts_output = await tts_service.generate_speech(
                text=normalized_text,
                voice=request.voice,
                speed=request.speed,
            )

        # Apply post-processing
        final_output = await audio_service.process_audio(
            input_path=tts_output,
            pitch=request.pitch,
            speed=1.0,  # Speed already applied in TTS
            tone=request.tone,
            output_format=request.format,
            normalize=settings.NORMALIZE_AUDIO,
            trim_silence=settings.TRIM_SILENCE,
        )

        # Delete intermediate file
        if tts_output.exists() and tts_output != final_output:
            tts_output.unlink()

        # Get audio info
        audio_info = audio_service.get_audio_info(final_output)

        generation_time = time.time() - start_time

        logger.info(
            f"Audio generated in {generation_time:.2f}s: {final_output.name}"
        )

        # Generate download URL
        audio_url = f"/api/outputs/{final_output.name}"

        return AudioGenerationResponse(
            audio_url=audio_url,
            file_id=request.file_id,
            chapter=request.chapter,
            duration=audio_info.get("duration", 0),
            file_size=audio_info.get("file_size", 0),
            format=request.format,
            generation_time=round(generation_time, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio generation failed: {str(e)}",
        )


# AUDIO DOWNLOAD

@router.get(
    "/outputs/{filename}",
    summary="Download Audio",
    description="Download generated audio file",
    responses={404: {"description": "File not found"}},
)
async def download_audio(filename: str):
    """Download generated audio file"""
    try:
        file_path = settings.OUTPUT_DIR / filename

        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audio file not found",
            )

        # Determine media type
        media_type = "audio/wav" if filename.endswith(".wav") else "audio/mpeg"

        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {str(e)}",
        )


# SYSTEM MANAGEMENT

@router.post(
    "/cleanup",
    summary="Cleanup Files",
    description="Clean up old temporary files",
    responses={200: {"description": "Cleanup completed"}},
)
async def cleanup_files():
    """Clean up old files"""
    try:
        # Cleanup in parallel
        pdf_count, audio_count, temp_count = await asyncio.gather(
            asyncio.to_thread(pdf_service.cleanup_old_files, days=7),
            asyncio.to_thread(tts_service.cleanup_old_outputs, hours=24),
            asyncio.to_thread(audio_service.cleanup_temp_files),
        )

        return {
            "status": "success",
            "files_deleted": {
                "pdfs": pdf_count,
                "audio": audio_count,
                "temp": temp_count,
                "total": pdf_count + audio_count + temp_count,
            },
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cleanup failed: {str(e)}",
        )


# STATISTICS

@router.get(
    "/stats",
    summary="Get Statistics",
    description="Get system usage statistics",
)
async def get_statistics():
    """Get system statistics"""
    try:
        # Count files
        upload_count = len(list(settings.UPLOAD_DIR.glob("*.pdf")))
        output_count = len(list(settings.OUTPUT_DIR.glob("*.wav"))) + len(
            list(settings.OUTPUT_DIR.glob("*.mp3"))
        )

        # Calculate total output size
        total_size = sum(
            f.stat().st_size
            for f in settings.OUTPUT_DIR.glob("*")
            if f.is_file()
        )

        stats = {
            "uploads": {
                "total": upload_count,
                "cached": len(pdf_cache),
            },
            "audio": {
                "total": output_count,
                "total_size": settings.format_file_size(total_size),
            },
            "voices": {
                "total": len(settings.DEMO_VOICES),
            },
            "model": tts_service.get_model_info(),
        }
        
        # Add Phase 2 stats if available
        if PHASE_2_ENABLED:
            stats["phase_2"] = {
                "enabled": True,
                "processed_files": len(segment_cache),
            }
        
        return stats

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}",
        )


# ==================== PHASE 2 ENDPOINTS (NEW) ====================

@router.post(
    "/process/v2",
    response_model=ProcessingResponseV2,
    summary="Process PDF with Multi-Speaker Detection [PHASE 2]",
    description="Process PDF with dialogue detection, speaker identification, and emotion analysis",
    responses={404: {"model": ErrorResponse, "description": "File not found"}},
)
@limiter.limit("10/minute")
async def process_pdf_v2(request: Request, body: ProcessingRequestV2):
    """
    **NEW: Multi-Speaker Emotion-Aware Processing**

    Process PDF with:
    - Dialogue detection
    - Speaker identification
    - Emotion analysis
    - Gender inference

    Returns speaker-tagged, emotion-labeled segments
    """
    try:
        logger.info(f"Processing v2: {body.file_id}")

        # CRITICAL FIX: Use cached data instead of looking for file
        if body.file_id not in chapter_cache:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found in cache: {body.file_id}. Please upload PDF first using /api/upload",
            )

        # Get cached data
        chapters = chapter_cache[body.file_id]
        pdf_doc = pdf_cache.get(body.file_id)

        if not pdf_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF document not found in cache",
            )

        # Process using cached data (NOT file path)
        result = await audiobook_processor.process_pdf_from_cache(
            pdf_doc=pdf_doc,
            chapters=chapters,
            detect_emotions=body.detect_emotions
        )

        # Cache processed segments for later use
        segment_cache[body.file_id] = result
        
        logger.info(
            f"Processed {result['total_segments']} segments "
            f"with {len(result['speakers_detected'])} speakers"
        )
        
        return ProcessingResponseV2(
            file_id=result['file_id'],
            total_chapters=result['total_chapters'],
            total_segments=result['total_segments'],
            speakers_detected=result['speakers_detected'],
            chapters=result['chapters'],
            processing_time=result['processing_time']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing v2 failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}",
        )

@router.post(
    "/generate/multi-speaker",
    response_model=MultiSpeakerGenerationResponse,
    summary="Generate Multi-Speaker Audiobook [PHASE 2]",
    description="Generate audiobook with multiple voices and emotion-aware prosody",
)
async def generate_multi_speaker(request: MultiSpeakerGenerationRequest):
    """
    **UPDATED: Multi-Speaker Emotion-Aware Generation with Translation**
    
    NOW ACCEPTS BOTH FORMATS:
    1. Direct segments array
    2. /process/v2 output with chapters
    
    Generate audiobook with:
    - Multiple voices for different speakers
    - Emotion-aware prosody adjustments
    - Natural dialogue narration
    - Multilingual translation support
    """
    try:
        logger.info(
            f"Multi-speaker generation: {request.file_id}"
        )
        
        start_time = time.time()
        
        # CRITICAL FIX: Extract segments from EITHER format
        segments = None
        
        # Format 1: Direct segments array (original format)
        if request.segments:
            segments = [seg.dict() for seg in request.segments]
            logger.info(f"Using direct segments format: {len(segments)} segments")
        
        # Format 2: Chapters with nested segments (from /process/v2)
        elif hasattr(request, '__dict__') and 'chapters' in request.__dict__:
            # Extract from Pydantic model's extra fields
            chapters = request.__dict__.get('chapters', [])
            if chapters:
                segments = []
                for chapter in chapters:
                    if isinstance(chapter, dict) and 'segments' in chapter:
                        segments.extend(chapter['segments'])
                logger.info(f"Extracted {len(segments)} segments from {len(chapters)} chapters")
        
        # Format 3: Check raw request dict (if Config.extra = "allow")
        if not segments:
            # Try to get from the raw request
            request_dict = request.dict()
            if 'chapters' in request_dict and request_dict['chapters']:
                chapters = request_dict['chapters']
                segments = []
                for chapter in chapters:
                    if 'segments' in chapter:
                        segments.extend(chapter['segments'])
                logger.info(f"Extracted {len(segments)} segments from chapters in request dict")
        
        # Final check
        if not segments or len(segments) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No segments found. Please provide either:\n"
                    "1. 'segments' array directly, OR\n"
                    "2. 'chapters' array from /process/v2 output"
                ),
            )
        
        logger.info(f"Generating audio for {len(segments)} segments")
        
        # ==================== TRANSLATION LOGIC ====================
        # Check if translation is needed
        if request.source_language != request.target_language:
            logger.info(
                f"Translation enabled: {request.source_language} → {request.target_language}"
            )
            try:
                from app.services.translation_service import translation_service
                
                # Translate all segments
                logger.info(f"Translating {len(segments)} segments...")
                translated_segments = translation_service.translate_segments(
                    segments=segments,
                    source_lang=request.source_language,
                    target_lang=request.target_language
                )
                
                # Use translated text instead of original
                for i, seg in enumerate(translated_segments):
                    if 'translated_text' in seg and seg['translated_text']:
                        seg['text'] = seg['translated_text']
                        logger.debug(f"Segment {i}: Using translated text")
                    else:
                        logger.warning(f"Segment {i}: No translation, using original")
                
                segments = translated_segments
                logger.info("✅ Translation completed successfully")
                
            except Exception as e:
                logger.error(f"Translation failed: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Translation service error: {str(e)}",
                )
        else:
            logger.info(f"No translation needed (source = target = {request.source_language})")
        
        # Create voice assignments
        voice_assignments = {}
        if request.voice_assignments:
            for assignment in request.voice_assignments:
                voice_assignments[assignment.speaker_name] = assignment.voice_id
        
        # Resolve TTS language code from the target language name.
        # XTTS uses ISO 639-1 codes; fall back to "en" for any unknown language.
        _LANG_TO_XTTS = {
            "english": "en", "spanish": "es", "french": "fr", "german": "de",
            "italian": "it", "portuguese": "pt", "polish": "pl", "turkish": "tr",
            "russian": "ru", "dutch": "nl", "czech": "cs", "arabic": "ar",
            "chinese": "zh-cn", "japanese": "ja", "korean": "ko", "hindi": "hi",
            "hungarian": "hu", "urdu": "ur",
        }
        tts_language = _LANG_TO_XTTS.get(
            request.target_language.lower().strip(), "en"
        )

        # Generate audiobook
        output_path = await audiobook_processor.generate_audiobook(
            segments=segments,
            voice_assignments=voice_assignments if voice_assignments else None,
            speed=request.base_speed,
            language=tts_language,
        )
        
        # Get audio info
        audio_info = audio_service.get_audio_info(output_path)
        
        generation_time = time.time() - start_time
        
        # Generate audiobook ID
        audiobook_id = output_path.stem
        
        # Get speakers used
        unique_speakers = {seg['speaker']: seg['gender'] for seg in segments}
        
        logger.info(
            f"Multi-speaker audio generated in {generation_time:.1f}s: "
            f"{output_path.name}"
        )
        
        return MultiSpeakerGenerationResponse(
            audiobook_id=audiobook_id,
            audio_url=f"/api/outputs/{output_path.name}",
            duration=audio_info.get('duration', 0.0),
            segments_processed=len(segments),
            speakers_used=unique_speakers,
            generation_time=generation_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Multi-speaker generation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}",
        )


@router.post(
    "/generate/from-processing",
    summary="Generate from Process/v2 Output [PHASE 2 - FIXED]",
    description="Accepts the exact output from /process/v2 and generates multi-speaker audio",
)
@limiter.limit("5/minute")
async def generate_from_processing(request: Request, body: dict):
    """
    **FIXED ENDPOINT: Accepts /process/v2 output directly**
    
    Just paste the entire response from /process/v2 into this endpoint!
    No manual JSON conversion needed.
    
    Example usage:
    1. Call /process/v2 → Get response
    2. Paste entire response here
    3. Get audio!
    """
    try:
        import time
        
        # Extract file_id
        file_id = body.get('file_id')
        if not file_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_id is required"
            )

        logger.info(f"Generating from processing output: {file_id}")

        # Extract chapters list
        chapters_input = body.get('chapters', [])
        if not isinstance(chapters_input, list) or not chapters_input:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No chapters found in request. Expected output from /process/v2"
            )

        total_segments = sum(len(ch.get('segments', [])) for ch in chapters_input)
        if total_segments == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No segments found in chapters"
            )

        logger.info(f"Generating {len(chapters_input)} chapters, {total_segments} total segments")

        # Get optional parameters (with defaults)
        base_speed = body.get('base_speed', 1.0)
        apply_emotion_prosody = body.get('apply_emotion_prosody', True)
        output_format = body.get('output_format', 'wav')

        target_language = body.get('target_language', 'english')
        source_language = body.get('source_language', 'english')

        # Build human-readable output filename from title if provided
        import re as _re
        raw_title = body.get('title', '') or ''
        safe_title = _re.sub(r'[^\w\s-]', '', raw_title).strip().replace(' ', '-')[:60]
        if not safe_title:
            safe_title = file_id[:12]
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        named_output_path = settings.OUTPUT_DIR / f"{safe_title}_{timestamp}.wav"
        
        start_time = time.time()

        from app.services.processor import audiobook_processor
        from app.services.audio_service import audio_service

        _LANG_TO_XTTS_FP = {
            "english": "en", "en": "en",
            "spanish": "es", "es": "es",
            "french": "fr", "fr": "fr",
            "german": "de", "de": "de",
            "italian": "it", "it": "it",
            "portuguese": "pt", "pt": "pt",
            "polish": "pl", "pl": "pl",
            "turkish": "tr", "tr": "tr",
            "russian": "ru", "ru": "ru",
            "dutch": "nl", "nl": "nl",
            "czech": "cs", "cs": "cs",
            "arabic": "ar", "ar": "ar",
            "chinese": "zh-cn", "zh": "zh-cn",
            "japanese": "ja", "ja": "ja",
            "korean": "ko", "ko": "ko",
            "hindi": "hi", "hi": "hi",
            "hungarian": "hu", "hu": "hu",
            # Urdu uses Arabic script — map to "ar" since XTTS v2 doesn't have "ur"
            "urdu": "ar", "ur": "ar",
        }
        tts_lang_fp = _LANG_TO_XTTS_FP.get(target_language.lower().strip(), "en")

        # Generate audio per chapter, then merge into one full-book file
        chapter_results = []
        all_chapter_paths = []
        unique_speakers = {}
        total_segments_processed = 0

        for chapter in chapters_input:
            ch_id = chapter.get('chapter_id', len(chapter_results) + 1)
            ch_title = chapter.get('chapter_title', f'Chapter {ch_id}')
            ch_segments = chapter.get('segments', [])
            if not ch_segments:
                continue

            # Translate if needed
            if target_language.lower().strip() != source_language.lower().strip():
                try:
                    from app.services.translation_service import translation_service
                    ch_segments = translation_service.translate_segments(
                        segments=ch_segments,
                        source_lang=source_language,
                        target_lang=target_language,
                    )
                except Exception as te:
                    logger.warning(f"Translation failed for chapter {ch_id}: {te}")

            safe_ch = f"ch{ch_id}_{safe_title}"[:60]
            ch_output_path = settings.OUTPUT_DIR / f"{safe_ch}_{timestamp}.wav"

            logger.info(f"Generating chapter {ch_id}: '{ch_title}' ({len(ch_segments)} segments)")
            ch_path = await audiobook_processor.generate_audiobook(
                segments=ch_segments,
                voice_assignments=None,
                speed=base_speed,
                output_path=ch_output_path,
                language=tts_lang_fp,
            )

            ch_info = audio_service.get_audio_info(ch_path)
            all_chapter_paths.append(ch_path)
            total_segments_processed += len(ch_segments)
            for seg in ch_segments:
                unique_speakers[seg['speaker']] = seg.get('gender', 'neutral')

            chapter_results.append({
                "chapter_id": ch_id,
                "chapter_title": ch_title,
                "audio_url": f"/api/outputs/{ch_path.name}",
                "duration": ch_info.get('duration', 0.0),
                "segments": len(ch_segments),
            })
            logger.info(f"✅ Chapter {ch_id} done: {ch_path.name}")

        if not all_chapter_paths:
            raise HTTPException(status_code=500, detail="No audio generated for any chapter")

        # Merge all chapters into one full-book file
        if len(all_chapter_paths) == 1:
            output_path = all_chapter_paths[0]
        else:
            output_path = await audio_service.merge_audio_files(
                all_chapter_paths,
                output_path=named_output_path,
            )

        generation_time = time.time() - start_time
        audio_info = audio_service.get_audio_info(output_path)

        logger.info(
            f"✅ Full audiobook generated: {output_path.name} "
            f"({total_segments_processed} segments, {len(chapter_results)} chapters, {generation_time:.1f}s)"
        )

        return {
            "success": True,
            "audiobook_id": output_path.stem,
            "audio_url": f"/api/outputs/{output_path.name}",
            "duration": audio_info.get('duration', 0.0),
            "file_size": audio_info.get('file_size', 0),
            "segments_processed": total_segments_processed,
            "speakers_used": unique_speakers,
            "generation_time": generation_time,
            "chapters": chapter_results,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generation from processing failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}",
        )



@router.get(
    "/segments/{file_id}",
    summary="Get Processed Segments [PHASE 2]",
    description="Get speaker-tagged, emotion-labeled segments for a file",
)
async def get_segments(file_id: str):
    """Get processed segments with speaker and emotion data"""
    try:
        if file_id not in segment_cache:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not processed yet. Use /process/v2 first.",
            )
        
        return segment_cache[file_id]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get segments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ==================== VOICE CLONING ====================

@router.post(
    "/voices/clone",
    summary="Clone Custom Voice [VOICE CLONING]",
    description="Extract and clone a custom voice from audio sample for use in audiobook generation",
)
async def clone_voice(
    voice_name: str = Form(...),
    gender: str = Form(...),
    language: str = Form(default="english"),
    audio_file: UploadFile = File(...)
):
    """
    Clone a custom voice from audio sample
    
    **Requirements:**
    - Audio duration: 6-30 seconds
    - Supported formats: WAV, MP3, OGG
    - Audio quality: Clear speech, minimal background noise
    - Content: Natural speech (not whisper)
    
    **Returns:**
    - voice_id: Unique identifier for this cloned voice
    - status: "ready" when usable
    
    **Usage:**
    After cloning, use voice_id in voice_assignments:
    ```json
    {
      "speaker_name": "Harry",
      "voice_id": "<returned_voice_id>"
    }
    ```
    """
    try:
        import uuid
        import torch
        from pathlib import Path
        from app.models.schemas import VoiceProfile
        
        logger.info(f"Cloning voice: {voice_name} ({gender}, {language})")
        
        # Validate audio file
        if not audio_file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No audio file provided"
            )
        
        # Save temporary audio file
        voice_dir = settings.EMBEDDINGS_DIR / "temp"
        voice_dir.mkdir(parents=True, exist_ok=True)
        
        audio_path = voice_dir / f"sample_{uuid.uuid4().hex[:8]}.wav"
        content = await audio_file.read()
        
        with open(audio_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"Audio file saved to: {audio_path}")
        
        # Save the reference audio as the voice profile
        # XTTS uses raw conditioning audio — no GPU-only embedding extraction needed
        try:
            import shutil
            
            voice_id_temp = f"custom_{uuid.uuid4().hex[:12]}"
            final_audio_path = settings.EMBEDDINGS_DIR / f"{voice_id_temp}.wav"
            shutil.copy2(str(audio_path), str(final_audio_path))
            
            # Optionally validate audio duration using pydub/soundfile
            try:
                import soundfile as sf
                data, sr = sf.read(str(final_audio_path))
                duration = len(data) / sr
                if duration < 3:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Audio too short ({duration:.1f}s). Please upload at least 6 seconds of speech."
                    )
                logger.info(f"✅ Voice audio saved: {final_audio_path.name} ({duration:.1f}s)")
            except HTTPException:
                raise
            except Exception:
                logger.info(f"✅ Voice audio saved: {final_audio_path.name}")
            
            # Store a small metadata .pt file so existing code can find it
            import torch
            meta = {"audio_path": str(final_audio_path), "voice_name": voice_name, "gender": gender}
            torch.save(meta, settings.EMBEDDINGS_DIR / f"{voice_id_temp}.pt")
            voice_id = voice_id_temp
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to save voice profile: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Voice extraction failed: {str(e)}"
            )
        
        # Embedding path already saved above
        embeddings_path = settings.EMBEDDINGS_DIR / f"{voice_id}.pt"
        logger.info(f"Voice profile saved to: {embeddings_path}")
        
        # Cache in Redis for fast access
        try:
            from app.services.translation_service import cache_client
            if cache_client:
                cache_key = f"voice_embedding:{voice_id}"
                # Store embedding reference (don't store actual tensor)
                cache_data = {
                    "voice_id": voice_id,
                    "embedding_path": str(embeddings_path),
                    "voice_name": voice_name,
                    "gender": gender,
                    "language": language,
                    "created_at": str(Path(embeddings_path).stat().st_ctime)
                }
                cache_client.setex(
                    cache_key, 
                    settings.CACHE_TTL,
                    json.dumps(cache_data)
                )
                logger.info(f"✅ Voice cached in Redis: {cache_key}")
        except Exception as e:
            logger.warning(f"Redis caching failed (non-fatal): {e}")
        
        # Clean up temporary file
        try:
            audio_path.unlink()
            logger.info("Temporary audio file cleaned up")
        except:
            pass
        
        # Create response
        voice_profile = VoiceProfile(
            voice_id=voice_id,
            voice_name=voice_name,
            gender=gender,
            language=language,
            embedding_path=str(embeddings_path),
            is_custom=True,
            sample_audio_url=f"/api/voices/{voice_id}/sample"
        )
        
        logger.info(f"✅ Voice cloning completed: {voice_id}")
        
        return {
            "voice_id": voice_id,
            "voice_name": voice_name,
            "gender": gender,
            "language": language,
            "embedding_path": str(embeddings_path),
            "is_custom": True,
            "status": "ready",
            "message": f"Voice '{voice_name}' cloned successfully. Use voice_id '{voice_id}' in voice_assignments."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice cloning failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice cloning failed: {str(e)}"
        )


@router.get(
    "/voices",
    summary="List Available Voices [VOICE MANAGEMENT]",
    description="Get all available default and custom voices",
)
async def list_voices():
    """
    List all available voices (default + custom cloned)
    
    **Returns:**
    - Default voices from DEMO_VOICES
    - Custom cloned voices from embeddings directory
    """
    try:
        voices = []
        
        # Add default voices (with mood/type/featured for the frontend)
        for demo_voice in settings.DEMO_VOICES:
            voices.append({
                "voice_id": demo_voice["id"],
                "voice_name": demo_voice["name"],
                "gender": demo_voice.get("gender", "neutral"),
                "language": demo_voice.get("language", "en"),
                "type": demo_voice.get("type", "Neural"),
                "mood": demo_voice.get("mood", "Natural"),
                "featured": demo_voice.get("featured", False),
                "is_custom": False,
                "description": demo_voice.get("description", ""),
                "sample_url": f"/api/voices/{demo_voice['id']}/sample",
            })
        
        # Add custom cloned voices — read metadata from .pt file
        import torch as _torch
        embeddings_dir = settings.EMBEDDINGS_DIR
        if embeddings_dir.exists():
            for pt_file in sorted(embeddings_dir.glob("custom_*.pt")):
                voice_id = pt_file.stem
                voice_name = f"Custom Voice ({voice_id[:8]})"
                gender = "neutral"
                try:
                    meta = _torch.load(str(pt_file), map_location="cpu", weights_only=False)
                    if isinstance(meta, dict) and "voice_name" in meta:
                        voice_name = meta["voice_name"]
                        gender = meta.get("gender", "neutral")
                except Exception:
                    pass
                voices.append({
                    "voice_id": voice_id,
                    "voice_name": voice_name,
                    "gender": gender,
                    "language": "en",
                    "type": "Cloned",
                    "mood": "Custom Clone",
                    "featured": False,
                    "is_custom": True,
                    "sample_url": f"/api/voices/{voice_id}/sample",
                })
        
        logger.info(f"Retrieved {len(voices)} available voices ({sum(1 for v in voices if v['is_custom'])} cloned)")
        return {
            "voices": voices,
            "total": len(voices)
        }
        
    except Exception as e:
        logger.error(f"Failed to list voices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ==================== ASYNC TASK ENDPOINTS ====================

def _run_generation_background(
    task_id: str,
    chapters_input: list,
    voice_assignments: dict,
    speed: float,
    language: str = "en",
    target_language: str = "en",
    source_language: str = "en",
    emotion_intensity: float = 1.5,
):
    """
    Run per-chapter audiobook generation in a background thread.
    Updates task_store with incremental progress so the frontend can poll.
    """
    import asyncio

    task = task_store[task_id]
    task["status"] = "processing"
    task["progress"] = 0
    task["message"] = "Starting generation…"

    async def _run():
        try:
            from app.services.processor import audiobook_processor
            from app.services.audio_service import audio_service

            timestamp = int(time.time())
            chapter_results = []
            all_chapter_paths = []
            total_segments = sum(len(ch.get("segments", [])) for ch in chapters_input)
            segments_done = 0

            for ch_idx, chapter in enumerate(chapters_input):
                ch_id = chapter.get("chapter_id", ch_idx + 1)
                ch_title = chapter.get("chapter_title", f"Chapter {ch_id}")
                ch_segments = chapter.get("segments", [])
                if not ch_segments:
                    continue

                task["message"] = f"Generating chapter {ch_id}: {ch_title}…"

                # Translate segments if source and target languages differ
                if source_language.lower().strip() != target_language.lower().strip():
                    try:
                        from app.services.translation_service import translation_service
                        task["message"] = f"Translating chapter {ch_id}…"
                        ch_segments = translation_service.translate_segments(
                            segments=ch_segments,
                            source_lang=source_language,
                            target_lang=target_language,
                        )
                        logger.info(f"Task {task_id}: chapter {ch_id} translated → {target_language}")
                    except Exception as te:
                        logger.warning(f"Task {task_id}: translation failed for chapter {ch_id}: {te}")

                safe_title_ch = "".join(c if c.isalnum() else "_" for c in ch_title)[:30]
                safe_ch = f"ch{ch_id}_{safe_title_ch}"[:60]
                ch_output_path = settings.OUTPUT_DIR / f"{safe_ch}_{timestamp}.wav"

                ch_path = await audiobook_processor.generate_audiobook(
                    segments=ch_segments,
                    voice_assignments=None,
                    speed=speed,
                    output_path=ch_output_path,
                    language=language,
                )

                ch_info = audio_service.get_audio_info(ch_path)
                all_chapter_paths.append(ch_path)
                segments_done += len(ch_segments)
                chapter_results.append({
                    "chapter_id": ch_id,
                    "chapter_title": ch_title,
                    "audio_url": f"/api/outputs/{ch_path.name}",
                    "duration": ch_info.get("duration", 0.0),
                    "segments": len(ch_segments),
                })

                # Progress: 0-90% across chapters, 90-100% reserved for merge
                task["progress"] = int((segments_done / max(total_segments, 1)) * 90)
                task["message"] = f"Chapter {ch_id} done ({segments_done}/{total_segments} segments)"
                logger.info(f"Task {task_id}: chapter {ch_id} done → {ch_path.name}")

            if not all_chapter_paths:
                raise RuntimeError("No audio generated for any chapter")

            task["message"] = "Merging chapters…"
            task["progress"] = 91

            if len(all_chapter_paths) == 1:
                final_audio = all_chapter_paths[0]
            else:
                named_output = settings.OUTPUT_DIR / f"audiobook_{task_id}_{timestamp}.mp3"
                final_audio = await audio_service.merge_audio_files(
                    all_chapter_paths,
                    output_path=named_output,
                )

            audio_info = audio_service.get_audio_info(final_audio)
            task["status"] = "done"
            task["progress"] = 100
            task["message"] = "Complete"
            task["result"] = {
                "audiobook_id": final_audio.stem,
                "audio_url": f"/api/outputs/{final_audio.name}",
                "duration": audio_info.get("duration", 0.0),
                "file_size": audio_info.get("file_size", 0),
                "segments_processed": segments_done,
                "chapters": chapter_results,
            }

        except Exception as e:
            logger.error(f"Background task {task_id} failed: {e}")
            task["status"] = "error"
            task["error"] = str(e)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()


@router.post(
    "/generate/async",
    summary="Start Async Audiobook Generation [FAST]",
    description=(
        "Kick off audiobook generation in the background and immediately return a "
        "task_id.  Poll GET /tasks/{task_id} or stream GET /tasks/{task_id}/stream "
        "for live progress."
    ),
)
async def generate_async(request: dict):
    """
    Non-blocking audiobook generation.

    Accepts the same body as /generate/from-processing.
    Returns a task_id immediately so the user is not left waiting.
    """
    chapters_input = request.get("chapters", [])
    if not chapters_input:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No chapters found. Provide 'chapters' array (from /process/v2).",
        )

    total_segments = sum(len(ch.get("segments", [])) for ch in chapters_input)
    if total_segments == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No segments found in provided chapters.",
        )

    base_speed = float(request.get("base_speed", 1.0))
    source_language = request.get("source_language", "en")
    target_language = request.get("target_language", "en")
    emotion_intensity = float(request.get("emotion_intensity", 1.5))

    _LANG_TO_XTTS = {
        "english": "en", "en": "en",
        "spanish": "es", "es": "es",
        "french": "fr", "fr": "fr",
        "german": "de", "de": "de",
        "italian": "it", "it": "it",
        "portuguese": "pt", "pt": "pt",
        "polish": "pl", "pl": "pl",
        "turkish": "tr", "tr": "tr",
        "russian": "ru", "ru": "ru",
        "dutch": "nl", "nl": "nl",
        "czech": "cs", "cs": "cs",
        "arabic": "ar", "ar": "ar",
        "chinese": "zh-cn", "zh": "zh-cn",
        "japanese": "ja", "ja": "ja",
        "korean": "ko", "ko": "ko",
        "hindi": "hi", "hi": "hi",
        "hungarian": "hu", "hu": "hu",
        # Urdu uses Arabic script — map to "ar" since XTTS v2 doesn't have "ur"
        "urdu": "ar", "ur": "ar",
    }
    tts_lang = _LANG_TO_XTTS.get(target_language.lower().strip(), "en")

    task_id = _uuid.uuid4().hex[:16]
    task_store[task_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Queued",
        "result": None,
        "error": None,
        "created_at": time.time(),
    }

    voice_assignments = {}
    for assignment in request.get("voice_assignments", []):
        if isinstance(assignment, dict):
            voice_assignments[assignment.get("speaker_name", "")] = assignment.get("voice_id", "")

    thread = threading.Thread(
        target=_run_generation_background,
        kwargs={
            "task_id": task_id,
            "chapters_input": chapters_input,
            "voice_assignments": voice_assignments,
            "speed": base_speed,
            "language": tts_lang,
            "target_language": target_language,
            "source_language": source_language,
            "emotion_intensity": emotion_intensity,
        },
        daemon=True,
    )
    thread.start()

    logger.info(f"Async task started: {task_id} ({len(chapters_input)} chapters, {total_segments} segments)")
    return {"task_id": task_id, "status": "queued", "chapters": len(chapters_input), "segments": total_segments}


@router.get(
    "/tasks/{task_id}",
    summary="Poll Task Status",
    description="Check the current status and progress of an async generation task.",
)
async def get_task_status(task_id: str):
    """Poll task progress."""
    task = task_store.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )
    return {"task_id": task_id, **task}


@router.get(
    "/tasks/{task_id}/stream",
    summary="Stream Task Progress (SSE)",
    description=(
        "Server-Sent Events stream for real-time generation progress. "
        "Connect and receive updates until status is 'done' or 'error'."
    ),
)
async def stream_task_progress(task_id: str):
    """SSE stream for a running generation task."""

    async def event_generator():
        last_progress = -1
        while True:
            task = task_store.get(task_id)
            if task is None:
                yield f"event: error\ndata: {json.dumps({'error': 'Task not found'})}\n\n"
                return

            if task["progress"] != last_progress or task["status"] in ("done", "error"):
                last_progress = task["progress"]
                payload = json.dumps({"task_id": task_id, **task})
                yield f"data: {payload}\n\n"

            if task["status"] in ("done", "error"):
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ==================== EVALUATION ENDPOINT ====================

@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    summary="Evaluate Voice Quality",
    description=(
        "Run objective voice quality metrics on a generated audio file.\n\n"
        "**Metrics computed:**\n"
        "- **WER** (Word Error Rate) — requires `original_text`\n"
        "- **UTMOS** (Predicted MOS, 1–5)\n"
        "- **SNR** (Signal-to-Noise Ratio in dB)\n"
        "- **SER** (Emotion accuracy) — enhanced when `intended_emotion` is given\n"
        "- **SECS** (Speaker similarity, −1 to 1) — requires `reference_audio`\n\n"
        "Called internally by the Django admin portal — not intended for end users."
    ),
)
async def evaluate_audio(
    audio_file: UploadFile = File(..., description="Generated audio file (wav/mp3)"),
    reference_audio: Optional[UploadFile] = File(None, description="Reference voice sample for SECS (optional)"),
    original_text: Optional[str] = Form(None, description="Source text for WER computation (optional)"),
    intended_emotion: Optional[str] = Form(None, description="Intended emotion label for SER accuracy (optional)"),
):
    """Evaluate voice quality across all objective metrics."""
    import tempfile, os

    audio_tmp = None
    ref_tmp = None

    try:
        # Save uploaded audio to temp file
        suffix = Path(audio_file.filename or "audio.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(await audio_file.read())
            audio_tmp = f.name

        # Save reference audio if provided
        ref_path = None
        if reference_audio and reference_audio.filename:
            ref_suffix = Path(reference_audio.filename).suffix or ".wav"
            with tempfile.NamedTemporaryFile(delete=False, suffix=ref_suffix) as f:
                f.write(await reference_audio.read())
                ref_tmp = f.name
                ref_path = ref_tmp

        logger.info(
            f"Evaluate request: emotion={intended_emotion}, "
            f"has_text={bool(original_text)}, has_reference={bool(ref_path)}"
        )

        result = evaluation_service.evaluate(
            audio_path=audio_tmp,
            original_text=original_text,
            reference_audio_path=ref_path,
            intended_emotion=intended_emotion,
        )

        return EvaluationResponse(**result)

    finally:
        if audio_tmp and os.path.exists(audio_tmp):
            os.unlink(audio_tmp)
        if ref_tmp and os.path.exists(ref_tmp):
            os.unlink(ref_tmp)


# EXPORT

__all__ = ["router"]