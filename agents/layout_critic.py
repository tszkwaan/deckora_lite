"""
Layout Critic Agent.
Reviews Google Slides presentations for visual layout issues using Vision API.
"""

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from config import RETRY_CONFIG, DEFAULT_MODEL
from tools.google_slides_layout_tool import review_slides_layout


def create_layout_critic_agent():
    """
    Create the Layout Critic Agent.
    
    This agent reviews Google Slides presentations for visual layout issues
    such as text overlap, text overflow, and spacing problems.
    """
    
    def review_layout_tool(presentation_id: str, output_dir: str = "output") -> dict:
        """
        Tool function to review Google Slides presentation layout.
        
        Args:
            presentation_id: Google Slides presentation ID (must be a string)
            output_dir: Output directory for saving PDFs (default: "output")
            
        Returns:
            Dict with layout review results including overlaps, overflow, and recommendations
            Always returns a dict, even on error (with 'error' key)
        """
        # Validate input to prevent MALFORMED_FUNCTION_CALL
        if not isinstance(presentation_id, str):
            # Try to convert to string
            if presentation_id is None:
                return {
                    'review_type': 'layout_vision_api',
                    'presentation_id': None,
                    'error': 'presentation_id cannot be None',
                    'total_slides_reviewed': 0,
                    'issues_summary': {'total_issues': 0, 'overlaps_detected': 0, 'overflow_detected': 0, 'overlap_severity': {'critical': 0, 'major': 0, 'minor': 0}},
                    'issues': [],
                    'overall_quality': 'unknown',
                    'passed': False
                }
            try:
                presentation_id = str(presentation_id)
            except Exception as e:
                return {
                    'review_type': 'layout_vision_api',
                    'presentation_id': None,
                    'error': f'presentation_id must be a string, got {type(presentation_id).__name__}: {e}',
                    'total_slides_reviewed': 0,
                    'issues_summary': {'total_issues': 0, 'overlaps_detected': 0, 'overflow_detected': 0, 'overlap_severity': {'critical': 0, 'major': 0, 'minor': 0}},
                    'issues': [],
                    'overall_quality': 'unknown',
                    'passed': False
                }
        
        # Strip whitespace
        presentation_id = presentation_id.strip()
        
        if not presentation_id:
            return {
                'review_type': 'layout_vision_api',
                'presentation_id': '',
                'error': 'presentation_id cannot be empty',
                'total_slides_reviewed': 0,
                'issues_summary': {'total_issues': 0, 'overlaps_detected': 0, 'overflow_detected': 0, 'overlap_severity': {'critical': 0, 'major': 0, 'minor': 0}},
                'issues': [],
                'overall_quality': 'unknown',
                'passed': False
            }
        
        # Validate output_dir
        if not isinstance(output_dir, str):
            output_dir = str(output_dir) if output_dir else "output"
        
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
    
    return LlmAgent(
        name="LayoutCriticAgent",
        model=Gemini(
            model=DEFAULT_MODEL,
            retry_options=RETRY_CONFIG,
        ),
        instruction="""You are the Layout Critic Agent.

Your role is to review Google Slides presentations for visual layout issues.

------------------------------------------------------------
OBJECTIVES
------------------------------------------------------------

1. Use the review_layout_tool to analyze the Google Slides presentation
2. Review the tool's output for:
   - Text overlap issues (critical, major, minor severity)
   - Text overflow issues (text extending beyond boundaries)
   - Overall layout quality
3. Provide actionable recommendations for fixing issues
4. Assess severity and prioritize issues

------------------------------------------------------------
INPUTS YOU WILL RECEIVE
------------------------------------------------------------

You will receive:
- presentation_id: Google Slides presentation ID to review
- The tool will export slides as images and analyze them with Vision API

------------------------------------------------------------
TOOLS AVAILABLE
------------------------------------------------------------

You have access to the review_layout_tool function:
- Call this tool with presentation_id
- The tool will:
  1. Export slides as PDF and convert to images
  2. Analyze each image with Google Cloud Vision API
  3. Detect text overlaps and overflow issues
  4. Return detailed analysis results

------------------------------------------------------------
REQUIRED OUTPUT FORMAT
------------------------------------------------------------

After reviewing, respond with JSON:

{
  "review_type": "layout",
  "presentation_id": "<presentation_id>",
  "overall_quality": "<excellent | good | needs_improvement | poor>",
  "total_slides_reviewed": <number>,
  "issues_summary": {
    "total_issues": <number>,
    "overlaps_detected": <number>,
    "overflow_detected": <number>,
    "overlap_severity": {
      "critical": <number>,
      "major": <number>,
      "minor": <number>
    }
  },
  "issues": [
    {
      "slide_number": <number>,
      "issue_type": "<text_overlap | text_overflow | spacing>",
      "severity": "<critical | major | minor>",
      "description": "<detailed description>",
      "affected_elements": ["<element1>", "<element2>"],
      "suggestion": "<how to fix>"
    }
  ],
  "recommendations": [
    "<recommendation 1>",
    "<recommendation 2>"
  ],
  "passed": true/false
}

------------------------------------------------------------
CRITICAL: OUTPUT RULES
------------------------------------------------------------

**THE TOOL ALREADY RETURNS A COMPLETE JSON DICT. JUST RETURN IT AS-IS.**

1. Call review_layout_tool(presentation_id, output_dir)
2. The tool returns a dict with all required fields already filled in
3. Return that dict directly - DO NOT modify it, DO NOT add text, DO NOT explain
4. If the tool has an "error" key, that's fine - return the dict with the error included
5. **NEVER return a string. ALWAYS return the tool's dict output.**

Example: If tool returns {"review_type": "layout", "error": "pdf2image not installed", ...}
Then you return: {"review_type": "layout", "error": "pdf2image not installed", ...}
Do NOT return: "The layout review could not be completed because..."

**DO NOT GENERATE YOUR OWN TEXT. JUST RETURN THE TOOL'S OUTPUT.**

""",
        tools=[review_layout_tool],
        output_key="layout_review",
    )

