"""
Outline Generator Agent.

This agent is responsible for generating the presentation outline structure from report knowledge.
It creates a logical flow of slides with timing, content notes, and slide breakdown.

Implementation:
- Uses Gemini 2.5 Flash Lite for fast, cost-effective generation
- Loads instructions from markdown file for maintainability
- Outputs structured JSON with slide breakdown and timing information

Design:
- No tools required - pure LLM-based generation
- Designed to work with critic feedback for retry scenarios
- Accepts previous outline and critic feedback as input for improvement iterations

Behavior:
- Generates outline based on report knowledge, scenario, and target audience
- Creates slide-by-slide breakdown with estimated timing
- Can incorporate critic feedback and previous outline when retrying
- Outputs JSON structure that feeds into slide generation step
"""

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
import sys
import os

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RETRY_CONFIG, DEFAULT_MODEL
from pathlib import Path
from presentation_agent.agents.utils.instruction_loader import load_instruction

# Load instruction from markdown file
_agent_dir = Path(__file__).parent
_instruction = load_instruction(_agent_dir)

agent = LlmAgent(
    name="OutlineGeneratorAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction=_instruction,
    tools=[],
    output_key="presentation_outline",
)

