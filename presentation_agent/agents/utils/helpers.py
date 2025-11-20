"""
Helper functions for the presentation generation pipeline.
"""

import json
from typing import Any, Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


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


def filter_sections_by_semantic_similarity(
    sections: List[Dict[str, Any]],
    presentation_outline: Dict[str, Any],
    similarity_threshold: float = 0.3
) -> List[Dict[str, Any]]:
    """
    ✅ BEST PRACTICE: Semantic section filtering using embedding similarity.
    Filters report sections based on semantic similarity to outline topics.
    
    Uses google.generativeai.embed_content() to compute embeddings and cosine similarity
    to determine which sections are relevant to the outline.
    
    Args:
        sections: List of report sections to filter
        presentation_outline: Presentation outline with slides
        similarity_threshold: Minimum cosine similarity threshold (0.0-1.0)
        
    Returns:
        Filtered list of relevant sections
    """
    if not sections or not presentation_outline:
        return sections
    
    try:
        import google.generativeai as genai
        import numpy as np
    except ImportError:
        logger.warning("⚠️  google.generativeai not available, falling back to keyword matching")
        return _fallback_keyword_filtering(sections, presentation_outline)
    
    try:
        # Extract outline topics from slides
        slides = presentation_outline.get('slides', [])
        if not slides:
            return sections
        
        outline_texts = []
        for slide in slides:
            key_points = slide.get('key_points', [])
            title = slide.get('title', '')
            content_notes = slide.get('content_notes', '')
            # Combine all text from slide
            slide_text = f"{title} {content_notes} {' '.join(key_points)}".strip()
            if slide_text:
                outline_texts.append(slide_text)
        
        if not outline_texts:
            return sections
        
        # Create embeddings for outline topics (combine all slides into one query)
        combined_outline_text = " ".join(outline_texts)
        
        try:
            # Get embedding for outline
            outline_embedding_result = genai.embed_content(
                model="models/text-embedding-004",
                content=combined_outline_text,
                task_type="retrieval_document"  # Use retrieval_document for better similarity matching
            )
            outline_embedding = np.array(outline_embedding_result['embedding'])
        except Exception as e:
            logger.warning(f"⚠️  Error generating outline embedding: {e}, falling back to keyword matching")
            return _fallback_keyword_filtering(sections, presentation_outline)
        
        # Get embeddings for each section
        relevant_sections = []
        section_texts = []
        section_indices = []
        
        for idx, section in enumerate(sections):
            section_label = section.get('label', '')
            section_summary = section.get('summary', '')
            section_key_points = ' '.join(section.get('key_points', []))
            section_text = f"{section_label} {section_summary} {section_key_points}".strip()
            
            if section_text:
                section_texts.append(section_text)
                section_indices.append(idx)
        
        if not section_texts:
            return sections
        
        # Batch embed sections
        try:
            section_embeddings_result = genai.embed_content(
                model="models/text-embedding-004",
                content=section_texts,
                task_type="retrieval_document"
            )
            section_embeddings = np.array(section_embeddings_result['embedding'])
        except Exception as e:
            logger.warning(f"⚠️  Error generating section embeddings: {e}, falling back to keyword matching")
            return _fallback_keyword_filtering(sections, presentation_outline)
        
        # Normalize embeddings for cosine similarity
        outline_embedding_norm = outline_embedding / (np.linalg.norm(outline_embedding) + 1e-10)
        section_embeddings_norm = section_embeddings / (np.linalg.norm(section_embeddings, axis=1, keepdims=True) + 1e-10)
        
        # Compute cosine similarity
        similarities = np.dot(section_embeddings_norm, outline_embedding_norm)
        
        # Filter sections by similarity threshold
        for i, similarity in enumerate(similarities):
            if similarity >= similarity_threshold:
                relevant_sections.append(sections[section_indices[i]])
        
        # If no sections pass threshold, include top 50% by similarity (fallback)
        if not relevant_sections and len(sections) > 0:
            top_indices = np.argsort(similarities)[::-1][:max(1, len(sections) // 2)]
            relevant_sections = [sections[section_indices[i]] for i in top_indices]
            logger.info(f"📊 Semantic filtering: No sections above threshold {similarity_threshold}, using top {len(relevant_sections)} sections")
        
        # Log filtering results
        if len(sections) > 0:
            filter_ratio = len(relevant_sections) / len(sections)
            avg_similarity = float(np.mean(similarities))
            logger.info(f"📊 Semantic filtering: {len(relevant_sections)}/{len(sections)} sections relevant ({filter_ratio:.1%}), avg similarity: {avg_similarity:.3f}")
        
        return relevant_sections
        
    except Exception as e:
        logger.warning(f"⚠️  Error in semantic filtering: {e}, falling back to keyword matching")
        return _fallback_keyword_filtering(sections, presentation_outline)


def _fallback_keyword_filtering(
    sections: List[Dict[str, Any]],
    presentation_outline: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Fallback keyword-based filtering when semantic similarity is not available.
    """
    # Extract topics from outline
    outline_topics = set()
    slides = presentation_outline.get('slides', [])
    for slide in slides:
        key_points = slide.get('key_points', [])
        title = slide.get('title', '')
        content_notes = slide.get('content_notes', '')
        all_text = f"{title} {content_notes} {' '.join(key_points)}".lower()
        outline_topics.add(all_text)
    
    # Filter sections based on keyword matching
    relevant_sections = []
    for section in sections:
        section_label = section.get('label', '').lower()
        section_summary = section.get('summary', '').lower()
        section_key_points = ' '.join(section.get('key_points', [])).lower()
        section_text = f"{section_label} {section_summary} {section_key_points}"
        
        is_relevant = False
        for topic_text in outline_topics:
            common_words = set(section_text.split()) & set(topic_text.split())
            if len(common_words) >= 3:
                is_relevant = True
                break
        
        if is_relevant:
            relevant_sections.append(section)
    
    # If no relevant sections found, include all sections (fallback)
    if not relevant_sections:
        relevant_sections = sections
    
    if len(sections) > 0:
        filter_ratio = len(relevant_sections) / len(sections)
        logger.info(f"📊 Keyword filtering (fallback): {len(relevant_sections)}/{len(sections)} sections relevant ({filter_ratio:.1%})")
    
    return relevant_sections


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
            'figures': compress_figure_metadata(report_knowledge.get('figures', [])),  # ✅ BEST PRACTICE: Compressed figure metadata
        }
    
    elif agent_name == "OutlineCriticAgent":
        # Needs FULL report_knowledge for hallucination checking
        return report_knowledge
    
    elif agent_name == "SlideAndScriptGeneratorAgent":
        # Only needs sections that match the outline topics
        if presentation_outline:
            # ✅ BEST PRACTICE: Use semantic similarity for section filtering
            relevant_sections = filter_sections_by_semantic_similarity(
                report_knowledge.get('sections', []),
                presentation_outline
            )
            
            return {
                **base_fields,
                'sections': relevant_sections,
                'key_takeaways': report_knowledge.get('key_takeaways', []),
                'presentation_focus': report_knowledge.get('presentation_focus', {}),
                'figures': compress_figure_metadata(report_knowledge.get('figures', [])),  # ✅ BEST PRACTICE: Compressed figure metadata
                'audience_profile': report_knowledge.get('audience_profile', {}),
            }
        else:
            # No outline available, return essential fields only
            return {
                **base_fields,
                'sections': report_knowledge.get('sections', []),
                'key_takeaways': report_knowledge.get('key_takeaways', []),
                'presentation_focus': report_knowledge.get('presentation_focus', {}),
                'figures': compress_figure_metadata(report_knowledge.get('figures', [])),  # ✅ BEST PRACTICE: Compressed figure metadata
                'audience_profile': report_knowledge.get('audience_profile', {}),
            }
    
    else:
        # Unknown agent - return full knowledge (safe default)
        return report_knowledge


def compress_critic_review(critic_review: Dict[str, Any]) -> Dict[str, Any]:
    """
    ✅ BEST PRACTICE: Context compaction - compress outline critic review for retry.
    Extracts only actionable feedback needed by OutlineGeneratorAgent during retry:
    - hallucination_issues: List of specific hallucination issues with slide numbers
    - safety_issues: List of specific safety violations with slide numbers
    - quality_issues: List of quality issues with severity and suggestions
    - slides_to_fix: List of slide numbers that need fixing
    
    Removes metadata like:
    - review_type (not needed for fixing)
    - overall_quality (not actionable)
    - strengths (not actionable)
    - missing_elements (can be inferred from issues)
    - recommendations (redundant with suggestions in issues)
    - tone_check (not actionable)
    - hallucination_check.score, safety_check.score (not actionable, only issues matter)
    
    Args:
        critic_review: Full critic review dictionary from OutlineCriticAgent
        
    Returns:
        Compressed critic review dictionary with only actionable feedback:
        {
            "hallucination_issues": [...],
            "safety_issues": [...],
            "quality_issues": [...],
            "slides_to_fix": [1, 2, 3]
        }
    """
    if not isinstance(critic_review, dict):
        return critic_review
    
    # Extract hallucination issues
    hallucination_check = critic_review.get("hallucination_check", {})
    hallucination_issues = hallucination_check.get("grounding_issues", [])
    
    # Extract safety issues
    safety_check = critic_review.get("safety_check", {})
    safety_issues = safety_check.get("violations", [])
    
    # Extract quality issues (from main issues array)
    quality_issues = []
    issues = critic_review.get("issues", [])
    for issue in issues:
        if isinstance(issue, dict):
            # Only include issues with severity and suggestion
            if "severity" in issue and "suggestion" in issue:
                quality_issues.append({
                    "severity": issue.get("severity"),
                    "issue": issue.get("issue"),
                    "suggestion": issue.get("suggestion")
                })
    
    # Extract slide numbers that need fixing
    slides_to_fix = set()
    
    # From hallucination issues
    for issue in hallucination_issues:
        if isinstance(issue, dict):
            slide_num = issue.get("slide_number")
            if slide_num is not None:
                try:
                    slides_to_fix.add(int(slide_num))
                except (ValueError, TypeError):
                    pass
    
    # From safety issues
    for issue in safety_issues:
        if isinstance(issue, dict):
            slide_num = issue.get("slide_number")
            if slide_num is not None:
                try:
                    slides_to_fix.add(int(slide_num))
                except (ValueError, TypeError):
                    pass
    
    compressed = {
        "hallucination_issues": hallucination_issues,
        "safety_issues": safety_issues,
        "quality_issues": quality_issues,
        "slides_to_fix": sorted(list(slides_to_fix)) if slides_to_fix else []
    }
    
    return compressed


def compress_layout_review(layout_review: Dict[str, Any]) -> Dict[str, Any]:
    """
    ✅ BEST PRACTICE: Context compaction - compress layout review for retry.
    Extracts only actionable feedback needed by SlideAndScriptGeneratorAgent during retry:
    - issues: List of specific issues found
    - slides_to_fix: List of slide numbers that need fixing
    
    Removes metadata like:
    - review_type (not needed for fixing)
    - presentation_id (not needed for fixing)
    - total_slides, total_slides_reviewed (not needed for fixing)
    - issues_summary (redundant, issues list is sufficient)
    - overlap_severity (can be inferred from issues)
    - overall_quality (not actionable)
    - passed (not actionable, agent should fix regardless)
    
    Args:
        layout_review: Full layout review dictionary from LayoutCriticAgent
        
    Returns:
        Compressed layout review dictionary with only actionable feedback:
        {
            "issues": [...],  # List of specific issues
            "slides_to_fix": [1, 4, 5]  # Slide numbers that need fixing
        }
    """
    if not isinstance(layout_review, dict):
        return layout_review
    
    # Extract issues - handle nested structure (e.g., review_layout_tool_response wrapper)
    issues = []
    if "review_layout_tool_response" in layout_review:
        # Handle nested structure from tool response
        nested_review = layout_review.get("review_layout_tool_response", {})
        if isinstance(nested_review, dict):
            issues = nested_review.get("issues", [])
    else:
        issues = layout_review.get("issues", [])
    
    # Extract slide numbers that have issues
    slides_to_fix = set()
    for issue in issues:
        if isinstance(issue, dict):
            # Check multiple possible field names for slide number
            slide_num = issue.get("slide_number") or issue.get("slide") or issue.get("slide_num")
            if slide_num is not None:
                try:
                    slides_to_fix.add(int(slide_num))
                except (ValueError, TypeError):
                    pass  # Skip invalid slide numbers
    
    # If no slides found in issues, check if there are any issues at all
    # If there are issues but no slide numbers, we can't determine which slides to fix
    # In that case, return empty slides_to_fix (agent will need to infer from issues)
    
    compressed = {
        "issues": issues,
        "slides_to_fix": sorted(list(slides_to_fix)) if slides_to_fix else []
    }
    
    return compressed


def compute_incremental_updates(
    old_version: Dict[str, Any],
    new_version: Dict[str, Any],
    version_type: str = "outline"  # "outline" or "slide_and_script"
) -> Dict[str, Any]:
    """
    ✅ BEST PRACTICE: Context compaction - compute incremental updates for retry.
    Compares old and new versions to extract only the changes (delta).
    
    Args:
        old_version: Previous version (e.g., old presentation_outline or slide_and_script)
        new_version: New version to compare against
        version_type: Type of version ("outline" or "slide_and_script")
        
    Returns:
        Incremental update dictionary:
        {
            "slides_to_update": [1, 4],
            "changes": {
                "slide_1": {...},  # Only changed fields
                "slide_4": {...}
            }
        }
    """
    if not isinstance(old_version, dict) or not isinstance(new_version, dict):
        return {"slides_to_update": [], "changes": {}}
    
    slides_to_update = []
    changes = {}
    
    if version_type == "outline":
        old_slides = old_version.get("slides", [])
        new_slides = new_version.get("slides", [])
        
        # Create maps by slide_number
        old_slide_map = {slide.get("slide_number"): slide for slide in old_slides if slide.get("slide_number")}
        new_slide_map = {slide.get("slide_number"): slide for slide in new_slides if slide.get("slide_number")}
        
        # Find changed slides
        all_slide_numbers = set(old_slide_map.keys()) | set(new_slide_map.keys())
        
        for slide_num in all_slide_numbers:
            old_slide = old_slide_map.get(slide_num, {})
            new_slide = new_slide_map.get(slide_num, {})
            
            # Compare slides (simple deep comparison)
            if old_slide != new_slide:
                slides_to_update.append(slide_num)
                # Only include changed fields
                slide_changes = {}
                for key in new_slide:
                    if new_slide.get(key) != old_slide.get(key):
                        slide_changes[key] = new_slide[key]
                if slide_changes:
                    changes[f"slide_{slide_num}"] = slide_changes
    
    elif version_type == "slide_and_script":
        # Compare slide_deck slides
        old_slide_deck = old_version.get("slide_deck", {})
        new_slide_deck = new_version.get("slide_deck", {})
        
        old_slides = old_slide_deck.get("slides", [])
        new_slides = new_slide_deck.get("slides", [])
        
        old_slide_map = {slide.get("slide_number"): slide for slide in old_slides if slide.get("slide_number")}
        new_slide_map = {slide.get("slide_number"): slide for slide in new_slides if slide.get("slide_number")}
        
        all_slide_numbers = set(old_slide_map.keys()) | set(new_slide_map.keys())
        
        for slide_num in all_slide_numbers:
            old_slide = old_slide_map.get(slide_num, {})
            new_slide = new_slide_map.get(slide_num, {})
            
            if old_slide != new_slide:
                slides_to_update.append(slide_num)
                slide_changes = {}
                for key in new_slide:
                    if new_slide.get(key) != old_slide.get(key):
                        slide_changes[key] = new_slide[key]
                if slide_changes:
                    changes[f"slide_{slide_num}"] = slide_changes
    
    return {
        "slides_to_update": sorted(slides_to_update),
        "changes": changes
    }


def compress_figure_metadata(figures: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    ✅ BEST PRACTICE: Context compaction - compress figure metadata.
    Extracts only essential fields needed by agents:
    - id: Figure identifier
    - importance: Importance score (for prioritization)
    
    Removes metadata like:
    - caption (not needed for outline/slide generation)
    - inferred_role (not needed)
    - recommended_use (not needed)
    
    Args:
        figures: List of figure dictionaries with full metadata
        
    Returns:
        Compressed list of figures with only id and importance:
        [
            {"id": "fig1", "importance": 1},
            {"id": "fig2", "importance": 2}
        ]
    """
    if not isinstance(figures, list):
        return figures
    
    compressed = []
    for figure in figures:
        if not isinstance(figure, dict):
            continue
        
        compressed_figure = {
            "id": figure.get("id"),
            "importance": figure.get("importance_score") or figure.get("importance", 1)
        }
        
        # Only include if we have an id
        if compressed_figure.get("id"):
            compressed.append(compressed_figure)
    
    return compressed


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


def compress_presentation_script(presentation_script: Dict[str, Any]) -> Dict[str, Any]:
    """
    ✅ BEST PRACTICE: Context compaction - compress presentation script for export.
    Extracts only essential fields needed by SlidesExportAgent for speaker notes:
    - script_sections with only slide_number, speaker_notes (condensed), and estimated_time
    - total_estimated_time
    
    Removes metadata like:
    - opening_line (not needed for speaker notes)
    - transitions (from_previous, to_next) (not needed for speaker notes)
    - key_phrases (not needed for speaker notes)
    - main_content (detailed explanations) (not needed, condensed into speaker_notes)
    - notes (redundant with speaker_notes)
    - script_metadata (tone, language_level) (not needed for export)
    - opening_remarks, closing_remarks (not needed for speaker notes)
    
    Args:
        presentation_script: Full presentation script dictionary
        
    Returns:
        Compressed presentation script dictionary with only essential fields:
        {
            "script_sections": [
                {
                    "slide_number": 1,
                    "speaker_notes": "<condensed notes>",
                    "estimated_time": 60
                }
            ],
            "total_estimated_time": 300
        }
    """
    if not isinstance(presentation_script, dict):
        return presentation_script
    
    script_sections = presentation_script.get("script_sections", [])
    compressed_sections = []
    
    for section in script_sections:
        if not isinstance(section, dict):
            continue
        
        slide_number = section.get("slide_number")
        estimated_time = section.get("estimated_time")
        
        # Condense speaker notes from multiple sources
        speaker_notes_parts = []
        
        # Get opening_line if present
        opening_line = section.get("opening_line", "")
        if opening_line:
            speaker_notes_parts.append(opening_line)
        
        # Get main_content explanations (condensed)
        main_content = section.get("main_content", [])
        if main_content:
            for content_item in main_content:
                if isinstance(content_item, dict):
                    point = content_item.get("point", "")
                    explanation = content_item.get("explanation", "")
                    if explanation:
                        speaker_notes_parts.append(f"{point}: {explanation}")
                    elif point:
                        speaker_notes_parts.append(point)
        
        # Get notes if present
        notes = section.get("notes", "")
        if notes:
            speaker_notes_parts.append(notes)
        
        # Combine into single speaker_notes string
        speaker_notes = " | ".join(speaker_notes_parts) if speaker_notes_parts else ""
        
        compressed_section = {
            "slide_number": slide_number,
            "speaker_notes": speaker_notes,
            "estimated_time": estimated_time
        }
        
        # Only include if we have essential data
        if slide_number is not None:
            compressed_sections.append(compressed_section)
    
    compressed = {
        "script_sections": compressed_sections,
        "total_estimated_time": presentation_script.get("script_metadata", {}).get("total_estimated_time") or 
                                presentation_script.get("total_estimated_time")
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

