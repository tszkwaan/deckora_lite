"""
Agent execution utilities.
Extracted from main.py to follow Single Responsibility Principle.
"""

import json
import logging
from typing import Any, Optional, Dict
from google.adk.runners import InMemoryRunner
# Session type is dynamic from ADK

from presentation_agent.agents.utils.helpers import extract_output_from_events
from presentation_agent.core.json_parser import parse_json_robust

logger = logging.getLogger(__name__)


class AgentExecutor:
    """
    Handles agent execution with consistent error handling and output parsing.
    """
    
    def __init__(self, session: Any):
        self.session = session
    
    async def run_agent(
        self,
        agent: Any,
        user_message: str,
        output_key: str,
        parse_json: bool = True
    ) -> Optional[Any]:
        """
        Execute an agent and extract its output.
        
        Args:
            agent: The ADK agent to execute
            user_message: Input message for the agent
            output_key: Key to extract from agent output
            parse_json: Whether to parse JSON from string output
            
        Returns:
            Agent output (parsed if parse_json=True), or None if failed
        """
        runner = InMemoryRunner(agent=agent)
        events = await runner.run_debug(user_message, session_id=self.session.id)
        
        output = extract_output_from_events(events, output_key)
        
        if output is None:
            logger.warning(f"Agent {agent.name if hasattr(agent, 'name') else 'Unknown'} returned no output for key '{output_key}'")
            return None
        
        # Parse JSON if requested and output is a string
        if parse_json and isinstance(output, str):
            parsed = parse_json_robust(output)
            if parsed:
                return parsed
            # If parsing fails, return original string
            logger.warning(f"Failed to parse JSON from agent output for key '{output_key}'")
        
        return output
    
    def build_critic_input(
        self,
        presentation_outline: Dict,
        report_knowledge: Dict,
        config: Any,
        custom_instruction: Optional[str] = None
    ) -> str:
        """
        Build input message for critic agents.
        
        Args:
            presentation_outline: The presentation outline to review
            report_knowledge: The report knowledge for context
            config: PresentationConfig object
            custom_instruction: Optional custom instruction
            
        Returns:
            Formatted input message
        """
        scenario_section = (
            f"[SCENARIO]\n{config.scenario}\n\n"
            if config.scenario and config.scenario.strip()
            else "[SCENARIO]\nN/A\n\n"
        )
        target_audience_section = (
            f"[TARGET_AUDIENCE]\n{config.target_audience}\n\n"
            if config.target_audience
            else "[TARGET_AUDIENCE]\nN/A\n\n"
        )
        custom_instruction_section = (
            f"[CUSTOM_INSTRUCTION]\n{custom_instruction}\n\n"
            if custom_instruction and custom_instruction.strip()
            else ""
        )
        
        return f"""[PRESENTATION_OUTLINE]
{json.dumps(presentation_outline, indent=2)}
[END_PRESENTATION_OUTLINE]

[REPORT_KNOWLEDGE]
{json.dumps(report_knowledge, indent=2)}
[END_REPORT_KNOWLEDGE]

{scenario_section}[DURATION]
{config.duration}

{target_audience_section}{custom_instruction_section}Review this outline for quality, hallucination, and safety."""

