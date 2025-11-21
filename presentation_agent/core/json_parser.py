"""
JSON parsing utilities with robust error handling.
Extracted from main.py to eliminate code duplication.
"""

import json
import re
from typing import Any, Optional, Dict


def clean_json_string(text: str) -> str:
    """
    Clean JSON string by removing markdown code blocks and fixing common issues.
    
    Args:
        text: Raw JSON string (may contain markdown, Python booleans, etc.)
        
    Returns:
        Cleaned JSON string
    """
    cleaned = text.strip()
    
    # Remove markdown code blocks
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:].lstrip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:].lstrip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].rstrip()
    
    # Convert Python-style booleans to JSON-compliant
    cleaned = re.sub(r'\bTrue\b', 'true', cleaned)
    cleaned = re.sub(r'\bFalse\b', 'false', cleaned)
    cleaned = re.sub(r'\bNone\b', 'null', cleaned)
    
    # Fix invalid escape sequences (e.g., \' should be just ')
    cleaned = re.sub(r"\\'", "'", cleaned)
    
    # Remove trailing commas before closing brackets/braces
    cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
    
    # Remove comments (// or /* */)
    cleaned = re.sub(r'//.*?$', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    
    return cleaned


def extract_json_from_text(text: str) -> Optional[str]:
    """
    Extract JSON object from text by finding matching braces.
    Handles nested JSON and markdown code blocks.
    
    Args:
        text: Text that may contain a JSON object
        
    Returns:
        Extracted JSON string, or None if not found
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # First, try to find JSON in markdown code blocks
    # Look for ```json ... ``` or ``` ... ```
    json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    import re
    match = re.search(json_block_pattern, text, re.DOTALL)
    if match:
        json_str = match.group(1)
        logger.debug(f"Found JSON in markdown code block (length: {len(json_str)})")
        return json_str
    
    # If no markdown block, find the largest JSON object (likely the main output)
    start_idx = text.find("{")
    if start_idx == -1:
        logger.debug("No opening brace found in text")
        return None
    
    # Find matching closing brace (handle nested braces)
    brace_count = 0
    end_idx = start_idx
    for i in range(start_idx, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i
                break
    
    if end_idx > start_idx:
        json_str = text[start_idx:end_idx+1]
        logger.debug(f"Extracted JSON from text (length: {len(json_str)})")
        return json_str
    
    logger.debug("Could not extract valid JSON from text")
    return None


def parse_json_robust(text: Any, extract_wrapped: bool = True) -> Optional[Dict]:
    """
    Robustly parse JSON from various formats (string, dict, with markdown, etc.).
    
    Args:
        text: Input that may be JSON string, dict, or text containing JSON
        extract_wrapped: If True, extract from wrapper keys like "review_layout_tool_response"
        
    Returns:
        Parsed JSON dict, or None if parsing fails
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # If already a dict, return as is
    if isinstance(text, dict):
        if extract_wrapped:
            # Check for common wrapper keys
            for wrapper_key in ["review_layout_tool_response", "tool_response", "response"]:
                if wrapper_key in text:
                    return text[wrapper_key]
        return text
    
    # If not a string, convert to string
    if not isinstance(text, str):
        text = str(text)
    
    # Clean the string
    cleaned = clean_json_string(text)
    
    # Try direct parse first
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            if extract_wrapped:
                # Check for wrapper keys
                for wrapper_key in ["review_layout_tool_response", "tool_response", "response"]:
                    if wrapper_key in parsed:
                        return parsed[wrapper_key]
            return parsed
    except json.JSONDecodeError:
        pass
    
    # Try extracting JSON from text
    json_str = extract_json_from_text(cleaned)
    if json_str:
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                if extract_wrapped:
                    for wrapper_key in ["review_layout_tool_response", "tool_response", "response"]:
                        if wrapper_key in parsed:
                            return parsed[wrapper_key]
                return parsed
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse extracted JSON: {e}")
    
    return None

