"""
API Routes - Enhanced with Multi-Speaker Emotion-Aware Features
Backward compatible with Phase 1 (all original endpoints preserved)
"""

import asyncio
from pathlib import Path
from typing import List, Optional
import torch
import time

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
    Query,
)
from fastapi.responses import FileResponse
from loguru import logger

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
)

# Phase 1 Services (Original)
from app.services.audio_service import audio_service
from app.services.pdf_service import pdf_service
from app.services.text_service import text_service
from app.services.tts_service import tts_service

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
segment_cache = {}

# NEW: Cache for processed segments (file_id -> processed data)
segment_cache = {}


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
async def upload_pdf(file: UploadFile = File(..., description="PDF file to upload")):
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
    response_model=VoicesResponse,
    summary="Get Voices",
    description="Get list of available voices",
)
async def get_voices():
    """Returns list of voice options"""
    try:
        voices_data = tts_service.get_available_voices()

        voices = [
            VoiceInfo(
                id=v["id"],
                name=v["name"],
                language=v["language"],
                gender=v["gender"],
                description=v["description"],
                sample_url=v.get("sample_url"),
                is_custom=False,
            )
            for v in voices_data
        ]

        return VoicesResponse(voices=voices, total_voices=len(voices))

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
    """Get voice sample audio"""
    try:
        # Find voice config
        voice_config = next(
            (v for v in settings.DEMO_VOICES if v["id"] == voice_id), None
        )

        if not voice_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Voice not found: {voice_id}",
            )

        sample_path = settings.VOICE_DIR / voice_config["sample_file"]

        if not sample_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice sample not available",
            )

        return FileResponse(
            path=sample_path,
            media_type="audio/wav",
            filename=f"{voice_id}_sample.wav",
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

        # Normalize text
        normalized_text = text_service.normalize(chapter.content)

        # Validate normalized text
        is_valid, error_msg = text_service.validate_text(normalized_text)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg
            )

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
async def process_pdf_v2(request: ProcessingRequestV2):
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
        logger.info(f"Processing v2: {request.file_id}")
        
        # CRITICAL FIX: Use cached data instead of looking for file
        if request.file_id not in chapter_cache:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found in cache: {request.file_id}. Please upload PDF first using /api/upload",
            )
        
        # Get cached data
        chapters = chapter_cache[request.file_id]
        pdf_doc = pdf_cache.get(request.file_id)
        
        if not pdf_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF document not found in cache",
            )
        
        # Process using cached data (NOT file path)
        result = await audiobook_processor.process_pdf_from_cache(
            pdf_doc=pdf_doc,
            chapters=chapters,
            detect_emotions=request.detect_emotions
        )
        
        # Cache processed segments for later use
        segment_cache[request.file_id] = result
        
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
    **UPDATED: Multi-Speaker Emotion-Aware Generation**
    
    NOW ACCEPTS BOTH FORMATS:
    1. Direct segments array
    2. /process/v2 output with chapters
    
    Generate audiobook with:
    - Multiple voices for different speakers
    - Emotion-aware prosody adjustments
    - Natural dialogue narration
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
        
        # Create voice assignments
        voice_assignments = {}
        if request.voice_assignments:
            for assignment in request.voice_assignments:
                voice_assignments[assignment.speaker_name] = assignment.voice_id
        
        # Generate audiobook
        output_path = await audiobook_processor.generate_audiobook(
            segments=segments,
            voice_assignments=voice_assignments if voice_assignments else None,
            speed=request.base_speed
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
async def generate_from_processing(request: dict):
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
        file_id = request.get('file_id')
        if not file_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="file_id is required"
            )
        
        logger.info(f"Generating from processing output: {file_id}")
        
        # Extract segments from chapters
        segments = []
        
        if 'chapters' in request and isinstance(request['chapters'], list):
            for chapter in request['chapters']:
                if 'segments' in chapter and isinstance(chapter['segments'], list):
                    segments.extend(chapter['segments'])
            logger.info(f"Extracted {len(segments)} segments from {len(request['chapters'])} chapters")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No chapters found in request. Expected output from /process/v2"
            )
        
        if not segments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No segments found in chapters"
            )
        
        # Get optional parameters (with defaults)
        base_speed = request.get('base_speed', 1.0)
        apply_emotion_prosody = request.get('apply_emotion_prosody', True)
        output_format = request.get('output_format', 'wav')
        
        # Generate audiobook
        logger.info(f"Generating multi-speaker audio for {len(segments)} segments")
        
        start_time = time.time()
        
        # Import here to avoid circular imports
        from app.services.processor import audiobook_processor
        from app.services.audio_service import audio_service
        
        output_path = await audiobook_processor.generate_audiobook(
            segments=segments,
            voice_assignments=None,  # Auto-assign by gender
            speed=base_speed
        )
        
        generation_time = time.time() - start_time
        
        # Get audio info
        audio_info = audio_service.get_audio_info(output_path)
        
        # Get unique speakers
        unique_speakers = {seg['speaker']: seg['gender'] for seg in segments}
        
        logger.info(
            f"✅ Multi-speaker audio generated: {output_path.name} "
            f"({len(segments)} segments in {generation_time:.1f}s)"
        )
        
        return {
            "success": True,
            "audiobook_id": output_path.stem,
            "audio_url": f"/api/outputs/{output_path.name}",
            "duration": audio_info.get('duration', 0.0),
            "file_size": audio_info.get('file_size', 0),
            "segments_processed": len(segments),
            "speakers_used": unique_speakers,
            "speakers_detected": request.get('speakers_detected', []),
            "generation_time": generation_time
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


# EXPORT

__all__ = ["router"]