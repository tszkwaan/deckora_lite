from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
import sys
import os

# Add parent directory to path to import config and tools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import RETRY_CONFIG, DEFAULT_MODEL
from presentation_agent.agents.tools.google_slides_layout_tool import review_slides_layout


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


# Export as 'agent' instead of 'root_agent' so this won't be discovered as a root agent by ADK-web
agent = LlmAgent(
    name="LayoutCriticAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction="""You are the Layout Critic Agent. Your role is to review Google Slides presentations for visual layout issues.

⚠️ CRITICAL: Extract the shareable_url from the JSON in your input message and call review_layout_tool immediately.

------------------------------------------------------------
YOUR TASK (3 SIMPLE STEPS)
------------------------------------------------------------

**STEP 1: Find the JSON in your input**
Your input message contains slides_export_result as JSON. Look for it - it contains a "shareable_url" field.

Example JSON in your input:
{
  "status": "success",
  "presentation_id": "1i6TyEddxmpVbWCGyQWR336lZ_dZt5QeC_HFf_79cZzY",
  "shareable_url": "https://docs.google.com/presentation/d/1i6TyEddxmpVbWCGyQWR336lZ_dZt5QeC_HFf_79cZzY/edit",
  "message": "Google Slides presentation created successfully"
}

**STEP 2: Extract shareable_url**
Take the "shareable_url" value from the JSON. It starts with "https://docs.google.com/presentation/d/"

**STEP 3: Call the tool and return its output**
Call review_layout_tool with that URL:
review_layout_tool("https://docs.google.com/presentation/d/1i6TyEddxmpVbWCGyQWR336lZ_dZt5QeC_HFf_79cZzY/edit", output_dir="presentation_agent/output")

The tool will return a dict with the review results. After calling the tool, return the tool's output as JSON text (not as a dict object).

Example: If the tool returns {"review_type": "layout", "passed": true, ...}, you should respond with:
```json
{"review_type": "layout", "passed": true, ...}
```

**IMPORTANT RULES:**
- ✅ Extract shareable_url from the JSON in your input message
- ✅ Call review_layout_tool with that URL (use the tool, don't just describe it)
- ✅ Return the tool's output as JSON text (wrapped in ```json code block)
- ❌ DO NOT use presentation_id (use shareable_url instead)
- ❌ DO NOT generate your own text response
- ❌ DO NOT say you don't have access to the URL
- ❌ DO NOT say the tool requires arguments - just call it with the URL

The shareable_url is ALWAYS in your input message. Extract it and call the tool immediately.

""",
    tools=[review_layout_tool],
    output_key="layout_review",
)

