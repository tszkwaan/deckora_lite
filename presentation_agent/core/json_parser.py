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
    Finds the OUTERMOST (largest) JSON object, not the first one.
    
    Args:
        text: Text that may contain a JSON object
        
    Returns:
        Extracted JSON string, or None if not found
    """
    import logging
    import re
    logger = logging.getLogger(__name__)
    
    # First, try to find JSON in markdown code blocks
    # Look for ```json ... ``` or ``` ... ```
    # Extract the code block content first, then find the largest JSON object within it
    code_block_pattern = r'```(?:json)?\s*(.*?)\s*```'
    match = re.search(code_block_pattern, text, re.DOTALL)
    if match:
        code_block_content = match.group(1).strip()
        logger.debug(f"Found code block (length: {len(code_block_content)})")
        # Now find the largest JSON object within the code block
        # Find all JSON objects and return the largest
        json_objects = []
        start_positions = []
        for i, char in enumerate(code_block_content):
            if char == '{':
                if i == 0 or code_block_content[i-1] in [' ', '\n', '\t', '\r', ':', '[', ',', '(', '=']:
                    start_positions.append(i)
        
        for start_idx in start_positions:
            brace_count = 0
            end_idx = start_idx
            for i in range(start_idx, len(code_block_content)):
                if code_block_content[i] == '{':
                    brace_count += 1
                elif code_block_content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        json_objects.append((start_idx, end_idx, end_idx - start_idx + 1))
                        break
        
        if json_objects:
            largest = max(json_objects, key=lambda x: x[2])
            start_idx, end_idx, length = largest
            json_str = code_block_content[start_idx:end_idx+1]
            logger.debug(f"Extracted largest JSON from code block (length: {len(json_str)})")
            return json_str
        else:
            # Fallback: try to parse the whole code block content
            logger.debug("No JSON objects found in code block, trying whole content")
            return code_block_content
    
    # If no markdown block, find ALL JSON objects and return the largest one
    # This ensures we get the outermost/complete object, not a fragment
    json_objects = []
    
    # Find all potential JSON object start positions
    start_positions = []
    for i, char in enumerate(text):
        if char == '{':
            # Check if this is likely the start of a JSON object (not inside a string)
            # Simple heuristic: previous char should be whitespace, newline, or start of string
            if i == 0 or text[i-1] in [' ', '\n', '\t', '\r', ':', '[', ',', '(', '=']:
                start_positions.append(i)
    
    # For each start position, try to find the matching closing brace
    for start_idx in start_positions:
        brace_count = 0
        end_idx = start_idx
        
        for i in range(start_idx, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    json_objects.append((start_idx, end_idx, end_idx - start_idx + 1))
                    break
    
    if json_objects:
        # Return the largest JSON object (most likely the complete output)
        largest = max(json_objects, key=lambda x: x[2])
        start_idx, end_idx, length = largest
        json_str = text[start_idx:end_idx+1]
        logger.debug(f"Extracted largest JSON object from text (length: {len(json_str)}, position: {start_idx}-{end_idx})")
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

