# """
# Emotion Detection Service
# Implements GoEmotions (BERT-based) emotion detection
# Maps emotions to prosody parameters
# """

# from typing import Dict, Tuple
# from transformers import pipeline
# from loguru import logger

# from app.config import settings


# class EmotionService:
#     """
#     Emotion Intelligence Service
    
#     Requirements from PDF Section 3.8:
#     - Use GoEmotions (BERT-based) model
#     - Map to: happy, sad, serious, neutral
#     - Apply prosody settings during TTS
#     """
    
#     # Emotion → Prosody mapping (from PDF Section 3.8.4)
#     # ENHANCED: Added romantic, passionate, tender, sensual emotions for romantic content
#     EMOTION_PROSODY_MAP = {
#         # Neutral & Calm
#         "neutral": {"pitch": 1.0, "speed": 1.0, "energy": 1.0},
#         "calm": {"pitch": 0.95, "speed": 0.95, "energy": 0.9},
#         "serious": {"pitch": 0.9, "speed": 1.0, "energy": 1.1},
        
#         # Positive emotions - higher, faster, more energy
#         "happy": {"pitch": 1.2, "speed": 1.1, "energy": 1.2},
#         "excited": {"pitch": 1.35, "speed": 1.25, "energy": 1.4},
#         "joyful": {"pitch": 1.25, "speed": 1.15, "energy": 1.3},
        
#         # Romantic emotions - NEW! Soft, warm, intimate
#         "romantic": {"pitch": 1.1, "speed": 0.9, "energy": 1.1},
#         "passionate": {"pitch": 1.2, "speed": 1.1, "energy": 1.35},
#         "tender": {"pitch": 0.95, "speed": 0.85, "energy": 0.9},
#         "love": {"pitch": 1.05, "speed": 0.95, "energy": 1.1},
#         "sensual": {"pitch": 0.95, "speed": 0.8, "energy": 1.0},
#         "longing": {"pitch": 0.9, "speed": 0.85, "energy": 0.85},
        
#         # Negative emotions - slower, lower, softer
#         "sad": {"pitch": 0.8, "speed": 0.9, "energy": 0.8},
#         "heartbroken": {"pitch": 0.75, "speed": 0.7, "energy": 0.6},
#         "disappointed": {"pitch": 0.85, "speed": 0.85, "energy": 0.75},
        
#         # Tension emotions
#         "nervous": {"pitch": 1.1, "speed": 1.15, "energy": 1.05},
#         "anxious": {"pitch": 1.15, "speed": 1.2, "energy": 1.15},
#         "angry": {"pitch": 1.25, "speed": 1.25, "energy": 1.4},
#         "fear": {"pitch": 1.2, "speed": 1.2, "energy": 1.25},
#     }
    
#     def __init__(self):
#         self.logger = logger.bind(name=__name__)
#         self.model = None
#         self._load_model()
    
#     def _load_model(self):
#         """Load GoEmotions model"""
#         try:
#             self.logger.info(f"Loading emotion model: {settings.EMOTION_MODEL}")
            
#             self.model = pipeline(
#                 "text-classification",
#                 model=settings.EMOTION_MODEL,
#                 top_k=None,  # Return all emotion scores
#                 device=-1,   # CPU (change to 0 for GPU)
#             )
            
#             self.logger.info("Emotion model loaded successfully")
            
#         except Exception as e:
#             self.logger.error(f"Failed to load emotion model: {e}")
#             self.logger.warning("Emotion detection will be disabled")
    
#     def detect_emotion(self, text: str) -> str:
#         """
#         Detect emotion from text
        
#         Args:
#             text: Input text
            
#         Returns:
#             Emotion label: "happy", "sad", "serious", or "neutral"
#         """
#         if not self.model or not text.strip():
#             return "neutral"
        
#         try:
#             # Get predictions
#             results = self.model(text[:512])  # Limit to 512 chars
            
#             # Find highest scoring emotion
#             if results and len(results) > 0:
#                 top_emotion = max(results[0], key=lambda x: x['score'])
#                 raw_label = top_emotion['label']
                
#                 # Map to our categories (from PDF Section 3.8.3)
#                 mapped_emotion = self._map_emotion(raw_label)
                
#                 self.logger.debug(
#                     f"Detected emotion: {raw_label} -> {mapped_emotion} "
#                     f"(confidence: {top_emotion['score']:.2f})"
#                 )
                
#                 return mapped_emotion
            
#             return "neutral"
            
#         except Exception as e:
#             self.logger.error(f"Emotion detection failed: {e}")
#             return "neutral"
    
#     def _map_emotion(self, label: str) -> str:
#         """
#         Map GoEmotions labels to our 4 categories
        
#         Requirement from PDF Section 3.8.3:
#         - joy, excitement → happy
#         - sadness, grief → sad  
#         - anger, fear → serious
#         - else → neutral
#         """
#         label_lower = label.lower()
        
#         # Happy emotions
#         if label_lower in ["joy", "amusement", "excitement", "love", "optimism", 
#                           "admiration", "approval", "caring", "gratitude", "relief"]:
#             return "happy"
        
#         # Sad emotions
#         elif label_lower in ["sadness", "grief", "disappointment", "remorse", 
#                             "embarrassment", "nervousness"]:
#             return "sad"
        
#         # Serious emotions
#         elif label_lower in ["anger", "annoyance", "disapproval", "fear", 
#                             "disgust", "confusion"]:
#             return "serious"
        
#         # Neutral
#         else:
#             return "neutral"
    
#     def get_prosody_settings(self, emotion: str) -> Dict[str, float]:
#         """
#         Get prosody settings for emotion
        
#         Requirement: Apply prosody parameters during TTS inference
        
#         Args:
#             emotion: Emotion label
            
#         Returns:
#             Dict with pitch, speed, energy multipliers
#         """
#         return self.EMOTION_PROSODY_MAP.get(emotion, self.EMOTION_PROSODY_MAP["neutral"])
    
#     def get_prosody_with_intensity(
#         self, 
#         emotion: str, 
#         intensity: float = 1.0
#     ) -> Dict[str, float]:
#         """
#         Get prosody settings with intensity multiplier
        
#         NEW METHOD: Allows emotional intensity control for romantic content
        
#         Args:
#             emotion: Emotion label
#             intensity: Multiplier (1.0 = normal, 1.5 = 50% more intense, 2.0 = double)
            
#         Returns:
#             Dict with adjusted pitch, speed, energy multipliers
#         """
#         base_prosody = self.get_prosody_settings(emotion)
        
#         # Apply intensity multiplier
#         # For speed: interpolate between 1.0 (neutral) and base_speed
#         # For pitch: apply direct multiplier
#         # For energy: apply direct multiplier
        
#         return {
#             "pitch": 1.0 + ((base_prosody["pitch"] - 1.0) * intensity),
#             "speed": 1.0 + ((base_prosody["speed"] - 1.0) * intensity),
#             "energy": 1.0 + ((base_prosody["energy"] - 1.0) * intensity),
#         }
    
#     def analyze_text_with_prosody(self, text: str) -> Tuple[str, Dict[str, float]]:
#         """
#         Detect emotion and return prosody settings
        
#         Returns:
#             Tuple of (emotion_label, prosody_settings)
#         """
#         emotion = self.detect_emotion(text)
#         prosody = self.get_prosody_settings(emotion)
        
#         return emotion, prosody


# # Global instance
# emotion_service = EmotionService()

# __all__ = ["EmotionService", "emotion_service"]



"""
Emotion Detection Engine with AUTOMATIC ROMANTIC ENHANCEMENT
Converts basic emotions (happy, sad) to romantic emotions (passionate, tender)
"""

from typing import Dict, Optional
from loguru import logger


class EmotionEngine:
    """
    Enhanced emotion detection with automatic romantic emotion mapping
    
    Flow:
    1. Base model detects: "happy", "sad", "neutral", etc.
    2. Context analyzer checks for romantic keywords
    3. Auto-converts: "happy" + "love" → "passionate"
    """
    
    def __init__(self):
        self.logger = logger.bind(name=__name__)
        
        # Load emotion model (existing - don't change)
        try:
            from transformers import pipeline
            self.emotion_model = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                top_k=None
            )
            self.logger.info("✅ Emotion model loaded")
        except Exception as e:
            self.logger.warning(f"Emotion model loading failed: {e}")
            self.emotion_model = None
        
        # Romantic keyword dictionaries
        self.romantic_keywords = {
            'passionate': ['love', 'loved', 'adore', 'passion', 'desire', 'need', 'want'],
            'tender': ['gentle', 'soft', 'tender', 'caress', 'brush', 'touch', 'stroke'],
            'longing': ['miss', 'long', 'yearn', 'ache', 'wait', 'dream', 'wish'],
            'heartbroken': ['tear', 'cry', 'weep', 'sob', 'hurt', 'pain', 'broken'],
            'breathless': ['breath', 'gasp', 'catch', 'breathless', 'pant'],
            'nervous': ['nervous', 'anxious', 'racing', 'pounding', 'trembl', 'shake'],
            'romantic': ['heart', 'soul', 'forever', 'always', 'never'],
            'sensual': ['kiss', 'lips', 'embrace', 'melt', 'tangl', 'close'],
        }
        
        # Enhanced prosody settings
        self.EMOTION_PROSODY = {
            # ========== ROMANTIC EMOTIONS ==========
            "passionate": {"speed": 1.20, "pitch": 0.35},
            "tender": {"speed": 0.85, "pitch": 0.15},
            "romantic": {"speed": 0.90, "pitch": 0.20},
            "loving": {"speed": 0.95, "pitch": 0.18},
            "longing": {"speed": 0.80, "pitch": -0.05},
            "sensual": {"speed": 0.75, "pitch": -0.08},
            "heartbroken": {"speed": 0.70, "pitch": -0.30},
            "breathless": {"speed": 1.15, "pitch": 0.25},
            
            # ========== POSITIVE EMOTIONS ==========
            "happy": {"speed": 1.25, "pitch": 0.40},
            "excited": {"speed": 1.35, "pitch": 0.50},
            "joyful": {"speed": 1.30, "pitch": 0.45},
            
            # ========== NEGATIVE EMOTIONS ==========
            "sad": {"speed": 0.75, "pitch": -0.25},
            "crying": {"speed": 0.70, "pitch": -0.20},
            
            # ========== TENSION EMOTIONS ==========
            "angry": {"speed": 1.30, "pitch": 0.40},
            "fear": {"speed": 1.25, "pitch": 0.30},
            "nervous": {"speed": 1.20, "pitch": 0.25},
            "anxious": {"speed": 1.25, "pitch": 0.28},
            
            # ========== CALM EMOTIONS ==========
            "neutral": {"speed": 1.0, "pitch": 0.0},
            "calm": {"speed": 0.95, "pitch": -0.05},
            "serious": {"speed": 0.95, "pitch": -0.10},
        }
    
    # Label mapping reused in single + batch paths
    _LABEL_MAP = {
        'joy': 'happy',
        'sadness': 'sad',
        'anger': 'angry',
        'fear': 'fear',
        'surprise': 'neutral',
        'disgust': 'serious',
        'neutral': 'neutral',
    }

    # Simple in-process emotion cache (text hash → emotion)
    _emotion_cache: dict = {}

    def detect_emotion(self, text: str) -> str:
        """
        Detect emotion with AUTOMATIC romantic enhancement.
        Results are cached by text so repeated sentences cost nothing.
        """
        if not text or len(text) < 3:
            return "neutral"

        cache_key = hash(text)
        if cache_key in self._emotion_cache:
            return self._emotion_cache[cache_key]

        base_emotion = self._get_base_emotion(text)
        enhanced = self._enhance_with_romantic_context(base_emotion, text)

        if enhanced != base_emotion:
            self.logger.debug(f"Enhanced: '{base_emotion}' → '{enhanced}' for: {text[:50]}...")

        self._emotion_cache[cache_key] = enhanced
        return enhanced

    def batch_detect_emotions(self, texts: list) -> list:
        """
        Detect emotions for ALL texts in ONE model call (5-10x faster than one-by-one).

        Returns a list of emotion strings in the same order as `texts`.
        Already-cached results are returned without hitting the model.
        """
        if not texts:
            return []

        results = ["neutral"] * len(texts)
        uncached_indices = []
        uncached_texts = []

        # Separate cached from uncached
        for i, text in enumerate(texts):
            if not text or len(text) < 3:
                results[i] = "neutral"
                continue
            key = hash(text)
            if key in self._emotion_cache:
                results[i] = self._emotion_cache[key]
            else:
                uncached_indices.append(i)
                uncached_texts.append(text[:512])  # BERT limit

        if uncached_texts and self.emotion_model:
            try:
                # Single batched call instead of N individual calls
                batch_results = self.emotion_model(uncached_texts, batch_size=16)
                for pos, idx in enumerate(uncached_indices):
                    raw = batch_results[pos]
                    top = max(raw, key=lambda x: x["score"])
                    label = top["label"]
                    confidence = top["score"]

                    base = self._LABEL_MAP.get(label.lower(), label.lower()) if confidence > 0.4 else "neutral"
                    enhanced = self._enhance_with_romantic_context(base, texts[idx])

                    self._emotion_cache[hash(texts[idx])] = enhanced
                    results[idx] = enhanced
            except Exception as e:
                self.logger.warning(f"Batch emotion detection failed, using neutral: {e}")
                for idx in uncached_indices:
                    results[idx] = "neutral"

        return results

    def _get_base_emotion(self, text: str) -> str:
        """Get basic emotion from model (single call — use batch_detect_emotions for lists)."""
        if not self.emotion_model:
            return "neutral"

        try:
            result = self.emotion_model(text[:512])

            if result and len(result) > 0 and len(result[0]) > 0:
                top_emotion = max(result[0], key=lambda x: x['score'])
                emotion_label = top_emotion['label']
                confidence = top_emotion['score']

                mapped = self._LABEL_MAP.get(emotion_label.lower(), emotion_label.lower())

                if confidence > 0.4:
                    return mapped

            return "neutral"

        except Exception as e:
            self.logger.debug(f"Emotion detection failed: {e}")
            return "neutral"
    
    def _enhance_with_romantic_context(self, base_emotion: str, text: str) -> str:
        """
        AUTOMATIC romantic emotion enhancement based on keywords
        
        This is the KEY function that converts:
        - "happy" + "love" → "passionate"
        - "neutral" + "kiss" → "sensual"
        - "sad" + "tears" → "heartbroken"
        """
        text_lower = text.lower()
        
        # Check each romantic emotion category
        for romantic_emotion, keywords in self.romantic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                
                # Context-based mapping
                if romantic_emotion == 'passionate':
                    if base_emotion in ['happy', 'excited', 'neutral']:
                        return 'passionate'
                
                elif romantic_emotion == 'tender':
                    if base_emotion in ['neutral', 'happy', 'calm']:
                        return 'tender'
                
                elif romantic_emotion == 'longing':
                    if base_emotion in ['sad', 'neutral', 'serious']:
                        return 'longing'
                
                elif romantic_emotion == 'heartbroken':
                    if base_emotion in ['sad', 'fear']:
                        return 'heartbroken'
                
                elif romantic_emotion == 'breathless':
                    if base_emotion in ['neutral', 'excited', 'fear']:
                        return 'breathless'
                
                elif romantic_emotion == 'nervous':
                    if base_emotion in ['fear', 'neutral']:
                        return 'nervous'
                
                elif romantic_emotion == 'romantic':
                    if base_emotion in ['neutral', 'happy']:
                        return 'romantic'
                
                elif romantic_emotion == 'sensual':
                    if base_emotion in ['neutral', 'happy']:
                        return 'sensual'
        
        # Special case: "I love you" always gets passionate
        if 'i love you' in text_lower or 'love you' in text_lower:
            return 'passionate'
        
        # No romantic context - return base emotion
        return base_emotion
    
    def get_prosody_settings(
        self, 
        emotion: str,
        intensity: float = 1.0
    ) -> Dict[str, float]:
        """
        Get prosody settings with intensity multiplier
        
        Args:
            emotion: Emotion label (can be romantic or basic)
            intensity: Multiplier (1.0 = normal, 2.0 = double)
        
        Returns:
            Dict with speed, pitch adjustments
        """
        emotion_lower = emotion.lower()
        
        # Get base prosody
        if emotion_lower in self.EMOTION_PROSODY:
            base = self.EMOTION_PROSODY[emotion_lower]
        else:
            self.logger.warning(f"Unknown emotion '{emotion}', using neutral")
            base = self.EMOTION_PROSODY["neutral"]
        
        # Apply intensity multiplier
        adjusted = {
            "speed": 1.0 + ((base["speed"] - 1.0) * intensity),
            "pitch": base["pitch"] * intensity,
        }
        
        return adjusted


# Global instance
emotion_service = EmotionEngine()

__all__ = ["EmotionEngine", "emotion_service"]