"""
Slide generation handler - extracted from pipeline_orchestrator for better code organization.
Handles the slide and script generation step of the pipeline.
"""

import json
import logging
import re
from typing import Dict, Any, Optional

from config import (
    PresentationConfig,
    LLM_RETRY_COUNT,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_NUM_SLIDES,
    SLIDE_DECK_FILE,
    PRESENTATION_SCRIPT_FILE,
)
from presentation_agent.agents.utils.helpers import save_json_output
from presentation_agent.agents.utils.observability import AgentStatus
from presentation_agent.core.agent_executor import AgentExecutor
from presentation_agent.core.json_parser import parse_json_robust
from presentation_agent.core.exceptions import AgentExecutionError, JSONParseError, AgentOutputError
from presentation_agent.core.logging_utils import log_agent_error

logger = logging.getLogger(__name__)


class SlideGenerationHandler:
    """
    Handles slide and script generation step.
    Extracted from PipelineOrchestrator to reduce file size and improve maintainability.
    """
    
    def __init__(
        self,
        config: PresentationConfig,
        executor: AgentExecutor,
        agent_registry,
        obs_logger,
        serialization_service,
        get_serialized_outline_fn,
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
            get_serialized_outline_fn: Function to get serialized outline (from orchestrator)
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
        self.get_serialized_outline_fn = get_serialized_outline_fn
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
            # Include custom_instruction explicitly in the message if present
            custom_instruction_note = self._build_custom_instruction_note()
            
            # Build the message with custom instruction at the TOP if present
            # Use cached serialization for performance
            serialized_outline = self.get_serialized_outline_fn(pretty=False)
            
            # CONTEXT ENGINEERING: Use selective context extraction to reduce token usage
            # Extract only relevant report sections based on slide topics
            selective_report_knowledge = self.build_selective_context_fn(presentation_outline, report_knowledge)
            
            # Serialize the selective context (compact format for agent messages)
            selective_report_knowledge_str = self.serialization_service.serialize(
                selective_report_knowledge,
                pretty=False
            )
            
            message_parts = []
            if custom_instruction_note:
                message_parts.append(custom_instruction_note)
            
            # Add explicit duration requirement with calculated target
            duration_note = self._build_duration_note()
            message_parts.append(duration_note)
            message_parts.append(f"Generate slides and script based on:\nOutline: {serialized_outline}\nReport Knowledge: {selective_report_knowledge_str}")
            
            slide_and_script = await self.executor.run_agent(
                self.agent_registry.get("slide_and_script_generator"),
                "\n".join(message_parts),
                "slide_and_script",
                parse_json=True
            )
            
            # Validate that custom instruction was followed (for icon-feature card)
            self._validate_custom_instruction(slide_and_script)
            
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
    
    def _build_custom_instruction_note(self) -> str:
        """Build custom instruction note based on config."""
        if not self.config.custom_instruction or not self.config.custom_instruction.strip():
            return ""
        
        custom_instr_lower = self.config.custom_instruction.lower()
        
        if "icon-feature card" in custom_instr_lower or "icon feature card" in custom_instr_lower:
            return f"""

═══════════════════════════════════════════════════════════════
🚨 CRITICAL MANDATORY REQUIREMENT - MUST BE FOLLOWED 🚨
═══════════════════════════════════════════════════════════════

[CUSTOM_INSTRUCTION]
{self.config.custom_instruction}

⚠️⚠️⚠️ MANDATORY REQUIREMENT - THIS OVERRIDES ALL OTHER INSTRUCTIONS ⚠️⚠️⚠️

You MUST create at least ONE slide (can be any slide number 2-5) with:
  - layout_type: "comparison-grid"
  - visual_elements.sections array with 2-4 sections
  - Each section MUST have an "image_keyword" field

Example structure:
{{
  "slide_number": 2,  // or 3, 4, or 5
  "design_spec": {{
    "layout_type": "comparison-grid"
  }},
  "visual_elements": {{
    "sections": [
      {{"title": "Security", "content": "...", "image_keyword": "security"}},
      {{"title": "Vulnerability", "content": "...", "image_keyword": "warning"}},
      {{"title": "Evaluation", "content": "...", "image_keyword": "analytics"}}
    ]
  }}
}}

This is NOT optional. You MUST include at least ONE comparison-grid slide with image_keyword fields.
The comparison-grid will render as icon-feature cards with images generated on-the-fly.

═══════════════════════════════════════════════════════════════
"""
        elif "timeline" in custom_instr_lower:
            return f"\n\n[CUSTOM_INSTRUCTION - CRITICAL]\n{self.config.custom_instruction}\n\n⚠️ MANDATORY REQUIREMENT: You MUST create at least ONE slide with layout_type: \"timeline\" AND provide visual_elements.timeline_items array with format: [{{\"year\": \"...\", \"title\": \"...\", \"description\": \"...\"}}, ...]. This is NOT optional - you MUST include a timeline slide.\n"
        elif "flowchart" in custom_instr_lower:
            return f"\n\n[CUSTOM_INSTRUCTION - CRITICAL]\n{self.config.custom_instruction}\n\n⚠️ MANDATORY REQUIREMENT: You MUST create at least ONE slide with layout_type: \"flowchart\" AND provide visual_elements.flowchart_steps array. This is NOT optional.\n"
        elif "comparison" in custom_instr_lower or "grid" in custom_instr_lower:
            return f"\n\n[CUSTOM_INSTRUCTION - CRITICAL]\n{self.config.custom_instruction}\n\n⚠️ MANDATORY REQUIREMENT: You MUST create at least ONE slide with layout_type: \"comparison-grid\" AND provide visual_elements.sections array. This is NOT optional.\n"
        elif "table" in custom_instr_lower:
            return f"\n\n[CUSTOM_INSTRUCTION - CRITICAL]\n{self.config.custom_instruction}\n\n⚠️ MANDATORY REQUIREMENT: You MUST create at least ONE slide with layout_type: \"data-table\" AND provide visual_elements.table_data object. This is NOT optional.\n"
        elif "image" in custom_instr_lower and ("at least" in custom_instr_lower or "least" in custom_instr_lower):
            # Extract number if present (e.g., "at least 3 images" -> 3)
            num_match = re.search(r'at least (\d+)|least (\d+)', custom_instr_lower)
            num_images = int(num_match.group(1) or num_match.group(2)) if num_match else 3
            return f"""

═══════════════════════════════════════════════════════════════
🚨 CRITICAL MANDATORY REQUIREMENT - MUST BE FOLLOWED 🚨
═══════════════════════════════════════════════════════════════

[CUSTOM_INSTRUCTION]
{self.config.custom_instruction}

⚠️⚠️⚠️ MANDATORY REQUIREMENT - THIS OVERRIDES ALL OTHER INSTRUCTIONS ⚠️⚠️⚠️

You MUST provide at least {num_images} images TOTAL across all slides (not per slide).

Distribute images across slides - you can put 1-2 images on some slides, more on others, as long as the total across all slides is at least {num_images}.

For slides (except slide_number: 1), you can include:
  - visual_elements.image_keywords array with 1-3 keywords per slide
  - OR visual_elements.figures array with dictionaries containing "image_keyword" fields

**CRITICAL: DO NOT ASK QUESTIONS - JUST GENERATE THE KEYWORDS**

Interpretation: "at least {num_images} images" means "{num_images} images TOTAL ACROSS ALL SLIDES"
- Automatically generate relevant keywords based on each slide's content
- Choose keywords that match the slide topic (e.g., security slide → ["security"], evaluation slide → ["analytics", "chart"])
- DO NOT use figure IDs like "fig1" or "placeholder_image_1" - use actual keywords
- Distribute images across slides (e.g., 1 image on slide 2, 1 on slide 3, 1 on slide 4 = 3 total)

Example distribution for "at least 3 images":
- Slide 2: {{"visual_elements": {{"image_keywords": ["security"]}}}}  // 1 image
- Slide 3: {{"visual_elements": {{"image_keywords": ["analytics"]}}}}  // 1 image
- Slide 4: {{"visual_elements": {{"image_keywords": ["chart"]}}}}     // 1 image
Total: 3 images across all slides ✅

This is NOT optional. You MUST include at least {num_images} image keywords TOTAL across all slides (except cover slide).
DO NOT ask for clarification - just generate the keywords automatically and distribute them across slides.

═══════════════════════════════════════════════════════════════
"""
        else:
            return f"\n\n[CUSTOM_INSTRUCTION]\n{self.config.custom_instruction}\n\nIMPORTANT: You MUST follow this custom instruction.\n"
    
    def _build_duration_note(self) -> str:
        """Build duration requirement note."""
        # Parse duration string to calculate target seconds
        duration_str = self.config.duration.lower()
        target_seconds = DEFAULT_DURATION_SECONDS
        if "minute" in duration_str or "min" in duration_str:
            match = re.search(r'(\d+)', duration_str)
            if match:
                minutes = int(match.group(1))
                target_seconds = minutes * 60
        elif "second" in duration_str or "sec" in duration_str:
            match = re.search(r'(\d+)', duration_str)
            if match:
                target_seconds = int(match.group(1))
        
        # Calculate required words (words = seconds × 2, since estimated_seconds = words / 2)
        required_words = target_seconds * 2
        
        # Get number of slides from outline for distribution calculation
        outline = self.outputs.get('presentation_outline', {})
        num_slides = len(outline.get('slides', [])) or DEFAULT_NUM_SLIDES
        words_per_content_slide = int((required_words - 50) / max(1, num_slides - 1)) if num_slides > 1 else required_words - 50
        
        return f"""
═══════════════════════════════════════════════════════════════
⏱️ CRITICAL DURATION REQUIREMENT ⏱️
═══════════════════════════════════════════════════════════════
TARGET DURATION: {self.config.duration} ({target_seconds} seconds)

You MUST generate enough script content to fill this duration.

TIMING CALCULATION:
- System calculates: estimated_seconds = total_words / 2 (≈120 words/minute)
- Target: {target_seconds} seconds = {required_words} words total
- Distribute across all slides:
  * Cover slide (slide 1): ~40-50 words (opening remarks + brief intro)
  * Content slides: ~{words_per_content_slide} words each
  * Each slide's main_content explanations should be DETAILED (40-80 words per point)

CRITICAL: Your script explanations must be DETAILED enough to reach ~{required_words} words total.
If your current content is too short, EXPAND the explanations with more detail, examples, context, and elaboration.

After generation, verify: Sum of all estimated_time values should be close to {target_seconds} seconds.
═══════════════════════════════════════════════════════════════
"""
    
    def _validate_custom_instruction(self, slide_and_script: Dict):
        """Validate that custom instruction was followed (for icon-feature card)."""
        if not self.config.custom_instruction:
            return
        
        custom_instr_lower = self.config.custom_instruction.lower()
        if "icon-feature card" in custom_instr_lower or "icon feature card" in custom_instr_lower:
            has_comparison_grid = False
            for slide in slide_and_script.get("slide_deck", {}).get("slides", []):
                if slide.get("design_spec", {}).get("layout_type") == "comparison-grid":
                    sections = slide.get("visual_elements", {}).get("sections", [])
                    if sections and any(s.get("image_keyword") for s in sections):
                        has_comparison_grid = True
                        break
            
            if not has_comparison_grid:
                print("\n⚠️  WARNING: Custom instruction requires comparison-grid with image_keyword, but agent did not create one.")
                print("   The generated slides may not fully satisfy the custom instruction.")
                print("   Consider re-running or adjusting the custom instruction.")
    
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
                    serialized_outline = self.get_serialized_outline_fn(pretty=False)
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
                    serialized_outline = self.get_serialized_outline_fn(pretty=False)
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
            serialized_outline = self.get_serialized_outline_fn(pretty=False)
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

