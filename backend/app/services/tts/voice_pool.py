"""
Voice Pool Service
Manages voice embeddings cache for efficient multi-speaker generation

Requirement from PDF Section 3.9:
- Cache speaker embeddings for "Voice Pools" (Narrator, Male, Female)
- Reduce compute by reusing embeddings
"""

from pathlib import Path
from typing import Dict, Optional
import pickle
from loguru import logger

from app.config import settings


class VoicePoolService:
    """
    Voice embedding cache manager
    
    Caches extracted speaker embeddings to avoid recomputation
    Particularly important for multi-speaker audiobooks where same
    voices are used repeatedly
    """
    
    def __init__(self):
        self.logger = logger.bind(name=__name__)
        self.cache_dir = settings.CACHE_DIR / "voice_embeddings"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache
        self._embedding_cache: Dict[str, any] = {}
    
    def get_embedding(self, voice_id: str) -> Optional[any]:
        """
        Get cached embedding for voice
        
        Args:
            voice_id: Voice identifier
            
        Returns:
            Cached embedding or None
        """
        # Check memory cache first
        if voice_id in self._embedding_cache:
            self.logger.debug(f"Embedding cache HIT (memory): {voice_id}")
            return self._embedding_cache[voice_id]
        
        # Check disk cache
        cache_file = self.cache_dir / f"{voice_id}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    embedding = pickle.load(f)
                
                # Store in memory
                self._embedding_cache[voice_id] = embedding
                
                self.logger.debug(f"Embedding cache HIT (disk): {voice_id}")
                return embedding
                
            except Exception as e:
                self.logger.error(f"Failed to load cached embedding: {e}")
        
        self.logger.debug(f"Embedding cache MISS: {voice_id}")
        return None
    
    def cache_embedding(self, voice_id: str, embedding: any):
        """
        Cache embedding for voice
        
        Args:
            voice_id: Voice identifier
            embedding: Embedding data to cache
        """
        try:
            # Store in memory
            self._embedding_cache[voice_id] = embedding
            
            # Store on disk
            cache_file = self.cache_dir / f"{voice_id}.pkl"
            with open(cache_file, 'wb') as f:
                pickle.dump(embedding, f)
            
            self.logger.debug(f"Cached embedding: {voice_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to cache embedding: {e}")
    
    def clear_cache(self, voice_id: Optional[str] = None):
        """
        Clear cached embeddings
        
        Args:
            voice_id: Specific voice to clear, or None for all
        """
        if voice_id:
            # Clear specific voice
            if voice_id in self._embedding_cache:
                del self._embedding_cache[voice_id]
            
            cache_file = self.cache_dir / f"{voice_id}.pkl"
            if cache_file.exists():
                cache_file.unlink()
            
            self.logger.info(f"Cleared cache for: {voice_id}")
        else:
            # Clear all
            self._embedding_cache.clear()
            
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
            
            self.logger.info("Cleared all voice embedding cache")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        memory_count = len(self._embedding_cache)
        disk_count = len(list(self.cache_dir.glob("*.pkl")))
        
        return {
            "memory_cached": memory_count,
            "disk_cached": disk_count,
            "cache_dir": str(self.cache_dir)
        }


# Global instance
voice_pool = VoicePoolService()

__all__ = ["VoicePoolService", "voice_pool"]