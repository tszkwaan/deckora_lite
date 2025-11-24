"""
Cache manager for serialization caching.
Extracted from PipelineOrchestrator to follow Single Responsibility Principle.
"""

from typing import Dict, Optional, Any


class CacheManager:
    """
    Manages caching of serialized data for performance optimization.
    """
    
    def __init__(self):
        """Initialize cache manager with empty cache."""
        self._cache: Dict[str, Any] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found
        """
        return self._cache.get(key)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = value
    
    def has(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
        
        Returns:
            True if key exists, False otherwise
        """
        return key in self._cache
    
    def invalidate(self, key_prefix: Optional[str] = None) -> None:
        """
        Invalidate cache entries.
        
        Args:
            key_prefix: If provided, invalidate all keys starting with this prefix.
                       If None, clear entire cache.
        """
        if key_prefix:
            # Remove specific key and related keys
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(key_prefix)]
            for k in keys_to_remove:
                self._cache.pop(k, None)
        else:
            # Clear all cache
            self._cache.clear()
    
    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()

