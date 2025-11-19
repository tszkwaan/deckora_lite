from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
import sys
import os

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RETRY_CONFIG, DEFAULT_MODEL

# Import Google Slides export tool
from presentation_agent.agents.tools.google_slides_tool import export_slideshow_tool

# Export as 'agent' instead of 'root_agent' so this won't be discovered as a root agent by ADK-web
agent = LlmAgent(
    name="SlidesExportAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction="""You are a Slides Export Agent. Your role is to export generated slides to Google Slides.

You will receive:
- slide_deck: The generated slide deck JSON (from slide_and_script_generator_agent)
- presentation_script: The generated presentation script JSON (from slide_and_script_generator_agent)
- scenario, duration, target_audience, custom_instruction: Presentation configuration

CRITICAL: You MUST call the export_slideshow_tool function. Do NOT skip this step.

STEP 1: Extract the required inputs from your input message (which contains the previous agent's output):
- Your input message contains the output from SlideAndScriptGeneratorAgent, which is a JSON object with "slide_deck" and "presentation_script" keys.
- Parse the JSON from your input message. The JSON may be wrapped in ```json ... ``` code blocks, or it may be raw JSON.
- slide_and_script: The entire parsed JSON object from your input message
- slide_deck: Extract from slide_and_script["slide_deck"]
- presentation_script: Extract from slide_and_script["presentation_script"]
- config: Build a dict with scenario, duration, target_audience, custom_instruction from session.state
- title: Optional, can be empty string ""

CRITICAL: Your input message IS the output from SlideAndScriptGeneratorAgent. Parse it directly - do NOT look for it in session.state. The previous agent's output is passed to you as your input message.

STEP 2: Call export_slideshow_tool with these parameters:
export_slideshow_tool(
    slide_deck=slide_deck,
    presentation_script=presentation_script,
    config={"scenario": scenario, "duration": duration, "target_audience": target_audience, "custom_instruction": custom_instruction},
    title=""
)

STEP 3: The tool returns a dict with this structure:
{
    "status": "success" or "partial_success" or "error",
    "presentation_id": "<presentation_id_string>",  # Present if status is "success" or "partial_success"
    "shareable_url": "https://docs.google.com/presentation/d/<presentation_id>/edit",  # Present if status is "success" or "partial_success"
    "message": "<status_message>",
    "error": "<error_description>"  # Present if status is "error" or "partial_success"
}

IMPORTANT: 
- If status="success": Presentation created successfully, use shareable_url
- If status="partial_success": Presentation created but encountered errors, STILL use shareable_url (presentation exists and can be accessed)
- If status="error": Presentation was NOT created, return the error dict as-is

STEP 4: Return the tool's output dict AS-IS. Do NOT convert to string. Do NOT add text. Do NOT modify it.

The shareable_url is ALWAYS present when status="success" OR status="partial_success".

Return ONLY the dict returned by export_slideshow_tool, nothing else.
""",
    tools=[export_slideshow_tool],
    output_key="slides_export_result",
)

