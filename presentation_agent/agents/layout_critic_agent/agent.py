from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
import sys
import os
import logging

# Add parent directory to path to import config and tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import RETRY_CONFIG, DEFAULT_MODEL
from pathlib import Path
from presentation_agent.agents.utils.instruction_loader import load_instruction
logger = logging.getLogger(__name__)


def review_layout_tool(presentation_id_or_url: str, output_dir: str = "presentation_agent/output") -> dict:
    """
    Tool function to review Google Slides presentation layout.
    
    Args:
        presentation_id_or_url: Google Slides presentation ID or shareable URL
            - ID format: "6701963407731676303"
            - URL format: "https://docs.google.com/presentation/d/6701963407731676303/edit"
        output_dir: Output directory for saving PDFs (default: "presentation_agent/output")
        
    Returns:
        Dict with layout review results including overlaps, overflow, and recommendations
        Always returns a dict, even on error (with 'error' key)
    """
    import re
    from presentation_agent.agents.tools.google_slides_layout_tool import extract_presentation_id_from_url
    
    # Validate input to prevent MALFORMED_FUNCTION_CALL
    if not isinstance(presentation_id_or_url, str):
        # Try to convert to string
        if presentation_id_or_url is None:
            return {
                'review_type': 'layout_vision_api',
                'presentation_id': None,
                'error': 'presentation_id_or_url cannot be None',
                'total_slides_reviewed': 0,
                'issues_summary': {'total_issues': 0, 'overlaps_detected': 0, 'overflow_detected': 0, 'overlap_severity': {'critical': 0, 'major': 0, 'minor': 0}},
                'issues': [],
                'overall_quality': 'unknown',
                'passed': False
            }
        try:
            presentation_id_or_url = str(presentation_id_or_url)
        except Exception as e:
            return {
                'review_type': 'layout_vision_api',
                'presentation_id': None,
                'error': f'presentation_id_or_url must be a string, got {type(presentation_id_or_url).__name__}: {e}',
                'total_slides_reviewed': 0,
                'issues_summary': {'total_issues': 0, 'overlaps_detected': 0, 'overflow_detected': 0, 'overlap_severity': {'critical': 0, 'major': 0, 'minor': 0}},
                'issues': [],
                'overall_quality': 'unknown',
                'passed': False
            }
    
    # Strip whitespace
    presentation_id_or_url = presentation_id_or_url.strip()
    
    if not presentation_id_or_url:
        return {
            'review_type': 'layout_vision_api',
            'presentation_id': '',
            'error': 'presentation_id_or_url cannot be empty',
            'total_slides_reviewed': 0,
            'issues_summary': {'total_issues': 0, 'overlaps_detected': 0, 'overflow_detected': 0, 'overlap_severity': {'critical': 0, 'major': 0, 'minor': 0}},
            'issues': [],
            'overall_quality': 'unknown',
            'passed': False
        }
    
    # Extract presentation_id from URL if it's a URL
    if 'docs.google.com' in presentation_id_or_url or 'presentation' in presentation_id_or_url:
        presentation_id = extract_presentation_id_from_url(presentation_id_or_url)
        if not presentation_id:
            return {
                'review_type': 'layout_vision_api',
                'presentation_id': None,
                'error': f'Could not extract presentation_id from URL: {presentation_id_or_url}',
                'total_slides_reviewed': 0,
                'issues_summary': {'total_issues': 0, 'overlaps_detected': 0, 'overflow_detected': 0, 'overlap_severity': {'critical': 0, 'major': 0, 'minor': 0}},
                'issues': [],
                'overall_quality': 'unknown',
                'passed': False
            }
    else:
        # Assume it's already a presentation_id
        presentation_id = presentation_id_or_url
    
    # Validate output_dir
    if not isinstance(output_dir, str):
        output_dir = str(output_dir) if output_dir else "presentation_agent/output"
    
    try:
        result = review_slides_layout(presentation_id, output_dir=output_dir)
        # Ensure result is always a dict
        if not isinstance(result, dict):
            return {
                'review_type': 'layout_vision_api',
                'presentation_id': presentation_id,
                'error': f'Tool returned non-dict result: {type(result).__name__}',
                'total_slides_reviewed': 0,
                'issues_summary': {'total_issues': 0, 'overlaps_detected': 0, 'overflow_detected': 0, 'overlap_severity': {'critical': 0, 'major': 0, 'minor': 0}},
                'issues': [],
                'overall_quality': 'unknown',
                'passed': False
            }
        return result
    except Exception as e:
        # Catch any exceptions and return a proper error dict
        error_msg = str(e)
        return {
            'review_type': 'layout_vision_api',
            'presentation_id': presentation_id,
            'error': error_msg,
            'total_slides_reviewed': 0,
            'issues_summary': {
                'total_issues': 0,
                'overlaps_detected': 0,
                'overflow_detected': 0,
                'overlap_severity': {
                    'critical': 0,
                    'major': 0,
                    'minor': 0
                }
            },
            'issues': [],
            'overall_quality': 'unknown',
            'passed': False
        }


def extract_layout_review_from_tool_result(callback_context):
    """
    After-agent callback to extract layout_review from agent output or tool result and store it in state.
    This ensures the layout_review is properly stored even if ADK doesn't parse it correctly.
    """
    import json
    import re
    
    try:
        layout_review = None
        
        # Priority 1: Check if layout_review is already in state (from agent output)
        if hasattr(callback_context, 'state'):
            try:
                if hasattr(callback_context.state, '__dict__'):
                    layout_review = callback_context.state.__dict__.get('layout_review')
                elif hasattr(callback_context.state, 'get'):
                    layout_review = callback_context.state.get('layout_review')
                else:
                    layout_review = getattr(callback_context.state, 'layout_review', None)
                
                if layout_review and isinstance(layout_review, dict):
                    logger.info("✅ Found layout_review already in state")
                    return
            except Exception as e:
                logger.debug(f"   Could not check state for layout_review: {e}")
        
        # Priority 2: Try to extract from agent's text output (if agent outputted JSON string)
        # Check if there's an output text we can parse
        if hasattr(callback_context, 'output') and callback_context.output:
            output_text = str(callback_context.output)
            # Try to find JSON in the output
            try:
                # Remove markdown code blocks if present
                cleaned = output_text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:].lstrip()
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:].lstrip()
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].rstrip()
                
                # Try to find JSON object
                start_idx = cleaned.find("{")
                if start_idx != -1:
                    # Find matching closing brace
                    brace_count = 0
                    end_idx = start_idx
                    for i in range(start_idx, len(cleaned)):
                        if cleaned[i] == '{':
                            brace_count += 1
                        elif cleaned[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i
                                break
                    
                    if end_idx > start_idx:
                        json_str = cleaned[start_idx:end_idx+1]
                        # Convert Python booleans
                        json_str = re.sub(r'\bTrue\b', 'true', json_str)
                        json_str = re.sub(r'\bFalse\b', 'false', json_str)
                        json_str = re.sub(r'\bNone\b', 'null', json_str)
                        # Fix invalid escape sequences
                        json_str = re.sub(r"\\'", "'", json_str)
                        
                        parsed = json.loads(json_str)
                        if isinstance(parsed, dict) and ('review_type' in parsed or 'passed' in parsed):
                            layout_review = parsed
                            logger.info("✅ Parsed layout_review from agent output text")
            except (json.JSONDecodeError, ValueError, AttributeError) as e:
                logger.debug(f"   Could not parse output text as JSON: {e}")
        
        # Priority 3: If we have slides_export_result in state, we could call the tool again
        # But that's wasteful, so we skip this and let main.py handle extraction from tool_results
        
        # Store in state if found
        if layout_review:
            if hasattr(callback_context, 'state'):
                try:
                    if hasattr(callback_context.state, '__dict__'):
                        callback_context.state.__dict__['layout_review'] = layout_review
                    elif hasattr(callback_context.state, '__setitem__'):
                        callback_context.state['layout_review'] = layout_review
                    else:
                        setattr(callback_context.state, 'layout_review', layout_review)
                    logger.info("✅ Stored layout_review in state via callback")
                except Exception as e:
                    logger.warning(f"⚠️ Error storing layout_review in state: {e}")
            else:
                logger.warning("⚠️ No state object in callback_context")
        else:
            logger.debug("⚠️ Could not extract layout_review from callback - will rely on main.py extraction")
    except Exception as e:
        logger.error(f"❌ Error in extract_layout_review_from_tool_result callback: {e}")
        import traceback
        logger.error(traceback.format_exc())


# Export as 'agent' instead of 'root_agent' so this won't be discovered as a root agent by ADK-web
# Load instruction from markdown file
_agent_dir = Path(__file__).parent
_instruction = load_instruction(_agent_dir)

agent = LlmAgent(
    name="LayoutCriticAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction=_instruction,
    tools=[review_layout_tool],
    output_key="layout_review",
    after_agent_callback=extract_layout_review_from_tool_result,
)

