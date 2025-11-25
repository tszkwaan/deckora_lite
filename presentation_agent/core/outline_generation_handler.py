"""
Outline generation handler
Handles outline generation, evaluation, and retry logic with feedback loop.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from config import PresentationConfig, PRESENTATION_OUTLINE_FILE
from presentation_agent.agents.utils.helpers import save_json_output
from presentation_agent.agents.utils.observability import AgentStatus
from presentation_agent.core.agent_executor import AgentExecutor
from presentation_agent.core.json_parser import parse_json_robust
from presentation_agent.core.exceptions import AgentExecutionError, JSONParseError
from presentation_agent.core.logging_utils import log_agent_error
from presentation_agent.core.serialization_service import SerializationService
from presentation_agent.core.serialization_manager import SerializationManager

logger = logging.getLogger(__name__)


class OutlineGenerationHandler:
    """
    Handles outline generation step with evaluation and retry logic.
    """
    
    def __init__(
        self,
        config: PresentationConfig,
        executor: AgentExecutor,
        agent_registry,
        obs_logger,
        serialization_service: SerializationService,
        serialization_manager: SerializationManager,
        outputs: Dict[str, Any],
        output_dir: Path,
        save_intermediate: bool = True,
    ):
        """
        Initialize the outline generation handler.
        
        Args:
            config: Presentation configuration
            executor: Agent executor instance
            agent_registry: Agent registry for getting agents
            obs_logger: Observability logger
            serialization_service: Service for JSON serialization
            serialization_manager: Manager for serialization and caching
            outputs: Pipeline outputs dictionary (will be updated)
            output_dir: Output directory path
            save_intermediate: Whether to save intermediate outputs
        """
        self.config = config
        self.executor = executor
        self.agent_registry = agent_registry
        self.obs_logger = obs_logger
        self.serialization_service = serialization_service
        self.serialization_manager = serialization_manager
        self.outputs = outputs
        self.output_dir = output_dir
        self.save_intermediate = save_intermediate
        self.session = None  # Will be set by execute method
    
    async def execute(
        self,
        report_knowledge: Dict,
        session
    ) -> Dict[str, Any]:
        """
        Execute the outline generation step with evaluation and retry logic.
        
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
        - Final outline (original or retried) is stored regardless of evaluation result for traceability
        
        Args:
            report_knowledge: The report knowledge to generate outline from
            session: ADK session object (for storing state)
            invalidate_cache_fn: Function to invalidate serialization cache (from orchestrator)
        
        Returns:
            Dictionary with 'presentation_outline' and optionally 'critic_review_outline' keys
        """
        self.session = session
        
        print("\n📝 Step 2: Outline Generation")
        
        # Generate outline (first attempt)
        self.obs_logger.start_agent_execution("OutlineGeneratorAgent", output_key="presentation_outline")
        
        try:
            presentation_outline = await self._generate_outline(report_knowledge)
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
                    report_knowledge,
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
        self.serialization_manager.invalidate("presentation_outline")
        
        if self.save_intermediate:
            save_json_output(presentation_outline, str(self.output_dir / PRESENTATION_OUTLINE_FILE))
            print(f"✅ Presentation outline saved")
        
        result = {"presentation_outline": presentation_outline}
        if critic_review:
            result["critic_review_outline"] = critic_review
        
        return result
    
    async def _generate_outline(
        self,
        report_knowledge: Dict,
        critic_feedback: Optional[Dict[str, Any]] = None,
        previous_outline: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Helper method to generate presentation outline.
        
        Args:
            report_knowledge: The report knowledge to generate outline from
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
        serialized_report_knowledge = self.serialization_manager.get_serialized_report_knowledge(pretty=False)
        
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
    
    async def _evaluate_outline(
        self,
        presentation_outline: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate outline quality using critic agent.
        
        The critic evaluates the outline against the original report content to ensure
        the outline properly represents the source material, not just the extracted knowledge.
        
        Args:
            presentation_outline: The outline to evaluate
        
        Returns:
            Critic review dictionary, or None if evaluation failed
        """
        print("\n🔍 Evaluating outline quality...")
        self.obs_logger.start_agent_execution("OutlineCriticAgent", output_key="critic_review_outline")
        
        try:
            # Serialize outline for critic
            serialized_outline = self.serialization_service.serialize(presentation_outline, pretty=False)
            
            # Get original report content (not extracted knowledge) for validation
            # The critic should evaluate against the source material to ensure completeness
            report_content = self.config.report_content
            if not report_content:
                # Fallback to report_knowledge if original content not available
                logger.warning("⚠️  Original report content not available, using report_knowledge for critic evaluation")
                report_content = self.serialization_manager.get_serialized_report_knowledge(pretty=False)
                report_section = f"[REPORT_KNOWLEDGE]\n{report_content}\n[END_REPORT_KNOWLEDGE]"
            else:
                report_section = f"[REPORT_CONTENT]\n{report_content}\n[END_REPORT_CONTENT]"
            
            critic_review = await self.executor.run_agent(
                self.agent_registry.get("outline_critic"),
                f"[PRESENTATION_OUTLINE]\n{serialized_outline}\n[END_PRESENTATION_OUTLINE]\n\n{report_section}\n\nEvaluate the presentation outline quality.",
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

