"""
NLP Engine: Deterministic Pipeline for Speaker Detection
Production-grade implementation with spaCy and rule-based NLP
"""

import re
import spacy
from typing import List, Dict, Optional, Tuple
from loguru import logger

from app.core.config import settings
from app.models.schemas import SpeakerSegment, Gender, SegmentType, EmotionLabel


class NLPEngine:
    """
    Production NLP Engine for Multi-Speaker Detection
    
    Pipeline:
    1. Sentence Segmentation (spaCy)
    2. Dialogue Detection (Quotation marks)
    3. Speaker Identification (Rule-based patterns)
    4. Gender Inference (Name-based + context)
    """
    
    def __init__(self):
        """Initialize NLP models and patterns"""
        logger.info("Initializing NLP Engine...")
        
        # Load spaCy model
        try:
            self.nlp = spacy.load(settings.SPACY_MODEL)
            logger.info(f"✅ spaCy model loaded: {settings.SPACY_MODEL}")
        except OSError:
            logger.error(f"spaCy model not found. Run: python -m spacy download {settings.SPACY_MODEL}")
            raise
        
        # Reporting verbs for speaker identification
        self.reporting_verbs = {
            'said', 'exclaimed', 'asked', 'replied', 'shouted', 'whispered',
            'muttered', 'declared', 'announced', 'answered', 'responded',
            'continued', 'added', 'remarked', 'stated', 'mentioned',
            'yelled', 'screamed', 'cried', 'laughed', 'sighed', 'growled'
        }
        
        # Pronouns to filter out (not valid speakers)
        self.pronouns = {'he', 'she', 'they', 'it', 'i', 'you', 'we', 'him', 'her', 'them'}
        
        # Common character name patterns
        self.name_indicators = {'mr', 'mrs', 'miss', 'ms', 'dr', 'professor', 'lord', 'lady'}
        
        # Gender mapping (expandable)
        self.name_gender_map = {
            # Common male names
            'harry': Gender.MALE, 'ron': Gender.MALE, 'james': Gender.MALE,
            'john': Gender.MALE, 'peter': Gender.MALE, 'tom': Gender.MALE,
            'dumbledore': Gender.MALE, 'hagrid': Gender.MALE,
            
            # Common female names
            'hermione': Gender.FEMALE, 'lily': Gender.FEMALE, 'emma': Gender.FEMALE,
            'jane': Gender.FEMALE, 'mary': Gender.FEMALE, 'alice': Gender.FEMALE,
            'ginny': Gender.FEMALE, 'luna': Gender.FEMALE,
        }
        
        # Speaker registry for consistency
        self.speaker_registry: Dict[str, Gender] = {}
        
        logger.info("✅ NLP Engine initialized successfully")
    
    def process_text(
        self,
        text: str,
        detect_speakers: bool = True,
        detect_emotions: bool = True
    ) -> List[SpeakerSegment]:
        """
        Main processing pipeline
        
        Args:
            text: Raw text from PDF
            detect_speakers: Enable speaker detection
            detect_emotions: Enable emotion detection (placeholder)
        
        Returns:
            List of SpeakerSegment objects (MANDATORY format)
        """
        logger.info(f"Processing text: {len(text)} characters")
        
        # Reset speaker registry for new document
        self.speaker_registry.clear()
        
        # Step 1: Sentence segmentation with spaCy
        sentences = self._segment_sentences(text)
        logger.info(f"Segmented into {len(sentences)} sentences")
        
        # Step 2: Process each sentence
        segments: List[SpeakerSegment] = []
        previous_speaker = "Narrator"
        
        for idx, sentence in enumerate(sentences):
            if not sentence.strip():
                continue
            
            # Detect if dialogue
            is_dialogue = self._is_dialogue(sentence)
            
            if is_dialogue and detect_speakers:
                # Extract speaker and dialogue text
                speaker, dialogue_text = self._extract_speaker_and_dialogue(sentence)
                
                # Fallback to previous speaker if not found
                if speaker is None:
                    speaker = previous_speaker
                    dialogue_text = self._extract_dialogue_text(sentence)
                
                # Infer gender
                gender = self._infer_gender(speaker)
                
                # Create segment
                segment = SpeakerSegment(
                    speaker_name=speaker,
                    gender=gender,
                    original_text=dialogue_text or sentence,
                    segment_type=SegmentType.DIALOGUE,
                    segment_index=idx,
                    emotion=EmotionLabel.NEUTRAL  # Placeholder
                )
                
                # Update previous speaker for context
                previous_speaker = speaker
            else:
                # Narration segment
                segment = SpeakerSegment(
                    speaker_name="Narrator",
                    gender=Gender.NEUTRAL,
                    original_text=sentence,
                    segment_type=SegmentType.NARRATION,
                    segment_index=idx,
                    emotion=EmotionLabel.NEUTRAL
                )
            
            segments.append(segment)
        
        logger.info(f"✅ Generated {len(segments)} segments with {len(self.speaker_registry)} unique speakers")
        
        return segments
    
    def _segment_sentences(self, text: str) -> List[str]:
        """
        Linguistically meaningful sentence segmentation using spaCy
        
        Args:
            text: Raw text
        
        Returns:
            List of sentences
        """
        # Process with spaCy
        doc = self.nlp(text)
        
        # Extract sentences
        sentences = [sent.text.strip() for sent in doc.sents]
        
        # Filter empty sentences
        sentences = [s for s in sentences if s]
        
        return sentences
    
    def _is_dialogue(self, sentence: str) -> bool:
        """
        Check if sentence contains dialogue (quotation marks)
        
        Args:
            sentence: Input sentence
        
        Returns:
            True if dialogue detected
        """
        # Check for various quotation mark styles
        return bool(re.search(r'[""]', sentence))
    
    def _extract_dialogue_text(self, sentence: str) -> Optional[str]:
        """
        Extract text within quotation marks
        
        Args:
            sentence: Sentence with quotes
        
        Returns:
            Extracted dialogue text
        """
        # Try different quote patterns
        patterns = [
            r'"([^"]+)"',   # Standard double quotes
            r'"([^"]+)"',   # Smart quotes
            r"'([^']+)'",   # Single quotes
        ]
        
        for pattern in patterns:
            match = re.search(pattern, sentence)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_speaker_and_dialogue(self, sentence: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract speaker name and dialogue using rule-based patterns
        
        Patterns:
        1. "dialogue" said Speaker
        2. Speaker said, "dialogue"
        3. "dialogue," Speaker said
        4. Speaker said breathlessly, "dialogue"
        
        Args:
            sentence: Input sentence
        
        Returns:
            Tuple of (speaker_name, dialogue_text)
        """
        # Create regex pattern with all reporting verbs
        verbs_pattern = '|'.join(self.reporting_verbs)
        
        # Pattern 1: "dialogue" verb Speaker
        # Example: "Hello!" said Harry
        pattern1 = rf'"([^"]+)"\s*(?:{verbs_pattern})\s+([A-Z][a-z]+)'
        match = re.search(pattern1, sentence, re.IGNORECASE)
        if match:
            dialogue = match.group(1)
            speaker = match.group(2)
            if speaker.lower() not in self.pronouns:
                return speaker, dialogue
        
        # Pattern 2: Speaker verb, "dialogue"
        # Example: Harry said, "Hello!"
        pattern2 = rf'([A-Z][a-z]+)\s+(?:{verbs_pattern})\s*,?\s*"([^"]+)"'
        match = re.search(pattern2, sentence)
        if match:
            speaker = match.group(1)
            dialogue = match.group(2)
            if speaker.lower() not in self.pronouns:
                return speaker, dialogue
        
        # Pattern 3: "dialogue," Speaker verb
        # Example: "Hello," Harry said
        pattern3 = rf'"([^"]+),?"\s*,?\s*([A-Z][a-z]+)\s+(?:{verbs_pattern})'
        match = re.search(pattern3, sentence)
        if match:
            dialogue = match.group(1)
            speaker = match.group(2)
            if speaker.lower() not in self.pronouns:
                return speaker, dialogue
        
        # Pattern 4: Speaker verb adverb, "dialogue"
        # Example: Hermione said breathlessly, "It's a letter"
        pattern4 = rf'([A-Z][a-z]+)\s+(?:{verbs_pattern})\s+\w+ly\s*,?\s*"([^"]+)"'
        match = re.search(pattern4, sentence)
        if match:
            speaker = match.group(1)
            dialogue = match.group(2)
            if speaker.lower() not in self.pronouns:
                return speaker, dialogue
        
        # No speaker found - extract dialogue only
        dialogue = self._extract_dialogue_text(sentence)
        return None, dialogue
    
    def _infer_gender(self, speaker_name: str) -> Gender:
        """
        Infer speaker gender from name
        
        Strategy:
        1. Check speaker registry (for consistency)
        2. Check name-gender map
        3. Default to neutral
        
        Args:
            speaker_name: Speaker name
        
        Returns:
            Gender enum
        """
        # Normalize name
        name_lower = speaker_name.lower()
        
        # Check registry first (ensures consistency)
        if speaker_name in self.speaker_registry:
            return self.speaker_registry[speaker_name]
        
        # Check name map
        if name_lower in self.name_gender_map:
            gender = self.name_gender_map[name_lower]
        elif name_lower == "narrator":
            gender = Gender.NEUTRAL
        else:
            # Default to neutral for unknown names
            gender = Gender.NEUTRAL
            logger.debug(f"Unknown name '{speaker_name}', defaulting to neutral")
        
        # Register for consistency
        self.speaker_registry[speaker_name] = gender
        
        return gender
    
    def update_gender_mapping(self, speaker_name: str, gender: Gender):
        """
        Update gender mapping for a speaker (user correction)
        
        Args:
            speaker_name: Speaker name
            gender: Corrected gender
        """
        self.speaker_registry[speaker_name] = gender
        logger.info(f"Updated gender for '{speaker_name}': {gender}")
    
    def get_speaker_stats(self) -> Dict[str, any]:
        """Get statistics about detected speakers"""
        return {
            "total_speakers": len(self.speaker_registry),
            "speakers": list(self.speaker_registry.keys()),
            "gender_distribution": {
                "male": sum(1 for g in self.speaker_registry.values() if g == Gender.MALE),
                "female": sum(1 for g in self.speaker_registry.values() if g == Gender.FEMALE),
                "neutral": sum(1 for g in self.speaker_registry.values() if g == Gender.NEUTRAL),
            }
        }


# Global instance
nlp_engine = NLPEngine()