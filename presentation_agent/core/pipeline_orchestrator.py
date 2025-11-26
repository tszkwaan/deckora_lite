"""
Pipeline orchestrator - coordinates all agents in the presentation generation pipeline.
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from google.adk.sessions import InMemorySessionService

from config import (
    PresentationConfig,
    APP_NAME,
    USER_ID,
    OUTPUT_DIR,
    TRACE_HISTORY_FILE,
    OBSERVABILITY_LOG_FILE,
    REPORT_KNOWLEDGE_FILE,
)
from presentation_agent.core.agent_registry import AgentRegistry, create_default_agent_registry
from presentation_agent.utils.pdf_loader import load_pdf
from presentation_agent.utils.helpers import save_json_output, is_valid_chart_data
from presentation_agent.utils.observability import get_observability_logger, AgentStatus
from presentation_agent.core.agent_executor import AgentExecutor
from presentation_agent.core.json_parser import parse_json_robust
from presentation_agent.core.exceptions import AgentExecutionError, JSONParseError, AgentOutputError
from presentation_agent.core.logging_utils import log_agent_error
from presentation_agent.core.serialization_service import SerializationService
from presentation_agent.core.cache_manager import CacheManager
from presentation_agent.core.serialization_manager import SerializationManager
from presentation_agent.core.slide_generation_handler import SlideGenerationHandler
from presentation_agent.core.outline_generation_handler import OutlineGenerationHandler
from presentation_agent.core.web_slides_generation_handler import WebSlidesGenerationHandler
from presentation_agent.core.context_builder import ContextBuilder

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Orchestrates the complete presentation generation pipeline.
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
        self.serialization_manager = SerializationManager(
            serialization_service=self.serialization_service,
            cache_manager=self.cache_manager,
            outputs=self.outputs
        )
    
    async def initialize(self):
        """Initialize session and executor."""
        self.session = await self.session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID
        )
        self.executor = AgentExecutor(self.session)
        self.obs_logger.start_pipeline("presentation_pipeline")
        
        # Clear image cache at the start of each pipeline run (async)
        from presentation_agent.utils.image_helper import clear_image_cache_async
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
            outline_handler = OutlineGenerationHandler(
                config=self.config,
                executor=self.executor,
                agent_registry=self.agent_registry,
                obs_logger=self.obs_logger,
                serialization_service=self.serialization_service,
                serialization_manager=self.serialization_manager,
                outputs=self.outputs,
                output_dir=self.output_dir,
                save_intermediate=self.save_intermediate,
            )
            outline_result = await outline_handler.execute(
                report_knowledge=self.outputs["report_knowledge"],
                session=self.session
            )
            # Results already stored in self.outputs by handler
            
            # Step 3: Slide and Script Generation
            handler = SlideGenerationHandler(
                config=self.config,
                executor=self.executor,
                agent_registry=self.agent_registry,
                obs_logger=self.obs_logger,
                serialization_service=self.serialization_service,
                serialization_manager=self.serialization_manager,
                build_selective_context_fn=ContextBuilder.build_selective_context,
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
            web_slides_handler = WebSlidesGenerationHandler(
                config=self.config,
                obs_logger=self.obs_logger,
                outputs=self.outputs,
                output_dir=self.output_dir,
                session=self.session,
                save_intermediate=self.save_intermediate,
                open_browser=self.open_browser,
            )
            await web_slides_handler.execute(image_cache, keyword_usage_tracker)
            
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
        self.serialization_manager.invalidate("report_knowledge")
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
        from presentation_agent.tools.web_slides_generator_tool import pre_generate_images
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
    
