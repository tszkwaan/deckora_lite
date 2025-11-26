"""
Web slides generation handler
Handles the web slides (HTML) generation step of the pipeline.
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from config import PresentationConfig, WEB_SLIDES_RESULT_FILE
from presentation_agent.utils.helpers import save_json_output
from presentation_agent.utils.observability import AgentStatus
from presentation_agent.core.exceptions import AgentExecutionError, AgentOutputError
from presentation_agent.tools.web_slides_generator import generate_web_slides_tool

logger = logging.getLogger(__name__)


class WebSlidesGenerationHandler:
    """
    Handles web slides generation step.
    """
    
    def __init__(
        self,
        config: PresentationConfig,
        obs_logger,
        outputs: Dict[str, Any],
        output_dir: Path,
        session,
        save_intermediate: bool = True,
        open_browser: bool = True,
    ):
        """
        Initialize the web slides generation handler.
        
        Args:
            config: Presentation configuration
            obs_logger: Observability logger
            outputs: Pipeline outputs dictionary
            output_dir: Output directory path
            session: ADK session object (for accessing state)
            save_intermediate: Whether to save intermediate outputs
            open_browser: Whether to open the generated HTML in browser
        """
        self.config = config
        self.obs_logger = obs_logger
        self.outputs = outputs
        self.output_dir = output_dir
        self.session = session
        self.save_intermediate = save_intermediate
        self.open_browser = open_browser
    
    async def execute(
        self,
        image_cache: Optional[Dict[str, Any]] = None,
        keyword_usage_tracker: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        Execute the web slides generation step.
        
        This method generates HTML slides from the slide deck and presentation script.
        It handles JSON parsing, validation, error handling, and browser opening.
        
        Args:
            image_cache: Pre-generated image cache (from parallel generation step)
            keyword_usage_tracker: Keyword usage tracking (from parallel generation step)
        
        Returns:
            Dictionary with web_slides_result containing file path and URL
        
        Raises:
            AgentOutputError: If slide_deck or presentation_script is missing or invalid
            AgentExecutionError: If web slides generation fails
        """
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
                self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e), has_output=False)
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
                self.obs_logger.finish_agent_execution(AgentStatus.FAILED, str(e), has_output=False)
                raise AgentOutputError(
                    f"presentation_script is a string but not valid JSON: {e}",
                    agent_name="WebSlidesGenerator"
                )
        
        # Ensure they are dicts
        if not isinstance(slide_deck, dict):
            logger.error(f"❌ slide_deck is not a dict, got {type(slide_deck).__name__}")
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, f"slide_deck is {type(slide_deck).__name__}, expected dict", has_output=False)
            raise AgentOutputError(
                f"slide_deck must be a dict, got {type(slide_deck).__name__}",
                agent_name="WebSlidesGenerator"
            )
        
        if not isinstance(presentation_script, dict):
            logger.error(f"❌ presentation_script is not a dict, got {type(presentation_script).__name__}")
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, f"presentation_script is {type(presentation_script).__name__}, expected dict", has_output=False)
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
            logger.debug(f"web_result type: {type(web_result)}, value: {str(web_result)[:200] if isinstance(web_result, str) else 'dict'}")
        except Exception as e:
            logger.error(f"❌ Error calling generate_web_slides_tool: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
        
        # Ensure web_result is a dict before accessing it
        if not isinstance(web_result, dict):
            error_msg = f"web_result is {type(web_result).__name__}, expected dict. Value: {str(web_result)[:200]}"
            logger.error(f"❌ {error_msg}")
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, error_msg, has_output=False)
            raise AgentExecutionError(
                f"Failed to generate web slides: {error_msg}",
                agent_name="WebSlidesGenerator"
            )
        
        # Safely check status
        status = web_result.get('status') if isinstance(web_result, dict) else None
        if status == 'success':
            self.outputs["web_slides_result"] = web_result
            self.session.state["web_slides_result"] = web_result
            print(f"   ✅ Web slides generated successfully!")
            print(f"   📄 File: {web_result.get('file_path')}")
            print(f"   🌐 Open in browser: {web_result.get('url')}")
            
            # Optionally open in browser
            if self.open_browser:
                import webbrowser
                try:
                    url = web_result.get('url')
                    if url:
                        webbrowser.open(url)
                        print(f"   🌐 Opened in browser")
                except Exception as e:
                    print(f"   ⚠️  Could not open browser: {e}")
            
            if self.save_intermediate:
                save_json_output(web_result, str(self.output_dir / WEB_SLIDES_RESULT_FILE))
            
            self.obs_logger.finish_agent_execution(AgentStatus.SUCCESS, has_output=True)
            return {"web_slides_result": web_result}
        else:
            error_msg = web_result.get('error', 'Unknown error') if isinstance(web_result, dict) else str(web_result)
            self.obs_logger.finish_agent_execution(AgentStatus.FAILED, error_msg, has_output=False)
            raise AgentExecutionError(
                f"Failed to generate web slides: {error_msg}",
                agent_name="WebSlidesGenerator"
            )

