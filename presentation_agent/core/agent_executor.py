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
from presentation_agent.core.logging_utils import (
    get_logger,
    log_agent_error,
    log_agent_info,
    log_agent_debug,
    log_agent_warning,
    log_json_parse_error
)

logger = get_logger(__name__)


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
        parse_json: bool = True,
        max_json_parse_retries: int = 1
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
        log_agent_info(
            logger,
            f"Agent execution completed. Total events: {len(events)}",
            agent_name=agent_name,
            context={"total_events": len(events)}
        )
        
        # Debug: Log event details if output is not found
        output = extract_output_from_events(events, output_key)
        
        # Check if output is plain text (question/explanation) instead of JSON
        # This happens when agent asks questions instead of returning JSON
        if isinstance(output, str) and parse_json:
            output_lower = output.strip().lower()
            # Check for common question patterns
            question_indicators = [
                "could you please",
                "i need to know",
                "please provide",
                "do you want",
                "should i",
                "i need clarification",
                "however, the",
            ]
            if any(indicator in output_lower[:200] for indicator in question_indicators):
                log_agent_warning(
                    logger,
                    f"Agent returned a question/explanation instead of JSON. This will trigger retry.",
                    agent_name=agent_name,
                    context={"output_preview": output[:200]}
                )
        
        # Log what we extracted (before parsing)
        if output is not None:
            output_size = len(str(output)) if hasattr(output, '__len__') else 'N/A'
            log_agent_info(
                logger,
                f"Extracted output for '{output_key}'",
                agent_name=agent_name,
                context={
                    "output_key": output_key,
                    "output_type": type(output).__name__,
                    "output_size": output_size
                }
            )
            if isinstance(output, dict):
                log_agent_debug(
                    logger,
                    f"Output keys: {list(output.keys())}",
                    agent_name=agent_name
                )
                # For slide_and_script, log structure immediately
                if output_key == "slide_and_script":
                    has_slide_deck = "slide_deck" in output
                    has_presentation_script = "presentation_script" in output
                    single_slide_keys = {'slide_number', 'title', 'content', 'visual_elements', 'design_spec'}
                    looks_like_single_slide = single_slide_keys.issubset(set(output.keys()))
                    log_agent_warning(
                        logger,
                        "Structure check for slide_and_script",
                        agent_name=agent_name,
                        context={
                            "has_slide_deck": has_slide_deck,
                            "has_presentation_script": has_presentation_script,
                            "looks_like_single_slide": looks_like_single_slide
                        }
                    )
                    if looks_like_single_slide:
                        log_agent_error(
                            logger,
                            "Output looks like a SINGLE SLIDE OBJECT instead of required structure",
                            agent_name=agent_name,
                            output_key=output_key,
                            context={"keys_found": list(output.keys())}
                        )
            elif isinstance(output, str):
                log_agent_debug(
                    logger,
                    f"Output preview (first 500 chars): {output[:500]}",
                    agent_name=agent_name
                )
                # Check if string contains the required keys
                if output_key == "slide_and_script":
                    has_slide_deck_str = '"slide_deck"' in output or "'slide_deck'" in output
                    has_presentation_script_str = '"presentation_script"' in output or "'presentation_script'" in output
                    log_agent_warning(
                        logger,
                        "String check for slide_and_script",
                        agent_name=agent_name,
                        context={
                            "contains_slide_deck": has_slide_deck_str,
                            "contains_presentation_script": has_presentation_script_str
                        }
                    )
        
        if output is None:
            # Debug: Log what events we got
            log_agent_error(
                logger,
                f"Agent returned no output for key '{output_key}'",
                agent_name=agent_name,
                output_key=output_key,
                context={"total_events": len(events)}
            )
            # Log state_delta keys from all events
            for i, event in enumerate(events):
                if hasattr(event, 'actions') and event.actions:
                    if hasattr(event.actions, 'state_delta') and event.actions.state_delta:
                        delta_keys = list(event.actions.state_delta.keys())
                        log_agent_debug(
                            logger,
                            f"Event {i} state_delta keys: {delta_keys}",
                            agent_name=agent_name,
                            context={"event_index": i, "delta_keys": delta_keys}
                        )
                # Also check for text content in events
                if hasattr(event, 'content') and event.content:
                    if hasattr(event.content, 'parts') and event.content.parts:
                        for part_idx, part in enumerate(event.content.parts):
                            if hasattr(part, 'text') and part.text:
                                text_preview = part.text[:200] if len(part.text) > 200 else part.text
                                log_agent_debug(
                                    logger,
                                    f"Event {i}, part {part_idx} has text (length {len(part.text)}): {text_preview}...",
                                    agent_name=agent_name,
                                    context={
                                        "event_index": i,
                                        "part_index": part_idx,
                                        "text_length": len(part.text)
                                    }
                                )
            raise AgentExecutionError(
                f"Agent returned no output for key '{output_key}'",
                agent_name=agent_name,
                output_key=output_key
            )
        
        # Parse JSON if requested and output is a string
        if parse_json and isinstance(output, str):
            log_agent_debug(
                logger,
                f"Attempting to parse JSON for key '{output_key}'",
                agent_name=agent_name,
                context={
                    "output_key": output_key,
                    "output_length": len(output),
                    "first_500_chars": output[:500],
                    "last_500_chars": output[-500:]
                }
            )
            
            # Try robust parsing with incomplete JSON fixing enabled
            parsed = parse_json_robust(output, fix_incomplete=True)
            if parsed:
                return parsed
            
            # If parsing fails, try one more time with extract_json_from_text directly
            # This handles cases where clean_json_string might have affected extraction
            from presentation_agent.core.json_parser import extract_json_from_text, fix_incomplete_json
            json_str = extract_json_from_text(output)
            if json_str:
                # Try fixing incomplete JSON before parsing
                fixed_json = fix_incomplete_json(json_str)
                if fixed_json and fixed_json != json_str:
                    try:
                        parsed = json.loads(fixed_json)
                        if isinstance(parsed, dict):
                            log_agent_info(
                                logger,
                                f"Successfully parsed fixed incomplete JSON for key '{output_key}'",
                                agent_name=agent_name,
                                context={"output_key": output_key}
                            )
                            return parsed
                    except json.JSONDecodeError:
                        pass
                log_agent_debug(
                    logger,
                    f"Extracted JSON string for key '{output_key}'",
                    agent_name=agent_name,
                    context={
                        "json_str_length": len(json_str),
                        "first_500_chars": json_str[:500],
                        "last_500_chars": json_str[-500:]
                    }
                )
                # Try parsing with retry for incomplete JSON
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict):
                        log_agent_info(
                            logger,
                            f"Successfully parsed JSON after direct extraction for key '{output_key}'",
                            agent_name=agent_name,
                            context={"output_key": output_key}
                        )
                        return parsed
                except json.JSONDecodeError as e:
                    # Check if it's a syntax error (should retry LLM) or incomplete (can fix)
                    from presentation_agent.core.json_parser import is_json_syntax_error
                    is_syntax_error = is_json_syntax_error(e)
                    
                    if not is_syntax_error and fix_incomplete:
                        # Try fixing incomplete JSON (truncated response)
                        fixed_json = fix_incomplete_json(json_str)
                        if fixed_json and fixed_json != json_str:
                            try:
                                parsed = json.loads(fixed_json)
                                if isinstance(parsed, dict):
                                    log_agent_info(
                                        logger,
                                        f"Successfully parsed fixed incomplete JSON on retry for key '{output_key}'",
                                        agent_name=agent_name,
                                        context={"output_key": output_key}
                                    )
                                    return parsed
                            except json.JSONDecodeError:
                                pass
                    
                    error_pos = e.pos if hasattr(e, 'pos') else None
                    context_str = None
                    if error_pos is not None:
                        start = max(0, error_pos - 100)
                        end = min(len(json_str), error_pos + 100)
                        context_str = json_str[start:end]
                    
                    error_type = "syntax error" if is_syntax_error else "incomplete JSON"
                    log_json_parse_error(
                        logger,
                        f"JSONDecodeError after extraction ({error_type})",
                        agent_name=agent_name,
                        output_key=output_key,
                        raw_output_preview=context_str,
                        error=e
                    )
            # If all parsing attempts fail, raise exception
            log_json_parse_error(
                logger,
                f"All JSON parsing attempts failed for key '{output_key}'",
                agent_name=agent_name,
                output_key=output_key,
                raw_output_preview=output[:2000] if len(output) > 2000 else output
            )
            log_agent_debug(
                logger,
                f"Output details",
                agent_name=agent_name,
                context={"output_type": type(output).__name__, "output_length": len(output)}
            )
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
        custom_instruction: Optional[str] = None,
        serialized_outline: Optional[str] = None,
        serialized_report_knowledge: Optional[str] = None
    ) -> str:
        """
        Build input message for critic agents.
        
        Args:
            presentation_outline: The presentation outline to review
            report_knowledge: The report knowledge for context
            config: PresentationConfig object
            custom_instruction: Optional custom instruction
            serialized_outline: Optional pre-serialized outline (for performance)
            serialized_report_knowledge: Optional pre-serialized report knowledge (for performance)
            
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
        
        # Use pre-serialized strings if provided (performance optimization)
        outline_str = serialized_outline if serialized_outline else json.dumps(presentation_outline, indent=2)
        report_knowledge_str = serialized_report_knowledge if serialized_report_knowledge else json.dumps(report_knowledge, indent=2)
        
        return f"""[PRESENTATION_OUTLINE]
{outline_str}
[END_PRESENTATION_OUTLINE]

[REPORT_KNOWLEDGE]
{report_knowledge_str}
[END_REPORT_KNOWLEDGE]

{scenario_section}[DURATION]
{config.duration}

{target_audience_section}{custom_instruction_section}Review this outline for quality, hallucination, and safety."""

