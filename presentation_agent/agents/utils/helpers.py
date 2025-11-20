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
    
    # Priority 2: Check content.parts[].function_response.response (tool responses)
    if raw is None:
        logger.debug(f"   Checking content.parts for '{output_key}'...")
        for i, event in enumerate(reversed(events)):  # Check from last to first
            agent_name = getattr(event, 'agent_name', None) or (getattr(event, 'agent', None) and getattr(event.agent, 'name', None)) or 'Unknown'
            if hasattr(event, 'content') and event.content:
                if hasattr(event.content, 'parts') and event.content.parts:
                    try:
                        for part_idx, part in enumerate(event.content.parts):
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
        # Log all agent names for debugging
        agent_names = []
        for event in events:
            agent_name = getattr(event, 'agent_name', None) or (getattr(event, 'agent', None) and getattr(event.agent, 'name', None)) or 'Unknown'
            agent_names.append(agent_name)
        logger.debug(f"   Agents seen in events: {agent_names}")
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


def extract_relevant_knowledge(
    report_knowledge: Dict[str, Any],
    agent_name: str,
    presentation_outline: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Extract only the relevant parts of report_knowledge for a specific agent.
    
    ✅ BEST PRACTICE: Context compaction at orchestration layer
    - This function is called in main.py (orchestration layer) before passing data to agents
    - Reduces token usage by passing only necessary data to each agent
    - Full report_knowledge remains in session.state for reference
    - This follows ADK best practices: data preprocessing at orchestration level, not in agents
    
    Args:
        report_knowledge: Full report_knowledge dictionary
        agent_name: Name of the agent requesting the knowledge
        presentation_outline: Optional outline to filter sections (for SlideAndScriptGeneratorAgent)
        
    Returns:
        Filtered report_knowledge dictionary with only relevant fields
    """
    if not isinstance(report_knowledge, dict):
        return report_knowledge
    
    # Base fields that all agents might need
    base_fields = {
        'scenario': report_knowledge.get('scenario'),
        'duration': report_knowledge.get('duration'),
        'report_url': report_knowledge.get('report_url'),
        'report_title': report_knowledge.get('report_title'),
        'one_sentence_summary': report_knowledge.get('one_sentence_summary'),
    }
    
    if agent_name == "OutlineGeneratorAgent":
        # Only needs: sections, key_takeaways, presentation_focus
        return {
            **base_fields,
            'sections': report_knowledge.get('sections', []),
            'key_takeaways': report_knowledge.get('key_takeaways', []),
            'presentation_focus': report_knowledge.get('presentation_focus', {}),
            'figures': report_knowledge.get('figures', []),  # For figure references
        }
    
    elif agent_name == "OutlineCriticAgent":
        # Needs FULL report_knowledge for hallucination checking
        return report_knowledge
    
    elif agent_name == "SlideAndScriptGeneratorAgent":
        # Only needs sections that match the outline topics
        if presentation_outline:
            # Extract topics from outline
            outline_topics = set()
            slides = presentation_outline.get('slides', [])
            for slide in slides:
                # Extract key points and titles
                key_points = slide.get('key_points', [])
                title = slide.get('title', '')
                content_notes = slide.get('content_notes', '')
                
                # Add keywords from these fields
                all_text = f"{title} {content_notes} {' '.join(key_points)}".lower()
                outline_topics.add(all_text)
            
            # Filter sections based on relevance to outline topics
            all_sections = report_knowledge.get('sections', [])
            relevant_sections = []
            
            for section in all_sections:
                section_label = section.get('label', '').lower()
                section_summary = section.get('summary', '').lower()
                section_key_points = ' '.join(section.get('key_points', [])).lower()
                section_text = f"{section_label} {section_summary} {section_key_points}"
                
                # Check if section is relevant to any outline topic
                is_relevant = False
                for topic_text in outline_topics:
                    # Simple keyword matching (can be improved with semantic similarity)
                    common_words = set(section_text.split()) & set(topic_text.split())
                    if len(common_words) >= 3:  # At least 3 common words
                        is_relevant = True
                        break
                
                if is_relevant:
                    relevant_sections.append(section)
            
            # If no relevant sections found, include all sections (fallback)
            if not relevant_sections:
                relevant_sections = all_sections
            
            # Log filtering results
            import logging
            logger = logging.getLogger(__name__)
            if len(all_sections) > 0:
                filter_ratio = len(relevant_sections) / len(all_sections)
                logger.info(f"📊 Section filtering: {len(relevant_sections)}/{len(all_sections)} sections relevant ({filter_ratio:.1%})")
            
            return {
                **base_fields,
                'sections': relevant_sections,
                'key_takeaways': report_knowledge.get('key_takeaways', []),
                'presentation_focus': report_knowledge.get('presentation_focus', {}),
                'figures': report_knowledge.get('figures', []),
                'audience_profile': report_knowledge.get('audience_profile', {}),
            }
        else:
            # No outline available, return essential fields only
            return {
                **base_fields,
                'sections': report_knowledge.get('sections', []),
                'key_takeaways': report_knowledge.get('key_takeaways', []),
                'presentation_focus': report_knowledge.get('presentation_focus', {}),
                'figures': report_knowledge.get('figures', []),
                'audience_profile': report_knowledge.get('audience_profile', {}),
            }
    
    else:
        # Unknown agent - return full knowledge (safe default)
        return report_knowledge


def compress_outline(presentation_outline: Dict[str, Any]) -> Dict[str, Any]:
    """
    ✅ BEST PRACTICE: Context compaction - compress presentation outline.
    Extracts only essential fields needed by SlideAndScriptGeneratorAgent:
    - slides: The actual slide content
    - total_slides: Total number of slides
    
    Removes metadata like:
    - presentation_title (can be inferred)
    - estimated_duration (already in session.state)
    - time_allocation (not needed for generation)
    - outline_notes (not needed for generation)
    
    Args:
        presentation_outline: Full presentation outline dictionary
        
    Returns:
        Compressed outline dictionary with only slides and total_slides
    """
    if not isinstance(presentation_outline, dict):
        return presentation_outline
    
    compressed = {
        "slides": presentation_outline.get("slides", []),
        "total_slides": presentation_outline.get("total_slides", len(presentation_outline.get("slides", [])))
    }
    
    return compressed


def compress_slide_and_script(slide_and_script: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compress slide_and_script by extracting only slide_deck.
    
    This reduces token usage when passing data to SlidesExportAgent.
    The presentation_script should be stored separately in session.state.
    
    Args:
        slide_and_script: Full slide_and_script dictionary with slide_deck and presentation_script
        
    Returns:
        Compressed dictionary containing only slide_deck and config
    """
    if not isinstance(slide_and_script, dict):
        return slide_and_script
    
    # Extract only slide_deck (presentation_script will be read from session.state)
    compressed = {
        'slide_deck': slide_and_script.get('slide_deck'),
    }
    
    # Optionally include config if present
    if 'config' in slide_and_script:
        compressed['config'] = slide_and_script.get('config')
    
    return compressed


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

