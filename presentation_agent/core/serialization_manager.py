"""
Serialization manager - manages serialization and caching of pipeline outputs.
"""

from typing import Dict, Any, Optional

from presentation_agent.core.serialization_service import SerializationService
from presentation_agent.core.cache_manager import CacheManager


class SerializationManager:
    """
    Manages serialization and caching of pipeline outputs.
    Provides cached serialization for performance optimization.
    
    This class centralizes the logic for serializing pipeline outputs (like report_knowledge,
    presentation_outline) with caching to avoid redundant serialization operations.
    """
    
    def __init__(
        self,
        serialization_service: SerializationService,
        cache_manager: CacheManager,
        outputs: Dict[str, Any]
    ):
        """
        Initialize the serialization manager.
        
        Args:
            serialization_service: Service for JSON serialization
            cache_manager: Cache manager for storing serialized results
            outputs: Reference to orchestrator's outputs dictionary
        """
        self.serialization_service = serialization_service
        self.cache_manager = cache_manager
        self.outputs = outputs  # Reference to orchestrator's outputs
    
    def get_serialized(
        self,
        key: str,
        pretty: bool = False
    ) -> str:
        """
        Get serialized output with caching.
        
        This method serializes pipeline outputs (like report_knowledge, presentation_outline)
        and caches the result for performance. Subsequent calls with the same key and format
        will return the cached value.
        
        Args:
            key: Output key (e.g., 'report_knowledge', 'presentation_outline')
            pretty: If True, use indent=2 for pretty printing (for logs).
                   If False, use compact format (for agent messages).
        
        Returns:
            Serialized JSON string
        
        Raises:
            ValueError: If key not available in outputs
        """
        cache_key = f"{key}_{'pretty' if pretty else 'compact'}"
        
        if not self.cache_manager.has(cache_key):
            data = self.outputs.get(key)
            if data is None:
                raise ValueError(f"{key} not available in outputs")
            
            serialized = self.serialization_service.serialize(data, pretty=pretty)
            self.cache_manager.set(cache_key, serialized)
        
        return self.cache_manager.get(cache_key)
    
    def invalidate(self, key: Optional[str] = None):
        """
        Invalidate serialization cache when data changes.
        
        This should be called whenever an output value is updated to ensure
        subsequent serialization uses the latest data.
        
        Args:
            key: Specific cache key to invalidate, or None to clear all
        """
        self.cache_manager.invalidate(key_prefix=key)
    
    # Convenience methods for common keys (for backward compatibility and clarity)
    def get_serialized_report_knowledge(self, pretty: bool = False) -> str:
        """
        Get serialized report_knowledge with caching.
        
        Args:
            pretty: If True, use indent=2 for pretty printing (for logs).
                   If False, use compact format (for agent messages).
        
        Returns:
            Serialized JSON string
        """
        return self.get_serialized("report_knowledge", pretty=pretty)
    
    def get_serialized_presentation_outline(self, pretty: bool = False) -> str:
        """
        Get serialized presentation_outline with caching.
        
        Args:
            pretty: If True, use indent=2 for pretty printing (for logs).
                   If False, use compact format (for agent messages).
        
        Returns:
            Serialized JSON string
        """
        return self.get_serialized("presentation_outline", pretty=pretty)

