"""
Slide and Script Generator Agent.

This agent generates detailed slide content and presentation scripts from the outline.
It creates slide-by-slide content with design specifications, visual elements, and
timed presentation scripts.

Implementation:
- Uses Gemini 2.5 Flash Lite for content generation
- Uses selective context extraction (only relevant report sections per slide) for efficiency
- Has access to chart generator tool (though chart generation is handled separately in parallel)
- Generates both slide_deck and presentation_script in a single output

Design:
- Designed to work with minimal context (selective extraction) to reduce token usage
- Generates content that matches target duration requirements
- Creates design specifications for each slide (layout, colors, fonts)
- Outputs structured JSON with both slides and script

Behavior:
- Processes outline slide-by-slide with relevant report sections
- Generates detailed slide content with visual element specifications
- Creates presentation script with timing and transitions
- Validates output structure (must contain both slide_deck and presentation_script)
- Can handle custom instructions
"""

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
import sys
import os
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RETRY_CONFIG, DEFAULT_MODEL
from presentation_agent.agents.utils.instruction_loader import load_instruction

# Import chart generator tool (available but chart generation handled separately in parallel)
try:
    from presentation_agent.agents.tools.chart_generator_tool import generate_chart_tool
except ImportError:
    # If chart tool is not available, use empty list
    generate_chart_tool = None

# Load instruction from markdown file
_agent_dir = Path(__file__).parent
_instruction = load_instruction(_agent_dir)

# Export as 'agent' instead of 'root_agent' so this won't be discovered as a root agent by ADK-web
agent = LlmAgent(
    name="SlideAndScriptGeneratorAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction=_instruction,
    tools=[generate_chart_tool] if generate_chart_tool else [],
    output_key="slide_and_script",
)