"""
Web Slides Generator Tool.
Generates an HTML webpage with interactive slides from slide deck and presentation script.
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from .image_collection import pre_generate_images
from .frontend_data import _generate_frontend_slides_data
from .utils import _parse_json_safely

logger = logging.getLogger(__name__)


def generate_web_slides_tool(
    slide_deck: Dict,
    presentation_script: Dict,
    config: Optional[Dict] = None,
    title: str = "Generated Presentation",
    output_path: Optional[str] = None,
    image_cache: Optional[Dict[str, list]] = None,
    keyword_usage_tracker: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    Generate frontend-ready JSON format with individual slide HTML fragments for Deckora frontend.
    
    Args:
        slide_deck: Slide deck JSON with slides array
        presentation_script: Presentation script JSON
        config: Optional config dict (scenario, duration, etc.)
        title: Presentation title
        output_path: Output JSON file path (default: from config OUTPUT_DIR/SLIDES_DATA_FILE)
        image_cache: Optional pre-generated image cache
        keyword_usage_tracker: Optional keyword usage tracker for round-robin
        
    Returns:
        Dict with status, slides_data_path, and slides_data (for frontend)
    """
    try:
        # Validate and parse inputs if they are strings (handle serialization issues and escaped JSON)
        if isinstance(slide_deck, str):
            try:
                slide_deck = _parse_json_safely(slide_deck)
                logger.info("✅ Parsed slide_deck from JSON string (with unescaping)")
            except ValueError as e:
                logger.error(f"❌ slide_deck is a string but not valid JSON: {e}")
                raise ValueError(f"slide_deck must be a dict or valid JSON string, got: {type(slide_deck).__name__}")
        
        if not isinstance(slide_deck, dict):
            logger.error(f"❌ slide_deck is not a dict, got {type(slide_deck).__name__}")
            raise ValueError(f"slide_deck must be a dict, got: {type(slide_deck).__name__}")
        
        if isinstance(presentation_script, str):
            try:
                presentation_script = _parse_json_safely(presentation_script)
                logger.info("✅ Parsed presentation_script from JSON string (with unescaping)")
            except ValueError as e:
                logger.error(f"❌ presentation_script is a string but not valid JSON: {e}")
                raise ValueError(f"presentation_script must be a dict or valid JSON string, got: {type(presentation_script).__name__}")
        
        if not isinstance(presentation_script, dict):
            logger.error(f"❌ presentation_script is not a dict, got {type(presentation_script).__name__}")
            raise ValueError(f"presentation_script must be a dict, got: {type(presentation_script).__name__}")
        
        # Default output path
        if output_path is None:
            from config import OUTPUT_DIR, SLIDES_DATA_FILE
            output_dir = Path(OUTPUT_DIR)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / SLIDES_DATA_FILE)
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Extract slides and script
        slides = slide_deck.get("slides", [])
        script_sections = presentation_script.get("script_sections", [])
        
        # Validate and parse slides if needed (handle cases where they might be strings or escaped JSON)
        if isinstance(slides, str):
            try:
                slides = _parse_json_safely(slides)
            except ValueError:
                logger.error(f"❌ slides is a string but not valid JSON")
                raise ValueError(f"slides must be a list or valid JSON string, got: {type(slides).__name__}")
        if not isinstance(slides, list):
            logger.error(f"❌ slides is not a list, got {type(slides).__name__}")
            raise ValueError(f"slides must be a list, got: {type(slides).__name__}")
        
        # Validate and parse script_sections if needed
        if isinstance(script_sections, str):
            try:
                script_sections = _parse_json_safely(script_sections)
            except ValueError:
                logger.error(f"❌ script_sections is a string but not valid JSON")
                raise ValueError(f"script_sections must be a list or valid JSON string, got: {type(script_sections).__name__}")
        if not isinstance(script_sections, list):
            logger.error(f"❌ script_sections is not a list, got {type(script_sections).__name__}")
            raise ValueError(f"script_sections must be a list, got: {type(script_sections).__name__}")
        
        # Validate that script_sections contains dicts, not strings
        valid_script_sections = []
        for idx, section in enumerate(script_sections):
            if isinstance(section, str):
                try:
                    section = _parse_json_safely(section)
                except ValueError:
                    logger.warning(f"⚠️  script_section[{idx}] is a string but not valid JSON, skipping")
                    continue
            if not isinstance(section, dict):
                logger.warning(f"⚠️  script_section[{idx}] is not a dict (got {type(section).__name__}), skipping")
                continue
            valid_script_sections.append(section)
        script_sections = valid_script_sections
        
        # Validate that slides contains dicts, not strings
        valid_slides = []
        for idx, slide in enumerate(slides):
            if isinstance(slide, str):
                try:
                    slide = _parse_json_safely(slide)
                except ValueError:
                    logger.warning(f"⚠️  slide[{idx}] is a string but not valid JSON, skipping")
                    continue
            if not isinstance(slide, dict):
                logger.warning(f"⚠️  slide[{idx}] is not a dict (got {type(slide).__name__}), skipping")
                continue
            valid_slides.append(slide)
        slides = valid_slides
        
        if not slides:
            logger.error("❌ No valid slides found after validation")
            raise ValueError("No valid slides found - all slides were invalid or empty")
        
        # Create script map for easy lookup
        script_map = {section.get("slide_number"): section for section in script_sections if isinstance(section, dict)}
        
        # Use pre-generated image cache if provided, otherwise generate on-demand
        if image_cache is None:
            image_cache = {}
        if keyword_usage_tracker is None:
            keyword_usage_tracker = {}
        
        # Generate frontend-ready JSON format (pass image_cache and usage tracker for use during HTML generation)
        slides_data = _generate_frontend_slides_data(
            slides, script_map, title, config,
            image_cache=image_cache,
            keyword_usage_tracker=keyword_usage_tracker
        )
        output_path.write_text(json.dumps(slides_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        logger.info(f"✅ Frontend slides data generated: {output_path}")
        print(f"✅ Frontend slides data generated: {output_path}")
        print(f"   📊 Total slides: {len(slides_data.get('slides', []))}")
        print(f"   📦 JSON file ready for Deckora frontend integration")
        
        return {
            "status": "success",
            "slides_data_path": str(output_path.absolute()),
            "slides_data": slides_data,
            "message": "Frontend slides data generated successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating frontend slides data: {type(e).__name__}: {e}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Full traceback:\n{error_trace}")
        # Include more context in error message
        error_details = {
            "error": str(e),
            "error_type": type(e).__name__,
            "slide_deck_type": type(slide_deck).__name__ if 'slide_deck' in locals() else "unknown",
            "presentation_script_type": type(presentation_script).__name__ if 'presentation_script' in locals() else "unknown",
        }
        logger.error(f"Error context: {error_details}")
        # Re-raise the exception so the handler can see the actual error and decide whether to retry
        # This is better than returning error status which might cause infinite retries
        raise


# Export main functions for backward compatibility
__all__ = [
    'generate_web_slides_tool',
    'pre_generate_images',
]

