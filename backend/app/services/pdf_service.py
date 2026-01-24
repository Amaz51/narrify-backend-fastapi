# Handles PDF text extraction and chapter detection.
# Uses PyMuPDF (fitz) for robust PDF processing.

import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Tuple

import fitz  # PyMuPDF
from loguru import logger

from app.config import settings
from app.models.schemas import Chapter, PDFDocument


class PDFService:
    
    #Extracts text from PDFs and detects chapters automatically.

    def __init__(self):
        # Initialize PDF service
        self.logger = logger.bind(name=__name__)
        self.upload_dir = settings.UPLOAD_DIR
        self.cache_dir = settings.CACHE_DIR
        self.chapter_patterns = [re.compile(p) for p in settings.CHAPTER_PATTERNS]

    async def extract_text(self, pdf_path: Path) -> Tuple[str, Dict, int]:
        
        # Extract all text from PDF
        
        try:
            self.logger.info(f"Extracting text from: {pdf_path}")

            # Open PDF
            doc = fitz.open(pdf_path)
            page_count = len(doc)

            # Extract metadata
            metadata = {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "creator": doc.metadata.get("creator", ""),
                "producer": doc.metadata.get("producer", ""),
                "creation_date": doc.metadata.get("creationDate", ""),
                "mod_date": doc.metadata.get("modDate", ""),
            }

            # Extract text from all pages
            text_content = ""
            for page_num in range(page_count):
                page = doc[page_num]
                text = page.get_text("text")
                text_content += f"\n\n--- Page {page_num + 1} ---\n\n{text}"

            doc.close()

            self.logger.info(
                f"Extracted {len(text_content)} characters from {page_count} pages"
            )

            return text_content, metadata, page_count

        except Exception as e:
            self.logger.error(f"Failed to extract text from PDF: {e}")
            raise Exception(f"PDF extraction failed: {str(e)}")

    def detect_chapters(
        self, text: str, min_length: Optional[int] = None
    ) -> List[Chapter]:
        
        # Detect chapters in text using pattern matching
        # Args: text: Full text content
        if min_length is None:
            min_length = settings.MIN_CHAPTER_LENGTH

        self.logger.info("Detecting chapters...")

        chapters = []
        lines = text.split("\n")

        current_chapter_title = None
        current_chapter_content = []
        current_chapter_start = None
        chapter_id = 0

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Check if line matches chapter pattern
            is_chapter_heading = any(
                pattern.match(line_stripped) for pattern in self.chapter_patterns
            )

            if is_chapter_heading:
                # Save previous chapter if exists
                if current_chapter_title and current_chapter_content:
                    content = "\n".join(current_chapter_content).strip()
                    if len(content) >= min_length:
                        chapter_id += 1
                        chapters.append(
                            Chapter(
                                id=chapter_id,
                                title=current_chapter_title,
                                content=content,
                                word_count=len(content.split()),
                                start_page=self._extract_page_number(
                                    current_chapter_start
                                ),
                            )
                        )
                        self.logger.debug(f"Found chapter: {current_chapter_title}")

                # Start new chapter
                current_chapter_title = line_stripped
                current_chapter_content = []
                current_chapter_start = line_stripped

            elif current_chapter_title:
                # Add content to current chapter
                if line_stripped:  # Skip empty lines
                    current_chapter_content.append(line_stripped)

        # Add final chapter
        if current_chapter_title and current_chapter_content:
            content = "\n".join(current_chapter_content).strip()
            if len(content) >= min_length:
                chapter_id += 1
                chapters.append(
                    Chapter(
                        id=chapter_id,
                        title=current_chapter_title,
                        content=content,
                        word_count=len(content.split()),
                        start_page=self._extract_page_number(current_chapter_start),
                    )
                )

        # If no chapters detected, create single chapter from all content
        if not chapters:
            self.logger.warning("No chapters detected, creating single chapter")
            clean_text = text.strip()
            if len(clean_text) >= min_length:
                chapters.append(
                    Chapter(
                        id=1,
                        title="Full Document",
                        content=clean_text,
                        word_count=len(clean_text.split()),
                        start_page=1,
                    )
                )

        self.logger.info(f"Detected {len(chapters)} chapters")
        return chapters

    def _extract_page_number(self, text: str) -> Optional[int]:
        
        # Extract page number from text
        match = re.search(r"--- Page (\d+) ---", text)
        if match:
            return int(match.group(1))
        return None

    async def process_pdf(self, file_path: Path) -> PDFDocument:
        
        # Complete PDF processing pipeline
        # PDFDocument object with all extracted data
        
        try:
            self.logger.info(f"Processing PDF: {file_path}")

            # Generate file ID
            file_id = str(uuid.uuid4())[:12]

            # Extract text and metadata
            text_content, metadata, pages = await self.extract_text(file_path)

            # Create document object
            doc = PDFDocument(
                file_id=file_id,
                filename=file_path.name,
                file_path=str(file_path),
                text_content=text_content,
                metadata=metadata,
                pages=pages,
            )

            self.logger.info(f"PDF processed successfully: {file_id}")
            return doc

        except Exception as e:
            self.logger.error(f"Failed to process PDF: {e}")
            raise

    def get_chapter_by_id(
        self, chapters: List[Chapter], chapter_id: int
    ) -> Optional[Chapter]:
        
        # Get specific chapter by ID
        
        for chapter in chapters:
            if chapter.id == chapter_id:
                return chapter
        return None

    def estimate_duration(self, word_count: int, speed: float = 1.0) -> float:
        
        # Estimate audio duration(seconds) based on word count
        
        words_per_minute = 150 * speed
        duration_minutes = word_count / words_per_minute
        duration_seconds = duration_minutes * 60
        return round(duration_seconds, 2)

    def validate_pdf(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        
        # Validate PDF file

        try:
            # Check file exists
            if not file_path.exists():
                return False, "File does not exist"

            # Check file size
            file_size = file_path.stat().st_size
            if file_size > settings.MAX_UPLOAD_SIZE:
                max_size_mb = settings.MAX_UPLOAD_SIZE / (1024 * 1024)
                return False, f"File too large (max {max_size_mb}MB)"

            # Check if valid PDF
            try:
                doc = fitz.open(file_path)
                page_count = len(doc)
                doc.close()

                if page_count == 0:
                    return False, "PDF has no pages"

            except Exception as e:
                return False, f"Invalid PDF file: {str(e)}"

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    async def save_upload(self, file_content: bytes, filename: str) -> Path:
        
        # Save uploaded file
        # file_content: Raw file bytes
        # filename: Original filename
        
        try:
            # Generate unique filename
            file_id = str(uuid.uuid4())[:12]
            safe_filename = f"{file_id}_{filename}"
            file_path = self.upload_dir / safe_filename

            # Save file
            with open(file_path, "wb") as f:
                f.write(file_content)

            self.logger.info(f"File saved: {file_path}")
            return file_path

        except Exception as e:
            self.logger.error(f"Failed to save upload: {e}")
            raise Exception(f"File save failed: {str(e)}")

    def cleanup_old_files(self, days: int = 7) -> int:
        
        # Clean up old uploaded files
        # days: Delete files older than this many days
        # Returns: Number of files deleted
        
        import time

        deleted_count = 0
        cutoff_time = time.time() - (days * 24 * 60 * 60)

        for file_path in self.upload_dir.glob("*.pdf"):
            if file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()
                deleted_count += 1
                self.logger.debug(f"Deleted old file: {file_path}")

        if deleted_count > 0:
            self.logger.info(f"Cleaned up {deleted_count} old files")

        return deleted_count


# SINGLETON INSTANCE

pdf_service = PDFService()

__all__ = ["PDFService", "pdf_service"]
