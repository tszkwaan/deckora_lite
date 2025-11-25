"""
Pipeline orchestrator - coordinates all agents in the presentation generation pipeline.
Extracted from main.py to follow Single Responsibility Principle.
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import webbrowser

from google.adk.sessions import InMemorySessionService

from config import (
    PresentationConfig,
    LLM_RETRY_COUNT,
    APP_NAME,
    USER_ID,
    OUTPUT_DIR,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_NUM_SLIDES,
    TRACE_HISTORY_FILE,
    OBSERVABILITY_LOG_FILE,
    REPORT_KNOWLEDGE_FILE,
    PRESENTATION_OUTLINE_FILE,
    SLIDE_AND_SCRIPT_DEBUG_FILE,
    SLIDE_DECK_FILE,
    PRESENTATION_SCRIPT_FILE,
    WEB_SLIDES_RESULT_FILE,
)
from presentation_agent.agents.tools.web_slides_generator_tool import generate_web_slides_tool
from presentation_agent.core.agent_registry import AgentRegistry, create_default_agent_registry
from presentation_agent.agents.utils.pdf_loader import load_pdf
from presentation_agent.agents.utils.helpers import save_json_output, is_valid_chart_data
from presentation_agent.agents.utils.observability import get_observability_logger, AgentStatus
from presentation_agent.core.agent_executor import AgentExecutor
from presentation_agent.core.json_parser import parse_json_robust
from presentation_agent.core.exceptions import AgentExecutionError, JSONParseError, AgentOutputError
from presentation_agent.core.logging_utils import log_agent_error
from presentation_agent.core.serialization_service import SerializationService
from presentation_agent.core.cache_manager import CacheManager
from presentation_agent.core.slide_generation_handler import SlideGenerationHandler

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Orchestrates the complete presentation generation pipeline.
    Follows Single Responsibility Principle - only handles orchestration.
    """
    
    def __init__(
        self,
        config: PresentationConfig,
        output_dir: str = OUTPUT_DIR,
        include_critics: bool = True,
        save_intermediate: bool = True,
        open_browser: bool = True,
        agent_registry: Optional[AgentRegistry] = None
    ):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.include_critics = include_critics
        self.save_intermediate = save_intermediate
        self.open_browser = open_browser
        
        # Initialize agent registry (dependency injection)
        self.agent_registry = agent_registry or create_default_agent_registry()
        
        # Initialize observability
        trace_file = str(self.output_dir / TRACE_HISTORY_FILE)
        self.obs_logger = get_observability_logger(
            log_file=str(self.output_dir / OBSERVABILITY_LOG_FILE),
            trace_file=trace_file
        )
        
        # Initialize session
        self.session_service = InMemorySessionService()
        self.session = None  # Will be set in initialize()
        self.executor: Optional[AgentExecutor] = None
        
        # Pipeline outputs
        self.outputs: Dict[str, Any] = {}
        
        # Initialize services (following SRP)
        self.serialization_service = SerializationService()
        self.cache_manager = CacheManager()
    
    async def initialize(self):
        """Initialize session and executor."""
        self.session = await self.session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID
        )
        self.executor = AgentExecutor(self.session)
        self.obs_logger.start_pipeline("presentation_pipeline")
        
        # Clear image cache at the start of each pipeline run (async)
        from presentation_agent.templates.image_helper import clear_image_cache_async
        await clear_image_cache_async()
    
    async def run(self) -> Dict[str, Any]:
        """
        Run the complete pipeline.
        
        Returns:
            Dictionary with all generated outputs
        """
        await self.initialize()
        
        try:
            # Step 1: Report Understanding
            await self._step_report_understanding()
            
            # Step 2: Outline Generation with Critic
            await self._step_outline_generation()
            
            # Step 3: Slide and Script Generation
            handler = SlideGenerationHandler(
                config=self.config,
                executor=self.executor,
                agent_registry=self.agent_registry,
                obs_logger=self.obs_logger,
                serialization_service=self.serialization_service,
                get_serialized_outline_fn=self._get_serialized_presentation_outline,
                build_selective_context_fn=self._build_selective_context,
                outputs=self.outputs,
                output_dir=self.output_dir,
                save_intermediate=self.save_intermediate,
            )
            result = await handler.execute(
                presentation_outline=self.outputs["presentation_outline"],
                report_knowledge=self.outputs["report_knowledge"]
            )
            # Store in session state
            self.session.state["slide_deck"] = result["slide_deck"]
            self.session.state["presentation_script"] = result["presentation_script"]
            
            # Step 3.5: Parallel Chart and Image Generation (OPTIMIZATION)
            # Generate charts and images in parallel to save time
            image_cache, keyword_usage_tracker = await self._step_parallel_chart_and_image_generation()
            
            # Step 4: Web Slides Generation
            await self._step_generate_web_slides(image_cache=image_cache, keyword_usage_tracker=keyword_usage_tracker)
            
            print("\n✅ Pipeline completed - web slides generated!")
            
            self.obs_logger.finish_pipeline()
            return self.outputs
            
        except (AgentExecutionError, JSONParseError, AgentOutputError) as e:
            # Expected errors from agent execution - log with context and re-raise
            log_agent_error(
                logger,
                f"Pipeline failed with agent execution error: {e}",
                agent_name=getattr(e, 'agent_name', 'PipelineOrchestrator'),
                output_key=getattr(e, 'output_key', None),
                error=e,
                context={
                    "error_type": type(e).__name__,
                    "outputs_so_far": list(self.outputs.keys()) if self.outputs else []
                }
            )
            self.obs_logger.finish_pipeline()
            raise
        except (FileNotFoundError, ValueError, KeyError, TypeError, AttributeError) as e:
            # Configuration or data errors - log with context
            logger.error(
                f"Pipeline failed with configuration/data error: {type(e).__name__}: {e}",
                exc_info=True,
                extra={
                    "error_type": type(e).__name__,
                    "config_duration": getattr(self.config, 'duration', None),
                    "config_scenario": getattr(self.config, 'scenario', None),
                    "outputs_so_far": list(self.outputs.keys()) if self.outputs else []
                }
            )
            self.obs_logger.finish_pipeline()
            raise
        except Exception as e:
            # Unexpected errors - log with full context for debugging
            logger.error(
                f"Pipeline failed with unexpected error: {type(e).__name__}: {e}",
                exc_info=True,
                extra={
                    "error_type": type(e).__name__,
                    "outputs_so_far": list(self.outputs.keys()) if self.outputs else [],
                    "config_duration": getattr(self.config, 'duration', None)
                }
            )
            self.obs_logger.finish_pipeline()
            raise
    
    def _get_serialized_report_knowledge(self, pretty: bool = False) -> str:
        """
        Get serialized report_knowledge, caching result for performance.
        
        Args:
            pretty: If True, use indent=2 for pretty printing (for logs).
                   If False, use compact format (for agent messages).
        
        Returns:
            Serialized JSON string
        """
        cache_key = f"report_knowledge_{'pretty' if pretty else 'compact'}"
        
        if not self.cache_manager.has(cache_key):
            report_knowledge = self.outputs.get("report_knowledge")
            if report_knowledge is None:
                raise ValueError("report_knowledge not available in outputs")
            
            serialized = self.serialization_service.serialize(report_knowledge, pretty=pretty)
            self.cache_manager.set(cache_key, serialized)
        
        return self.cache_manager.get(cache_key)
    
    def _get_serialized_presentation_outline(self, pretty: bool = False) -> str:
        """
        Get serialized presentation_outline, caching result for performance.
        
        Args:
            pretty: If True, use indent=2 for pretty printing (for logs).
                   If False, use compact format (for agent messages).
        
        Returns:
            Serialized JSON string
        """
        cache_key = f"presentation_outline_{'pretty' if pretty else 'compact'}"
        
        if not self.cache_manager.has(cache_key):
            presentation_outline = self.outputs.get("presentation_outline")
            if presentation_outline is None:
                raise ValueError("presentation_outline not available in outputs")
            
            serialized = self.serialization_service.serialize(presentation_outline, pretty=pretty)
            self.cache_manager.set(cache_key, serialized)
        
        return self.cache_manager.get(cache_key)
    
    def _invalidate_serialization_cache(self, key: Optional[str] = None):
        """
        Invalidate serialization cache when data changes.
        
        Args:
            key: Specific cache key to invalidate, or None to clear all
        """
        self.cache_manager.invalidate(key_prefix=key)
    
    def _extract_relevant_report_sections(
        self,
        outline: Dict,
        report_knowledge: Dict,
        max_sections_per_slide: int = 5  # Increased from 3 to be less aggressive
    ) -> Dict[int, List[Dict]]:
        """
        Extract only relevant report_knowledge.sections for each slide based on topic matching.
        
        Uses keyword-based matching to identify which report sections are relevant to each slide.
        
        Args:
            outline: Presentation outline with slides
            report_knowledge: Full report knowledge structure
            max_sections_per_slide: Maximum number of relevant sections to include per slide
        
        Returns:
            Dict mapping slide_number -> list of relevant report sections
        """
        slides = outline.get("slides", [])
        all_sections = report_knowledge.get("sections", [])
        
        if not all_sections:
            return {}
        
        slide_to_sections = {}
        
        for slide in slides:
            slide_num = slide.get("slide_number")
            if not slide_num:
                continue
            
            # Extract slide content for matching
            slide_title = slide.get("title", "").lower()
            key_points = [p.lower() for p in slide.get("key_points", [])]
            content_notes = slide.get("content_notes", "").lower()
            
            # Combine all slide text for matching
            slide_text = f"{slide_title} {' '.join(key_points)} {content_notes}"
            
            # Find relevant sections using keyword matching
            relevant = []
            for section in all_sections:
                section_id = section.get("id", "")
                section_label = section.get("label", "").lower()
                section_summary = section.get("summary", "").lower()
                section_key_points = [p.lower() for p in section.get("key_points", [])]
                
                # Calculate relevance score
                score = 0
                
                # Match section label with slide title (strong match)
                if section_label:
                    label_words = set(section_label.split())
                    slide_words = set(slide_title.split())
                    common_words = label_words.intersection(slide_words)
                    if common_words:
                        # More common words = higher score
                        score += len(common_words) * 3
                
                # Match section summary with slide content (medium match)
                if section_summary:
                    summary_words = set(section_summary.split()[:20])  # First 20 words
                    slide_words = set(slide_text.split())
                    common_words = summary_words.intersection(slide_words)
                    if common_words:
                        score += len(common_words) * 2
                
                # Match section key points with slide key points (strong match)
                for section_kp in section_key_points:
                    section_kp_words = set(section_kp.split()[:5])  # First 5 words
                    for slide_kp in key_points:
                        slide_kp_words = set(slide_kp.split()[:5])
                        common_words = section_kp_words.intersection(slide_kp_words)
                        if common_words:
                            score += len(common_words) * 2
                
                # Match section label in content_notes (medium match)
                if section_label and section_label in content_notes:
                    score += 2
                
                # If score > 0, section is relevant
                if score > 0:
                    relevant.append((score, section))
            
            # Sort by relevance score (descending) and take top N
            relevant.sort(reverse=True, key=lambda x: x[0])
            slide_to_sections[slide_num] = [s[1] for s in relevant[:max_sections_per_slide]]
        
        return slide_to_sections
    
    def _build_selective_context(
        self,
        outline: Dict,
        report_knowledge: Dict
    ) -> Dict:
        """
        Build minimal report_knowledge context with only relevant sections for slide generation.
        
        LESS AGGRESSIVE: For small reports (< 10 sections), includes all sections.
        For larger reports, includes relevant sections + ensures at least 70% coverage.
        
        Args:
            outline: Presentation outline with slides
            report_knowledge: Full report knowledge structure
        
        Returns:
            Minimal report_knowledge dict with relevant sections (less aggressive filtering)
        """
        all_sections = report_knowledge.get("sections", [])
        total_sections = len(all_sections)
        
        # LESS AGGRESSIVE: If report has few sections (< 10), include ALL sections
        # This prevents information loss and ensures agent has enough context
        if total_sections <= 10:
            logger.info(f"📊 Small report ({total_sections} sections): Including ALL sections (less aggressive filtering)")
            minimal_context = report_knowledge.copy()  # Use full context for small reports
            return minimal_context
        
        # For larger reports, use selective extraction but ensure minimum coverage
        # Always include metadata (small, essential)
        minimal_context = {
            "scenario": report_knowledge.get("scenario"),
            "duration": report_knowledge.get("duration"),
            "report_url": report_knowledge.get("report_url"),
            "report_title": report_knowledge.get("report_title"),
            "one_sentence_summary": report_knowledge.get("one_sentence_summary"),
            "audience_profile": report_knowledge.get("audience_profile"),
            "presentation_focus": report_knowledge.get("presentation_focus"),
            "key_takeaways": report_knowledge.get("key_takeaways", []),  # Include all, not just top 5
            "recommended_focus_for_presentation": report_knowledge.get("recommended_focus_for_presentation", [])
        }
        
        # Extract relevant sections for all slides (union of all relevant sections)
        slide_to_sections = self._extract_relevant_report_sections(outline, report_knowledge, max_sections_per_slide=5)
        
        # Collect all unique relevant sections (deduplicated by section ID)
        seen_section_ids = set()
        relevant_sections = []
        
        for sections in slide_to_sections.values():
            for section in sections:
                section_id = section.get("id")
                if section_id and section_id not in seen_section_ids:
                    relevant_sections.append(section)
                    seen_section_ids.add(section_id)
        
        # LESS AGGRESSIVE: Ensure minimum 70% coverage to prevent information loss
        min_coverage = max(7, int(total_sections * 0.7))  # At least 70% or minimum 7 sections
        if len(relevant_sections) < min_coverage:
            logger.warning(f"⚠️  Only {len(relevant_sections)} relevant sections found (need {min_coverage} for 70% coverage). Including all sections as fallback.")
            relevant_sections = all_sections
        else:
            logger.info(f"✅ Extracted {len(relevant_sections)} relevant sections (from {total_sections} total, {len(relevant_sections)/total_sections*100:.1f}% coverage)")
        
        minimal_context["sections"] = relevant_sections
        
        # Include all figures (usually small, and may be referenced by any slide)
        minimal_context["figures"] = report_knowledge.get("figures", [])
        
        return minimal_context
    
    async def _step_report_understanding(self):
        """Step 1: Report Understanding Agent."""
        print("\n📊 Step 1: Report Understanding Agent")
        self.obs_logger.start_agent_execution("ReportUnderstandingAgent", output_key="report_knowledge")
        
        # Load PDF if needed
        if self.config.report_url and not self.config.report_content:
            print(f"📄 Loading PDF from URL: {self.config.report_url}")
            self.config.report_content = load_pdf(report_url=self.config.report_url)
            lines = self.config.report_content.split('\n')
            words = self.config.report_content.split()
            print(f"✅ Loaded PDF: {len(self.config.report_content)} characters, {len(lines)} lines, {len(words)} words")
        
        # Build initial message
        scenario_provided = bool(self.config.scenario and self.config.scenario.strip())
        target_audience_provided = self.config.target_audience is not None
        
        scenario_section = (
            f"[SCENARIO]\n{self.config.scenario}\n\n"
            if scenario_provided
            else "[SCENARIO]\nN/A (Please infer from report content)\n\n"
        )
        target_audience_section = (
            f"[TARGET_AUDIENCE]\n{self.config.target_audience}\n\n"
            if target_audience_provided
            else "[TARGET_AUDIENCE]\nN/A (Please infer from scenario and report content)\n\n"
        )
        custom_instruction_section = (
            f"[CUSTOM_INSTRUCTION]\n{self.config.custom_instruction}\n\n"
            if self.config.custom_instruction and self.config.custom_instruction.strip()
            else ""
        )
        
        initial_message = f"""[REPORT_CONTENT]
{self.config.report_content}
[END_REPORT_CONTENT]

{scenario_section}{target_audience_section}[DURATION]
{self.config.duration}

{custom_instruction_section}Extract structured knowledge from this report. Analyze the content, identify key sections, figures, and takeaways. Infer scenario and target_audience if not provided."""
        
        try:
            report_knowledge = await self.executor.run_agent(
                self.agent_registry.get("report_understanding"),
                initial_message,
                "report_knowledge",
                parse_json=True
            )
        except (AgentExecutionError, JSONParseError) as e:
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e), has_output=False)
            raise
        
        # Log inference results
        self._log_inference_results(report_knowledge, scenario_provided, target_audience_provided)
        
        self.outputs["report_knowledge"] = report_knowledge
        self.session.state["report_knowledge"] = report_knowledge
        # Invalidate cache when report_knowledge is updated
        self._invalidate_serialization_cache("report_knowledge")
        self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
        
        if self.save_intermediate:
            save_json_output(report_knowledge, str(self.output_dir / REPORT_KNOWLEDGE_FILE))
            print(f"✅ Report knowledge saved")
    
    def _log_inference_results(self, report_knowledge: Dict, scenario_provided: bool, target_audience_provided: bool):
        """Log inference results for scenario and target_audience."""
        print("\n🔍 Inference Results:")
        print("=" * 60)
        inferred_scenario = report_knowledge.get("scenario", "N/A")
        inferred_audience = report_knowledge.get("audience_profile", {}).get("primary_audience", "N/A")
        
        if not scenario_provided:
            print(f"  🧠 scenario: INFERRED")
            print(f"     Inferred Value: {inferred_scenario}")
        else:
            print(f"  ✅ scenario: PROVIDED (not inferred)")
            print(f"     Provided Value: {self.config.scenario}")
        
        if not target_audience_provided:
            print(f"  🧠 target_audience: INFERRED")
            print(f"     Inferred Value: {inferred_audience}")
            audience_level = report_knowledge.get("audience_profile", {}).get("assumed_knowledge_level", "N/A")
            print(f"     Knowledge Level: {audience_level}")
        else:
            print(f"  ✅ target_audience: PROVIDED (not inferred)")
            print(f"     Provided Value: {self.config.target_audience}")
        
        print("=" * 60)
    
    async def _generate_outline(self, critic_feedback: Optional[Dict[str, Any]] = None, previous_outline: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Helper method to generate presentation outline.
        
        Args:
            critic_feedback: Optional critic review from previous attempt (for retry)
            previous_outline: Optional previous outline that was evaluated (for retry)
        
        Returns:
            Generated presentation outline dictionary
        """
        # Include custom instruction in outline generation message if present
        custom_instr_note = ""
        if self.config.custom_instruction and self.config.custom_instruction.strip():
            custom_instr_note = f"\n\n[CUSTOM_INSTRUCTION]\n{self.config.custom_instruction}\n\nIMPORTANT: If the custom instruction requires icon-feature cards, timeline, flowchart, or table layouts, you MUST suggest those specific layout types in the relevant slide's content_notes (e.g., 'Use a comparison-grid layout with icon-feature cards' instead of just 'use an icon').\n"
        
        # Build previous outline note if provided (for retry)
        previous_outline_note = ""
        if previous_outline:
            serialized_previous_outline = self.serialization_service.serialize(previous_outline, pretty=False)
            previous_outline_note = f"\n\n[PREVIOUS_OUTLINE]\nThe following outline was previously generated but needs improvement:\n{serialized_previous_outline}\n[END_PREVIOUS_OUTLINE]\n"
        
        # Build critic feedback note if provided
        critic_feedback_note = ""
        if critic_feedback:
            strengths = critic_feedback.get("strengths", [])
            weaknesses = critic_feedback.get("weaknesses", [])
            recommendations = critic_feedback.get("recommendations", [])
            evaluation_notes = critic_feedback.get("evaluation_notes", "")
            
            feedback_parts = []
            if weaknesses:
                feedback_parts.append(f"**Weaknesses identified:**\n" + "\n".join(f"- {w}" for w in weaknesses))
            if recommendations:
                feedback_parts.append(f"**Recommendations:**\n" + "\n".join(f"- {r}" for r in recommendations))
            if evaluation_notes:
                feedback_parts.append(f"**Evaluation Notes:**\n{evaluation_notes}")
            
            if feedback_parts:
                critic_feedback_note = f"\n\n[PREVIOUS_CRITIC_REVIEW]\nThe previous outline was evaluated and found to need improvement. Please address the following feedback:\n\n" + "\n\n".join(feedback_parts) + "\n\n[END_PREVIOUS_CRITIC_REVIEW]\n"
        
        # Use cached serialization for performance
        serialized_report_knowledge = self._get_serialized_report_knowledge(pretty=False)
        
        message = f"Based on the report knowledge:\n{serialized_report_knowledge}{custom_instr_note}{previous_outline_note}{critic_feedback_note}\n\nGenerate a presentation outline."
        
        presentation_outline = await self.executor.run_agent(
            self.agent_registry.get("outline_generator"),
            message,
            "presentation_outline",
            parse_json=True
        )
        
        if not presentation_outline:
            raise AgentExecutionError(
                "Failed to generate outline",
                agent_name="OutlineGeneratorAgent",
                output_key="presentation_outline"
            )
        
        return presentation_outline
    
    async def _evaluate_outline(self, presentation_outline: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Evaluate outline quality using critic agent.
        
        Args:
            presentation_outline: The outline to evaluate
        
        Returns:
            Critic review dictionary, or None if evaluation failed
        """
        print("\n🔍 Evaluating outline quality...")
        self.obs_logger.start_agent_execution("OutlineCriticAgent", output_key="critic_review_outline")
        
        try:
            # Serialize outline and report knowledge for critic
            serialized_outline = self.serialization_service.serialize(presentation_outline, pretty=False)
            serialized_report_knowledge = self._get_serialized_report_knowledge(pretty=False)
            
            critic_review = await self.executor.run_agent(
                self.agent_registry.get("outline_critic"),
                f"[PRESENTATION_OUTLINE]\n{serialized_outline}\n[END_PRESENTATION_OUTLINE]\n\n[REPORT_KNOWLEDGE]\n{serialized_report_knowledge}\n[END_REPORT_KNOWLEDGE]\n\nEvaluate the presentation outline quality.",
                "critic_review_outline",
                parse_json=True
            )
            
            if critic_review:
                self.outputs["critic_review_outline"] = critic_review
                self.session.state["critic_review_outline"] = critic_review
                
                # Log the evaluation result
                quality_score = critic_review.get("overall_quality_score", "N/A")
                is_acceptable = critic_review.get("is_acceptable", False)
                evaluation_notes = critic_review.get("evaluation_notes", "")
                
                print(f"📊 Outline Quality Score: {quality_score}/100")
                print(f"✅ Acceptable: {is_acceptable}")
                if evaluation_notes:
                    print(f"📝 Evaluation: {evaluation_notes}")
                
                # Save critic review if intermediate saving is enabled
                if self.save_intermediate:
                    save_json_output(critic_review, str(self.output_dir / "outline_review.json"))
                    print(f"✅ Outline evaluation saved")
                
                self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, f"Quality score: {quality_score}, Acceptable: {is_acceptable}")
                return critic_review
            else:
                self.obs_logger.finish_agent_execution(AgentStatus.FAILED, "Critic returned empty result", has_output=False)
                print("⚠️  Outline evaluation returned empty result")
                return None
                
        except (AgentExecutionError, JSONParseError) as e:
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e), has_output=False)
            # Don't raise - evaluation failure shouldn't stop the pipeline
            print(f"⚠️  Outline evaluation failed: {e}")
            log_agent_error(logger, e, "OutlineCriticAgent")
            return None
    
    async def _step_outline_generation(self):
        """
        Step 2: Outline Generation with Evaluation and Retry Logic.
        
        This method implements a feedback loop for quality assurance:
        1. Generate initial outline
        2. Evaluate outline quality using critic agent
        3. If unacceptable, retry with critic feedback and previous outline (max 1 retry)
        4. Re-evaluate retried outline
        
        Design:
        - Uses stronger model (gemini-2.5-flash) for critic evaluation (industry best practice)
        - Passes both previous outline and critic feedback to generator for actionable improvements
        - Limits retry to 1 attempt to prevent infinite loops
        - Continues with original outline if retry fails (graceful degradation)
        
        Behavior:
        - Always evaluates outline after generation
        - Retry only triggered if critic marks outline as unacceptable
        - Both previous outline and feedback are passed to generator for context
        - Final outline (original or retried) is stored regardless of evaluation result
        """
        print("\n📝 Step 2: Outline Generation")
        
        # Generate outline (first attempt)
        self.obs_logger.start_agent_execution("OutlineGeneratorAgent", output_key="presentation_outline")
        
        try:
            presentation_outline = await self._generate_outline()
        except (AgentExecutionError, JSONParseError) as e:
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e), has_output=False)
            raise
        
        self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, "Outline generated successfully")
        
        # Evaluate outline quality using critic agent (stronger model for better judgment)
        critic_review = await self._evaluate_outline(presentation_outline)
        
        # Retry logic: If outline is unacceptable, regenerate with feedback (max 1 retry)
        # This implements the feedback loop pattern for quality assurance
        if critic_review and not critic_review.get("is_acceptable", False):
            print("\n🔄 Outline not acceptable. Retrying with critic feedback and previous outline (max 1 retry)...")
            self.obs_logger.start_agent_execution("OutlineGeneratorAgent", output_key="presentation_outline")
            
            try:
                # Retry with critic feedback AND previous outline for context
                # This allows the generator to see what was wrong and what needs improvement
                presentation_outline = await self._generate_outline(
                    critic_feedback=critic_review,
                    previous_outline=presentation_outline
                )
                self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, "Outline regenerated with critic feedback")
                
                # Re-evaluate the retried outline to check if improvements were made
                print("\n🔍 Re-evaluating retried outline...")
                critic_review = await self._evaluate_outline(presentation_outline)
            except (AgentExecutionError, JSONParseError) as e:
                self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e), has_output=False)
                print(f"⚠️  Outline retry failed: {e}")
                # Graceful degradation: Continue with original outline if retry fails
                log_agent_error(logger, e, "OutlineGeneratorAgent")
        
        # Store final outline
        self.outputs["presentation_outline"] = presentation_outline
        self.session.state["presentation_outline"] = presentation_outline
        # Invalidate cache when outline is updated
        self._invalidate_serialization_cache("presentation_outline")
        
        if self.save_intermediate:
            save_json_output(presentation_outline, str(self.output_dir / PRESENTATION_OUTLINE_FILE))
            print(f"✅ Presentation outline saved")
    
    async def _step_slide_generation(self):
        """Step 3: Slide and Script Generation - now handled by SlideGenerationHandler."""
        handler = SlideGenerationHandler(
            config=self.config,
            executor=self.executor,
            agent_registry=self.agent_registry,
            obs_logger=self.obs_logger,
            serialization_service=self.serialization_service,
            get_serialized_outline_fn=self._get_serialized_presentation_outline,
            build_selective_context_fn=self._build_selective_context,
            outputs=self.outputs,
            output_dir=self.output_dir,
            save_intermediate=self.save_intermediate,
        )
        result = await handler.execute(
            presentation_outline=self.outputs["presentation_outline"],
            report_knowledge=self.outputs["report_knowledge"]
        )
        # Store in session state
        self.session.state["slide_deck"] = result["slide_deck"]
        self.session.state["presentation_script"] = result["presentation_script"]
    
    async def _step_chart_generation(self):
        """Step 3.5: Chart Generation."""
        print("\n📊 Step 3.5: Chart Generation")
        self.obs_logger.start_agent_execution("ChartGeneratorAgent", output_key="chart_generation_status")
        
        slide_deck = self.outputs.get("slide_deck")
        if not slide_deck:
            print("   ℹ️  No slide deck available")
            self.obs_logger.finish_agent_execution(AgentStatus.SKIPPED, "No slide deck", has_output=False)
            return
        
        # Check if any slides need charts
        slides_with_charts = []
        for slide in slide_deck.get('slides', []):
            visual_elements = slide.get('visual_elements', {})
            if visual_elements.get('charts_needed', False) and visual_elements.get('chart_spec'):
                slides_with_charts.append(slide)
        
        if not slides_with_charts:
            print("   ℹ️  No slides require charts")
            self.obs_logger.finish_agent_execution(AgentStatus.SKIPPED, "No charts needed", has_output=False)
            return
        
        # Generate charts for each slide
        chart_results = []
        for slide in slides_with_charts:
            chart_spec = slide['visual_elements']['chart_spec']
            chart_type = chart_spec.get('type', 'bar')
            
            try:
                from presentation_agent.agents.utils.chart_generator import generate_chart_tool
                
                chart_result = await generate_chart_tool(
                    chart_type=chart_type,
                    chart_data=chart_spec.get('data', {}),
                    chart_config=chart_spec.get('config', {}),
                    output_dir=str(self.output_dir / "generated_images")
                )
                
                if chart_result and chart_result.get('image_path'):
                    slide['visual_elements']['chart_image_path'] = chart_result['image_path']
                    chart_results.append({
                        'slide_number': slide.get('slide_number'),
                        'chart_path': chart_result['image_path'],
                        'status': 'success'
                    })
                    print(f"   ✅ Generated chart for slide {slide.get('slide_number')}")
                else:
                    chart_results.append({
                        'slide_number': slide.get('slide_number'),
                        'status': 'failed',
                        'error': 'Chart generation returned no image path'
                    })
                    print(f"   ⚠️  Chart generation failed for slide {slide.get('slide_number')}")
            except Exception as e:
                logger.error(f"Error generating chart for slide {slide.get('slide_number')}: {e}")
                chart_results.append({
                    'slide_number': slide.get('slide_number'),
                    'status': 'error',
                    'error': str(e)
                })
                print(f"   ❌ Error generating chart for slide {slide.get('slide_number')}: {e}")
        
        self.outputs["chart_generation_status"] = {
            "charts_generated": len([r for r in chart_results if r.get('status') == 'success']),
            "charts_failed": len([r for r in chart_results if r.get('status') != 'success']),
            "results": chart_results
        }
        
        self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
    
    async def _step_chart_generation(self):
        """Step 3.5: Chart Generation."""
        print("\n📊 Step 3.5: Chart Generation")
        self.obs_logger.start_agent_execution("ChartGeneratorAgent", output_key="chart_generation_status")
        
        slide_deck = self.outputs.get("slide_deck")
        if not slide_deck:
            print("   ℹ️  No slide deck available")
            self.obs_logger.finish_agent_execution(AgentStatus.SKIPPED, "No slide deck", has_output=False)
            return
        
        # Check if any slides need charts
        slides_with_charts = []
        for slide in slide_deck.get('slides', []):
            visual_elements = slide.get('visual_elements', {})
            if visual_elements.get('charts_needed', False) and visual_elements.get('chart_spec'):
                slides_with_charts.append(slide.get('slide_number'))
        
        if slides_with_charts:
            print(f"   📊 Found {len(slides_with_charts)} slide(s) needing charts: {slides_with_charts}")
            
            chart_input = json.dumps({"slide_deck": slide_deck}, separators=(',', ':'))
            try:
                chart_status = await self.executor.run_agent(
                    self.agent_registry.get("chart_generator"),
                    chart_input,
                    "chart_generation_status",
                    parse_json=False
                )
            except AgentExecutionError as e:
                self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e), has_output=False)
                raise
            
            # Get updated slide_deck from session.state
            updated_slide_deck = self.session.state.get("slide_deck") or slide_deck
            
            # Verify charts were generated
            charts_generated_count = 0
            for slide in updated_slide_deck.get('slides', []):
                visual_elements = slide.get('visual_elements', {})
                chart_data = visual_elements.get('chart_data')
                if is_valid_chart_data(chart_data):
                    charts_generated_count += 1
            
            if charts_generated_count > 0:
                print(f"   ✅ Successfully generated {charts_generated_count} chart(s)")
                slide_deck = updated_slide_deck
                self.outputs["slide_deck"] = slide_deck
                self.session.state["slide_deck"] = slide_deck
            
            self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
        else:
            print("   ℹ️  No charts needed for this presentation")
            self.obs_logger.finish_agent_execution(AgentStatus.SKIPPED, "No charts needed", has_output=False)
    
    async def _step_parallel_chart_and_image_generation(self) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """
        Step 3.5: Generate charts and images in parallel (OPTIMIZATION).
        
        This method demonstrates parallel processing by running chart generation and
        image pre-generation simultaneously using asyncio.gather(). This significantly
        reduces total execution time compared to sequential execution.
        
        Implementation:
        - Uses asyncio.gather() to run both tasks concurrently
        - Chart generation uses ChartGeneratorAgent (LLM-based) with generate_chart_tool
        - Image pre-generation uses pre_generate_images utility (tool-based)
        - Both tasks are independent and can run simultaneously
        
        Design:
        - Parallel execution reduces total pipeline time (performance optimization)
        - Both tasks write to session.state independently
        - Returns image_cache and keyword_usage_tracker for web slides generation
        - Handles cases where charts may not be needed (skips chart generation)
        
        Behavior:
        - Always pre-generates images (required for web slides)
        - Conditionally generates charts only if slides require them
        - If charts needed: runs both tasks in parallel
        - If no charts needed: only runs image pre-generation
        - Returns cached results for downstream web slides generation
        
        Returns:
            Tuple of (image_cache, keyword_usage_tracker) for use in web slides generation
        """
        print("\n⚡ Step 3.5: Parallel Chart and Image Generation")
        
        slide_deck = self.outputs.get("slide_deck")
        if not slide_deck:
            print("   ℹ️  No slide deck available")
            return {}, {}
        
        # Check if charts are needed (some presentations may not require charts)
        slides_with_charts = []
        for slide in slide_deck.get('slides', []):
            visual_elements = slide.get('visual_elements', {})
            if visual_elements.get('charts_needed', False) and visual_elements.get('chart_spec'):
                slides_with_charts.append(slide.get('slide_number'))
        
        # Pre-generate images (always needed for web slides, regardless of charts)
        from presentation_agent.agents.tools.web_slides_generator_tool import pre_generate_images
        print("   🖼️  Pre-generating images...")
        
        # Run chart generation and image pre-generation in parallel using asyncio.gather()
        # This optimization reduces total execution time by running independent tasks concurrently
        if slides_with_charts:
            print(f"   📊 Found {len(slides_with_charts)} slide(s) needing charts: {slides_with_charts}")
            # Run both in parallel: chart generation (async) and image pre-generation (sync, wrapped in thread)
            chart_task = self._step_chart_generation()
            image_task = asyncio.to_thread(pre_generate_images, slide_deck)
            
            # Wait for both to complete in parallel
            _, image_result = await asyncio.gather(chart_task, image_task)
            image_cache, keyword_usage_tracker = image_result
        else:
            print("   ℹ️  No charts needed for this presentation")
            # Only pre-generate images
            image_cache, keyword_usage_tracker = await asyncio.to_thread(pre_generate_images, slide_deck)
        
        # Get updated slide_deck from session.state (may have been updated by ChartGeneratorAgent)
        updated_slide_deck = self.session.state.get("slide_deck") or slide_deck
        if updated_slide_deck != slide_deck:
            self.outputs["slide_deck"] = updated_slide_deck
        
        print(f"   ✅ Parallel generation complete: {len(image_cache)} image keywords cached")
        return image_cache, keyword_usage_tracker
    
    async def _step_generate_web_slides(self, image_cache: Optional[Dict[str, Any]] = None, keyword_usage_tracker: Optional[Dict[str, int]] = None):
        """Step 4: Generate Web Slides (HTML)."""
        print("\n🌐 Step 4: Generate Web Slides")
        self.obs_logger.start_agent_execution("WebSlidesGenerator", output_key="web_slides_result")
        
        # CRITICAL: Get the latest slide_deck from session.state (may have been updated by ChartGeneratorAgent)
        slide_deck = self.session.state.get("slide_deck") or self.outputs.get("slide_deck")
        presentation_script = self.outputs.get("presentation_script")
        
        # Parse JSON strings if needed (handle cases where data is stored as string)
        if isinstance(slide_deck, str):
            try:
                slide_deck = json.loads(slide_deck)
                logger.info("✅ Parsed slide_deck from JSON string")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse slide_deck JSON string: {e}")
                raise AgentOutputError(
                    f"slide_deck is a string but not valid JSON: {e}",
                    agent_name="WebSlidesGenerator"
                )
        
        if isinstance(presentation_script, str):
            try:
                presentation_script = json.loads(presentation_script)
                logger.info("✅ Parsed presentation_script from JSON string")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse presentation_script JSON string: {e}")
                raise AgentOutputError(
                    f"presentation_script is a string but not valid JSON: {e}",
                    agent_name="WebSlidesGenerator"
                )
        
        # Ensure they are dicts
        if not isinstance(slide_deck, dict):
            logger.error(f"❌ slide_deck is not a dict, got {type(slide_deck).__name__}")
            raise AgentOutputError(
                f"slide_deck must be a dict, got {type(slide_deck).__name__}",
                agent_name="WebSlidesGenerator"
            )
        
        if not isinstance(presentation_script, dict):
            logger.error(f"❌ presentation_script is not a dict, got {type(presentation_script).__name__}")
            raise AgentOutputError(
                f"presentation_script must be a dict, got {type(presentation_script).__name__}",
                agent_name="WebSlidesGenerator"
            )
        
        if not slide_deck or not presentation_script:
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, "Missing slide_deck or presentation_script", has_output=False)
            raise AgentOutputError(
                "Cannot generate web slides: missing slide_deck or presentation_script",
                agent_name="WebSlidesGenerator"
            )
        
        config_dict = {
            'scenario': self.config.scenario,
            'duration': self.config.duration,
            'target_audience': self.config.target_audience,
            'custom_instruction': self.config.custom_instruction
        }
        
        # Get presentation title from first slide or config
        slides = slide_deck.get('slides', [])
        if slides and isinstance(slides[0], dict):
            presentation_title = slides[0].get('title', 'Generated Presentation')
        else:
            presentation_title = 'Generated Presentation'
        
        print("   🚀 Generating web slides HTML...")
        try:
            web_result = generate_web_slides_tool(
                slide_deck=slide_deck,
                presentation_script=presentation_script,
                config=config_dict,
                title=presentation_title,
                image_cache=image_cache,
                keyword_usage_tracker=keyword_usage_tracker
            )
        except Exception as e:
            logger.error(f"❌ Error calling generate_web_slides_tool: {e}")
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e), has_output=False)
            raise AgentExecutionError(
                f"Failed to generate web slides: {e}",
                agent_name="WebSlidesGenerator"
            )
        
        # Ensure web_result is a dict (handle cases where it might be a string)
        if isinstance(web_result, str):
            try:
                web_result = json.loads(web_result)
                logger.info("✅ Parsed web_result from JSON string")
            except json.JSONDecodeError:
                # If it's not JSON, treat it as an error message
                error_msg = web_result
                self.obs_logger.finish_agent_execution(AgentStatus.FAILED, error_msg, has_output=False)
                raise AgentExecutionError(
                    f"Failed to generate web slides: {error_msg}",
                    agent_name="WebSlidesGenerator"
                )
        
        if not isinstance(web_result, dict):
            logger.error(f"❌ web_result is not a dict, got {type(web_result).__name__}")
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, f"web_result is {type(web_result).__name__}, expected dict", has_output=False)
            raise AgentExecutionError(
                f"Failed to generate web slides: web_result is {type(web_result).__name__}, expected dict",
                agent_name="WebSlidesGenerator"
            )
        
        if web_result.get('status') == 'success':
            self.outputs["web_slides_result"] = web_result
            self.session.state["web_slides_result"] = web_result
            print(f"   ✅ Web slides generated successfully!")
            print(f"   📄 File: {web_result.get('file_path')}")
            print(f"   🌐 Open in browser: {web_result.get('url')}")
            
            # Optionally open in browser
            if self.open_browser:
                import webbrowser
                try:
                    webbrowser.open(web_result.get('url'))
                    print(f"   🌐 Opened in browser")
                except Exception as e:
                    print(f"   ⚠️  Could not open browser: {e}")
            
            if self.save_intermediate:
                save_json_output(web_result, str(self.output_dir / WEB_SLIDES_RESULT_FILE))
            
            self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
        else:
            error_msg = web_result.get('error', 'Unknown error')
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, error_msg, has_output=False)
            raise AgentExecutionError(
                f"Failed to generate web slides: {error_msg}",
                agent_name="WebSlidesGenerator"
            )
    
