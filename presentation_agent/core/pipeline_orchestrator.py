"""
Pipeline orchestrator - coordinates all agents in the presentation generation pipeline.
Extracted from main.py to follow Single Responsibility Principle.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import webbrowser

from google.adk.sessions import InMemorySessionService

from config import PresentationConfig, LAYOUT_MAX_RETRY_LOOPS
from presentation_agent.agents.report_understanding_agent.agent import agent as report_understanding_agent
from presentation_agent.agents.outline_generator_agent.agent import agent as outline_generator_agent
from presentation_agent.agents.outline_critic_agent.agent import agent as outline_critic_agent
from presentation_agent.agents.slide_and_script_generator_agent.agent import agent as slide_and_script_generator_agent
from presentation_agent.agents.chart_generator_agent.agent import agent as chart_generator_agent
from presentation_agent.agents.layout_critic_agent.agent import agent as layout_critic_agent
from presentation_agent.agents.tools.google_slides_tool import export_slideshow_tool
from presentation_agent.agents.utils.pdf_loader import load_pdf
from presentation_agent.agents.utils.helpers import save_json_output
from presentation_agent.agents.utils.observability import get_observability_logger, AgentStatus
from presentation_agent.agents.utils.quality_check import check_outline_quality
from presentation_agent.core.agent_executor import AgentExecutor
from presentation_agent.core.retry_handler import OutlineRetryHandler, LayoutRetryHandler
from presentation_agent.core.json_parser import parse_json_robust

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Orchestrates the complete presentation generation pipeline.
    Follows Single Responsibility Principle - only handles orchestration.
    """
    
    def __init__(
        self,
        config: PresentationConfig,
        output_dir: str = "presentation_agent/output",
        include_critics: bool = True,
        save_intermediate: bool = True,
        open_browser: bool = True
    ):
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.include_critics = include_critics
        self.save_intermediate = save_intermediate
        self.open_browser = open_browser
        
        # Initialize observability
        trace_file = str(self.output_dir / "trace_history.json")
        self.obs_logger = get_observability_logger(
            log_file=str(self.output_dir / "observability.log"),
            trace_file=trace_file
        )
        
        # Initialize session
        self.session_service = InMemorySessionService()
        self.session = None  # Will be set in initialize()
        self.executor: Optional[AgentExecutor] = None
        
        # Pipeline outputs
        self.outputs: Dict[str, Any] = {}
    
    async def initialize(self):
        """Initialize session and executor."""
        self.session = await self.session_service.create_session(
            app_name="presentation_agent",
            user_id="local_user"
        )
        self.executor = AgentExecutor(self.session)
        self.obs_logger.start_pipeline("presentation_pipeline")
    
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
            await self._step_slide_generation()
            
            # Step 3.5: Chart Generation
            await self._step_chart_generation()
            
            # Step 4: Google Slides Export
            await self._step_export_slides()
            
            # Step 5: Layout Review with Retry
            if self.include_critics:
                await self._step_layout_review()
            
            self.obs_logger.finish_pipeline()
            return self.outputs
            
        except Exception as e:
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
        
        report_knowledge = await self.executor.run_agent(
            report_understanding_agent,
            initial_message,
            "report_knowledge",
            parse_json=True
        )
        
        if not report_knowledge:
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, "No output generated", has_output=False)
            raise ValueError("ReportUnderstandingAgent failed to generate output")
        
        # Parse if string
        if isinstance(report_knowledge, str):
            parsed = parse_json_robust(report_knowledge)
            if parsed:
                report_knowledge = parsed
        
        # Log inference results
        self._log_inference_results(report_knowledge, scenario_provided, target_audience_provided)
        
        self.outputs["report_knowledge"] = report_knowledge
        self.session.state["report_knowledge"] = report_knowledge
        self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
        
        if self.save_intermediate:
            save_json_output(report_knowledge, str(self.output_dir / "report_knowledge.json"))
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
    
    async def _step_outline_generation(self):
        """Step 2: Outline Generation with Critic Loop."""
        print("\n📝 Step 2: Outline Generation with Critic Loop")
        
        report_knowledge = self.outputs["report_knowledge"]
        outline_retries = 0
        max_outline_retries = 3
        
        while outline_retries < max_outline_retries:
            # Generate outline
            self.obs_logger.start_agent_execution("OutlineGeneratorAgent", output_key="presentation_outline", retry_count=outline_retries)
            
            presentation_outline = await self.executor.run_agent(
                outline_generator_agent,
                f"Based on the report knowledge:\n{json.dumps(report_knowledge, indent=2)}\n\nGenerate a presentation outline.",
                "presentation_outline",
                parse_json=True
            )
            
            if not presentation_outline:
                self.obs_logger.finish_agent_execution(AgentStatus.FAILED, "No outline generated", has_output=False)
                outline_retries += 1
                continue
            
            self.session.state["presentation_outline"] = presentation_outline
            
            # Critic review (if enabled)
            if self.include_critics:
                self.obs_logger.start_agent_execution("OutlineCriticAgent", output_key="critic_review_outline")
                
                critic_input = self.executor.build_critic_input(
                    presentation_outline,
                    report_knowledge,
                    self.config,
                    self.config.custom_instruction
                )
                
                critic_review = await self.executor.run_agent(
                    outline_critic_agent,
                    critic_input,
                    "critic_review_outline",
                    parse_json=True
                )
                
                if critic_review:
                    passed, quality_details = check_outline_quality(critic_review)
                    self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
                    
                    if passed:
                        print(f"✅ Outline quality check passed")
                        break
                    else:
                        failure_reasons = quality_details.get('failure_reasons', ['Quality check failed'])
                        feedback = '; '.join(failure_reasons)
                        print(f"⚠️  Outline quality check failed: {feedback}")
                        outline_retries += 1
                        self.obs_logger.log_retry("OutlineGeneratorAgent", outline_retries, feedback)
                        continue
                else:
                    self.obs_logger.finish_agent_execution(AgentStatus.FAILED, "No critic review generated", has_output=False)
                    break
            else:
                break
        
        if not presentation_outline:
            raise ValueError("OutlineGeneratorAgent failed to generate outline after retries")
        
        self.outputs["presentation_outline"] = presentation_outline
        if self.save_intermediate:
            save_json_output(presentation_outline, str(self.output_dir / "presentation_outline.json"))
            print(f"✅ Presentation outline saved")
    
    async def _step_slide_generation(self):
        """Step 3: Slide and Script Generation."""
        print("\n🎨 Step 3: Slide and Script Generation")
        self.obs_logger.start_agent_execution("SlideAndScriptGeneratorAgent", output_key="slide_and_script")
        
        presentation_outline = self.outputs["presentation_outline"]
        report_knowledge = self.outputs["report_knowledge"]
        
        slide_and_script = await self.executor.run_agent(
            slide_and_script_generator_agent,
            f"Generate slides and script based on:\nOutline: {json.dumps(presentation_outline, indent=2)}\nReport Knowledge: {json.dumps(report_knowledge, indent=2)}",
            "slide_and_script",
            parse_json=True
        )
        
        if not slide_and_script:
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, "No slide_and_script generated", has_output=False)
            raise ValueError("SlideAndScriptGeneratorAgent failed to generate output")
        
        # Parse if still string - try multiple parsing strategies
        if isinstance(slide_and_script, str):
            logger.debug(f"slide_and_script is a string (length: {len(slide_and_script)}). Attempting to parse...")
            logger.debug(f"First 500 chars: {slide_and_script[:500]}")
            
            parsed = parse_json_robust(slide_and_script, extract_wrapped=True)
            if parsed:
                logger.info(f"✅ Successfully parsed slide_and_script from string (keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'})")
                slide_and_script = parsed
            else:
                logger.warning(f"⚠️ parse_json_robust failed. Trying alternative parsing...")
                # If parse_json_robust failed, try extracting JSON from markdown code block
                import re
                # Look for ```json ... ``` or ``` ... ```
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', slide_and_script, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    try:
                        slide_and_script = json.loads(json_str)
                        logger.info(f"✅ Successfully parsed JSON from markdown code block")
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
                            slide_and_script = json.loads(cleaned)
                        except json.JSONDecodeError as e2:
                            logger.error(f"Failed to parse slide_and_script: {e2}")
                            logger.error(f"First 1000 chars: {slide_and_script[:1000]}")
                            raise ValueError(f"Failed to parse slide_and_script as JSON: {e2}")
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
                        slide_and_script = json.loads(cleaned)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse slide_and_script: {e}")
                        logger.error(f"First 1000 chars: {slide_and_script[:1000]}")
                        raise ValueError(f"Failed to parse slide_and_script as JSON: {e}")
        
        # Ensure it's a dict
        if not isinstance(slide_and_script, dict):
            logger.error(f"slide_and_script is not a dict, got {type(slide_and_script).__name__}")
            logger.error(f"slide_and_script value (first 500 chars): {str(slide_and_script)[:500]}")
            raise ValueError(f"slide_and_script is not a dict, got {type(slide_and_script).__name__}")
        
        # Log what we got for debugging
        logger.info(f"✅ slide_and_script parsed successfully. Keys: {list(slide_and_script.keys())}")
        
        slide_deck = slide_and_script.get("slide_deck")
        presentation_script = slide_and_script.get("presentation_script")
        
        if not slide_deck:
            logger.error(f"❌ slide_and_script missing 'slide_deck' field")
            logger.error(f"   Available keys: {list(slide_and_script.keys())}")
            logger.error(f"   slide_and_script type: {type(slide_and_script)}")
            logger.error(f"   slide_and_script preview (first 1000 chars): {json.dumps(slide_and_script, indent=2)[:1000]}")
            raise ValueError(f"slide_and_script missing 'slide_deck' field. Available keys: {list(slide_and_script.keys())}")
        if not presentation_script:
            logger.error(f"❌ slide_and_script missing 'presentation_script' field")
            logger.error(f"   Available keys: {list(slide_and_script.keys())}")
            raise ValueError(f"slide_and_script missing 'presentation_script' field. Available keys: {list(slide_and_script.keys())}")
        
        # Store outputs
        self.outputs["slide_deck"] = slide_deck
        self.session.state["slide_deck"] = slide_deck
        self.outputs["presentation_script"] = presentation_script
        self.session.state["presentation_script"] = presentation_script
        
        if self.save_intermediate:
            save_json_output(slide_deck, str(self.output_dir / "slide_deck.json"))
            save_json_output(presentation_script, str(self.output_dir / "presentation_script.json"))
            print(f"✅ Slide deck and script saved")
        
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
            chart_status = await self.executor.run_agent(
                chart_generator_agent,
                chart_input,
                "chart_generation_status",
                parse_json=False
            )
            
            # Get updated slide_deck from session.state
            updated_slide_deck = self.session.state.get("slide_deck") or slide_deck
            
            # Verify charts were generated
            charts_generated_count = 0
            for slide in updated_slide_deck.get('slides', []):
                visual_elements = slide.get('visual_elements', {})
                chart_data = visual_elements.get('chart_data')
                if chart_data and chart_data != "PLACEHOLDER_CHART_DATA" and len(chart_data) > 100:
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
    
    async def _step_export_slides(self):
        """Step 4: Google Slides Export."""
        print("\n📤 Step 4: Google Slides Export")
        self.obs_logger.start_agent_execution("SlidesExportAgent", output_key="slides_export_result")
        
        slide_deck = self.outputs.get("slide_deck")
        presentation_script = self.outputs.get("presentation_script")
        
        if not slide_deck or not presentation_script:
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, "Missing slide_deck or presentation_script", has_output=False)
            raise ValueError("Cannot export: missing slide_deck or presentation_script")
        
        config_dict = {
            'scenario': self.config.scenario,
            'duration': self.config.duration,
            'target_audience': self.config.target_audience,
            'custom_instruction': self.config.custom_instruction
        }
        
        print("   🚀 Calling export_slideshow_tool directly...")
        export_result = export_slideshow_tool(
            slide_deck=slide_deck,
            presentation_script=presentation_script,
            config=config_dict,
            title=""
        )
        
        if export_result.get('status') in ['success', 'partial_success']:
            self.outputs["slideshow_export_result"] = export_result
            self.session.state["slideshow_export_result"] = export_result
            
            presentation_id = export_result.get("presentation_id")
            shareable_url = export_result.get("shareable_url") or f"https://docs.google.com/presentation/d/{presentation_id}/edit"
            
            if presentation_id:
                id_file = self.output_dir / "presentation_slides_id.txt"
                url_file = self.output_dir / "presentation_slides_url.txt"
                
                id_file.write_text(presentation_id)
                url_file.write_text(shareable_url)
                
                print(f"\n✅ Google Slides export successful!")
                print(f"   Presentation ID: {presentation_id}")
                print(f"   🔗 Shareable URL: {shareable_url}")
                print(f"\n📄 Presentation ID saved to: {id_file}")
                print(f"📄 Shareable URL saved to: {url_file}")
                
                if self.open_browser:
                    print(f"\n🌐 Opening Google Slides in browser...")
                    try:
                        webbrowser.open(shareable_url)
                        print(f"   ✅ Opened: {shareable_url}")
                    except Exception as e:
                        print(f"   ⚠️  Could not open browser: {e}")
            
            if self.save_intermediate:
                save_json_output(export_result, str(self.output_dir / "slideshow_export_result.json"))
            
            self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
        else:
            error_msg = export_result.get('error', 'Unknown error')
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, error_msg, has_output=False)
            print(f"⚠️  Google Slides export failed: {error_msg}")
    
    async def _step_layout_review(self):
        """
        Step 5: Layout Review with Retry Loop.
        
        TODO: Implement full retry logic with slide regeneration.
        Current implementation is simplified - only performs single review.
        Full implementation should:
        1. Review layout
        2. If issues found, regenerate slides with feedback
        3. Re-export slides
        4. Re-review
        5. Repeat up to LAYOUT_MAX_RETRY_LOOPS times
        """
        print("\n🎨 Step 5: Layout Review with Retry Loop")
        
        export_result = self.outputs.get("slideshow_export_result")
        if not export_result or export_result.get('status') not in ['success', 'partial_success']:
            print("   ⚠️  Skipping layout review (export did not succeed)")
            return
        
        layout_retries = 0
        max_layout_retries = LAYOUT_MAX_RETRY_LOOPS + 1
        
        while layout_retries < max_layout_retries:
            if layout_retries > 0:
                print(f"\n🔄 Layout Review Retry {layout_retries}/{LAYOUT_MAX_RETRY_LOOPS}")
            
            self.obs_logger.start_agent_execution("LayoutCriticAgent", output_key="layout_review", retry_count=layout_retries)
            
            shareable_url = export_result.get("shareable_url") or f"https://docs.google.com/presentation/d/{export_result.get('presentation_id')}/edit"
            self.session.state["slides_export_result"] = export_result
            
            layout_input = f"""The SlidesExportAgent has completed. Here is the slides_export_result:

{json.dumps(export_result, separators=(',', ':'))}

Extract the shareable_url from slides_export_result and call review_layout_tool with it to review the layout."""
            
            layout_review = await self.executor.run_agent(
                layout_critic_agent,
                layout_input,
                "layout_review",
                parse_json=True
            )
            
            # Check session.state as fallback
            if not layout_review and self.session.state.get("layout_review"):
                layout_review = self.session.state.get("layout_review")
            
            # Parse if string
            if isinstance(layout_review, str):
                parsed = parse_json_robust(layout_review)
                if parsed:
                    layout_review = parsed
            
            if layout_review and isinstance(layout_review, dict):
                self.session.state["layout_review"] = layout_review
                passed = layout_review.get("passed", False)
                issues_summary = layout_review.get("issues_summary", {})
                total_issues = issues_summary.get("total_issues", 0) if isinstance(issues_summary, dict) else 0
                overall_quality = layout_review.get("overall_quality", "unknown")
                
                if self.save_intermediate:
                    save_json_output(layout_review, str(self.output_dir / "layout_review.json"))
                
                self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
                
                # Check if layout passes
                if passed and total_issues == 0:
                    print(f"✅ Layout review passed! Quality: {overall_quality}, Issues: {total_issues}")
                    self.outputs["layout_review"] = layout_review
                    break
                else:
                    print(f"⚠️  Layout review failed: Quality: {overall_quality}, Issues: {total_issues}")
                    
                    # If max retries reached, save and exit
                    if layout_retries >= LAYOUT_MAX_RETRY_LOOPS:
                        print(f"⚠️  Reached maximum layout retry attempts ({LAYOUT_MAX_RETRY_LOOPS}). Proceeding with current slides.")
                        self.outputs["layout_review"] = layout_review
                        break
                    
                    # TODO: Implement slide regeneration with feedback
                    # This would involve:
                    # 1. Building feedback message from layout_review
                    # 2. Regenerating slides with feedback
                    # 3. Regenerating charts if needed
                    # 4. Re-exporting slides
                    # 5. Updating export_result
                    print(f"⚠️  Full retry logic with slide regeneration not yet implemented. Skipping retry.")
                    self.outputs["layout_review"] = layout_review
                    break
            else:
                print("⚠️  Layout review did not return valid output")
                self.obs_logger.finish_agent_execution(AgentStatus.FAILED, "No valid layout review", has_output=False)
                break

