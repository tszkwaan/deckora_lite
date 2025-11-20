"""
Google Slides Export Tool.
A tool function that can be used by agents to export slide decks to Google Slides.
"""

import json
from typing import Dict, Any, Union
from presentation_agent.agents.utils.google_slides_exporter import export_to_google_slides


def _validate_and_normalize_input(value: Any, expected_type: type, param_name: str) -> Any:
    """
    Validate and normalize input parameter.
    
    Args:
        value: Input value to validate
        expected_type: Expected type (dict, str, etc.)
        param_name: Parameter name for error messages
        
    Returns:
        Normalized value
        
    Raises:
        TypeError: If value cannot be converted to expected type
    """
    if value is None:
        raise TypeError(f"{param_name} cannot be None")
    
    # If already correct type, return as is
    if isinstance(value, expected_type):
        return value
    
    # Try to convert string to dict (JSON parsing)
    if expected_type == dict and isinstance(value, str):
        try:
            # Strip markdown code blocks if present
            cleaned = value.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:].lstrip()
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:].lstrip()
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].rstrip()
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError) as e:
            raise TypeError(f"{param_name} must be a dict or valid JSON string. Error: {e}")
    
    # Try to convert dict to string (for title)
    if expected_type == str and isinstance(value, dict):
        # If it's a dict when expecting string, try to extract a reasonable string
        if 'title' in value:
            return str(value['title'])
        return json.dumps(value)
    
    # Try direct conversion
    try:
        return expected_type(value)
    except (TypeError, ValueError) as e:
        raise TypeError(f"{param_name} must be {expected_type.__name__}, got {type(value).__name__}. Error: {e}")


def export_slideshow_tool(
    slide_deck: dict, 
    presentation_script: dict = None, 
    config: dict = None, 
    title: str = "",
    use_state_for_script: bool = False
) -> dict:
    """
    Tool function to export slide deck and script to Google Slides.
    
    This tool can be used by agents to create Google Slides presentations
    from generated slide decks and presentation scripts.
    
    Args:
        slide_deck: Slide deck JSON from slide generator (dict or JSON string)
        presentation_script: Script JSON from script generator (dict or JSON string)
        config: Presentation configuration dict with keys:
            - scenario: Presentation scenario (e.g., "academic_teaching")
            - duration: Presentation duration (e.g., "20 minutes")
            - target_audience: Target audience (optional)
            - custom_instruction: Custom instructions (optional)
        title: Presentation title (optional, defaults to generated title based on scenario)
        
    Returns:
        Dict with keys:
            - status: "success" or "error"
            - presentation_id: Google Slides presentation ID (if success)
            - shareable_url: URL to access the presentation (if success)
            - message: Status message
            - error: Error description (if error)
            
    Example:
        >>> result = export_slideshow_tool(
        ...     slide_deck={"slides": [...]},
        ...     presentation_script={"script_sections": [...]},
        ...     config={"scenario": "academic_teaching", "duration": "20 minutes"},
        ...     title="My Presentation"
        ... )
        >>> print(result["shareable_url"])
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("🚀 export_slideshow_tool CALLED")
    logger.info(f"   slide_deck type: {type(slide_deck).__name__}")
    logger.info(f"   presentation_script type: {type(presentation_script).__name__ if presentation_script else 'None'}")
    logger.info(f"   config type: {type(config).__name__ if config else 'None'}, keys: {list(config.keys()) if isinstance(config, dict) else 'N/A'}")
    logger.info(f"   use_state_for_script: {use_state_for_script}")
    
    # If use_state_for_script=True, try to read from session.state
    # Note: This requires access to the current invocation context, which may not be available
    # For now, we'll require agents to pass presentation_script explicitly
    # Future: Could use a context manager or thread-local storage to access session.state
    
    try:
        # Validate and normalize inputs to prevent MALFORMED_FUNCTION_CALL
        slide_deck = _validate_and_normalize_input(slide_deck, dict, "slide_deck")
        
        # If presentation_script is None and use_state_for_script is True, we'd need to read from state
        # For now, require explicit passing (agents can read from state themselves)
        if presentation_script is None and not use_state_for_script:
            raise ValueError("presentation_script is required unless use_state_for_script=True")
        
        if presentation_script:
            presentation_script = _validate_and_normalize_input(presentation_script, dict, "presentation_script")
        
        if config is None:
            config = {}
        config = _validate_and_normalize_input(config, dict, "config")
        title = _validate_and_normalize_input(title if title else "", str, "title")
        
        # Validate required keys in slide_deck
        if not isinstance(slide_deck, dict) or "slides" not in slide_deck:
            raise ValueError("slide_deck must be a dict with 'slides' key")
        
        # Validate required keys in presentation_script (if provided)
        if presentation_script is not None:
            if not isinstance(presentation_script, dict) or "script_sections" not in presentation_script:
                raise ValueError("presentation_script must be a dict with 'script_sections' key")
        
        # Validate required keys in config
        if not isinstance(config, dict):
            raise ValueError("config must be a dict")
        if "scenario" not in config:
            config["scenario"] = "presentation"
        if "duration" not in config:
            config["duration"] = "20 minutes"
        
    except (TypeError, ValueError) as e:
        # Return error dict instead of raising to prevent MALFORMED_FUNCTION_CALL
        return {
            "status": "error",
            "error": f"Invalid input parameters: {str(e)}",
            "message": f"Please check that slide_deck, presentation_script, and config are valid dicts. Error: {e}"
        }
    
    try:
        # Logger already imported above
        logger.info("🚀 export_slideshow_tool called - starting Google Slides export")
        logger.info(f"   Slide deck has {len(slide_deck.get('slides', []))} slides")
        if presentation_script:
            logger.info(f"   Script has {len(presentation_script.get('script_sections', []))} sections")
        else:
            logger.warning("   ⚠️ presentation_script is None - speaker notes will not be added")
        print(f"🚀 export_slideshow_tool called - starting Google Slides export")
        
        # Create a simple config object-like structure for compatibility
        class SimpleConfig:
            def __init__(self, config_dict):
                self.scenario = config_dict.get('scenario', 'presentation')
                self.duration = config_dict.get('duration', '20 minutes')
                self.target_audience = config_dict.get('target_audience')
                self.custom_instruction = config_dict.get('custom_instruction', '')
        
        simple_config = SimpleConfig(config)
        # Use provided title or generate one from scenario
        if title and title.strip():
            presentation_title = title
        else:
            presentation_title = f"Presentation: {simple_config.scenario}"
        
        logger.info(f"   Calling export_to_google_slides with title: {presentation_title}")
        result = export_to_google_slides(
            slide_deck=slide_deck,
            presentation_script=presentation_script,
            config=simple_config,
            title=presentation_title
        )
        logger.info(f"✅ export_slideshow_tool completed: {result.get('status', 'unknown')}")
        if result.get('presentation_id'):
            logger.info(f"   Presentation ID: {result.get('presentation_id')}")
        if result.get('shareable_url'):
            logger.info(f"   🔗 Google Slides URL: {result.get('shareable_url')}")
            print(f"🔗 Google Slides URL: {result.get('shareable_url')}")
        elif result.get('presentation_id'):
            # Generate URL if we have ID but no URL
            generated_url = f"https://docs.google.com/presentation/d/{result.get('presentation_id')}/edit"
            logger.info(f"   🔗 Google Slides URL (generated): {generated_url}")
            print(f"🔗 Google Slides URL (generated): {generated_url}")
        return result
    except Exception as e:
        # Return error dict instead of raising to prevent crashes
        return {
            "status": "error",
            "error": str(e),
            "message": f"Failed to export to Google Slides: {e}"
        }

