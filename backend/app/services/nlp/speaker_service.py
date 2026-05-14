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
    
    # Female name suffixes — heuristic for names not in the explicit dictionary.
    # These endings are strongly female-associated in English and many languages.
    _FEMALE_SUFFIXES = (
        'a', 'ia', 'ie', 'ine', 'ette', 'ina', 'elle', 'ette', 'lyn',
        'lynn', 'lyn', 'anne', 'ane', 'ene', 'yna', 'ina', 'ita',
    )

    def __init__(self):
        self.logger = logger.bind(name=__name__)

        # Comprehensive character gender mapping.
        # Covers common English names, literary characters, and names from
        # non-Western traditions frequently encountered in translated fiction.
        self.character_gender = {
            # ── Neutral / Special ──────────────────────────────────────────
            "narrator": "neutral",
            "unknown": "neutral",

            # ── Male ───────────────────────────────────────────────────────
            # Harry Potter universe
            "harry": "male", "ron": "male", "dumbledore": "male",
            "snape": "male", "draco": "male", "neville": "male",
            "hagrid": "male", "sirius": "male", "lupin": "male",
            "voldemort": "male", "malfoy": "male", "weasley": "male",
            # Common English male
            "james": "male", "john": "male", "tom": "male", "peter": "male",
            "david": "male", "michael": "male", "robert": "male",
            "william": "male", "richard": "male", "charles": "male",
            "joseph": "male", "thomas": "male", "christopher": "male",
            "daniel": "male", "matthew": "male", "anthony": "male",
            "mark": "male", "donald": "male", "steven": "male",
            "george": "male", "andrew": "male", "edward": "male",
            "henry": "male", "arthur": "male", "benjamin": "male",
            "samuel": "male", "jonathan": "male", "nicholas": "male",
            "alexander": "male", "adam": "male", "brian": "male",
            "patrick": "male", "scott": "male", "timothy": "male",
            "eric": "male", "stephen": "male", "kevin": "male",
            "paul": "male", "frank": "male", "raymond": "male",
            "gregory": "male", "jack": "male", "oliver": "male",
            "ethan": "male", "liam": "male", "noah": "male",
            "mason": "male", "logan": "male", "lucas": "male",
            "jacob": "male", "ryan": "male", "tyler": "male",
            "cole": "male", "dylan": "male", "seth": "male",
            # Literary male
            "gatsby": "male", "atticus": "male", "holden": "male",
            "heathcliff": "male", "darcy": "male", "rochester": "male",
            "pip": "male", "raskolnikov": "male", "karenin": "male",
            "levin": "male", "dorian": "male", "basil": "male",
            # Arabic / South Asian male
            "ali": "male", "ahmed": "male", "omar": "male", "hassan": "male",
            "khalid": "male", "yusuf": "male", "ibrahim": "male",
            "muhammad": "male", "amir": "male", "tariq": "male",
            "raj": "male", "arjun": "male", "vikram": "male", "rajan": "male",
            # East Asian male
            "wei": "male", "ming": "male", "jun": "male", "jae": "male",
            "hiro": "male", "kenji": "male", "takeshi": "male",
            # Spanish / Latin male
            "carlos": "male", "juan": "male", "miguel": "male",
            "antonio": "male", "pablo": "male", "luis": "male",
            "santiago": "male", "gabriel": "male", "rafael": "male",

            # ── Female ─────────────────────────────────────────────────────
            # Harry Potter universe
            "hermione": "female", "ginny": "female", "luna": "female",
            "lily": "female", "molly": "female", "minerva": "female",
            "bellatrix": "female", "narcissa": "female", "cho": "female",
            "fleur": "female", "lavender": "female",
            # Common English female
            "emma": "female", "sarah": "female", "mary": "female",
            "jennifer": "female", "elizabeth": "female", "jessica": "female",
            "linda": "female", "barbara": "female", "susan": "female",
            "karen": "female", "nancy": "female", "betty": "female",
            "helen": "female", "sandra": "female", "donna": "female",
            "carol": "female", "ruth": "female", "sharon": "female",
            "patricia": "female", "lisa": "female", "margaret": "female",
            "dorothy": "female", "diane": "female", "alice": "female",
            "anna": "female", "jane": "female", "claire": "female",
            "grace": "female", "amy": "female", "rachel": "female",
            "emily": "female", "megan": "female", "hannah": "female",
            "charlotte": "female", "sophie": "female", "victoria": "female",
            "olivia": "female", "isabelle": "female", "claire": "female",
            "eleanor": "female", "diana": "female", "julia": "female",
            "kate": "female", "ella": "female", "chloe": "female",
            "zoe": "female", "lucy": "female", "mia": "female",
            "eliza": "female", "natasha": "female", "stella": "female",
            "vera": "female", "nina": "female", "iris": "female",
            "rose": "female", "violet": "female", "daisy": "female",
            "amber": "female", "ruby": "female", "scarlett": "female",
            # Literary female
            "elizabeth": "female", "jane": "female", "emma": "female",
            "dorothy": "female", "lydia": "female", "anne": "female",
            "ophelia": "female", "juliet": "female", "desdemona": "female",
            "portia": "female", "beatrice": "female", "rosalind": "female",
            "anna": "female", "natasha": "female", "kitty": "female",
            # Arabic / South Asian female
            "fatima": "female", "aisha": "female", "sara": "female",
            "nadia": "female", "layla": "female", "yasmin": "female",
            "priya": "female", "anjali": "female", "kavya": "female",
            "deepa": "female", "meena": "female", "sunita": "female",
            # East Asian female
            "mei": "female", "xiao": "female", "yuki": "female",
            "sakura": "female", "hana": "female", "akiko": "female",
            "keiko": "female", "yuna": "female",
            # Spanish / Latin female
            "maria": "female", "elena": "female", "isabella": "female",
            "sofia": "female", "valentina": "female", "gabriela": "female",
            "lucia": "female", "camila": "female", "ana": "female",
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
            # Suffix heuristic for names not in the dictionary.
            # Many female names end in vowel-rich suffixes; many male names end
            # in consonants. This is imperfect but far better than always
            # defaulting to neutral for novel characters and non-Western names.
            if name_lower.endswith(self._FEMALE_SUFFIXES):
                gender = "female"
                self.logger.debug(
                    f"Gender inferred by suffix: '{speaker_name}' → female"
                )
            elif len(name_lower) >= 3 and name_lower[-1] not in 'aeiou':
                gender = "male"
                self.logger.debug(
                    f"Gender inferred by suffix: '{speaker_name}' → male"
                )
            else:
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