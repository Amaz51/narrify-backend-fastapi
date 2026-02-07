"""
NLP Services Package
Handles all natural language processing tasks
"""

from .dialogue_service import dialogue_service
from .speaker_service import speaker_service
from .emotion_engine import emotion_service

__all__ = [
    "dialogue_service",
    "speaker_service", 
    "emotion_service",
]