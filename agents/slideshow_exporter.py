"""
Slideshow Exporter Agent.
Exports slide deck and script to Google Slides using Google Slides API as an agent tool.
"""

from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from config import RETRY_CONFIG, DEFAULT_MODEL
from utils.google_slides_exporter import export_to_google_slides


def create_slideshow_exporter_agent():
    """
    Create the Slideshow Exporter Agent.
    
    This agent exports the slide deck and script to Google Slides format.
    It uses the Google Slides API as a tool to create the presentation.
    """
    
    # Define the tool function that the agent can use
    def export_slideshow_tool(slide_deck: dict, presentation_script: dict, config: dict, title: Optional[str] = None) -> dict:
        """
        Tool function to export slide deck and script to Google Slides.
        
        Args:
            slide_deck: Slide deck JSON from slide generator
            presentation_script: Script JSON from script generator
            config: Presentation configuration dict
            title: Optional presentation title (defaults to "Generated Presentation")
            
        Returns:
            Dict with presentation_id and shareable_url
        """
        # Create a simple config object-like structure for compatibility
        class SimpleConfig:
            def __init__(self, config_dict):
                self.scenario = config_dict.get('scenario', 'presentation')
                self.duration = config_dict.get('duration', '20 minutes')
                self.target_audience = config_dict.get('target_audience')
                self.custom_instruction = config_dict.get('custom_instruction', '')
        
        simple_config = SimpleConfig(config)
        presentation_title = title or f"Presentation: {simple_config.scenario}"
        
        return export_to_google_slides(
            slide_deck=slide_deck,
            presentation_script=presentation_script,
            config=simple_config,
            title=presentation_title
        )
    
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
- Extract slide_deck and presentation_script from the message sections above
- Build config dict from [CONFIG] section
- Call the tool: export_slideshow_tool(slide_deck, presentation_script, config_dict)
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

