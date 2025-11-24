"""
Serialization service for JSON serialization operations.
Extracted from PipelineOrchestrator to follow Single Responsibility Principle.
"""

import json
from typing import Any, Dict


class SerializationService:
    """
    Handles JSON serialization with support for pretty and compact formats.
    """
    
    @staticmethod
    def serialize(data: Any, pretty: bool = False) -> str:
        """
        Serialize data to JSON string.
        
        Args:
            data: Data to serialize
            pretty: If True, use indent=2 for pretty printing (for logs).
                   If False, use compact format (for agent messages).
        
        Returns:
            Serialized JSON string
        """
        if pretty:
            # Pretty format for logs/debugging
            return json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            )
        else:
            # Compact format for agent messages (better performance)
            return json.dumps(
                data,
                ensure_ascii=False,
                separators=(',', ':')  # Compact: no spaces
            )
    
    @staticmethod
    def deserialize(json_str: str) -> Any:
        """
        Deserialize JSON string to Python object.
        
        Args:
            json_str: JSON string to deserialize
        
        Returns:
            Deserialized Python object
        """
        return json.loads(json_str)

