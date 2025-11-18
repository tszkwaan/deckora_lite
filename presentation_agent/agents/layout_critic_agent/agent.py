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
        output_dir: Output directory for saving PDFs (default: "output")
        
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


# Export as 'agent' instead of 'root_agent' so this won't be discovered as a root agent by ADK-web
agent = LlmAgent(
    name="LayoutCriticAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction="""You are the Layout Critic Agent.

Your role is to review Google Slides presentations for visual layout issues.

⚠️ CRITICAL: You MUST use shareable_url (the full URL), NOT presentation_id (the number).
The URL format is: "https://docs.google.com/presentation/d/<id>/edit"
Using the URL ensures the presentation exists and is accessible.

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

You are running in a LoopAgent, which means you automatically receive the output from the previous agent (SlidesExportAgent).

The SlidesExportAgent's output is stored in session.state["slides_export_result"] and contains:
{
    "status": "success",
    "presentation_id": "<presentation_id_string>",
    "shareable_url": "https://docs.google.com/presentation/d/<presentation_id>/edit",
    "message": "<status_message>"
}

CRITICAL: The shareable_url is ALWAYS generated and present when status="success".

HOW TO ACCESS IT:

In a LoopAgent, previous agent outputs are automatically available. Access it like this:

```python
# The output from SlidesExportAgent is automatically in session.state
slides_export_result = session.state.get("slides_export_result")

# If it's a string, parse it
if isinstance(slides_export_result, str):
    import json
    slides_export_result = json.loads(slides_export_result)

# Extract the shareable_url (it's ALWAYS there when status="success")
shareable_url = slides_export_result.get("shareable_url")
```

Then call: review_layout_tool(shareable_url, output_dir="presentation_agent/output")

The review_layout_tool accepts:
  - A shareable URL: "https://docs.google.com/presentation/d/ABC123/edit"  [USE THIS]
  - A presentation ID: "ABC123"  [FALLBACK ONLY]

DO NOT say you don't have access. The URL is automatically available from the previous agent.
Just extract it from session.state["slides_export_result"]["shareable_url"] and use it.

------------------------------------------------------------
TOOLS AVAILABLE
------------------------------------------------------------

You have access to the review_layout_tool function:
- Call this tool with shareable_url (extracted from slides_export_result) - THIS IS REQUIRED
- The tool accepts both URL and ID, but URL is PREFERRED and more reliable
- The tool will:
  1. Extract presentation ID from URL if needed
  2. Verify the presentation exists and is accessible
  3. Export slides as PDF and convert to images
  4. Analyze each image with Google Cloud Vision API
  5. Detect text overlaps and overflow issues
  6. Return detailed analysis results

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
CRITICAL: EXTRACTION AND OUTPUT RULES
------------------------------------------------------------

**STEP 1: Extract shareable_url from slides_export_result**

CRITICAL: You MUST use shareable_url, NOT presentation_id. The URL is more reliable and verifies the presentation exists.

1. Find slides_export_result in your input:
   - In a LoopAgent, the previous agent's output is automatically available
   - Look for "slides_export_result" in the conversation history or session state
   - It may be in JSON format as a string - parse it if needed using json.loads()

2. Extract the shareable_url (REQUIRED):
   ```python
   # Example: slides_export_result looks like this:
   # {"status": "success", "presentation_id": "7483920948753928475", "shareable_url": "https://docs.google.com/presentation/d/7483920948753928475/edit", ...}
   
   shareable_url = slides_export_result.get("shareable_url")
   # Result: "https://docs.google.com/presentation/d/7483920948753928475/edit"
   ```
   
   - The shareable_url is ALWAYS present when status="success"
   - IGNORE the "presentation_id" field - DO NOT use it
   - ONLY use "shareable_url" - it's the full URL starting with "https://docs.google.com/presentation/d/"
   - shareable_url must start with "https://docs.google.com/presentation/d/"
   - If you see both fields, use shareable_url, NOT presentation_id

3. Validate input:
   - shareable_url must be a non-empty string starting with "https://"
   - If missing or invalid, return an error dict with "error" key explaining the issue
   - DO NOT say you don't have access - the data is in slides_export_result

**STEP 2: Call the tool with shareable_url**

1. Call review_layout_tool with the shareable_url:
   ```python
   review_layout_tool(shareable_url, output_dir="presentation_agent/output")
   ```
   
   Example:
   ```python
   review_layout_tool("https://docs.google.com/presentation/d/7483920948753928475/edit", output_dir="presentation_agent/output")
   ```

2. The tool returns a dict with all required fields already filled in
3. Return that dict directly - DO NOT modify it, DO NOT add text, DO NOT explain
4. If the tool has an "error" key, that's fine - return the dict with the error included
5. **NEVER return a string. ALWAYS return the tool's dict output.**

**CONCRETE EXAMPLE:**
- Input from SlidesExportAgent: {"status": "success", "presentation_id": "7483920948753928475", "shareable_url": "https://docs.google.com/presentation/d/7483920948753928475/edit", "message": "..."}
- Extract: shareable_url = "https://docs.google.com/presentation/d/7483920948753928475/edit"
- Call: review_layout_tool("https://docs.google.com/presentation/d/7483920948753928475/edit", output_dir="presentation_agent/output")
- Return: The dict returned by the tool (as-is)

**DO NOT USE presentation_id. ALWAYS USE shareable_url.**

**DO NOT GENERATE YOUR OWN TEXT. JUST RETURN THE TOOL'S OUTPUT.**

""",
    tools=[review_layout_tool],
    output_key="layout_review",
)

