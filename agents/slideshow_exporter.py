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
        instruction="""You are the Slideshow Exporter Agent. Export slide deck and script to Google Slides.

TOOL: export_slideshow_tool(slide_deck: dict, presentation_script: dict, config: dict, title: str = "")

INSTRUCTIONS:
1. Extract the three JSON dicts from the message (slide_deck, presentation_script, config)
2. Parse them if they're JSON strings, or use them directly if they're already dicts
3. Call export_slideshow_tool with the three dicts and empty title string
4. Return the tool's result as JSON with status, presentation_id, shareable_url

OUTPUT FORMAT (JSON only, no markdown):
{"status": "success", "presentation_id": "...", "shareable_url": "...", "message": "..."}

CRITICAL: 
- All parameters MUST be dicts (not strings)
- Parse JSON strings to dicts before calling the tool
- The tool accepts dicts directly - pass them as-is after parsing
""",
        tools=[export_slideshow_tool],
        output_key="slideshow_export_result",
    )

