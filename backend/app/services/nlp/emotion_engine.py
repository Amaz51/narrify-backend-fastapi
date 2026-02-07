"""
Emotion Detection Service
Implements GoEmotions (BERT-based) emotion detection
Maps emotions to prosody parameters
"""

from typing import Dict, Tuple
from transformers import pipeline
from loguru import logger

from app.config import settings


class EmotionService:
    """
    Emotion Intelligence Service
    
    Requirements from PDF Section 3.8:
    - Use GoEmotions (BERT-based) model
    - Map to: happy, sad, serious, neutral
    - Apply prosody settings during TTS
    """
    
    # Emotion → Prosody mapping (from PDF Section 3.8.4)
    EMOTION_PROSODY_MAP = {
        "neutral": {"pitch": 1.0, "speed": 1.0, "energy": 1.0},
        "happy":   {"pitch": 1.2, "speed": 1.1, "energy": 1.2},
        "sad":     {"pitch": 0.8, "speed": 0.9, "energy": 0.8},
        "serious": {"pitch": 0.9, "speed": 1.0, "energy": 1.1},
    }
    
    def __init__(self):
        self.logger = logger.bind(name=__name__)
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load GoEmotions model"""
        try:
            self.logger.info(f"Loading emotion model: {settings.EMOTION_MODEL}")
            
            self.model = pipeline(
                "text-classification",
                model=settings.EMOTION_MODEL,
                top_k=None,  # Return all emotion scores
                device=-1,   # CPU (change to 0 for GPU)
            )
            
            self.logger.info("Emotion model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to load emotion model: {e}")
            self.logger.warning("Emotion detection will be disabled")
    
    def detect_emotion(self, text: str) -> str:
        """
        Detect emotion from text
        
        Args:
            text: Input text
            
        Returns:
            Emotion label: "happy", "sad", "serious", or "neutral"
        """
        if not self.model or not text.strip():
            return "neutral"
        
        try:
            # Get predictions
            results = self.model(text[:512])  # Limit to 512 chars
            
            # Find highest scoring emotion
            if results and len(results) > 0:
                top_emotion = max(results[0], key=lambda x: x['score'])
                raw_label = top_emotion['label']
                
                # Map to our categories (from PDF Section 3.8.3)
                mapped_emotion = self._map_emotion(raw_label)
                
                self.logger.debug(
                    f"Detected emotion: {raw_label} -> {mapped_emotion} "
                    f"(confidence: {top_emotion['score']:.2f})"
                )
                
                return mapped_emotion
            
            return "neutral"
            
        except Exception as e:
            self.logger.error(f"Emotion detection failed: {e}")
            return "neutral"
    
    def _map_emotion(self, label: str) -> str:
        """
        Map GoEmotions labels to our 4 categories
        
        Requirement from PDF Section 3.8.3:
        - joy, excitement → happy
        - sadness, grief → sad  
        - anger, fear → serious
        - else → neutral
        """
        label_lower = label.lower()
        
        # Happy emotions
        if label_lower in ["joy", "amusement", "excitement", "love", "optimism", 
                          "admiration", "approval", "caring", "gratitude", "relief"]:
            return "happy"
        
        # Sad emotions
        elif label_lower in ["sadness", "grief", "disappointment", "remorse", 
                            "embarrassment", "nervousness"]:
            return "sad"
        
        # Serious emotions
        elif label_lower in ["anger", "annoyance", "disapproval", "fear", 
                            "disgust", "confusion"]:
            return "serious"
        
        # Neutral
        else:
            return "neutral"
    
    def get_prosody_settings(self, emotion: str) -> Dict[str, float]:
        """
        Get prosody settings for emotion
        
        Requirement: Apply prosody parameters during TTS inference
        
        Args:
            emotion: Emotion label
            
        Returns:
            Dict with pitch, speed, energy multipliers
        """
        return self.EMOTION_PROSODY_MAP.get(emotion, self.EMOTION_PROSODY_MAP["neutral"])
    
    def analyze_text_with_prosody(self, text: str) -> Tuple[str, Dict[str, float]]:
        """
        Detect emotion and return prosody settings
        
        Returns:
            Tuple of (emotion_label, prosody_settings)
        """
        emotion = self.detect_emotion(text)
        prosody = self.get_prosody_settings(emotion)
        
        return emotion, prosody


# Global instance
emotion_service = EmotionService()

__all__ = ["EmotionService", "emotion_service"]