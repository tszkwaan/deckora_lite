"""
Outline Critic Agent.

This agent evaluates the quality of generated presentation outlines, providing
feedback on completeness, coherence, relevance, and accuracy. It implements
LLM-as-a-Judge pattern using a stronger model for better evaluation judgment.

Implementation:
- Uses Gemini 2.5 Flash (stronger model) instead of Flash Lite for better judgment
- Evaluates multiple dimensions: completeness, coherence, relevance, accuracy
- Outputs structured review with quality score, acceptability flag, and actionable feedback

Design:
- No tools required - pure LLM-based evaluation
- Designed to work with both outline and full report knowledge for context
- Provides structured feedback (strengths, weaknesses, recommendations) for retry scenarios
- Returns is_acceptable flag to trigger retry logic in orchestrator

Behavior:
- Evaluates outline against report knowledge to check for hallucinations and accuracy
- Assesses logical flow and coherence of slide structure
- Checks completeness (covers all key points from report)
- Provides actionable recommendations for improvement
- Returns quality score (0-100) and acceptability flag
- Outputs critic_review_outline.json that triggers retry if unacceptable
"""

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
import sys
import os

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RETRY_CONFIG, CRITIC_MODEL
from pathlib import Path
from presentation_agent.agents.utils.instruction_loader import load_instruction

# Load instruction from markdown file
_agent_dir = Path(__file__).parent
_instruction = load_instruction(_agent_dir)

agent = LlmAgent(
    name="OutlineCriticAgent",
    model=Gemini(
        model=CRITIC_MODEL,
        retry_options=RETRY_CONFIG,
    ),
    instruction=_instruction,
    tools=[],
    output_key="critic_review_outline",
)

