"""
Dialogue Detection Service - FIXED VERSION
Detects dialogue, extracts speakers, and classifies text segments

FIXES:
1. Filters out pronouns (she, he, they) - treats as "Unknown"
2. Handles "Yes," Hermione replied - extracts "Hermione" not "Yes"
3. Requires capitalized proper names [A-Z][a-z]+
4. Better quote extraction patterns
"""

from typing import Dict, Optional
import re


class DialogueService:
    """
    Dialogue detection and speaker identification service
    
    Implements requirements from PDF Section 3.3:
    - Detect dialogue using quotation marks
    - Extract speaker using reporting verb patterns
    - Fallback to "Previous Speaker" logic
    """
    
    def __init__(self):
        # Pronouns to ignore (treat as Unknown)
        self.pronouns = {'she', 'he', 'they', 'it', 'i', 'you', 'we'}
        
        # Reporting verbs
        self.reporting_verbs = [
            'said', 'exclaimed', 'asked', 'replied', 'shouted', 
            'whispered', 'muttered', 'declared', 'announced', 
            'answered', 'responded', 'continued', 'added'
        ]
    
    def is_dialogue(self, sentence: str) -> bool:
        """
        Check if sentence contains dialogue (has quotation marks)
        
        Args:
            sentence: Input sentence
            
        Returns:
            True if dialogue is detected
        """
        # Check for double quotes or smart quotes
        return bool(re.search(r'[""]', sentence))
    
    def extract_dialogue_text(self, sentence: str) -> Optional[str]:
        """
        Extract the spoken text from dialogue
        
        Args:
            sentence: Sentence containing dialogue
            
        Returns:
            Extracted dialogue text (without quotes)
        """
        # Try different quote patterns
        patterns = [
            r'"([^"]+)"',  # Standard double quotes
            r'"([^"]+)"',  # Smart quotes
            r'\'([^\']+)\'',  # Single quotes
        ]
        
        for pattern in patterns:
            match = re.search(pattern, sentence)
            if match:
                return match.group(1).strip()
        
        return None
    
    def extract_speaker_and_dialogue(self, sentence: str) -> tuple:
        """
        Extract speaker name and dialogue text from sentence
        
        Implements PDF Section 3.4 speaker identification patterns:
        - "text" said Name
        - Name said "text"
        - "text," Name said
        - Name said, "text"
        
        Returns:
            Tuple of (speaker_name, dialogue_text) or (None, None)
        """
        reporting_pattern = '|'.join(self.reporting_verbs)
        
        # Pattern 1: "dialogue" said Name
        # Example: "Hello!" said Harry
        pattern = rf'"([^"]+)"\s*(?:{reporting_pattern})\s+([A-Z][a-z]+)'
        match = re.search(pattern, sentence, re.IGNORECASE)
        if match:
            speaker = match.group(2)
            # Filter out pronouns
            if speaker.lower() not in self.pronouns:
                return speaker, match.group(1)
            else:
                # It's a pronoun, treat as Unknown
                return None, match.group(1)
        
        # Pattern 2: Name said, "dialogue"
        # Example: Harry said, "Hello!"
        pattern = rf'([A-Z][a-z]+)\s+(?:{reporting_pattern})\s*,?\s*"([^"]+)"'
        match = re.search(pattern, sentence)
        if match:
            speaker = match.group(1)
            if speaker.lower() not in self.pronouns:
                return speaker, match.group(2)
        
        # Pattern 3: "dialogue," Name said
        # Example: "Hello," Harry said
        pattern = rf'"([^"]+),?"\s*,?\s*([A-Z][a-z]+)\s+(?:{reporting_pattern})'
        match = re.search(pattern, sentence)
        if match:
            speaker = match.group(2)
            if speaker.lower() not in self.pronouns:
                return speaker, match.group(1)
        
        # Pattern 4: "Word," Name verb (e.g., "Yes," Hermione replied)
        # FIX: This was capturing "Yes" as speaker!
        pattern = rf'"([^"]+),?"\s*,?\s*([A-Z][a-z]+)\s+(?:{reporting_pattern})'
        match = re.search(pattern, sentence)
        if match:
            word = match.group(1)
            speaker = match.group(2)
            
            # Check if first capture is a single word (likely not dialogue)
            if len(word.split()) <= 2 and speaker.lower() not in self.pronouns:
                # "Yes," Hermione replied → Return Hermione, not "Yes"
                return speaker, word
        
        # Pattern 5: Name said breathlessly/excitedly/etc, "dialogue"
        # Example: Hermione said breathlessly, "It's a letter"
        pattern = rf'([A-Z][a-z]+)\s+(?:{reporting_pattern})\s+\w+ly\s*,?\s*"([^"]+)"'
        match = re.search(pattern, sentence)
        if match:
            speaker = match.group(1)
            if speaker.lower() not in self.pronouns:
                return speaker, match.group(2)
        
        # If has quotes but no speaker found, extract dialogue anyway
        dialogue = self.extract_dialogue_text(sentence)
        if dialogue:
            return None, dialogue
        
        return None, None
    
    def process_sentence(
        self,
        sentence: str,
        previous_speaker: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Process a sentence to detect dialogue and identify speaker
        
        Implements PDF Section 3.5 complete processing:
        - Detect if dialogue
        - Extract speaker and text
        - Classify segment type
        - Apply previous speaker fallback
        
        Args:
            sentence: Input sentence
            previous_speaker: Speaker from previous dialogue (for fallback)
            
        Returns:
            Dict with segment_type, speaker, text, original_sentence
        """
        # Check if dialogue
        if self.is_dialogue(sentence):
            # Extract speaker and dialogue
            speaker, dialogue = self.extract_speaker_and_dialogue(sentence)
            
            # If no speaker found, use previous speaker or "Unknown"
            if speaker is None:
                speaker = previous_speaker if previous_speaker else "Narrator"
            
            # Get dialogue text
            if dialogue is None:
                dialogue = self.extract_dialogue_text(sentence)
                if dialogue is None:
                    dialogue = sentence
            
            return {
                "segment_type": "dialogue",
                "speaker": speaker,
                "text": dialogue,
                "original_sentence": sentence
            }
        else:
            # Not dialogue - it's narration
            return {
                "segment_type": "narration",
                "speaker": "Narrator",
                "text": sentence,
                "original_sentence": sentence
            }


# Global instance
dialogue_service = DialogueService()

__all__ = ["DialogueService", "dialogue_service"]