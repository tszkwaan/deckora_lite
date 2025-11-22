from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
import sys
import os
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RETRY_CONFIG, DEFAULT_MODEL
from presentation_agent.agents.utils.instruction_loader import load_instruction

# Import chart generator tool
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