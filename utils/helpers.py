"""
Helper functions for the presentation generation pipeline.
"""

import json
from typing import Any, Dict, Optional


def extract_output_from_events(events: list, output_key: str) -> Optional[Any]:
    """
    Extract output from the last event's state_delta.
    
    Args:
        events: List of events from runner.run_debug()
        output_key: Key to extract from state_delta
        
    Returns:
        Extracted value (dict if JSON, otherwise raw value)
    """
    if not events:
        return None
    
    last_event = events[-1]
    raw = last_event.actions.state_delta.get(output_key, None)
    
    if raw is None:
        return None
    
    # If already a dict, return as is
    if isinstance(raw, dict):
        return raw
    
    # Try to parse as JSON
    if isinstance(raw, str):
        # Strip markdown code blocks if present (```json ... ```)
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            # Remove opening ```json
            cleaned = cleaned[7:].lstrip()
        elif cleaned.startswith("```"):
            # Remove opening ```
            cleaned = cleaned[3:].lstrip()
        
        if cleaned.endswith("```"):
            # Remove closing ```
            cleaned = cleaned[:-3].rstrip()
        
        # Try to parse as JSON
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # If that fails, try to find JSON object in the string
            # Look for first { and last }
            start_idx = cleaned.find("{")
            end_idx = cleaned.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                try:
                    return json.loads(cleaned[start_idx:end_idx+1])
                except json.JSONDecodeError:
                    pass
            # Return raw string if not valid JSON
            return cleaned
    
    return raw


def save_json_output(data: Any, filename: str, indent: int = 2) -> None:
    """
    Save data as a pretty-printed JSON file.
    
    Args:
        data: Data to save (will be JSON serialized)
        filename: Output filename
        indent: JSON indentation level
    """
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    print(f"✅ JSON saved to `{filename}`")


def preview_json(data: Any, max_chars: int = 2000) -> str:
    """
    Generate a preview of JSON data.
    
    Args:
        data: Data to preview
        max_chars: Maximum characters to show
        
    Returns:
        Preview string
    """
    pretty = json.dumps(data, indent=2, ensure_ascii=False)
    preview = pretty[:max_chars]
    if len(pretty) > max_chars:
        preview += "\n... (truncated)"
    return preview


def build_initial_message(config: Dict[str, Any], report_content: str) -> str:
    """
    Build the initial message for agents that need all context upfront.
    
    Args:
        config: Presentation configuration dictionary
        report_content: Report content text
        
    Returns:
        Formatted initial message
    """
    return f"""
[SCENARIO]
{config.get('scenario', '')}

[DURATION]
{config.get('duration', '')}

[TARGET_AUDIENCE]
{config.get('target_audience', '')}

[CUSTOM_INSTRUCTION]
{config.get('custom_instruction', '')}

[REPORT_URL]
{config.get('report_url', 'N/A')}

[REPORT_CONTENT]
{report_content}
[END_REPORT_CONTENT]

Your task:
- Use ONLY the above information.
- Produce the required output.
- Do NOT ask any questions.
"""

