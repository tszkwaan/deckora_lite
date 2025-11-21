"""
Helper functions for the presentation generation pipeline.
"""

import json
from typing import Any, Dict, Optional


def extract_output_from_events(events: list, output_key: str) -> Optional[Any]:
    """
    Extract output from events, checking multiple locations:
    1. state_delta (primary location)
    2. content.parts[].function_response.response (tool responses)
    3. actions.tool_results (tool results)
    
    Args:
        events: List of events from runner.run_debug()
        output_key: Key to extract from state_delta
        
    Returns:
        Extracted value (dict if JSON, otherwise raw value)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not events:
        logger.warning(f"⚠️ extract_output_from_events: No events provided for key '{output_key}'")
        return None
    
    logger.info(f"🔍 extract_output_from_events: Searching for '{output_key}' in {len(events)} events")
    
    # Priority 1: Check state_delta in all events (not just last)
    raw = None
    
    for i, event in enumerate(reversed(events)):  # Check from last to first
        agent_name = getattr(event, 'agent_name', None) or (getattr(event, 'agent', None) and getattr(event.agent, 'name', None)) or 'Unknown'
        if hasattr(event, 'actions') and event.actions:
            if hasattr(event.actions, 'state_delta') and event.actions.state_delta:
                delta_keys = list(event.actions.state_delta.keys())
                logger.debug(f"   Event {len(events)-1-i} ({agent_name}): state_delta keys: {delta_keys}")
                if output_key in delta_keys:
                    raw = event.actions.state_delta.get(output_key, None)
                    logger.info(f"✅ Found '{output_key}' in state_delta of Event {len(events)-1-i} ({agent_name})")
                    break
    
    # Priority 2: Check content.parts[].text (agent text output)
    if raw is None:
        logger.debug(f"   Checking content.parts[].text for agent output...")
        for i, event in enumerate(reversed(events)):  # Check from last to first
            agent_name = getattr(event, 'agent_name', None) or (getattr(event, 'agent', None) and getattr(event.agent, 'name', None)) or 'Unknown'
            if hasattr(event, 'content') and event.content:
                if hasattr(event.content, 'parts') and event.content.parts:
                    try:
                        for part_idx, part in enumerate(event.content.parts):
                            # Check for text content (agent's text output)
                            if hasattr(part, 'text') and part.text:
                                text_content = part.text
                                logger.debug(f"   Event {len(events)-1-i} ({agent_name}), part {part_idx}: Found text content (length: {len(text_content)})")
                                # For slide_and_script, the text should contain JSON
                                if output_key == "slide_and_script" and text_content:
                                    raw = text_content
                                    logger.info(f"✅ Found '{output_key}' as text content in Event {len(events)-1-i} ({agent_name})")
                                    break
                            # Check for function_response (tool responses)
                            if hasattr(part, 'function_response') and part.function_response:
                                if hasattr(part.function_response, 'response'):
                                    response = part.function_response.response
                                    if isinstance(response, dict):
                                        response_keys = list(response.keys())
                                        logger.debug(f"   Event {len(events)-1-i} ({agent_name}), part {part_idx}: function_response keys: {response_keys}")
                                        raw = response.get(output_key, None)
                                        if raw is not None:
                                            logger.info(f"✅ Found '{output_key}' in function_response of Event {len(events)-1-i} ({agent_name})")
                                            break
                            if raw is not None:
                                break
                    except (TypeError, AttributeError) as e:
                        logger.debug(f"   Event {len(events)-1-i} ({agent_name}): Error checking parts: {e}")
                if raw is not None:
                    break
    
    # Priority 3: Check actions.tool_results
    if raw is None:
        logger.debug(f"   Checking tool_results for '{output_key}'...")
        for i, event in enumerate(reversed(events)):  # Check from last to first
            agent_name = getattr(event, 'agent_name', None) or (getattr(event, 'agent', None) and getattr(event.agent, 'name', None)) or 'Unknown'
            if hasattr(event, 'actions') and event.actions:
                if hasattr(event.actions, 'tool_results') and event.actions.tool_results:
                    logger.debug(f"   Event {len(events)-1-i} ({agent_name}): Found {len(event.actions.tool_results)} tool_results")
                    for tr_idx, tool_result in enumerate(event.actions.tool_results):
                        if hasattr(tool_result, 'response'):
                            response = tool_result.response
                            if isinstance(response, dict):
                                response_keys = list(response.keys())
                                logger.debug(f"      Tool result {tr_idx} keys: {response_keys}")
                                # First try: look for nested key (e.g., response["layout_review"])
                                raw = response.get(output_key, None)
                                if raw is not None:
                                    logger.info(f"✅ Found '{output_key}' nested in tool_result {tr_idx} of Event {len(events)-1-i} ({agent_name})")
                                    break
                                # Second try: check if the response dict itself IS the output
                                # This handles cases where tool returns the output directly (e.g., layout_review tool)
                                # Check for common patterns that indicate this is the output dict itself
                                if output_key == "layout_review":
                                    # Layout review has specific keys: review_type, total_slides_reviewed, passed, overall_quality
                                    # Be more permissive - check for any of these key patterns
                                    if ('review_type' in response) or \
                                       ('total_slides_reviewed' in response) or \
                                       ('passed' in response and 'overall_quality' in response) or \
                                       ('presentation_id' in response and ('issues_summary' in response or 'overall_quality' in response)):
                                        raw = response
                                        logger.info(f"✅ Found '{output_key}' as direct tool_result {tr_idx} of Event {len(events)-1-i} ({agent_name})")
                                        break
                    if raw is not None:
                        break
    
    if raw is None:
        logger.warning(f"⚠️ extract_output_from_events: '{output_key}' not found in any event")
        # Log all agent names and state_delta keys for debugging
        agent_names = []
        for i, event in enumerate(events):
            agent_name = getattr(event, 'agent_name', None) or (getattr(event, 'agent', None) and getattr(event.agent, 'name', None)) or 'Unknown'
            agent_names.append(agent_name)
            # Log state_delta keys for each event
            if hasattr(event, 'actions') and event.actions:
                if hasattr(event.actions, 'state_delta') and event.actions.state_delta:
                    delta_keys = list(event.actions.state_delta.keys())
                    logger.debug(f"   Event {i} ({agent_name}): state_delta keys: {delta_keys}")
        logger.debug(f"   Agents seen in events: {agent_names}")
        logger.debug(f"   Searched for output_key: '{output_key}'")
        return None
    
    # If already a dict, return as is
    if isinstance(raw, dict):
        return raw
    
    # Try to parse as JSON
    if isinstance(raw, str):
        logger.debug(f"Raw output is a string (length: {len(raw)}). Attempting to parse...")
        
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
        
        # Try to parse as JSON directly first
        try:
            parsed = json.loads(cleaned)
            logger.debug(f"✅ Direct JSON parse succeeded (keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'})")
            return parsed
        except json.JSONDecodeError:
            logger.debug("Direct JSON parse failed, trying robust extraction...")
            # If that fails, use robust JSON extraction (finds largest/outermost object)
            from presentation_agent.core.json_parser import extract_json_from_text, parse_json_robust
            extracted_json = extract_json_from_text(cleaned)
            if extracted_json:
                try:
                    parsed = json.loads(extracted_json)
                    logger.debug(f"✅ Extracted JSON parse succeeded (keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'})")
                    return parsed
                except json.JSONDecodeError as e:
                    logger.debug(f"Extracted JSON parse failed: {e}")
                    # Try parse_json_robust as last resort
                    parsed = parse_json_robust(extracted_json)
                    if parsed:
                        logger.debug(f"✅ parse_json_robust succeeded (keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'})")
                        return parsed
            
            # Last resort: try to find JSON object in the string (simple approach)
            start_idx = cleaned.find("{")
            end_idx = cleaned.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                try:
                    parsed = json.loads(cleaned[start_idx:end_idx+1])
                    logger.debug(f"✅ Simple extraction parse succeeded (keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'})")
                    return parsed
                except json.JSONDecodeError:
                    pass
            
            # Return raw string if not valid JSON
            logger.warning(f"⚠️ Could not parse JSON from string. Returning raw string (first 200 chars: {cleaned[:200]})")
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

