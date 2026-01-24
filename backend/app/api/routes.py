# Defines all REST API endpoints for the Narrify application.
import asyncio
from pathlib import Path
from typing import List
import torch

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from loguru import logger

from app.config import settings
from app.models.schemas import (
    AudioGenerationRequest,
    AudioGenerationResponse,
    ChapterInfo,
    ChaptersResponse,
    ErrorResponse,
    FileUploadResponse,
    HealthResponse,
    VoiceInfo,
    VoicesResponse,
)
from app.services.audio_service import audio_service
from app.services.pdf_service import pdf_service
from app.services.text_service import text_service
from app.services.tts_service import tts_service

# Create router
router = APIRouter()

# Cache for processed PDFs (file_id -> PDFDocument)
pdf_cache = {}

# Cache for chapters (file_id -> List[Chapter])
chapter_cache = {}

# HEALTH CHECK

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check API health and model status",
)
async def health_check():
    # health status
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
    
    # Upload and process PDF file
    # Upload confirmation with file ID and metadata
    
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
    
    # Get chapters for uploaded file
    
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
    
    # Returns list of voice options
    
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
    
    # Get voice sample audio

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

# AUDIO GENERATION

@router.post(
    "/generate",
    response_model=AudioGenerationResponse,
    summary="Generate Audio",
    description="Generate audiobook for a chapter",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid parameters"},
        404: {"model": ErrorResponse, "description": "File or chapter not found"},
    },
)
async def generate_audio(request: AudioGenerationRequest):
    
    # Generate audiobook audio for a chapter
    # Generated audio information
    
    import time

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
    
    # Download generated audio file

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

    # Clean up old files

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

    # Get system statistics

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

        return {
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

    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}",
        )

# EXPORT

__all__ = ["router"]
