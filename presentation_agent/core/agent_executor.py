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
from presentation_agent.core.exceptions import AgentExecutionError, JSONParseError

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
    ) -> Any:
        """
        Execute an agent and extract its output.
        
        Args:
            agent: The ADK agent to execute
            user_message: Input message for the agent
            output_key: Key to extract from agent output
            parse_json: Whether to parse JSON from string output
            
        Returns:
            Agent output (parsed if parse_json=True)
            
        Raises:
            AgentExecutionError: If agent returns no output
            JSONParseError: If JSON parsing fails when parse_json=True
        """
        agent_name = agent.name if hasattr(agent, 'name') else 'Unknown'
        runner = InMemoryRunner(agent=agent)
        events = await runner.run_debug(user_message, session_id=self.session.id)
        
        # Log total events for debugging
        logger.info(f"📊 Agent '{agent_name}' execution completed. Total events: {len(events)}")
        
        # Debug: Log event details if output is not found
        output = extract_output_from_events(events, output_key)
        
        # Log what we extracted (before parsing)
        if output is not None:
            logger.info(f"📦 Extracted output for '{output_key}': type={type(output).__name__}, size={len(str(output)) if hasattr(output, '__len__') else 'N/A'}")
            if isinstance(output, dict):
                logger.info(f"   Output keys: {list(output.keys())}")
                # For slide_and_script, log structure immediately
                if output_key == "slide_and_script":
                    has_slide_deck = "slide_deck" in output
                    has_presentation_script = "presentation_script" in output
                    single_slide_keys = {'slide_number', 'title', 'content', 'visual_elements', 'design_spec'}
                    looks_like_single_slide = single_slide_keys.issubset(set(output.keys()))
                    logger.warning(f"   🔍 STRUCTURE CHECK for slide_and_script:")
                    logger.warning(f"      Has 'slide_deck': {has_slide_deck}")
                    logger.warning(f"      Has 'presentation_script': {has_presentation_script}")
                    logger.warning(f"      Looks like single slide: {looks_like_single_slide}")
                    if looks_like_single_slide:
                        logger.error(f"   ❌ DETECTED: Output looks like a SINGLE SLIDE OBJECT instead of required structure!")
                        logger.error(f"      Keys found: {list(output.keys())}")
            elif isinstance(output, str):
                logger.debug(f"   Output preview (first 500 chars): {output[:500]}")
                # Check if string contains the required keys
                if output_key == "slide_and_script":
                    has_slide_deck_str = '"slide_deck"' in output or "'slide_deck'" in output
                    has_presentation_script_str = '"presentation_script"' in output or "'presentation_script'" in output
                    logger.warning(f"   🔍 STRING CHECK for slide_and_script:")
                    logger.warning(f"      Contains 'slide_deck': {has_slide_deck_str}")
                    logger.warning(f"      Contains 'presentation_script': {has_presentation_script_str}")
        
        if output is None:
            # Debug: Log what events we got
            logger.error(f"❌ Agent '{agent_name}' returned no output for key '{output_key}'")
            logger.error(f"   Total events: {len(events)}")
            # Log state_delta keys from all events
            for i, event in enumerate(events):
                if hasattr(event, 'actions') and event.actions:
                    if hasattr(event.actions, 'state_delta') and event.actions.state_delta:
                        delta_keys = list(event.actions.state_delta.keys())
                        logger.error(f"   Event {i} state_delta keys: {delta_keys}")
                # Also check for text content in events
                if hasattr(event, 'content') and event.content:
                    if hasattr(event.content, 'parts') and event.content.parts:
                        for part_idx, part in enumerate(event.content.parts):
                            if hasattr(part, 'text') and part.text:
                                text_preview = part.text[:200] if len(part.text) > 200 else part.text
                                logger.error(f"   Event {i}, part {part_idx} has text (length {len(part.text)}): {text_preview}...")
            raise AgentExecutionError(
                f"Agent returned no output for key '{output_key}'",
                agent_name=agent_name,
                output_key=output_key
            )
        
        # Parse JSON if requested and output is a string
        if parse_json and isinstance(output, str):
            logger.debug(f"Attempting to parse JSON for key '{output_key}' (output length: {len(output)})")
            logger.debug(f"First 500 chars: {output[:500]}")
            logger.debug(f"Last 500 chars: {output[-500:]}")
            
            parsed = parse_json_robust(output)
            if parsed:
                return parsed
            # If parsing fails, try one more time with extract_json_from_text directly
            # This handles cases where clean_json_string might have affected extraction
            from presentation_agent.core.json_parser import extract_json_from_text
            json_str = extract_json_from_text(output)
            if json_str:
                logger.debug(f"Extracted JSON string length: {len(json_str)}")
                logger.debug(f"Extracted JSON first 500 chars: {json_str[:500]}")
                logger.debug(f"Extracted JSON last 500 chars: {json_str[-500:]}")
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict):
                        logger.info(f"✅ Successfully parsed JSON after direct extraction for key '{output_key}'")
                        return parsed
                except json.JSONDecodeError as e:
                    logger.error(f"JSONDecodeError after extraction: {e}")
                    logger.error(f"Error at position: {e.pos if hasattr(e, 'pos') else 'unknown'}")
                    # Try to show context around the error
                    if hasattr(e, 'pos') and e.pos is not None:
                        start = max(0, e.pos - 100)
                        end = min(len(json_str), e.pos + 100)
                        logger.error(f"Context around error: {json_str[start:end]}")
            # If all parsing attempts fail, raise exception
            logger.error(f"All JSON parsing attempts failed for key '{output_key}'")
            logger.error(f"Output type: {type(output)}")
            logger.error(f"Output length: {len(output)}")
            raise JSONParseError(
                f"Failed to parse JSON from agent output for key '{output_key}'",
                agent_name=agent_name,
                output_key=output_key,
                raw_output=output[:2000] if len(output) > 2000 else output  # Include first 2000 chars for debugging
            )
        
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

