"""
Utility functions for web slides generation.
"""

import json
import logging
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


def _parse_json_safely(value: Union[str, dict, list]) -> Union[dict, list]:
    """
    Safely parse JSON from string, handling escaped JSON strings.
    
    Args:
        value: String that may contain JSON (possibly escaped) or already parsed dict/list
        
    Returns:
        Parsed dict or list
        
    Raises:
        ValueError: If value cannot be parsed
    """
    # If already a dict or list, return as-is
    if isinstance(value, (dict, list)):
        return value
    
    if not isinstance(value, str):
        raise ValueError(f"Expected str, dict, or list, got {type(value).__name__}")
    
    # Try parsing directly first
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    
    # If direct parsing fails, try unescaping first
    # Handle cases like: "{\"key\": \"value\"}" -> {"key": "value"}
    try:
        # Remove outer quotes if present and unescape
        unescaped = value.encode().decode('unicode_escape')
        # Remove surrounding quotes if they exist
        if unescaped.startswith('"') and unescaped.endswith('"'):
            unescaped = unescaped[1:-1]
        return json.loads(unescaped)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        pass
    
    # Try one more time with string replacement for common escape sequences
    try:
        # Replace escaped quotes and newlines
        cleaned = value.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # If all parsing attempts fail, raise error
    raise ValueError(f"Could not parse JSON string: {value[:200]}...")


def _ensure_dict(value: Any, field_name: str = "field", default: Optional[Dict] = None, slide_number: Optional[int] = None) -> Dict:
    """
    Ensure a value is a dict, parsing from JSON string if needed.
    This helper function eliminates DRY violations by centralizing the common
    pattern of parsing and validating dict fields.
    
    Args:
        value: Value that may be a string, dict, or other type
        field_name: Name of the field (for logging)
        default: Default dict to return if parsing fails (default: empty dict)
        slide_number: Optional slide number (for logging context)
        
    Returns:
        Dict - either the original dict, parsed dict, or default dict
    """
    if default is None:
        default = {}
    
    # If already a dict, return as-is
    if isinstance(value, dict):
        return value
    
    # Try to parse if it's a string
    if isinstance(value, str):
        try:
            parsed = _parse_json_safely(value)
            if isinstance(parsed, dict):
                log_context = f" for slide {slide_number}" if slide_number else ""
                logger.debug(f"   Parsed {field_name} from JSON string{log_context}")
                return parsed
        except ValueError:
            log_context = f" for slide {slide_number}" if slide_number else ""
            logger.warning(f"⚠️  {field_name} is a string but not valid JSON{log_context}, using default. Value: {value[:100]}")
            return default
    
    # Not a dict and not parseable - use default
    log_context = f" for slide {slide_number}" if slide_number else ""
    logger.warning(f"⚠️  {field_name} is not a dict (got {type(value).__name__}){log_context}, using default")
    return default


def _get_theme_colors(config: Optional[Dict]) -> Dict[str, str]:
    """Get theme colors based on scenario."""
    if not config or not isinstance(config, dict):
        return {
            "primary": "#7C3AED",
            "secondary": "#EC4899",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }
    
    scenario = config.get("scenario", "").lower()
    
    if "academic" in scenario:
        return {
            "primary": "#1E40AF",  # Blue
            "secondary": "#3B82F6",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }
    elif "business" in scenario:
        return {
            "primary": "#059669",  # Green
            "secondary": "#10B981",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }
    else:
        return {
            "primary": "#7C3AED",  # Purple
            "secondary": "#EC4899",
            "background": "#FFFFFF",
            "text": "#1F2937"
        }

