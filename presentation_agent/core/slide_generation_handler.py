"""
Handles the slide and script generation step of the pipeline.
"""

import json
import logging
import re
from typing import Dict, Any, Optional

from config import (
    PresentationConfig,
    LLM_RETRY_COUNT,
    SLIDE_DECK_FILE,
    PRESENTATION_SCRIPT_FILE,
)
from presentation_agent.utils.helpers import save_json_output
from presentation_agent.utils.observability import AgentStatus
from presentation_agent.core.agent_executor import AgentExecutor
from presentation_agent.core.json_parser import parse_json_robust
from presentation_agent.core.exceptions import AgentExecutionError, JSONParseError, AgentOutputError
from presentation_agent.core.logging_utils import log_agent_error
from presentation_agent.core.serialization_manager import SerializationManager

logger = logging.getLogger(__name__)


class SlideGenerationHandler:
    """
    Handles slide and script generation step.
    """
    
    def __init__(
        self,
        config: PresentationConfig,
        executor: AgentExecutor,
        agent_registry,
        obs_logger,
        serialization_service,
        serialization_manager: SerializationManager,
        build_selective_context_fn,
        outputs: Dict[str, Any],
        output_dir,
        save_intermediate: bool = True,
    ):
        """
        Initialize the slide generation handler.
        
        Args:
            config: Presentation configuration
            executor: Agent executor instance
            agent_registry: Agent registry for getting agents
            obs_logger: Observability logger
            serialization_service: Service for JSON serialization
            serialization_manager: Manager for serialization and caching
            build_selective_context_fn: Function to build selective context (from orchestrator)
            outputs: Pipeline outputs dictionary
            output_dir: Output directory path
            save_intermediate: Whether to save intermediate outputs
        """
        self.config = config
        self.executor = executor
        self.agent_registry = agent_registry
        self.obs_logger = obs_logger
        self.serialization_service = serialization_service
        self.serialization_manager = serialization_manager
        self.build_selective_context_fn = build_selective_context_fn
        self.outputs = outputs
        self.output_dir = output_dir
        self.save_intermediate = save_intermediate
    
    async def execute(
        self,
        presentation_outline: Dict,
        report_knowledge: Dict
    ) -> Dict[str, Any]:
        """
        Execute the slide generation step.
        
        Args:
            presentation_outline: The presentation outline
            report_knowledge: The report knowledge
            
        Returns:
            Dictionary with 'slide_deck' and 'presentation_script' keys
            
        Raises:
            AgentExecutionError: If agent execution fails
            JSONParseError: If JSON parsing fails
            AgentOutputError: If output validation fails
        """
        print("\n🎨 Step 3: Slide and Script Generation")
        self.obs_logger.start_agent_execution("SlideAndScriptGeneratorAgent", output_key="slide_and_script")
        
        try:
            # Use cached serialization for performance
            serialized_outline = self.serialization_manager.get_serialized_presentation_outline(pretty=False)
            
            # CONTEXT ENGINEERING: Use selective context extraction to reduce token usage
            # Extract only relevant report sections based on slide topics
            selective_report_knowledge = self.build_selective_context_fn(presentation_outline, report_knowledge)
            
            # Serialize the selective context (compact format for agent messages)
            selective_report_knowledge_str = self.serialization_service.serialize(
                selective_report_knowledge,
                pretty=False
            )
            
            # Build simple message with data - let agent's instructions.md handle interpretation
            # The agent already has all the logic for custom instructions, duration, etc. in its instructions.md
            message_parts = [
                f"[PRESENTATION_OUTLINE]\n{serialized_outline}\n[END_PRESENTATION_OUTLINE]",
                f"[REPORT_KNOWLEDGE]\n{selective_report_knowledge_str}\n[END_REPORT_KNOWLEDGE]",
            ]
            
            # Add simple data fields (not elaborate prompts - agent's instructions.md handles interpretation)
            if self.config.custom_instruction and self.config.custom_instruction.strip():
                message_parts.append(f"[CUSTOM_INSTRUCTION]\n{self.config.custom_instruction}\n[END_CUSTOM_INSTRUCTION]")
            
            message_parts.append(f"[DURATION]\n{self.config.duration}\n[END_DURATION]")
            
            if self.config.scenario:
                message_parts.append(f"[SCENARIO]\n{self.config.scenario}\n[END_SCENARIO]")
            
            if self.config.target_audience:
                message_parts.append(f"[TARGET_AUDIENCE]\n{self.config.target_audience}\n[END_TARGET_AUDIENCE]")
            
            slide_and_script = await self.executor.run_agent(
                self.agent_registry.get("slide_and_script_generator"),
                "\n\n".join(message_parts),
                "slide_and_script",
                parse_json=True
            )
            
        except JSONParseError as e:
            slide_and_script = await self._handle_json_parse_error(e, presentation_outline, report_knowledge)
        except AgentExecutionError as e:
            slide_and_script = await self._handle_agent_execution_error(e, presentation_outline, report_knowledge)
        
        # Validate and process the output
        slide_and_script = self._validate_and_fix_output(slide_and_script)
        
        slide_deck = slide_and_script.get("slide_deck")
        presentation_script = slide_and_script.get("presentation_script")
        
        if not slide_deck:
            logger.error(f"❌ slide_and_script missing 'slide_deck' field")
            logger.error(f"   Available keys: {list(slide_and_script.keys())}")
            raise AgentOutputError(
                f"slide_and_script missing 'slide_deck' field",
                agent_name="SlideAndScriptGeneratorAgent",
                output_key="slide_deck",
                available_keys=list(slide_and_script.keys())
            )
        if not presentation_script:
            logger.error(f"❌ slide_and_script missing 'presentation_script' field")
            logger.error(f"   Available keys: {list(slide_and_script.keys())}")
            raise AgentOutputError(
                f"slide_and_script missing 'presentation_script' field",
                agent_name="SlideAndScriptGeneratorAgent",
                output_key="presentation_script",
                available_keys=list(slide_and_script.keys())
            )
        
        # Recalculate estimated_time based on word count (estimated_seconds = total_words / 2)
        presentation_script = self._recalculate_speech_timing(presentation_script)
        
        # Store outputs
        self.outputs["slide_deck"] = slide_deck
        self.outputs["presentation_script"] = presentation_script
        
        if self.save_intermediate:
            save_json_output(slide_deck, str(self.output_dir / SLIDE_DECK_FILE))
            save_json_output(presentation_script, str(self.output_dir / PRESENTATION_SCRIPT_FILE))
            print(f"✅ Slide deck and script saved")
        
        self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
        
        return {
            "slide_deck": slide_deck,
            "presentation_script": presentation_script
        }
    
    async def _handle_json_parse_error(
        self,
        e: JSONParseError,
        presentation_outline: Dict,
        report_knowledge: Dict
    ) -> Dict:
        """Handle JSON parsing errors with retry logic."""
        error_msg = str(e)
        raw_output = getattr(e, 'raw_output', '')
        
        # Check if it's a syntax error or plain text response (should retry)
        is_syntax_error = any(indicator in error_msg.lower() for indicator in [
            "expecting property name",
            "expecting ',' delimiter",
            "expecting ':' delimiter",
            "invalid escape",
            "expecting value",  # Often means no JSON at all
            "failed to parse json",  # Generic parsing failure
        ])
        
        # Also check if the raw output looks like plain text (question/explanation) instead of JSON
        if raw_output and not raw_output.strip().startswith('{'):
            is_syntax_error = True
            logger.warning(f"Agent returned plain text instead of JSON (likely asked a question). Will retry LLM call.")
        
        # If we can't determine, default to retrying (safer approach)
        if not is_syntax_error and "failed to parse json" in error_msg.lower():
            is_syntax_error = True
            logger.warning(f"Generic JSON parsing failure detected. Will retry LLM call.")
        
        if is_syntax_error:
            logger.warning(f"JSONParseError indicates syntax error (malformed JSON from LLM). Retrying LLM call (up to {LLM_RETRY_COUNT} times): {e}")
            
            # Retry loop
            for retry_attempt in range(1, LLM_RETRY_COUNT + 1):
                try:
                    logger.info(f"Retry attempt {retry_attempt}/{LLM_RETRY_COUNT} for JSON syntax error")
                    serialized_outline = self.serialization_manager.get_serialized_presentation_outline(pretty=False)
                    selective_report_knowledge = self.build_selective_context_fn(presentation_outline, report_knowledge)
                    selective_report_knowledge_str = self.serialization_service.serialize(
                        selective_report_knowledge,
                        pretty=False
                    )
                    
                    slide_and_script = await self.executor.run_agent(
                        self.agent_registry.get("slide_and_script_generator"),
                        f"Generate slides and script based on:\nOutline: {serialized_outline}\nReport Knowledge: {selective_report_knowledge_str}",
                        "slide_and_script",
                        parse_json=True
                    )
                    logger.info(f"✅ Successfully parsed JSON after LLM retry attempt {retry_attempt}")
                    return slide_and_script
                except (AgentExecutionError, JSONParseError) as e2:
                    if retry_attempt < LLM_RETRY_COUNT:
                        logger.warning(f"Retry attempt {retry_attempt} failed, will retry again: {e2}")
                    else:
                        logger.error(f"All {LLM_RETRY_COUNT} retry attempts failed. Last error: {e2}")
                        self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e2), has_output=False)
                        raise
        
        # Not a syntax error - try fallback parsing
        logger.warning(f"JSONParseError (non-syntax): {e}. Attempting fallback parsing.")
        return await self._try_fallback_parsing(presentation_outline, report_knowledge)
    
    async def _handle_agent_execution_error(
        self,
        e: AgentExecutionError,
        presentation_outline: Dict,
        report_knowledge: Dict
    ) -> Dict:
        """Handle agent execution errors with retry logic."""
        error_msg = str(e)
        if "no output for key" in error_msg.lower():
            logger.warning(f"AgentExecutionError: Agent returned no output. This may be due to LLM format issue. Retrying LLM call (up to {LLM_RETRY_COUNT} times): {e}")
            
            # Retry loop
            for retry_attempt in range(1, LLM_RETRY_COUNT + 1):
                try:
                    logger.info(f"Retry attempt {retry_attempt}/{LLM_RETRY_COUNT} for missing output")
                    serialized_outline = self.serialization_manager.get_serialized_presentation_outline(pretty=False)
                    selective_report_knowledge = self.build_selective_context_fn(presentation_outline, report_knowledge)
                    selective_report_knowledge_str = self.serialization_service.serialize(
                        selective_report_knowledge,
                        pretty=False
                    )
                    
                    slide_and_script = await self.executor.run_agent(
                        self.agent_registry.get("slide_and_script_generator"),
                        f"Generate slides and script based on:\nOutline: {serialized_outline}\nReport Knowledge: {selective_report_knowledge_str}",
                        "slide_and_script",
                        parse_json=True
                    )
                    logger.info(f"✅ Successfully got output after LLM retry attempt {retry_attempt}")
                    return slide_and_script
                except (AgentExecutionError, JSONParseError) as e2:
                    if retry_attempt < LLM_RETRY_COUNT:
                        logger.warning(f"Retry attempt {retry_attempt} failed, will retry again: {e2}")
                    else:
                        logger.error(f"All {LLM_RETRY_COUNT} retry attempts failed. Last error: {e2}")
                        self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e2), has_output=False)
                        raise
        else:
            # Other types of AgentExecutionError - don't retry
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e), has_output=False)
            raise
    
    async def _try_fallback_parsing(
        self,
        presentation_outline: Dict,
        report_knowledge: Dict
    ) -> Dict:
        """Try fallback parsing strategies for JSON errors."""
        try:
            serialized_outline = self.serialization_manager.get_serialized_presentation_outline(pretty=False)
            selective_report_knowledge = self.build_selective_context_fn(presentation_outline, report_knowledge)
            selective_report_knowledge_str = self.serialization_service.serialize(
                selective_report_knowledge,
                pretty=False
            )
            
            slide_and_script = await self.executor.run_agent(
                self.agent_registry.get("slide_and_script_generator"),
                f"Generate slides and script based on:\nOutline: {serialized_outline}\nReport Knowledge: {selective_report_knowledge_str}",
                "slide_and_script",
                parse_json=False  # Get raw string output
            )
        except AgentExecutionError as e2:
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e2), has_output=False)
            raise
        
        # Now try fallback parsing
        if isinstance(slide_and_script, str):
            logger.debug(f"slide_and_script is a string (length: {len(slide_and_script)}). Attempting to parse...")
            logger.debug(f"First 500 chars: {slide_and_script[:500]}")
            
            parsed = parse_json_robust(slide_and_script, extract_wrapped=True)
            if parsed:
                logger.info(f"✅ Successfully parsed slide_and_script from string (keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'})")
                return parsed
            else:
                logger.warning(f"⚠️ parse_json_robust failed. Trying alternative parsing...")
                # If parse_json_robust failed, try extracting JSON from markdown code block
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', slide_and_script, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON from markdown block: {e}")
                        # Try direct JSON parsing as last resort
                        try:
                            cleaned = slide_and_script.strip()
                            if cleaned.startswith("```json"):
                                cleaned = cleaned[7:].lstrip()
                            elif cleaned.startswith("```"):
                                cleaned = cleaned[3:].lstrip()
                            if cleaned.endswith("```"):
                                cleaned = cleaned[:-3].rstrip()
                            return json.loads(cleaned)
                        except json.JSONDecodeError as e2:
                            logger.error(f"Failed to parse slide_and_script: {e2}")
                            logger.error(f"First 1000 chars: {slide_and_script[:1000]}")
                            raise JSONParseError(
                                f"Failed to parse slide_and_script as JSON: {e2}",
                                agent_name="SlideAndScriptGeneratorAgent",
                                output_key="slide_and_script",
                                raw_output=slide_and_script[:1000]
                            )
                else:
                    # Try direct JSON parsing as last resort
                    try:
                        cleaned = slide_and_script.strip()
                        if cleaned.startswith("```json"):
                            cleaned = cleaned[7:].lstrip()
                        elif cleaned.startswith("```"):
                            cleaned = cleaned[3:].lstrip()
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3].rstrip()
                        return json.loads(cleaned)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse slide_and_script: {e}")
                        logger.error(f"First 1000 chars: {slide_and_script[:1000]}")
                        # Check if it looks like an error message
                        if "unable" in slide_and_script.lower() or "error" in slide_and_script.lower() or "cannot" in slide_and_script.lower():
                            raise JSONParseError(
                                f"Agent returned a plain text error message instead of JSON. "
                                f"This usually means the agent encountered an issue (e.g., missing data) but failed to return JSON. "
                                f"Error message: {slide_and_script[:500]}",
                                agent_name="SlideAndScriptGeneratorAgent",
                                output_key="slide_and_script",
                                raw_output=slide_and_script[:500]
                            )
                        raise JSONParseError(
                            f"Failed to parse slide_and_script as JSON: {e}",
                            agent_name="SlideAndScriptGeneratorAgent",
                            output_key="slide_and_script",
                            raw_output=slide_and_script[:1000]
                        )
        
        return slide_and_script
    
    def _validate_and_fix_output(self, slide_and_script: Any) -> Dict:
        """Validate and fix output structure if needed."""
        # Ensure it's a dict
        if not isinstance(slide_and_script, dict):
            logger.error(f"slide_and_script is not a dict, got {type(slide_and_script).__name__}")
            logger.error(f"slide_and_script value (first 500 chars): {str(slide_and_script)[:500]}")
            raise AgentOutputError(
                f"slide_and_script is not a dict, got {type(slide_and_script).__name__}",
                agent_name="SlideAndScriptGeneratorAgent",
                output_key="slide_and_script"
            )
        
        # Log what we got for debugging
        logger.info(f"✅ slide_and_script parsed successfully. Keys: {list(slide_and_script.keys())}")
        logger.info(f"   Full structure preview: {json.dumps(slide_and_script, indent=2)[:2000]}")
        
        # CRITICAL VALIDATION: Check if agent returned a single slide object instead of the required structure
        single_slide_keys = {'slide_number', 'title', 'content', 'visual_elements', 'design_spec', 'formatting_notes', 'speaker_notes'}
        if single_slide_keys.issubset(set(slide_and_script.keys())):
            logger.warning(f"⚠️ Agent returned a SINGLE SLIDE OBJECT instead of the required structure!")
            logger.warning(f"   Attempting to auto-fix by wrapping the single slide in the required structure...")
            
            # AUTO-FIX: Wrap the single slide in the required structure
            single_slide = slide_and_script.copy()
            presentation_script_fallback = {
                "script_sections": [
                    {
                        "slide_number": single_slide.get("slide_number", 1),
                        "script_text": single_slide.get("speaker_notes", "Present this slide.")
                    }
                ],
                "total_duration_seconds": 60,
                "notes": "Auto-generated script from single slide output"
            }
            
            # Wrap in required structure
            slide_and_script = {
                "slide_deck": {
                    "slides": [single_slide]
                },
                "presentation_script": presentation_script_fallback
            }
            
            logger.warning(f"   ✅ Auto-fixed: Wrapped single slide in required structure")
        
        return slide_and_script
    
    def _recalculate_speech_timing(self, presentation_script: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recalculate estimated_time based on word count.
        Formula: estimated_seconds = total_words / 2
        
        Args:
            presentation_script: The presentation script dictionary
            
        Returns:
            Updated presentation_script with recalculated estimated_time values
        """
        if not presentation_script or not isinstance(presentation_script, dict):
            return presentation_script
        
        script_sections = presentation_script.get("script_sections", [])
        total_estimated_time = 0
        
        for section in script_sections:
            if not isinstance(section, dict):
                continue
            
            # Count words in opening_line if present and store the time
            opening_line = section.get("opening_line", "")
            if opening_line:
                opening_words = len(opening_line.split())
                opening_time = round(opening_words / 2)
                opening_time = max(1, opening_time)
                section["opening_line_time"] = opening_time
                total_estimated_time += opening_time
            
            # Recalculate estimated_time for each point in main_content
            main_content = section.get("main_content", [])
            for point in main_content:
                if not isinstance(point, dict):
                    continue
                
                explanation = point.get("explanation", "")
                if explanation:
                    word_count = len(explanation.split())
                    estimated_time = word_count / 2
                    estimated_time = round(estimated_time)
                    estimated_time = max(1, estimated_time)
                    
                    point["estimated_time"] = estimated_time
                    total_estimated_time += estimated_time
        
        # Update total_estimated_time in script_metadata
        if "script_metadata" in presentation_script:
            script_metadata = presentation_script["script_metadata"]
            if isinstance(script_metadata, dict):
                script_metadata["total_estimated_time"] = f"{total_estimated_time} seconds"
        
        logger.info(f"✅ Recalculated speech timing: total_estimated_time = {total_estimated_time} seconds")
        
        return presentation_script

