"""
Report Understanding Agent.

This agent extracts structured knowledge from PDF documents, identifying key sections,
figures, takeaways, and audience profiles. It serves as the first step in the pipeline,
transforming raw document content into structured knowledge that downstream agents can use.

Implementation:
- Uses Gemini 2.5 Flash Lite for efficient text understanding
- Processes PDF content (loaded via utility function before agent execution)
- Outputs structured JSON with sections, key takeaways, figures, and metadata

Design:
- No tools required - pure LLM-based extraction
- Designed to infer scenario and target audience if not explicitly provided
- Creates structured knowledge representation for efficient downstream processing

Behavior:
- Extracts document structure (sections, headings, key points)
- Identifies figures, tables, and visual elements
- Infers presentation scenario and target audience from content
- Generates one-sentence summary and key takeaways
- Outputs report_knowledge.json that feeds into outline generation
"""

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
import sys
import os

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RETRY_CONFIG, DEFAULT_MODEL
from pathlib import Path
from presentation_agent.utils.instruction_loader import load_instruction

# Load instruction from markdown file
_agent_dir = Path(__file__).parent
_instruction = load_instruction(_agent_dir)

agent = LlmAgent(
    name="ReportUnderstandingAgent",
    model=Gemini(
        model=DEFAULT_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction=_instruction,
    tools=[],
    output_key="report_knowledge",
)

