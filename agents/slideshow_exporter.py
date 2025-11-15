"""
Slideshow Exporter Agent.
Exports slide deck and script to Google Slides using Google Slides API as an agent tool.
"""

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from config import RETRY_CONFIG, DEFAULT_MODEL
from tools.google_slides_tool import export_slideshow_tool


def create_slideshow_exporter_agent():
    """
    Create the Slideshow Exporter Agent.
    
    This agent exports the slide deck and script to Google Slides format.
    It uses the Google Slides API as a tool to create the presentation.
    """
    
    return LlmAgent(
        name="SlideshowExporterAgent",
        model=Gemini(
            model=DEFAULT_MODEL,
            retry_options=RETRY_CONFIG,
        ),
        instruction="""You are the Slideshow Exporter Agent.

Your role is to export the generated slide deck and presentation script to Google Slides format.

------------------------------------------------------------
OBJECTIVES
------------------------------------------------------------

1. Read slide_deck from session state (from Slide Generator Agent)
2. Read presentation_script from session state (from Script Generator Agent)
3. Read presentation configuration (scenario, duration, etc.)
4. Use the export_slideshow_tool to create a Google Slides presentation
5. Ensure all slides and speaker notes are properly exported
6. Return the presentation ID and shareable URL

------------------------------------------------------------
INPUTS YOU WILL RECEIVE
------------------------------------------------------------

You will have access to session state with:
- slide_deck: Slide deck JSON from Slide Generator Agent
- presentation_script: Script JSON from Script Generator Agent
- scenario: Presentation scenario
- duration: Presentation duration
- target_audience: Target audience
- custom_instruction: Custom instructions

------------------------------------------------------------
TOOLS AVAILABLE
------------------------------------------------------------

You have access to the export_slideshow_tool function:
- Call this tool with slide_deck, presentation_script, config dict, and optional title
- The tool will create a Google Slides presentation and return presentation_id and shareable_url

------------------------------------------------------------
REQUIRED OUTPUT FORMAT
------------------------------------------------------------

After successfully exporting, respond with JSON:

{
  "status": "success",
  "presentation_id": "<google_slides_presentation_id>",
  "shareable_url": "<url_to_google_slides>",
  "message": "<confirmation message>"
}

If export fails, respond with:

{
  "status": "error",
  "error": "<error description>",
  "message": "<helpful message>"
}

------------------------------------------------------------
STYLE REQUIREMENTS
------------------------------------------------------------

- Use the export_slideshow_tool to perform the actual export
- Extract slide_deck and presentation_script from the [SLIDE_DECK] and [PRESENTATION_SCRIPT] sections above
- Build config dict from [CONFIG] section (it's already JSON, just parse it)
- **CRITICAL**: Call the tool with exactly these parameters:
  export_slideshow_tool(
    slide_deck=<the dict from [SLIDE_DECK] section>,
    presentation_script=<the dict from [PRESENTATION_SCRIPT] section>,
    config=<the dict from [CONFIG] section>,
    title=""  # Leave empty string to use default title
  )
- The tool will return a dict with status, presentation_id, and shareable_url
- **CRITICAL**: After the tool returns successfully, you MUST:
  1. Take the tool's return value (it's already a dict with status, presentation_id, shareable_url)
  2. Output it as JSON in the exact format shown above
  3. The output_key is "slideshow_export_result" - this will automatically set it in state
- If the tool fails, return error JSON with status "error"
- Output must be valid JSON without markdown code blocks
- Do NOT wrap the JSON in markdown code blocks (no ```json)

""",
        tools=[export_slideshow_tool],
        output_key="slideshow_export_result",
    )

