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

from config import PresentationConfig
from presentation_agent.agents.report_understanding_agent.agent import agent as report_understanding_agent
from presentation_agent.agents.outline_generator_agent.agent import agent as outline_generator_agent
from presentation_agent.agents.slide_and_script_generator_agent.agent import agent as slide_and_script_generator_agent
from presentation_agent.agents.chart_generator_agent.agent import agent as chart_generator_agent
from presentation_agent.agents.tools.web_slides_generator_tool import generate_web_slides_tool
from presentation_agent.agents.utils.pdf_loader import load_pdf
from presentation_agent.agents.utils.helpers import save_json_output, is_valid_chart_data
from presentation_agent.agents.utils.observability import get_observability_logger, AgentStatus
from presentation_agent.core.agent_executor import AgentExecutor
from presentation_agent.core.json_parser import parse_json_robust
from presentation_agent.core.exceptions import AgentExecutionError, JSONParseError, AgentOutputError

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
        
        # JSON serialization cache (performance optimization)
        # Cache serialized strings to avoid repeated expensive JSON serialization
        self._serialized_cache: Dict[str, str] = {}
    
    async def initialize(self):
        """Initialize session and executor."""
        self.session = await self.session_service.create_session(
            app_name="presentation_agent",
            user_id="local_user"
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
            await self._step_slide_generation()
            
            # Step 3.5: Parallel Chart and Image Generation (OPTIMIZATION)
            # Generate charts and images in parallel to save time
            image_cache, keyword_usage_tracker = await self._step_parallel_chart_and_image_generation()
            
            # Step 4: Web Slides Generation
            await self._step_generate_web_slides(image_cache=image_cache, keyword_usage_tracker=keyword_usage_tracker)
            
            print("\n✅ Pipeline completed - web slides generated!")
            
            self.obs_logger.finish_pipeline()
            return self.outputs
            
        except Exception as e:
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
        
        if cache_key not in self._serialized_cache:
            report_knowledge = self.outputs.get("report_knowledge")
            if report_knowledge is None:
                raise ValueError("report_knowledge not available in outputs")
            
            if pretty:
                # Pretty format for logs/debugging
                self._serialized_cache[cache_key] = json.dumps(
                    report_knowledge,
                    indent=2,
                    ensure_ascii=False
                )
            else:
                # Compact format for agent messages (better performance)
                self._serialized_cache[cache_key] = json.dumps(
                    report_knowledge,
                    ensure_ascii=False,
                    separators=(',', ':')  # Compact: no spaces
                )
        
        return self._serialized_cache[cache_key]
    
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
        
        if cache_key not in self._serialized_cache:
            presentation_outline = self.outputs.get("presentation_outline")
            if presentation_outline is None:
                raise ValueError("presentation_outline not available in outputs")
            
            if pretty:
                # Pretty format for logs/debugging
                self._serialized_cache[cache_key] = json.dumps(
                    presentation_outline,
                    indent=2,
                    ensure_ascii=False
                )
            else:
                # Compact format for agent messages (better performance)
                self._serialized_cache[cache_key] = json.dumps(
                    presentation_outline,
                    ensure_ascii=False,
                    separators=(',', ':')  # Compact: no spaces
                )
        
        return self._serialized_cache[cache_key]
    
    def _invalidate_serialization_cache(self, key: Optional[str] = None):
        """
        Invalidate serialization cache when data changes.
        
        Args:
            key: Specific cache key to invalidate, or None to clear all
        """
        if key:
            # Remove specific key and related keys
            keys_to_remove = [k for k in self._serialized_cache.keys() if k.startswith(key)]
            for k in keys_to_remove:
                self._serialized_cache.pop(k, None)
        else:
            # Clear all cache
            self._serialized_cache.clear()
    
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
                report_understanding_agent,
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
        """Step 2: Outline Generation."""
        print("\n📝 Step 2: Outline Generation")
        
        report_knowledge = self.outputs["report_knowledge"]
        
        # Generate outline
        self.obs_logger.start_agent_execution("OutlineGeneratorAgent", output_key="presentation_outline")
        
        try:
            # Include custom instruction in outline generation message if present
            custom_instr_note = ""
            if self.config.custom_instruction and self.config.custom_instruction.strip():
                custom_instr_note = f"\n\n[CUSTOM_INSTRUCTION]\n{self.config.custom_instruction}\n\nIMPORTANT: If the custom instruction requires icon-feature cards, timeline, flowchart, or table layouts, you MUST suggest those specific layout types in the relevant slide's content_notes (e.g., 'Use a comparison-grid layout with icon-feature cards' instead of just 'use an icon').\n"
            
            # Use cached serialization for performance
            serialized_report_knowledge = self._get_serialized_report_knowledge(pretty=False)
            
            presentation_outline = await self.executor.run_agent(
                outline_generator_agent,
                f"Based on the report knowledge:\n{serialized_report_knowledge}{custom_instr_note}\n\nGenerate a presentation outline.",
                "presentation_outline",
                parse_json=True
            )
        except (AgentExecutionError, JSONParseError) as e:
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e), has_output=False)
            raise
        
        if not presentation_outline:
            raise AgentExecutionError(
                "Failed to generate outline",
                agent_name="OutlineGeneratorAgent",
                output_key="presentation_outline"
            )
        
        self.outputs["presentation_outline"] = presentation_outline
        self.session.state["presentation_outline"] = presentation_outline
        # Invalidate cache when outline is updated
        self._invalidate_serialization_cache("presentation_outline")
        
        if self.save_intermediate:
            save_json_output(presentation_outline, str(self.output_dir / "presentation_outline.json"))
            print(f"✅ Presentation outline saved")
    
    async def _step_slide_generation(self):
        """Step 3: Slide and Script Generation."""
        print("\n🎨 Step 3: Slide and Script Generation")
        self.obs_logger.start_agent_execution("SlideAndScriptGeneratorAgent", output_key="slide_and_script")
        
        presentation_outline = self.outputs["presentation_outline"]
        report_knowledge = self.outputs["report_knowledge"]
        
        try:
            # Include custom_instruction explicitly in the message if present
            custom_instruction_note = ""
            if self.config.custom_instruction and self.config.custom_instruction.strip():
                custom_instr_lower = self.config.custom_instruction.lower()
                if "icon-feature card" in custom_instr_lower or "icon feature card" in custom_instr_lower:
                    custom_instruction_note = f"""

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
                    custom_instruction_note = f"\n\n[CUSTOM_INSTRUCTION - CRITICAL]\n{self.config.custom_instruction}\n\n⚠️ MANDATORY REQUIREMENT: You MUST create at least ONE slide with layout_type: \"timeline\" AND provide visual_elements.timeline_items array with format: [{{\"year\": \"...\", \"title\": \"...\", \"description\": \"...\"}}, ...]. This is NOT optional - you MUST include a timeline slide.\n"
                elif "flowchart" in custom_instr_lower:
                    custom_instruction_note = f"\n\n[CUSTOM_INSTRUCTION - CRITICAL]\n{self.config.custom_instruction}\n\n⚠️ MANDATORY REQUIREMENT: You MUST create at least ONE slide with layout_type: \"flowchart\" AND provide visual_elements.flowchart_steps array. This is NOT optional.\n"
                elif "comparison" in custom_instr_lower or "grid" in custom_instr_lower:
                    custom_instruction_note = f"\n\n[CUSTOM_INSTRUCTION - CRITICAL]\n{self.config.custom_instruction}\n\n⚠️ MANDATORY REQUIREMENT: You MUST create at least ONE slide with layout_type: \"comparison-grid\" AND provide visual_elements.sections array. This is NOT optional.\n"
                elif "table" in custom_instr_lower:
                    custom_instruction_note = f"\n\n[CUSTOM_INSTRUCTION - CRITICAL]\n{self.config.custom_instruction}\n\n⚠️ MANDATORY REQUIREMENT: You MUST create at least ONE slide with layout_type: \"data-table\" AND provide visual_elements.table_data object. This is NOT optional.\n"
                elif "image" in custom_instr_lower and ("at least" in custom_instr_lower or "least" in custom_instr_lower):
                    # Extract number if present (e.g., "at least 3 images" -> 3)
                    import re
                    num_match = re.search(r'at least (\d+)|least (\d+)', custom_instr_lower)
                    num_images = int(num_match.group(1) or num_match.group(2)) if num_match else 3
                    custom_instruction_note = f"""

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
                    custom_instruction_note = f"\n\n[CUSTOM_INSTRUCTION]\n{self.config.custom_instruction}\n\nIMPORTANT: You MUST follow this custom instruction.\n"
            
            # Build the message with custom instruction at the TOP if present
            # Use cached serialization for performance
            serialized_outline = self._get_serialized_presentation_outline(pretty=False)
            
            # CONTEXT ENGINEERING: Use selective context extraction to reduce token usage
            # Extract only relevant report sections based on slide topics
            selective_report_knowledge = self._build_selective_context(presentation_outline, report_knowledge)
            
            # Serialize the selective context (compact format for agent messages)
            selective_report_knowledge_str = json.dumps(
                selective_report_knowledge,
                ensure_ascii=False,
                separators=(',', ':')  # Compact: no spaces
            )
            
            message_parts = []
            if custom_instruction_note:
                message_parts.append(custom_instruction_note)
            
            # Add explicit duration requirement with calculated target
            # Parse duration string to calculate target seconds
            duration_str = self.config.duration.lower()
            target_seconds = 60  # Default to 1 minute
            if "minute" in duration_str or "min" in duration_str:
                import re
                match = re.search(r'(\d+)', duration_str)
                if match:
                    minutes = int(match.group(1))
                    target_seconds = minutes * 60
            elif "second" in duration_str or "sec" in duration_str:
                import re
                match = re.search(r'(\d+)', duration_str)
                if match:
                    target_seconds = int(match.group(1))
            
            # Calculate required words (words = seconds × 2, since estimated_seconds = words / 2)
            required_words = target_seconds * 2
            
            # Get number of slides from outline for distribution calculation
            outline = self.outputs.get('presentation_outline', {})
            num_slides = len(outline.get('slides', [])) or 8  # Default to 8 if not available
            words_per_content_slide = int((required_words - 50) / max(1, num_slides - 1)) if num_slides > 1 else required_words - 50
            
            duration_note = f"""
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
            message_parts.append(duration_note)
            message_parts.append(f"Generate slides and script based on:\nOutline: {serialized_outline}\nReport Knowledge: {selective_report_knowledge_str}")
            
            slide_and_script = await self.executor.run_agent(
                slide_and_script_generator_agent,
                "\n".join(message_parts),
                "slide_and_script",
                parse_json=True
            )
            
            # Validate that custom instruction was followed (for icon-feature card)
            if custom_instruction_note and ("icon-feature card" in self.config.custom_instruction.lower() or "icon feature card" in self.config.custom_instruction.lower()):
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
        except AgentExecutionError as e:
            # Agent failed to return output
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e), has_output=False)
            raise
        except JSONParseError as e:
            # If JSON parsing failed, check if it's a syntax error (should retry LLM call)
            # vs incomplete JSON (can try fallback parsing)
            from presentation_agent.core.json_parser import is_json_syntax_error
            error_msg = str(e)
            
            # Check if error indicates syntax error (malformed JSON from LLM) or plain text response
            # In this case, we should retry the LLM call, not just try to parse differently
            is_syntax_error = any(indicator in error_msg.lower() for indicator in [
                "expecting property name",
                "expecting ',' delimiter",
                "expecting ':' delimiter",
                "invalid escape",
                "expecting value",  # Often means no JSON at all
            ])
            
            # Also check if the raw output looks like plain text (question/explanation) instead of JSON
            # This happens when the agent asks questions instead of returning JSON
            try:
                raw_output = getattr(e, 'raw_output', '')
                if raw_output and not raw_output.strip().startswith('{'):
                    # Output doesn't start with JSON - likely plain text response
                    is_syntax_error = True
                    logger.warning(f"Agent returned plain text instead of JSON (likely asked a question). Will retry LLM call.")
            except:
                pass
            
            if is_syntax_error:
                logger.warning(f"JSONParseError indicates syntax error (malformed JSON from LLM). Retrying LLM call: {e}")
                # Retry the LLM call once
                try:
                    # Use cached serialization for performance
                    serialized_outline = self._get_serialized_presentation_outline(pretty=False)
                    
                    # Use selective context for retry as well
                    selective_report_knowledge = self._build_selective_context(presentation_outline, report_knowledge)
                    selective_report_knowledge_str = json.dumps(
                        selective_report_knowledge,
                        ensure_ascii=False,
                        separators=(',', ':')
                    )
                    
                    slide_and_script = await self.executor.run_agent(
                        slide_and_script_generator_agent,
                        f"Generate slides and script based on:\nOutline: {serialized_outline}\nReport Knowledge: {selective_report_knowledge_str}",
                        "slide_and_script",
                        parse_json=True  # Retry with JSON parsing
                    )
                    logger.info("✅ Successfully parsed JSON after LLM retry")
                    # Success! Continue with the retried output
                    if isinstance(slide_and_script, dict):
                        self.outputs["slide_and_script"] = slide_and_script
                        self.session.state["slide_and_script"] = slide_and_script
                        if self.save_intermediate:
                            save_json_output(slide_and_script, str(self.output_dir / "slide_and_script_raw_debug.json"))
                        self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
                        return  # Exit early, retry succeeded
                except (AgentExecutionError, JSONParseError) as e2:
                    logger.error(f"LLM retry also failed: {e2}")
                    # Fall through to fallback parsing
                    is_syntax_error = False
            
            if not is_syntax_error:
                # If JSON parsing failed, try fallback parsing strategies
                logger.warning(f"JSONParseError from agent executor, trying fallback parsing: {e}")
                # Try to get raw output without JSON parsing
            try:
                # Use cached serialization for performance
                serialized_outline = self._get_serialized_presentation_outline(pretty=False)
                
                # Use selective context for fallback as well
                selective_report_knowledge = self._build_selective_context(presentation_outline, report_knowledge)
                selective_report_knowledge_str = json.dumps(
                    selective_report_knowledge,
                    ensure_ascii=False,
                    separators=(',', ':')
                )
                
                slide_and_script = await self.executor.run_agent(
                    slide_and_script_generator_agent,
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
                            slide_and_script = json.loads(cleaned)
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
        # Single slide objects have keys like: slide_number, title, content, visual_elements, design_spec, etc.
        # The required structure should have: slide_deck, presentation_script
        single_slide_keys = {'slide_number', 'title', 'content', 'visual_elements', 'design_spec', 'formatting_notes', 'speaker_notes'}
        if single_slide_keys.issubset(set(slide_and_script.keys())):
            logger.warning(f"⚠️ Agent returned a SINGLE SLIDE OBJECT instead of the required structure!")
            logger.warning(f"   The agent returned a slide with keys: {list(slide_and_script.keys())}")
            logger.warning(f"   This looks like a single slide object, not the required structure with 'slide_deck' and 'presentation_script'")
            logger.warning(f"   Attempting to auto-fix by wrapping the single slide in the required structure...")
            
            # AUTO-FIX: Wrap the single slide in the required structure
            single_slide = slide_and_script.copy()
            # Create a minimal presentation_script if missing
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
            logger.warning(f"   ⚠️ NOTE: This is a fallback fix. The agent should return the correct structure directly.")
        
        slide_deck = slide_and_script.get("slide_deck")
        presentation_script = slide_and_script.get("presentation_script")
        
        if not slide_deck:
            logger.error(f"❌ slide_and_script missing 'slide_deck' field")
            logger.error(f"   Available keys: {list(slide_and_script.keys())}")
            logger.error(f"   slide_and_script type: {type(slide_and_script)}")
            logger.error(f"   slide_and_script preview (first 1000 chars): {json.dumps(slide_and_script, indent=2)[:1000]}")
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
        self.session.state["slide_deck"] = slide_deck
        self.outputs["presentation_script"] = presentation_script
        self.session.state["presentation_script"] = presentation_script
        
        if self.save_intermediate:
            save_json_output(slide_deck, str(self.output_dir / "slide_deck.json"))
            save_json_output(presentation_script, str(self.output_dir / "presentation_script.json"))
            print(f"✅ Slide deck and script saved")
        
        self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
    
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
                # Calculate opening_line time: total_words / 2
                opening_time = round(opening_words / 2)
                opening_time = max(1, opening_time)
                # Store opening_line_time in the section for frontend use
                section["opening_line_time"] = opening_time
                total_estimated_time += opening_time
            
            # Recalculate estimated_time for each point in main_content
            main_content = section.get("main_content", [])
            for point in main_content:
                if not isinstance(point, dict):
                    continue
                
                explanation = point.get("explanation", "")
                if explanation:
                    # Count words in explanation
                    word_count = len(explanation.split())
                    # Calculate estimated_time: total_words / 2
                    estimated_time = word_count / 2
                    # Round to nearest integer
                    estimated_time = round(estimated_time)
                    # Ensure minimum of 1 second
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
                    chart_generator_agent,
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
        
        Returns:
            Tuple of (image_cache, keyword_usage_tracker) for use in web slides generation
        """
        print("\n⚡ Step 3.5: Parallel Chart and Image Generation")
        
        slide_deck = self.outputs.get("slide_deck")
        if not slide_deck:
            print("   ℹ️  No slide deck available")
            return {}, {}
        
        # Check if charts are needed
        slides_with_charts = []
        for slide in slide_deck.get('slides', []):
            visual_elements = slide.get('visual_elements', {})
            if visual_elements.get('charts_needed', False) and visual_elements.get('chart_spec'):
                slides_with_charts.append(slide.get('slide_number'))
        
        # Pre-generate images (always needed for web slides)
        from presentation_agent.agents.tools.web_slides_generator_tool import pre_generate_images
        print("   🖼️  Pre-generating images...")
        
        # Run chart generation and image pre-generation in parallel
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
                save_json_output(web_result, str(self.output_dir / "web_slides_result.json"))
            
            self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
        else:
            error_msg = web_result.get('error', 'Unknown error')
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, error_msg, has_output=False)
            raise AgentExecutionError(
                f"Failed to generate web slides: {error_msg}",
                agent_name="WebSlidesGenerator"
            )
    
