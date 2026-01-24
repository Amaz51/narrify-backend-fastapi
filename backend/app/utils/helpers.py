# Helper Utilities
# Common helper functions used throughout the application.


import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


def generate_id(prefix: str = "") -> str:
    
    #Generate unique ID
    unique_id = str(uuid.uuid4())[:12]
    if prefix:
        return f"{prefix}_{unique_id}"
    return unique_id


def get_file_hash(file_path: Path) -> str:
    """
    Calculate file hash

    Args:
        file_path: Path to file

    Returns:
        MD5 hash of file
    """
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "1h 23m 45s")
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def safe_filename(filename: str) -> str:
    """
    Create safe filename by removing invalid characters

    Args:
        filename: Original filename

    Returns:
        Safe filename
    """
    import re

    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', "", filename)
    # Replace spaces with underscores
    filename = filename.replace(" ", "_")
    # Limit length
    name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
    if len(name) > 50:
        name = name[:50]
    return f"{name}.{ext}" if ext else name


def timestamp() -> str:
    """
    Get current timestamp string

    Returns:
        ISO formatted timestamp
    """
    return datetime.utcnow().isoformat()


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def ensure_dir(path: Path) -> Path:
    """
    Ensure directory exists

    Args:
        path: Directory path

    Returns:
        Path object
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_text(text: str) -> str:
    """
    Clean text of extra whitespace

    Args:
        text: Text to clean

    Returns:
        Cleaned text
    """
    import re

    # Remove multiple spaces
    text = re.sub(r" +", " ", text)
    # Remove multiple newlines
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


__all__ = [
    "generate_id",
    "get_file_hash",
    "format_duration",
    "format_file_size",
    "safe_filename",
    "timestamp",
    "truncate_text",
    "ensure_dir",
    "clean_text",
]
