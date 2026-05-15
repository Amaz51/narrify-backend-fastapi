# Main FastAPI Application

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.limiter import limiter

from app.api.routes import router
from app.config import settings
from app.models.schemas import ErrorResponse



# LIFESPAN MANAGEMENT

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Application lifespan manager
    # Handles startup and shutdown events

    # Startup
    logger.info("=" * 70)
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 70)
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"Device: {settings.get_device()}")
    logger.info(f"Upload dir: {settings.UPLOAD_DIR}")
    logger.info(f"Output dir: {settings.OUTPUT_DIR}")
    logger.info("=" * 70)

    # Import services to trigger initialization
    from app.services.tts_service import tts_service
    from app.services.evaluation_service import evaluation_service

    logger.info(f"TTS Model loaded: {tts_service.is_model_loaded()}")

    # Pre-load evaluation models so the first /api/evaluate call doesn't time out
    logger.info("Pre-loading evaluation models...")
    evaluation_service._load_whisper()
    evaluation_service._load_ser()
    evaluation_service._load_voice_encoder()
    evaluation_service._load_squim()
    logger.info("Evaluation models ready")
    logger.info("Application startup complete")

    yield

    # Shutdown
    logger.info("Application shutting down...")
    logger.info("Cleanup complete")

# CREATE APP

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    # Narrify Phase 1 - AI-Powered Audiobook Platform

    Convert PDFs to audiobooks with customizable AI voices.

    ## Features
    - PDF text extraction with chapter detection
    - Multiple voice options with zero-shot cloning
    - Speed, pitch, and tone customization
    - High-quality audio output (WAV/MP3)

    ## Quick Start
    1. Upload PDF → `/api/upload`
    2. Get chapters → `/api/chapters/{file_id}`
    3. Choose voice → `/api/voices`
    4. Generate audio → `/api/generate`
    5. Download → `/api/outputs/{filename}`

    ## Team
    - Abdullah Shahid (21L-7648)
    - Umer Khalid (22L-6546)
    - Amaz Ahmed (22L-6837)

    **Supervisor:** Ms. Seemab Ayub  
    **Institution:** FAST-NUCES Lahore
    """,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)



# MIDDLEWARE


# Rate limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=settings.ALLOWED_METHODS,
    allow_headers=settings.ALLOWED_HEADERS,
)


# Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log all requests
    logger.info(f"{request.method} {request.url.path}")

    try:
        response = await call_next(request)
        logger.info(f"{request.method} {request.url.path} - {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"{request.method} {request.url.path} - ERROR: {e}")
        raise

# EXCEPTION HANDLERS

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    
    # Handle validation errors
    
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "code": error["type"],
                "message": error["msg"],
                "field": ".".join(str(loc) for loc in error["loc"]),
            }
        )

    logger.warning(f"Validation error: {errors}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "detail": "Request validation failed",
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    
    # Handle general exceptions
    
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    if settings.DEBUG:
        detail = str(exc)
    else:
        detail = "Internal server error"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "detail": detail,
        },
    )



# ROUTES


# Include API router
app.include_router(router, prefix=settings.API_V1_PREFIX, tags=["API"])


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    
    # Root endpoint
    
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs" if settings.DEBUG else "disabled",
        "api": settings.API_V1_PREFIX,
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting server directly...")

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD and settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
