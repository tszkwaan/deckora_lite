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
    Improved to handle incomplete/truncated JSON by attempting to fix common issues.
    
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
            in_string = False
            escape_next = False
            
            for i in range(start_idx, len(code_block_content)):
                char = code_block_content[i]
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue
                
                if not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
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
    
    # If text doesn't start with {, find the first { and extract from there
    # This handles cases like "Here's the JSON: {...}"
    if not text.strip().startswith('{'):
        first_brace = text.find('{')
        if first_brace != -1:
            logger.debug(f"Text doesn't start with {{, found first brace at position {first_brace}, extracting from there")
            text = text[first_brace:]
    
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
    # Improved: track string state to avoid counting braces inside strings
    for start_idx in start_positions:
        brace_count = 0
        end_idx = start_idx
        in_string = False
        escape_next = False
        
        for i in range(start_idx, len(text)):
            char = text[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
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


def fix_json_syntax_errors(json_str: str) -> Optional[str]:
    """
    Attempt to fix common JSON syntax errors (not truncation).
    Handles issues like unescaped quotes, single quotes, etc.
    
    Args:
        json_str: JSON string with potential syntax errors
        
    Returns:
        Fixed JSON string, or None if fixing is not possible
    """
    import logging
    import re
    logger = logging.getLogger(__name__)
    
    fixed = json_str
    
    # Fix common issues:
    # 1. Single quotes around property names (JSON requires double quotes)
    # But be careful - single quotes inside strings are valid
    # Pattern: 'key': (single quote, key, single quote, colon)
    # This is tricky because we need to avoid strings. Let's be conservative.
    
    # 2. Unescaped quotes in strings - this is the most common issue
    # Pattern: "text "with" quotes" should be "text \"with\" quotes"
    # But this is very hard to fix automatically without a proper parser
    
    # 3. Trailing commas (already handled in clean_json_string)
    
    # 4. Python-style booleans (already handled in clean_json_string)
    
    # For now, return None - let the incomplete JSON fixer handle truncation
    # Syntax errors should trigger LLM retry, not auto-fix
    return None


def fix_incomplete_json(json_str: str) -> Optional[str]:
    """
    Attempt to fix incomplete/truncated JSON by closing unclosed structures.
    This handles cases where the LLM response was cut off mid-JSON.
    
    Args:
        json_str: Potentially incomplete JSON string
        
    Returns:
        Fixed JSON string, or None if fixing is not possible
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Count unclosed structures (ignoring those inside strings)
    # Simple approach: count braces/brackets, but this can be fooled by strings
    # Better approach: track if we're inside a string
    in_string = False
    escape_next = False
    open_braces = 0
    open_brackets = 0
    
    for char in json_str:
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if not in_string:
            if char == '{':
                open_braces += 1
            elif char == '}':
                open_braces -= 1
            elif char == '[':
                open_brackets += 1
            elif char == ']':
                open_brackets -= 1
    
    # If no unclosed structures, it's not incomplete (might be syntax error)
    if open_braces == 0 and open_brackets == 0:
        return None
    
    # Try to fix by closing structures
    fixed = json_str
    
    # Close unclosed brackets first (inner structures)
    fixed += ']' * open_brackets
    
    # Close unclosed braces (outer structures)
    fixed += '}' * open_braces
    
    logger.debug(f"Attempted to fix incomplete JSON: added {open_brackets} brackets, {open_braces} braces")
    return fixed


def is_json_syntax_error(error: json.JSONDecodeError) -> bool:
    """
    Determine if a JSON error is a syntax error (should retry LLM) 
    vs incomplete JSON (can try to fix).
    
    Args:
        error: JSONDecodeError exception
        
    Returns:
        True if it's a syntax error (like unescaped quotes), False if might be incomplete
    """
    error_msg = str(error).lower()
    
    # Syntax errors that indicate malformed JSON (should retry LLM):
    syntax_indicators = [
        "expecting property name",
        "expecting ',' delimiter",
        "expecting ':' delimiter",
        "invalid escape",
        "unterminated string",
        "invalid character",
    ]
    
    # Incomplete JSON indicators (can try to fix):
    incomplete_indicators = [
        "unexpected end of data",
        "expecting value",
        "expecting '}'",
        "expecting ']'",
    ]
    
    for indicator in syntax_indicators:
        if indicator in error_msg:
            return True
    
    for indicator in incomplete_indicators:
        if indicator in error_msg:
            return False
    
    # Default: assume syntax error (safer to retry)
    return True


def parse_json_robust(text: Any, extract_wrapped: bool = True, fix_incomplete: bool = True) -> Optional[Dict]:
    """
    Robustly parse JSON from various formats (string, dict, with markdown, etc.).
    Now includes handling for incomplete/truncated JSON responses.
    
    Args:
        text: Input that may be JSON string, dict, or text containing JSON
        extract_wrapped: If True, extract from wrapper keys like "review_layout_tool_response"
        fix_incomplete: If True, attempt to fix incomplete/truncated JSON
        
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
        # Try parsing the extracted JSON
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
            
            # If fix_incomplete is enabled, try to fix truncated JSON
            if fix_incomplete:
                fixed_json = fix_incomplete_json(json_str)
                if fixed_json and fixed_json != json_str:
                    try:
                        parsed = json.loads(fixed_json)
                        if isinstance(parsed, dict):
                            logger.debug("Successfully parsed fixed incomplete JSON")
                            if extract_wrapped:
                                for wrapper_key in ["review_layout_tool_response", "tool_response", "response"]:
                                    if wrapper_key in parsed:
                                        return parsed[wrapper_key]
                            return parsed
                    except json.JSONDecodeError:
                        logger.debug("Failed to parse fixed JSON")
    
    return None

