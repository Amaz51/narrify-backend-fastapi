"""
Speaker Gender Inference Service
Implements requirement: Name-based gender mapping
"""

from typing import Dict
from loguru import logger


class SpeakerService:
    """
    Gender inference and speaker management
    
    Requirement from PDF Section 3.6:
    - Assign male, female, or neutral voices
    - Name-based mapping (no ML required)
    """
    
    def __init__(self):
        self.logger = logger.bind(name=__name__)
        
        # Character gender mapping (from PDF example)
        self.character_gender = {
            # From PDF examples
            "harry": "male",
            "hermione": "female",
            "narrator": "neutral",
            
            # Extended common names - Male
            "ron": "male",
            "james": "male",
            "john": "male",
            "tom": "male",
            "peter": "male",
            "david": "male",
            "michael": "male",
            "robert": "male",
            "william": "male",
            "richard": "male",
            "charles": "male",
            "joseph": "male",
            "thomas": "male",
            "christopher": "male",
            "daniel": "male",
            "matthew": "male",
            "anthony": "male",
            "mark": "male",
            "donald": "male",
            "steven": "male",
            
            # Extended common names - Female  
            "ginny": "female",
            "lily": "female",
            "emma": "female",
            "sarah": "female",
            "mary": "female",
            "jennifer": "female",
            "elizabeth": "female",
            "jessica": "female",
            "linda": "female",
            "barbara": "female",
            "susan": "female",
            "karen": "female",
            "nancy": "female",
            "betty": "female",
            "helen": "female",
            "sandra": "female",
            "donna": "female",
            "carol": "female",
            "ruth": "female",
            "sharon": "female",
            
            # Neutral/Special
            "unknown": "neutral",
        }
        
        # Speaker registry (tracks all speakers in current book)
        self.speaker_registry: Dict[str, str] = {}
    
    def infer_gender(self, speaker_name: str) -> str:
        """
        Infer gender from speaker name
        
        Args:
            speaker_name: Name of speaker
            
        Returns:
            Gender string: "male", "female", or "neutral"
        """
        name_lower = speaker_name.lower().strip()
        
        # Check if already registered
        if speaker_name in self.speaker_registry:
            return self.speaker_registry[speaker_name]
        
        # Check name mapping
        if name_lower in self.character_gender:
            gender = self.character_gender[name_lower]
        else:
            # Default to neutral if unknown
            gender = "neutral"
            self.logger.warning(
                f"Unknown speaker '{speaker_name}', defaulting to neutral"
            )
        
        # Register
        self.speaker_registry[speaker_name] = gender
        
        return gender
    
    def register_speaker(self, speaker_name: str, gender: str):
        """Manually register a speaker with gender"""
        self.speaker_registry[speaker_name] = gender
        self.logger.info(f"Registered speaker: {speaker_name} ({gender})")
    
    def get_all_speakers(self) -> Dict[str, str]:
        """Get all registered speakers"""
        return self.speaker_registry.copy()
    
    def reset_registry(self):
        """Reset speaker registry (for new book)"""
        self.speaker_registry = {}
        self.logger.info("Speaker registry reset")


# Global instance
speaker_service = SpeakerService()

__all__ = ["SpeakerService", "speaker_service"]